#!/bin/bash
# Lambda deployment script with sudo for Docker commands
set -e

echo "================================================"
echo "Jupyter MCP Server - AWS Lambda Deployment"
echo "================================================"
echo

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! sudo docker --version &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found (using sudo)${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI found${NC}"

if ! command -v serverless &> /dev/null; then
    echo -e "${YELLOW}⚠ Serverless Framework not found. Installing...${NC}"
    sudo npm install -g serverless
fi
echo -e "${GREEN}✓ Serverless Framework found${NC}"

echo

# Get AWS account info
echo -e "${YELLOW}Getting AWS account information...${NC}"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}

echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  Region: $AWS_REGION"
echo

# Confirm
echo -e "${YELLOW}This will deploy Jupyter MCP Server to AWS Lambda${NC}"
echo "  Estimated cost: ~\$0.10-2/month (pay per use)"
echo "  Deployment time: ~5 minutes"
echo
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo

# Step 1: Build Docker image
echo -e "${YELLOW}Step 1/4: Building Lambda Docker image...${NC}"
sudo docker build -f Dockerfile.lambda -t jupyter-mcp-lambda:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

echo

# Step 2: Deploy with Serverless
echo -e "${YELLOW}Step 2/4: Deploying to AWS Lambda...${NC}"
echo "  This may take 3-5 minutes..."

serverless deploy -c serverless-lambda.yml --region $AWS_REGION

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment successful${NC}"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi

echo

# Step 3: Get endpoint
echo -e "${YELLOW}Step 3/4: Getting API endpoint...${NC}"
API_ENDPOINT=$(serverless info -c serverless-lambda.yml --region $AWS_REGION | grep "endpoint:" | awk '{print $2}' | head -1)

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${YELLOW}⚠ Extracting endpoint from output...${NC}"
    # Try alternative method
    serverless info -c serverless-lambda.yml --region $AWS_REGION > /tmp/sls-info.txt
    API_ENDPOINT=$(grep -oP 'https://[a-z0-9]+\.execute-api\.[a-z0-9-]+\.amazonaws\.com' /tmp/sls-info.txt | head -1)
fi

if [ -z "$API_ENDPOINT" ]; then
    echo -e "${YELLOW}⚠ Could not extract endpoint automatically${NC}"
    echo "  Run manually: serverless info -c serverless-lambda.yml"
    API_ENDPOINT="https://YOUR_API_ID.execute-api.$AWS_REGION.amazonaws.com"
fi

echo "  API Endpoint: $API_ENDPOINT"
echo "  MCP Endpoint: $API_ENDPOINT/mcp"
echo

# Step 4: Test deployment
echo -e "${YELLOW}Step 4/4: Testing deployment...${NC}"

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
echo "     serverless logs -f jupyterMcpServer -t"
echo
echo "To remove:"
echo "  serverless remove -c serverless-lambda.yml"
echo
echo "================================================"

# Save endpoint
echo "$API_ENDPOINT/mcp" > .lambda-endpoint
echo -e "${GREEN}Endpoint saved to .lambda-endpoint${NC}"
