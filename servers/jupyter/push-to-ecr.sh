#!/bin/bash
# Manually push Docker image to ECR with sudo
set -e

echo "================================================"
echo "Pushing Docker Image to ECR"
echo "================================================"
echo

# Get AWS info
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
ECR_REPO_NAME="jupyter-mcp-lambda-dev"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "ECR Repository: $ECR_REPO_NAME"
echo

# Step 1: Create ECR repository if it doesn't exist
echo "Step 1/4: Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
aws ecr create-repository \
  --repository-name $ECR_REPO_NAME \
  --region $AWS_REGION \
  --image-scanning-configuration scanOnPush=true \
  --query 'repository.repositoryUri' \
  --output text

echo "✓ ECR repository ready"
echo

# Step 2: Login to ECR
echo "Step 2/4: Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | sudo docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
echo "✓ Logged in to ECR"
echo

# Step 3: Tag image
echo "Step 3/4: Tagging image..."
sudo docker tag jupyter-mcp-lambda:latest ${ECR_URI}:latest
echo "✓ Image tagged"
echo

# Step 4: Push to ECR
echo "Step 4/4: Pushing to ECR (this may take 2-3 minutes)..."
sudo docker push ${ECR_URI}:latest
echo "✓ Image pushed"
echo

echo "================================================"
echo "✓ Docker image is now in ECR"
echo "================================================"
echo
echo "ECR URI: ${ECR_URI}:latest"
echo
echo "Now run: ./deploy-lambda-ecr.sh"
echo
