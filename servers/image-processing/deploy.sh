#!/bin/bash

# Image Processing MCP Server - Deployment Script
# CRITICAL FIX: Changed import statement in server.py from "from image_manager import ImageManager"
# to "from .image_manager import ImageManager" to fix Lambda import error

set -e

echo "================================"
echo "Image Processing MCP Deployment"
echo "================================"
echo ""
echo "FIXED: Import error that was causing 502 errors"
echo "  Old: from image_manager import ImageManager"
echo "  New: from .image_manager import ImageManager"
echo ""

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID=
ECR_REPO="image-processing-mcp-server"
ECR_URI=".dkr.ecr..amazonaws.com/"
LAMBDA_FUNCTION="image-processing-mcp-server-dev"

echo "AWS Account: "
echo "ECR Repository: "
echo "Lambda Function: "
echo ""

# Step 1: Build Docker image
echo "[1/5] Building Docker image..."
docker build --platform linux/amd64 -f Dockerfile.lambda -t :latest .
if [ 127 -ne 0 ]; then
    echo "ERROR: Docker build failed!"
    exit 1
fi
echo "✓ Docker image built successfully"
echo ""

# Step 2: Tag image for ECR
echo "[2/5] Tagging image for ECR..."
docker tag :latest :latest
echo "✓ Image tagged"
echo ""

# Step 3: Login to ECR
echo "[3/5] Logging into ECR..."
aws ecr get-login-password --region  | docker login --username AWS --password-stdin 
if [ 127 -ne 0 ]; then
    echo "ERROR: ECR login failed!"
    exit 1
fi
echo "✓ Logged into ECR"
echo ""

# Step 4: Push image to ECR
echo "[4/5] Pushing image to ECR..."
docker push :latest
if [ 127 -ne 0 ]; then
    echo "ERROR: Docker push failed!"
    exit 1
fi
echo "✓ Image pushed to ECR"
echo ""

# Step 5: Get new image digest and update Lambda
echo "[5/5] Updating Lambda function..."
IMAGE_DIGEST=
NEW_IMAGE_URI="@"

echo "New image URI: "

aws lambda update-function-code   --function-name    --image-uri    --region    --output json > /tmp/lambda-update.json

if [ 127 -ne 0 ]; then
    echo "ERROR: Lambda update failed!"
    exit 1
fi
echo "✓ Lambda function updated"
echo ""

# Wait for update to complete
echo "Waiting for Lambda update to complete..."
aws lambda wait function-updated --function-name  --region 
echo "✓ Lambda update complete"
echo ""

echo "================================"
echo "Deployment Complete!"
echo "================================"
echo ""
echo "To test the deployment:"
echo "1. Go to your frontend and refresh MCP tools"
echo "2. Try the image rotation tool"
echo "3. Check Lambda logs if there are issues:"
echo "   aws logs tail /aws/lambda/ --region us-east-1 --follow"
echo ""
