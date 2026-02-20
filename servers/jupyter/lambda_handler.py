"""
AWS Lambda handler for Jupyter MCP Server

Wraps the Flask application to work with Lambda + API Gateway
"""
import json
import base64
import os

# Initialize Flask app
from jupyter_mcp_server.server import app
from jupyter_mcp_server import server as server_module
from jupyter_mcp_server.kernel_manager import JupyterKernelManager

# Initialize kernel manager globally for warm starts
# This keeps the Jupyter kernel alive between Lambda invocations
if server_module.kernel_manager is None:
    print("Initializing Jupyter kernel (cold start)...")
    # S3 bucket for persistent file storage
    S3_BUCKET = 'jupyter-mcp-workspaces-654654422653'
    
    server_module.kernel_manager = JupyterKernelManager(
        working_dir=os.environ.get('JUPYTER_WORKING_DIR', '/tmp/notebooks'),
        s3_bucket=S3_BUCKET,
        enable_s3=True
    )
    print("Kernel initialized successfully")
else:
    print("Using existing kernel (warm start)")


def handler(event, context):
    """
    AWS Lambda handler for API Gateway HTTP API (v2 payload format)

    Converts API Gateway event to Flask request and returns API Gateway response
    """
    # ============================================================
    # DETAILED LOGGING FOR USER ID EXTRACTION
    # ============================================================
    print("=" * 80)
    print(f"Lambda invoked - Request ID: {context.aws_request_id}")
    print("=" * 80)

    # Log full event structure (sanitized)
    print("\n>>> FULL EVENT STRUCTURE:")
    print(json.dumps(event, indent=2, default=str))

    # Log headers specifically
    print("\n>>> HEADERS:")
    headers = event.get('headers', {})
    for key, value in headers.items():
        # Mask authorization tokens for security
        if key.lower() == 'authorization':
            print(f"  {key}: {value[:20]}... (truncated)")
        else:
            print(f"  {key}: {value}")

    # Log requestContext (may contain user info)
    print("\n>>> REQUEST CONTEXT:")
    if 'requestContext' in event:
        req_ctx = event['requestContext']
        print(json.dumps(req_ctx, indent=2, default=str))

        # Check for authorizer context (Cognito, Lambda authorizer)
        if 'authorizer' in req_ctx:
            print("\n>>> AUTHORIZER CONTEXT (User info may be here):")
            print(json.dumps(req_ctx['authorizer'], indent=2, default=str))

    # Log body (first 500 chars)
    print("\n>>> REQUEST BODY (first 500 chars):")
    body = event.get('body', '')
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')
    print(body[:500])

    # Try to extract user ID from common locations
    print("\n>>> ATTEMPTING TO EXTRACT USER ID:")
    user_id_candidates = []

    # 1. Check Authorization header (JWT)
    auth_header = headers.get('authorization') or headers.get('Authorization')
    if auth_header:
        print(f"  Found Authorization header: {auth_header[:30]}...")
        try:
            import jwt
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = auth_header
            # Decode without verification to see contents
            decoded = jwt.decode(token, options={"verify_signature": False})
            print(f"  Decoded JWT: {json.dumps(decoded, indent=4, default=str)}")

            # Look for user ID in common fields
            for field in ['sub', 'username', 'user_id', 'cognito:username', 'email']:
                if field in decoded:
                    user_id_candidates.append(('JWT.' + field, decoded[field]))
        except Exception as e:
            print(f"  Could not decode JWT: {e}")

    # 2. Check custom headers
    custom_user_id = headers.get('x-user-id') or headers.get('X-User-Id')
    if custom_user_id:
        user_id_candidates.append(('header.x-user-id', custom_user_id))

    # 3. Check requestContext.authorizer
    if 'requestContext' in event and 'authorizer' in event['requestContext']:
        authorizer = event['requestContext']['authorizer']
        if isinstance(authorizer, dict):
            for key, value in authorizer.items():
                if 'user' in key.lower() or 'sub' in key.lower():
                    user_id_candidates.append((f'authorizer.{key}', value))

    # 4. Check requestContext for Cognito identity
    if 'requestContext' in event and 'identity' in event['requestContext']:
        identity = event['requestContext']['identity']
        if isinstance(identity, dict):
            cognito_id = identity.get('cognitoIdentityId') or identity.get('user')
            if cognito_id:
                user_id_candidates.append(('identity.cognitoIdentityId', cognito_id))

    print(f"\n>>> USER ID CANDIDATES FOUND: {len(user_id_candidates)}")
    for source, value in user_id_candidates:
        print(f"  {source}: {value}")

    print("=" * 80)
    print("\n")

    # Handle API Gateway v2 (HTTP API) format
    if 'requestContext' in event and 'http' in event['requestContext']:
        return handle_http_api_v2(event, context)
    # Handle API Gateway v1 (REST API) format
    elif 'requestContext' in event:
        return handle_rest_api_v1(event, context)
    # Direct invocation (for testing)
    else:
        return handle_direct_invocation(event, context)


def handle_http_api_v2(event, context):
    """Handle API Gateway HTTP API (v2 payload format)"""
    request_context = event['requestContext']
    http = request_context['http']

    http_method = http['method']
    path = http['path']
    headers = event.get('headers', {})
    body = event.get('body', '')

    # Decode body if base64 encoded
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')

    return process_flask_request(http_method, path, headers, body, context)


def handle_rest_api_v1(event, context):
    """Handle API Gateway REST API (v1 payload format)"""
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')

    # Decode body if base64 encoded
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')

    return process_flask_request(http_method, path, headers, body, context)


def handle_direct_invocation(event, context):
    """Handle direct Lambda invocation (for testing)"""
    # Treat as POST to /mcp with the event as body
    return process_flask_request(
        'POST',
        '/mcp',
        {'Content-Type': 'application/json'},
        json.dumps(event),
        context
    )


def process_flask_request(http_method, path, headers, body, context):
    """Process request through Flask application"""

    # Quick health check response (skip Flask for performance)
    if path == '/health' and http_method == 'GET':
        kernel_status = server_module.kernel_manager.get_status() if server_module.kernel_manager else {"status": "not initialized"}
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'status': 'healthy',
                'runtime': 'lambda',
                'requestId': context.request_id,
                'kernel': kernel_status,
                'memoryLimit': context.memory_limit_in_mb,
                'remainingTime': context.get_remaining_time_in_millis()
            })
        }

    # Process through Flask
    with app.test_request_context(
        path=path,
        method=http_method,
        headers=headers,
        data=body,
        content_type=headers.get('content-type', 'application/json')
    ):
        try:
            # Dispatch request through Flask
            response = app.full_dispatch_request()

            # Get response data
            response_data = response.get_data(as_text=True)

            # Convert Flask response to API Gateway format
            api_response = {
                'statusCode': response.status_code,
                'headers': {
                    'Content-Type': response.content_type,
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': '*'
                },
                'body': response_data
            }

            # Add any additional headers from Flask response
            for key, value in response.headers:
                if key.lower() not in ['content-type', 'content-length']:
                    api_response['headers'][key] = value

            return api_response

        except Exception as e:
            print(f"Error processing request: {str(e)}")
            import traceback
            traceback.print_exc()

            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'jsonrpc': '2.0',
                    'error': {
                        'code': -32603,
                        'message': f'Internal error: {str(e)}'
                    }
                })
            }


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'requestContext': {
            'http': {
                'method': 'GET',
                'path': '/health'
            }
        },
        'headers': {},
        'body': ''
    }

    class MockContext:
        request_id = 'test-request-id'
        memory_limit_in_mb = 2048
        def get_remaining_time_in_millis(self):
            return 900000

    result = handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
