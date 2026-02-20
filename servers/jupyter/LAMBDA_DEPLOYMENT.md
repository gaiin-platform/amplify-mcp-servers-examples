# Deploy Jupyter MCP Server to AWS Lambda (Container Image)

## Overview

This guide shows how to deploy your Jupyter MCP server as an **AWS Lambda function** using container images. This is more cost-effective than ECS Fargate for low-to-medium usage.

## Comparison: Lambda vs Fargate

| Aspect | Lambda Container | ECS Fargate |
|--------|-----------------|-------------|
| **Cold Start** | 5-10 seconds | None (always running) |
| **Cost (low usage)** | ~$0.10/month | ~$40/month |
| **Max execution** | 15 minutes | Unlimited |
| **Kernel persistence** | Per-invocation | Always-on |
| **Scaling** | Automatic (1000s) | Manual configuration |
| **Best for** | Dev/test, sporadic use | Production, high frequency |

**Recommendation:** Start with Lambda, migrate to Fargate if needed.

---

## Quick Start

### Step 1: Modify Dockerfile for Lambda

Lambda requires a specific runtime interface. Update your Dockerfile:

```dockerfile
# Dockerfile.lambda
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies
RUN yum install -y gcc gcc-c++ make

# Copy application
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
COPY jupyter_mcp_server ${LAMBDA_TASK_ROOT}/jupyter_mcp_server/

# Install Python dependencies
RUN pip install --no-cache-dir -e ${LAMBDA_TASK_ROOT}/

# Install data science libraries
RUN pip install --no-cache-dir \
    numpy>=1.24.0 \
    pandas>=2.0.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    scikit-learn>=1.3.0 \
    scipy>=1.11.0

# Create Lambda handler
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Set the CMD to your handler
CMD ["lambda_handler.handler"]
```

### Step 2: Create Lambda Handler

Create `lambda_handler.py` in your project root:

```python
"""
Lambda handler that wraps the Jupyter MCP Flask server
"""
import json
import base64
from jupyter_mcp_server.server import app, kernel_manager
from jupyter_mcp_server.kernel_manager import JupyterKernelManager

# Initialize kernel manager globally (for warm starts)
if kernel_manager is None:
    from jupyter_mcp_server import server as server_module
    server_module.kernel_manager = JupyterKernelManager(working_dir='/tmp')

def handler(event, context):
    """
    AWS Lambda handler for API Gateway proxy integration

    Converts API Gateway event to Flask request and returns API Gateway response
    """
    print(f"Event: {json.dumps(event)}")

    # Extract request details from API Gateway event
    http_method = event.get('httpMethod', 'POST')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')

    # Decode body if base64 encoded
    if event.get('isBase64Encoded', False):
        body = base64.b64decode(body).decode('utf-8')

    # Handle health check
    if path == '/health' and http_method == 'GET':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'healthy',
                'runtime': 'lambda',
                'requestId': context.request_id
            })
        }

    # Create a test request context for Flask
    with app.test_request_context(
        path=path,
        method=http_method,
        headers=headers,
        data=body,
        content_type=headers.get('content-type', 'application/json')
    ):
        try:
            # Process the request through Flask
            response = app.full_dispatch_request()

            # Convert Flask response to API Gateway format
            return {
                'statusCode': response.status_code,
                'headers': dict(response.headers),
                'body': response.get_data(as_text=True)
            }

        except Exception as e:
            print(f"Error processing request: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Internal server error',
                    'message': str(e)
                })
            }
```

### Step 3: Build and Push to ECR

```bash
# Set variables
export AWS_ACCOUNT_ID="your-account-id"
export AWS_REGION="us-east-1"
export ECR_REPO="jupyter-mcp-lambda"

# Create ECR repository
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION

# Build Lambda-specific image
docker build -f Dockerfile.lambda -t jupyter-mcp-lambda .

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag jupyter-mcp-lambda:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

### Step 4: Create Lambda Function

#### Option A: AWS CLI

```bash
# Create execution role
aws iam create-role \
  --role-name jupyter-mcp-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name jupyter-mcp-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create Lambda function
aws lambda create-function \
  --function-name jupyter-mcp-server \
  --package-type Image \
  --code ImageUri=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest \
  --role arn:aws:iam::$AWS_ACCOUNT_ID:role/jupyter-mcp-lambda-role \
  --timeout 900 \
  --memory-size 2048 \
  --ephemeral-storage Size=1024 \
  --architectures x86_64
```

#### Option B: Serverless Framework

Create `serverless-lambda.yml`:

```yaml
service: jupyter-mcp-lambda

provider:
  name: aws
  region: us-east-1
  ecr:
    images:
      jupyter-mcp:
        path: ./
        file: Dockerfile.lambda

functions:
  jupyterMcp:
    image:
      name: jupyter-mcp
    timeout: 900
    memorySize: 2048
    ephemeralStorageSize: 1024
    events:
      - httpApi:
          path: /{proxy+}
          method: ANY
      - httpApi:
          path: /
          method: ANY
    environment:
      PYTHONUNBUFFERED: '1'

resources:
  Outputs:
    ApiEndpoint:
      Description: "API Gateway endpoint URL"
      Value:
        Fn::Sub: "https://${HttpApi}.execute-api.${AWS::Region}.amazonaws.com"
```

Deploy:
```bash
serverless deploy -c serverless-lambda.yml
```

### Step 5: Create API Gateway

```bash
# Create HTTP API
API_ID=$(aws apigatewayv2 create-api \
  --name jupyter-mcp-api \
  --protocol-type HTTP \
  --query 'ApiId' \
  --output text)

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
  --api-id $API_ID \
  --integration-type AWS_PROXY \
  --integration-uri arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:jupyter-mcp-server \
  --payload-format-version 2.0 \
  --query 'IntegrationId' \
  --output text)

# Create route
aws apigatewayv2 create-route \
  --api-id $API_ID \
  --route-key 'ANY /{proxy+}' \
  --target integrations/$INTEGRATION_ID

# Create default stage
aws apigatewayv2 create-stage \
  --api-id $API_ID \
  --stage-name '$default' \
  --auto-deploy

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name jupyter-mcp-server \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigatewayv2.amazonaws.com \
  --source-arn "arn:aws:execute-api:$AWS_REGION:$AWS_ACCOUNT_ID:$API_ID/*/*"

# Get endpoint URL
echo "Endpoint: https://$API_ID.execute-api.$AWS_REGION.amazonaws.com"
```

---

## Testing

```bash
# Get your API endpoint
export API_ENDPOINT="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"

# Health check
curl $API_ENDPOINT/health

# MCP Initialize
curl -X POST $API_ENDPOINT/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0.0"}
    }
  }'

# Execute code
curl -X POST $API_ENDPOINT/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {"code": "print(\"Hello from Lambda!\")"}
    }
  }'
```

---

## Performance Optimization

### Reduce Cold Starts

1. **Provisioned Concurrency** (keeps instances warm):
```bash
aws lambda put-provisioned-concurrency-config \
  --function-name jupyter-mcp-server \
  --provisioned-concurrent-executions 1 \
  --qualifier '$LATEST'
```
Cost: ~$13/month for 1 instance always warm

2. **Increase Memory** (faster cold starts):
```bash
aws lambda update-function-configuration \
  --function-name jupyter-mcp-server \
  --memory-size 3008  # Max: 10GB
```

3. **Keep Warm with Scheduled Events**:
```bash
# Ping every 5 minutes to keep warm
aws events put-rule \
  --name jupyter-mcp-keepwarm \
  --schedule-expression 'rate(5 minutes)'

aws events put-targets \
  --rule jupyter-mcp-keepwarm \
  --targets Id=1,Arn=arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:jupyter-mcp-server
```

---

## Cost Analysis

### Scenario 1: Development/Testing (100 requests/month)
- Lambda invocations: 100 × 5 sec × 2GB = 1000 GB-sec
- Cost: 1000 × $0.0000166667 = **$0.02/month**
- With keep-warm (12 × 24 × 30 = 8,640 invocations): **$0.20/month**

### Scenario 2: Production (10,000 requests/month)
- Lambda invocations: 10,000 × 5 sec × 2GB = 100,000 GB-sec
- Cost: 100,000 × $0.0000166667 = **$1.67/month**
- API Gateway: 10,000 × $0.0000010 = **$0.01/month**
- **Total: ~$1.70/month**

### Scenario 3: With Provisioned Concurrency (always warm)
- Provisioned: 1 instance × 730 hrs × 2GB × $0.0000041667 = **$6.08/month**
- Execution cost: Same as above
- **Total: ~$7.75/month** (vs $40 for Fargate)

---

## Limitations & Workarounds

### 1. 15-Minute Timeout
- **Solution**: Split long computations into chunks
- Or: Use Step Functions to chain multiple Lambda invocations
- Or: Migrate to Fargate for specific long-running operations

### 2. Kernel State Doesn't Persist
- **Solution**: Use warm starts to keep kernel alive between invocations
- Or: Store intermediate results in S3/DynamoDB
- Or: Accept that each execution is stateless

### 3. Cold Start Latency
- **Solution**: Use provisioned concurrency ($6/month for 1 instance)
- Or: Optimize image size (use multi-stage builds)
- Or: Accept 5-10 second first-invocation delay

---

## When to Migrate to Fargate

Consider migrating if:
- Cold starts become unacceptable (>1 second)
- Need executions >15 minutes regularly
- Want true persistent Jupyter kernel
- High frequency (>100,000 requests/month makes Fargate cheaper)
- Team needs consistent <500ms response times

Migration is easy - just deploy with the original `Dockerfile` and ECS config from `DEPLOYMENT.md`.

---

## Summary

✅ **Lambda Container** is best for:
- Development and testing
- Sporadic usage patterns
- Cost-sensitive deployments
- Quick code executions (<15 min)

✅ **ECS Fargate** is best for:
- Production workloads
- High-frequency usage
- Long-running computations
- Persistent kernel requirements

**Start with Lambda, monitor usage, and migrate to Fargate if needed!**
