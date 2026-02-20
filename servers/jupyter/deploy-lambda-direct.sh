#!/bin/bash
# Direct Lambda deployment using AWS CLI (bypasses Serverless Framework)
set -e

echo "================================================"
echo "Jupyter MCP Server - AWS Lambda Deployment"
echo "Direct AWS CLI Deployment"
echo "================================================"
echo

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get AWS account info
echo -e "${YELLOW}Getting AWS account information...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
FUNCTION_NAME="jupyter-mcp-server-dev"
ECR_REPO_NAME="jupyter-mcp-lambda-dev"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"

echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo "  Function: $FUNCTION_NAME"
echo

# Check if ECR image exists
echo -e "${YELLOW}Checking for ECR image...${NC}"
if aws ecr describe-images --repository-name $ECR_REPO_NAME --image-ids imageTag=latest --region $AWS_REGION &>/dev/null; then
    echo -e "${GREEN}✓ ECR image found${NC}"
    IMAGE_DIGEST=$(aws ecr describe-images --repository-name $ECR_REPO_NAME --image-ids imageTag=latest --region $AWS_REGION --query 'imageDetails[0].imageDigest' --output text)
    echo "  Digest: $IMAGE_DIGEST"
else
    echo -e "${RED}✗ ECR image not found${NC}"
    echo "  Please run: ./push-to-ecr.sh"
    exit 1
fi

echo

# Step 1: Create IAM role for Lambda
echo -e "${YELLOW}Step 1/5: Setting up IAM role...${NC}"
ROLE_NAME="jupyter-mcp-lambda-role"

# Check if role exists
if aws iam get-role --role-name $ROLE_NAME --region $AWS_REGION 2>/dev/null >/dev/null; then
    echo -e "${GREEN}✓ IAM role already exists${NC}"
else
    echo "  Creating IAM role..."

    # Create trust policy
    cat > /tmp/lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --region $AWS_REGION

    # Attach basic Lambda execution policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        --region $AWS_REGION

    echo -e "${GREEN}✓ IAM role created${NC}"
    echo "  Waiting 10 seconds for role to propagate..."
    sleep 10
fi

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"
echo "  Role ARN: $ROLE_ARN"
echo

# Step 2: Create or update Lambda function
echo -e "${YELLOW}Step 2/5: Creating/updating Lambda function...${NC}"

if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION 2>/dev/null >/dev/null; then
    echo "  Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $ECR_URI \
        --region $AWS_REGION \
        --output json > /tmp/lambda-update.json

    echo -e "${GREEN}✓ Lambda function updated${NC}"

    # Wait for update to complete
    echo "  Waiting for update to complete..."
    aws lambda wait function-updated --function-name $FUNCTION_NAME --region $AWS_REGION

    # Update configuration
    echo "  Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout 900 \
        --memory-size 2048 \
        --environment "Variables={PYTHONUNBUFFERED=1,JUPYTER_WORKING_DIR=/tmp/notebooks,LOG_LEVEL=INFO}" \
        --region $AWS_REGION \
        --output json > /tmp/lambda-config.json
else
    echo "  Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$ECR_URI \
        --role $ROLE_ARN \
        --timeout 900 \
        --memory-size 2048 \
        --ephemeral-storage "Size=1024" \
        --architectures x86_64 \
        --environment "Variables={PYTHONUNBUFFERED=1,JUPYTER_WORKING_DIR=/tmp/notebooks,LOG_LEVEL=INFO}" \
        --region $AWS_REGION \
        --output json > /tmp/lambda-create.json

    echo -e "${GREEN}✓ Lambda function created${NC}"
fi

# Wait for function to be ready
echo "  Waiting for function to be ready..."
aws lambda wait function-active --function-name $FUNCTION_NAME --region $AWS_REGION

FUNCTION_ARN=$(aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)
echo "  Function ARN: $FUNCTION_ARN"
echo

# Step 3: Create API Gateway
echo -e "${YELLOW}Step 3/5: Setting up API Gateway...${NC}"

# Check if API exists
API_NAME="jupyter-mcp-api"
API_ID=$(aws apigatewayv2 get-apis --region $AWS_REGION --query "Items[?Name=='${API_NAME}'].ApiId" --output text)

if [ -z "$API_ID" ]; then
    echo "  Creating HTTP API..."
    API_ID=$(aws apigatewayv2 create-api \
        --name $API_NAME \
        --protocol-type HTTP \
        --target $FUNCTION_ARN \
        --region $AWS_REGION \
        --query 'ApiId' \
        --output text)
    echo -e "${GREEN}✓ API created${NC}"
else
    echo -e "${GREEN}✓ API already exists${NC}"
fi

echo "  API ID: $API_ID"

# Create integration
INTEGRATION_ID=$(aws apigatewayv2 get-integrations --api-id $API_ID --region $AWS_REGION --query 'Items[0].IntegrationId' --output text 2>/dev/null || echo "")

if [ -z "$INTEGRATION_ID" ] || [ "$INTEGRATION_ID" == "None" ]; then
    echo "  Creating integration..."
    INTEGRATION_ID=$(aws apigatewayv2 create-integration \
        --api-id $API_ID \
        --integration-type AWS_PROXY \
        --integration-uri $FUNCTION_ARN \
        --payload-format-version 2.0 \
        --region $AWS_REGION \
        --query 'IntegrationId' \
        --output text)
    echo -e "${GREEN}✓ Integration created${NC}"
else
    echo -e "${GREEN}✓ Integration already exists${NC}"
fi

# Create routes
echo "  Setting up routes..."
aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'ANY /{proxy+}' \
    --target "integrations/${INTEGRATION_ID}" \
    --region $AWS_REGION 2>/dev/null || echo "  Route /{proxy+} already exists"

aws apigatewayv2 create-route \
    --api-id $API_ID \
    --route-key 'ANY /' \
    --target "integrations/${INTEGRATION_ID}" \
    --region $AWS_REGION 2>/dev/null || echo "  Route / already exists"

echo

# Step 4: Grant API Gateway permission to invoke Lambda
echo -e "${YELLOW}Step 4/5: Configuring permissions...${NC}"

STATEMENT_ID="apigateway-invoke-${API_ID}"
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id $STATEMENT_ID \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${API_ID}/*" \
    --region $AWS_REGION 2>/dev/null || echo "  Permission already exists"

echo -e "${GREEN}✓ Permissions configured${NC}"
echo

# Get API endpoint
API_ENDPOINT="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com"

echo -e "${GREEN}✓ Deployment complete${NC}"
echo

# Step 5: Test deployment
echo -e "${YELLOW}Step 5/5: Testing deployment...${NC}"

# Test health endpoint
echo "  Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "$API_ENDPOINT/health" -w "\n%{http_code}" 2>/dev/null || echo -e "curl failed\n000")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}  ✓ Health check passed${NC}"
    echo "    Response: ${BODY:0:100}"
else
    echo -e "${YELLOW}  ⚠ Health check returned HTTP $HTTP_CODE${NC}"
    echo "    Response: ${BODY:0:100}"
fi

# Test MCP initialize
echo "  Testing MCP protocol..."
MCP_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/mcp" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test", "version": "1.0.0"}
    }
  }' 2>/dev/null || echo -e "curl failed\n000")

MCP_HTTP_CODE=$(echo "$MCP_RESPONSE" | tail -1)
MCP_BODY=$(echo "$MCP_RESPONSE" | head -n -1)

if echo "$MCP_BODY" | grep -q "jupyter-mcp-server"; then
    echo -e "${GREEN}  ✓ MCP initialize successful${NC}"
    echo "    Response: ${MCP_BODY:0:100}..."
else
    echo -e "${YELLOW}  ⚠ MCP returned HTTP $MCP_HTTP_CODE${NC}"
    echo "    Response: ${MCP_BODY:0:200}"
fi

echo

# Summary
echo "================================================"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "================================================"
echo
echo "Your Jupyter MCP Server is now running on AWS Lambda"
echo
echo "Endpoints:"
echo "  Health: $API_ENDPOINT/health"
echo "  MCP: $API_ENDPOINT/mcp"
echo
echo "Resources Created:"
echo "  Lambda Function: $FUNCTION_NAME"
echo "  IAM Role: $ROLE_NAME"
echo "  API Gateway: $API_ID"
echo "  ECR Repository: $ECR_REPO_NAME"
echo
echo "Next steps:"
echo "  1. Test the endpoint:"
echo "     curl $API_ENDPOINT/health"
echo
echo "  2. Add to your Amplify DynamoDB config:"
echo "     URL: $API_ENDPOINT/mcp"
echo
echo "  3. Monitor logs:"
echo "     aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo
echo "To remove:"
echo "  aws lambda delete-function --function-name $FUNCTION_NAME"
echo "  aws apigatewayv2 delete-api --api-id $API_ID"
echo "  aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
echo "  aws iam delete-role --role-name $ROLE_NAME"
echo
echo "================================================"

# Save endpoint
echo "$API_ENDPOINT/mcp" > .lambda-endpoint
echo -e "${GREEN}Endpoint saved to .lambda-endpoint${NC}"
