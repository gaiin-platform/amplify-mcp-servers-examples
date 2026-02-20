"""
AWS Lambda handler for Data Transformation MCP Server

Wraps the Flask application to work with Lambda + API Gateway
"""
import json
import base64
import os

# Initialize Flask app
from data_mcp_server.server import app
from data_mcp_server import server as server_module
from data_mcp_server.data_manager import DataManager

# S3 bucket for persistent file storage
S3_BUCKET = 'jupyter-mcp-workspaces-654654422653'

# Initialize data manager globally for warm starts
if server_module.data_manager is None:
    print("Initializing Data Manager (cold start)...")
    server_module.data_manager = DataManager(
        working_dir=os.environ.get('DATA_WORKING_DIR', '/tmp/data'),
        s3_bucket=S3_BUCKET,
        enable_s3=True
    )
    print("Data Manager initialized successfully")
else:
    print("Using existing Data Manager (warm start)")


def handler(event, context):
    """
    AWS Lambda handler for API Gateway HTTP API (v2 payload format)
    """
    print("=" * 80)
    print(f"Lambda invoked - Request ID: {context.aws_request_id}")
    print("=" * 80)

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
    return process_flask_request(
        'POST',
        '/mcp',
        {'Content-Type': 'application/json'},
        json.dumps(event),
        context
    )


def process_flask_request(http_method, path, headers, body, context):
    """Process request through Flask application"""

    # Quick health check response
    if path == '/health' and http_method == 'GET':
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
                'server': server_module.SERVER_INFO,
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
        aws_request_id = 'test-aws-request-id'
        def get_remaining_time_in_millis(self):
            return 900000

    result = handler(test_event, MockContext())
    print(json.dumps(result, indent=2))
