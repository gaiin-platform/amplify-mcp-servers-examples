# Complete Deployment Guide - Amplify MCP Servers

This guide walks you through deploying all MCP servers to AWS Lambda for Amplify integration.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Setup](#aws-setup)
3. [Docker Setup](#docker-setup)
4. [Deploying Each Server](#deploying-each-server)
5. [Amplify Integration](#amplify-integration)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

1. **AWS CLI** - Version 2.x or higher
   ```bash
   # Check version
   aws --version

   # Configure (if not already done)
   aws configure
   # Enter: Access Key ID, Secret Access Key, Region (us-east-1), Output (json)
   ```

2. **Docker Desktop** - Latest version
   - Windows: Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - Ensure it's running before deployment

3. **Git** - For cloning repository
   ```bash
   git --version
   ```

### AWS Permissions

Your AWS user/role needs permissions for:
- **Lambda**: Create, update, and invoke functions
- **ECR**: Create repositories, push images
- **S3**: Create buckets, put/get objects (optional but recommended)
- **IAM**: Create execution roles for Lambda
- **CloudWatch Logs**: For monitoring

### AWS Account Setup

1. **Create S3 Bucket** (recommended for file storage):
   ```bash
   aws s3 mb s3://amplify-mcp-files --region us-east-1
   ```

2. **Note your AWS Account ID**:
   ```bash
   aws sts get-caller-identity --query Account --output text
   ```

---

## AWS Setup

### 1. IAM Role for Lambda

The deployment scripts will create the role automatically, but you can create it manually:

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
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

# Create role
aws iam create-role \
  --role-name lambda-mcp-execution-role \
  --assume-role-policy-document file://trust-policy.json

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name lambda-mcp-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Create and attach S3 policy
cat > s3-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::amplify-mcp-files/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name lambda-mcp-execution-role \
  --policy-name S3Access \
  --policy-document file://s3-policy.json
```

---

## Docker Setup

### Start Docker Desktop

1. **Windows**: Launch Docker Desktop from Start menu
2. **Verify it's running**:
   ```bash
   docker ps
   ```
   Should return without errors (even if no containers running)

### Login to AWS ECR

```bash
# Get login command
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

You should see: "Login Succeeded"

---

## Deploying Each Server

### General Deployment Pattern

Each server follows the same 5-step process:

1. Navigate to server directory
2. Build Docker image
3. Create ECR repository (first time only)
4. Push image to ECR
5. Deploy/update Lambda function

### 1. Data Transformation Server

```bash
cd servers/data-transformation

# Build Docker image
docker build --platform linux/amd64 -t data-transformation-mcp-server -f Dockerfile.lambda .

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name data-transformation-mcp-server \
  --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh

# Get Function URL
aws lambda get-function-url-config \
  --function-name data-transformation-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text
```

**Save the Function URL** - you'll need it for Amplify configuration.

### 2. Image Processing Server

```bash
cd servers/image-processing

# Build Docker image
docker build --platform linux/amd64 -t image-processing-mcp-server -f Dockerfile.lambda .

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name image-processing-mcp-server \
  --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh

# Get Function URL
aws lambda get-function-url-config \
  --function-name image-processing-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text
```

**Configuration Note**: Set S3 bucket for image storage:
```bash
aws lambda update-function-configuration \
  --function-name image-processing-mcp-lambda \
  --environment "Variables={S3_BUCKET=amplify-mcp-files}" \
  --region us-east-1
```

### 3. Node.js Execution Server

```bash
cd servers/nodejs-execution

# Build Docker image
docker build --platform linux/amd64 -t nodejs-execution-mcp-server -f Dockerfile.lambda .

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name nodejs-execution-mcp-server \
  --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh

# Get Function URL
aws lambda get-function-url-config \
  --function-name nodejs-execution-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text
```

### 4. Jupyter Notebook Server

```bash
cd servers/jupyter

# Build Docker image (this takes longer due to dependencies)
docker build --platform linux/amd64 -t jupyter-mcp-server -f Dockerfile.lambda .

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name jupyter-mcp-server \
  --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh

# Get Function URL
aws lambda get-function-url-config \
  --function-name jupyter-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text
```

**Configuration Note**: Set S3 bucket (required for Jupyter):
```bash
aws lambda update-function-configuration \
  --function-name jupyter-mcp-lambda \
  --environment "Variables={S3_BUCKET=amplify-mcp-files}" \
  --memory-size 1024 \
  --timeout 900 \
  --region us-east-1
```

---

## Amplify Integration

### DynamoDB Configuration

Your MCP servers need to be registered in Amplify's DynamoDB table.

#### 1. Find Your DynamoDB Table

Check your Amplify configuration for the table name. Common pattern:
- `amplify-v6-lambda-dev-user-data-storage`
- `amplify-v6-lambda-prod-user-data-storage`

#### 2. Get User ID

Your user ID is typically found in Amplify's authentication system. Format:
- `{user_id}#amplify-mcp#mcp_servers`

#### 3. Register Servers

You'll need to update the DynamoDB item with your server configurations. Here's the structure:

```json
{
  "PK": "YOUR_USER_ID#amplify-mcp#mcp_servers",
  "servers": {
    "data-transformation": {
      "name": "Data Transformation",
      "url": "https://xxxxx.lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "description": "Convert between CSV, JSON, XML, YAML formats",
      "tools": [
        {
          "name": "csv_to_json",
          "description": "Convert CSV to JSON format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "csv_data": {
                "type": "string",
                "description": "CSV formatted data"
              }
            },
            "required": ["csv_data"]
          }
        },
        {
          "name": "json_to_csv",
          "description": "Convert JSON to CSV format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "json_data": {
                "type": "string",
                "description": "JSON formatted data (array of objects)"
              }
            },
            "required": ["json_data"]
          }
        },
        {
          "name": "xml_to_json",
          "description": "Convert XML to JSON format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "xml_data": {
                "type": "string",
                "description": "XML formatted data"
              }
            },
            "required": ["xml_data"]
          }
        },
        {
          "name": "json_to_xml",
          "description": "Convert JSON to XML format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "json_data": {
                "type": "string",
                "description": "JSON formatted data"
              }
            },
            "required": ["json_data"]
          }
        },
        {
          "name": "yaml_to_json",
          "description": "Convert YAML to JSON format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "yaml_data": {
                "type": "string",
                "description": "YAML formatted data"
              }
            },
            "required": ["yaml_data"]
          }
        },
        {
          "name": "json_to_yaml",
          "description": "Convert JSON to YAML format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "json_data": {
                "type": "string",
                "description": "JSON formatted data"
              }
            },
            "required": ["json_data"]
          }
        }
      ]
    },
    "image-processing": {
      "name": "Image Processing",
      "url": "https://yyyyy.lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "description": "Resize, crop, rotate, filter, and convert images",
      "tools": [
        {
          "name": "resize_image",
          "description": "Resize an image to specified dimensions",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "width": {
                "type": "integer",
                "description": "Target width in pixels"
              },
              "height": {
                "type": "integer",
                "description": "Target height in pixels"
              },
              "maintain_aspect": {
                "type": "boolean",
                "description": "Maintain aspect ratio (default: true)"
              }
            },
            "required": ["image_data", "width", "height"]
          }
        },
        {
          "name": "crop_image",
          "description": "Crop an image to specified region",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "left": {
                "type": "integer",
                "description": "Left coordinate"
              },
              "top": {
                "type": "integer",
                "description": "Top coordinate"
              },
              "right": {
                "type": "integer",
                "description": "Right coordinate"
              },
              "bottom": {
                "type": "integer",
                "description": "Bottom coordinate"
              }
            },
            "required": ["image_data", "left", "top", "right", "bottom"]
          }
        },
        {
          "name": "rotate_image",
          "description": "Rotate an image by specified degrees",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "degrees": {
                "type": "number",
                "description": "Rotation angle in degrees"
              },
              "expand": {
                "type": "boolean",
                "description": "Expand canvas to fit rotated image (default: true)"
              }
            },
            "required": ["image_data", "degrees"]
          }
        },
        {
          "name": "apply_filter",
          "description": "Apply filter to an image",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "filter_type": {
                "type": "string",
                "enum": ["grayscale", "blur", "sharpen", "edge_enhance", "contour", "brightness", "contrast"],
                "description": "Filter to apply"
              },
              "intensity": {
                "type": "number",
                "description": "Filter intensity (default: 1.0, range: 0.1 to 3.0)"
              }
            },
            "required": ["image_data", "filter_type"]
          }
        },
        {
          "name": "convert_format",
          "description": "Convert image to different format",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "target_format": {
                "type": "string",
                "enum": ["PNG", "JPEG", "WebP", "GIF", "BMP"],
                "description": "Target image format"
              },
              "quality": {
                "type": "integer",
                "description": "Quality for lossy formats (1-100, default: 85)"
              }
            },
            "required": ["image_data", "target_format"]
          }
        },
        {
          "name": "create_thumbnail",
          "description": "Create thumbnail version of image",
          "inputSchema": {
            "type": "object",
            "properties": {
              "image_data": {
                "type": "string",
                "description": "Base64 encoded image data"
              },
              "max_size": {
                "type": "integer",
                "description": "Maximum dimension in pixels (default: 200)"
              }
            },
            "required": ["image_data"]
          }
        }
      ]
    },
    "nodejs-execution": {
      "name": "JavaScript Executor",
      "url": "https://zzzzz.lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "description": "Execute JavaScript code in a safe sandbox",
      "tools": [
        {
          "name": "execute_javascript",
          "description": "Execute JavaScript code with timeout protection",
          "inputSchema": {
            "type": "object",
            "properties": {
              "code": {
                "type": "string",
                "description": "JavaScript code to execute"
              },
              "timeout": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 5000, max: 30000)"
              }
            },
            "required": ["code"]
          }
        }
      ]
    },
    "jupyter": {
      "name": "Jupyter Notebooks",
      "url": "https://wwwww.lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "description": "Interactive Python notebook execution",
      "tools": [
        {
          "name": "create_notebook",
          "description": "Create a new Jupyter notebook",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_name": {
                "type": "string",
                "description": "Name for the notebook"
              }
            },
            "required": ["notebook_name"]
          }
        },
        {
          "name": "execute_cell",
          "description": "Execute Python code in a notebook cell",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_id": {
                "type": "string",
                "description": "Notebook identifier"
              },
              "code": {
                "type": "string",
                "description": "Python code to execute"
              }
            },
            "required": ["notebook_id", "code"]
          }
        },
        {
          "name": "list_cells",
          "description": "List all cells in a notebook",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_id": {
                "type": "string",
                "description": "Notebook identifier"
              }
            },
            "required": ["notebook_id"]
          }
        },
        {
          "name": "get_output",
          "description": "Get output from a specific cell",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_id": {
                "type": "string",
                "description": "Notebook identifier"
              },
              "cell_index": {
                "type": "integer",
                "description": "Cell index (0-based)"
              }
            },
            "required": ["notebook_id", "cell_index"]
          }
        },
        {
          "name": "install_package",
          "description": "Install a Python package in the notebook kernel",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_id": {
                "type": "string",
                "description": "Notebook identifier"
              },
              "package_name": {
                "type": "string",
                "description": "Package name to install (e.g., 'pandas', 'numpy')"
              }
            },
            "required": ["notebook_id", "package_name"]
          }
        },
        {
          "name": "upload_file",
          "description": "Upload a file to notebook workspace",
          "inputSchema": {
            "type": "object",
            "properties": {
              "notebook_id": {
                "type": "string",
                "description": "Notebook identifier"
              },
              "filename": {
                "type": "string",
                "description": "Filename"
              },
              "content": {
                "type": "string",
                "description": "Base64 encoded file content"
              }
            },
            "required": ["notebook_id", "filename", "content"]
          }
        }
      ]
    }
  }
}
```

#### Update DynamoDB via AWS CLI

```bash
# Create JSON file with your configuration
cat > mcp-servers-config.json << 'EOF'
{
  "PK": {"S": "YOUR_USER_ID#amplify-mcp#mcp_servers"},
  "servers": {"M": {
    // ... paste the servers configuration from above ...
  }}
}
EOF

# Put item in DynamoDB
aws dynamodb put-item \
  --table-name amplify-v6-lambda-dev-user-data-storage \
  --item file://mcp-servers-config.json \
  --region us-east-1
```

Or use AWS Console:
1. Go to DynamoDB → Tables
2. Select your table
3. Click "Explore items"
4. Find or create item with PK `YOUR_USER_ID#amplify-mcp#mcp_servers`
5. Update the `servers` attribute

---

## Testing

### Test Lambda Function Directly

```bash
# Test tools/list endpoint
aws lambda invoke \
  --function-name data-transformation-mcp-lambda \
  --payload '{"body":"{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}"}' \
  --region us-east-1 \
  response.json

cat response.json
```

### Test via Function URL

```bash
FUNCTION_URL="https://xxxxx.lambda-url.us-east-1.on.aws/"

curl -X POST $FUNCTION_URL \
  -H "Content-Type: application/json" \
  -d '{
    "body": "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"csv_to_json\",\"arguments\":{\"csv_data\":\"a,b\\n1,2\"}},\"id\":1}"
  }'
```

### Test via Amplify

1. Log into your Amplify application
2. Open chat or LLM interface
3. Try a natural language request:
   - "Convert this CSV to JSON: name,age\nAlice,30"
   - "Resize this image to 800x600" (with image upload)
   - "Execute this JavaScript: Math.random() * 100"
   - "Create a notebook called data_analysis"

---

## Troubleshooting

### Docker Build Fails

**Symptoms**: "Cannot connect to Docker daemon"

**Solutions**:
1. Start Docker Desktop
2. Wait for it to fully initialize
3. Run: `docker ps` to verify

### ECR Push Authentication Fails

**Symptoms**: "no basic auth credentials"

**Solution**:
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com
```

### Lambda 502 Errors

**Check logs**:
```bash
aws logs tail /aws/lambda/[function-name] --follow --region us-east-1
```

**Common causes**:
- Python syntax errors in source code
- Missing dependencies
- Timeout (increase with `--timeout` flag)
- Memory limit (increase with `--memory-size` flag)

### Function URL Not Working

**Verify CORS configuration**:
```bash
aws lambda get-function-url-config \
  --function-name [function-name] \
  --region us-east-1
```

Should show:
```json
{
  "Cors": {
    "AllowOrigins": ["*"],
    "AllowMethods": ["POST", "GET", "OPTIONS"],
    "AllowHeaders": ["*"],
    "MaxAge": 86400
  }
}
```

### Tools Not Showing in Amplify

1. **Verify DynamoDB registration**: Check the item exists and has correct structure
2. **Check Function URLs**: Ensure they're accessible
3. **Refresh Amplify**: Log out and log back in
4. **Check browser console**: Look for errors when loading tools

---

## Quick Reference

### All Deployment Commands

```bash
# Data Transformation
cd servers/data-transformation && docker build --platform linux/amd64 -t data-transformation-mcp-server -f Dockerfile.lambda . && ./push-to-ecr.sh && ./deploy-lambda-ecr.sh && cd ../..

# Image Processing
cd servers/image-processing && docker build --platform linux/amd64 -t image-processing-mcp-server -f Dockerfile.lambda . && ./push-to-ecr.sh && ./deploy-lambda-ecr.sh && cd ../..

# Node.js Execution
cd servers/nodejs-execution && docker build --platform linux/amd64 -t nodejs-execution-mcp-server -f Dockerfile.lambda . && ./push-to-ecr.sh && ./deploy-lambda-ecr.sh && cd ../..

# Jupyter
cd servers/jupyter && docker build --platform linux/amd64 -t jupyter-mcp-server -f Dockerfile.lambda . && ./push-to-ecr.sh && ./deploy-lambda-ecr.sh && cd ../..
```

### Get All Function URLs

```bash
for func in data-transformation-mcp-lambda image-processing-mcp-lambda nodejs-execution-mcp-lambda jupyter-mcp-lambda; do
  echo "$func:"
  aws lambda get-function-url-config --function-name $func --region us-east-1 --query 'FunctionUrl' --output text
  echo ""
done
```

---

## Next Steps

After successful deployment:

1. ✅ All Lambda functions deployed
2. ✅ Function URLs obtained
3. ✅ DynamoDB configured with tool schemas
4. ✅ Test each function via CLI/curl
5. ✅ Test integration in Amplify UI
6. 📊 Monitor CloudWatch Logs for errors
7. 🔒 Review IAM permissions
8. 📈 Set up CloudWatch alarms (optional)
9. 💰 Monitor AWS costs

**Congratulations!** Your Amplify MCP servers are now live and ready to supercharge your LLM with powerful capabilities! 🚀
