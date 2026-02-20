#!/bin/bash
set -e

echo "========================================"
echo "Node.js MCP Security Fix - Build & Deploy"
echo "========================================"

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="654654422653"
ECR_REPOSITORY="nodejs-mcp-lambda-dev"
FUNCTION_NAME="nodejs-execution-mcp-server-dev"
IMAGE_TAG="security-fix"

echo ""
echo "Step 1: Building Docker image..."
echo "--------------------------------"
docker buildx build --platform linux/amd64 --provenance=false --sbom=false \
  -t nodejs-mcp-security-fix \
  -f Dockerfile.lambda . \
  --load

echo ""
echo "Step 2: Logging into ECR..."
echo "----------------------------"
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

echo ""
echo "Step 3: Tagging image for ECR..."
echo "---------------------------------"
docker tag nodejs-mcp-security-fix:latest \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}

echo ""
echo "Step 4: Pushing to ECR..."
echo "-------------------------"
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}

echo ""
echo "Step 5: Updating Lambda function..."
echo "------------------------------------"
aws lambda update-function-code \
  --function-name ${FUNCTION_NAME} \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG} \
  --region ${AWS_REGION}

echo ""
echo "Step 6: Waiting for Lambda update..."
echo "-------------------------------------"
aws lambda wait function-updated --function-name ${FUNCTION_NAME} --region ${AWS_REGION}

echo ""
echo "Step 7: Verifying deployment..."
echo "--------------------------------"
aws lambda get-function-configuration \
  --function-name ${FUNCTION_NAME} \
  --region ${AWS_REGION} \
  --query '{State:State, LastUpdateStatus:LastUpdateStatus, LastModified:LastModified}'

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo ""
echo "To test the security fix, run:"
echo "  ./TEST_SECURITY_FIX.sh"
echo ""
