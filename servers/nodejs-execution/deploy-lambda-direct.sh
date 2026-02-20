#!/bin/bash
set -e

AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="654654422653"
ECR_REPOSITORY="nodejs-mcp-lambda-dev"
FUNCTION_NAME="nodejs-execution-mcp-server-dev"
IMAGE_TAG="latest"

echo "=========================================================="
echo "Deploy Data Transformation MCP Server to AWS Lambda"
echo "=========================================================="

IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo "Function: $FUNCTION_NAME"
echo "Image URI: $IMAGE_URI"
echo ""

# Check if function exists
if aws lambda get-function --function-name $FUNCTION_NAME --region $AWS_REGION 2>/dev/null; then
    echo "Function exists. Updating code..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $IMAGE_URI \
        --region $AWS_REGION

    echo "Waiting for update to complete..."
    aws lambda wait function-updated --function-name $FUNCTION_NAME --region $AWS_REGION

else
    echo "Function does not exist. Creating..."

    # Create IAM role if needed
    ROLE_NAME="nodejs-mcp-lambda-role"
    ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

    if ! aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
        echo "Creating IAM role..."

        cat > /tmp/trust-policy.json << TRUST
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
TRUST

        aws iam create-role \
            --role-name $ROLE_NAME \
            --assume-role-policy-document file:///tmp/trust-policy.json

        aws iam attach-role-policy \
            --role-name $ROLE_NAME \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

        cat > /tmp/s3-policy.json << S3POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::jupyter-mcp-workspaces-654654422653",
        "arn:aws:s3:::jupyter-mcp-workspaces-654654422653/*"
      ]
    }
  ]
}
S3POLICY

        aws iam put-role-policy \
            --role-name $ROLE_NAME \
            --policy-name NodeJSMCPS3Access \
            --policy-document file:///tmp/s3-policy.json

        echo "Waiting for role to be ready..."
        sleep 10
    fi

    # Create function
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$IMAGE_URI \
        --role $ROLE_ARN \
        --timeout 300 \
        --memory-size 2048 \
        --region $AWS_REGION

    echo "Waiting for function to be active..."
    aws lambda wait function-active --function-name $FUNCTION_NAME --region $AWS_REGION

    # Create function URL
    echo "Creating function URL..."
    aws lambda create-function-url-config \
        --function-name $FUNCTION_NAME \
        --auth-type NONE \
        --region $AWS_REGION 2>/dev/null || echo "Function URL may already exist"

    # Add permission for public access
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --region $AWS_REGION 2>/dev/null || echo "Permission may already exist"
fi

# Get function URL
FUNCTION_URL=$(aws lambda get-function-url-config --function-name $FUNCTION_NAME --region $AWS_REGION --query 'FunctionUrl' --output text 2>/dev/null || echo "")

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Function ARN: arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}"
if [ -n "$FUNCTION_URL" ]; then
    echo "Function URL: $FUNCTION_URL"
    echo "$FUNCTION_URL" > .lambda-endpoint
fi
