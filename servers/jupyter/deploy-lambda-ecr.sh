#!/bin/bash
# Lambda deployment script using pre-pushed ECR image
set -e

echo "================================================"
echo "Jupyter MCP Server - AWS Lambda Deployment"
echo "Using Pre-Pushed ECR Image"
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
export AWS_ACCOUNT_ID

echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo

# Check if ECR image exists
ECR_REPO_NAME="jupyter-mcp-lambda-dev"
echo -e "${YELLOW}Checking for ECR image...${NC}"
if aws ecr describe-images --repository-name $ECR_REPO_NAME --image-ids imageTag=latest --region $AWS_REGION &>/dev/null; then
    echo -e "${GREEN}✓ ECR image found${NC}"
else
    echo -e "${RED}✗ ECR image not found${NC}"
    echo "  Please run: ./push-to-ecr.sh"
    exit 1
fi

echo

# Deploy with Serverless
echo -e "${YELLOW}Deploying to AWS Lambda...${NC}"
echo "  This may take 3-5 minutes..."
echo

serverless deploy -c serverless-ecr.yml --region $AWS_REGION

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment successful${NC}"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi

echo

# Get endpoint
echo -e "${YELLOW}Getting API endpoint...${NC}"
API_ENDPOINT=$(serverless info -c serverless-ecr.yml --region $AWS_REGION | grep "endpoint:" | awk '{print $2}' | head -1)

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${YELLOW}⚠ Extracting endpoint from output...${NC}"
    serverless info -c serverless-ecr.yml --region $AWS_REGION > /tmp/sls-info.txt
    API_ENDPOINT=$(grep -oP 'https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com' /tmp/sls-info.txt | head -1)
fi

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${YELLOW}⚠ Could not extract endpoint automatically${NC}"
    echo "  Run manually: serverless info -c serverless-ecr.yml"
    API_ENDPOINT="https://YOUR_API_ID.execute-api.$AWS_REGION.amazonaws.com"
fi

echo "  API Endpoint: $API_ENDPOINT"
echo "  MCP Endpoint: $API_ENDPOINT/mcp"
echo

# Test deployment
echo -e "${YELLOW}Testing deployment...${NC}"

if [ "$API_ENDPOINT" != "https://YOUR_API_ID.execute-api.$AWS_REGION.amazonaws.com" ]; then
    # Test health endpoint
    echo "  Testing health endpoint..."
    HEALTH_RESPONSE=$(curl -s "$API_ENDPOINT/health" || echo "curl failed")

    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        echo -e "${GREEN}  ✓ Health check passed${NC}"
    else
        echo -e "${YELLOW}  ⚠ Health check response: ${HEALTH_RESPONSE:0:100}${NC}"
    fi

    # Test MCP initialize
    echo "  Testing MCP protocol..."
    MCP_RESPONSE=$(curl -s -X POST "$API_ENDPOINT/mcp" \
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
      }' || echo "curl failed")

    if echo "$MCP_RESPONSE" | grep -q "jupyter-mcp-server"; then
        echo -e "${GREEN}  ✓ MCP initialize successful${NC}"
    else
        echo -e "${YELLOW}  ⚠ MCP response: ${MCP_RESPONSE:0:100}...${NC}"
    fi
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
echo "Next steps:"
echo "  1. Test the endpoint:"
echo "     curl $API_ENDPOINT/health"
echo
echo "  2. Add to your Amplify DynamoDB config:"
echo "     URL: $API_ENDPOINT/mcp"
echo
echo "  3. Monitor logs:"
echo "     serverless logs -f jupyterMcpServer -c serverless-ecr.yml -t"
echo
echo "To remove:"
echo "  serverless remove -c serverless-ecr.yml"
echo
echo "================================================"

# Save endpoint
echo "$API_ENDPOINT/mcp" > .lambda-endpoint
echo -e "${GREEN}Endpoint saved to .lambda-endpoint${NC}"
