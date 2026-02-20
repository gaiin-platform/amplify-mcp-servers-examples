# Amplify MCP Servers - Deployment Examples

This repository contains example Model Context Protocol (MCP) servers designed to be deployed as AWS Lambda functions and integrated with Amplify applications. These servers provide LLMs with powerful capabilities like data transformation, image processing, code execution, and Jupyter notebook interaction.

## 📦 Available MCP Servers

| Server | Description | Tools Provided | Status |
|--------|-------------|----------------|--------|
| **Data Transformation** | Convert between data formats (CSV, JSON, XML, YAML) | `csv_to_json`, `json_to_csv`, `xml_to_json`, `json_to_xml`, `yaml_to_json`, `json_to_yaml` | ✅ Production Ready |
| **Image Processing** | Comprehensive image manipulation | `resize_image`, `crop_image`, `rotate_image`, `apply_filter`, `convert_format`, `create_thumbnail` | ✅ Production Ready |
| **Node.js Execution** | Safe sandboxed JavaScript execution | `execute_javascript` | ✅ Production Ready |
| **Jupyter Notebooks** | Interactive Python notebook execution | `create_notebook`, `execute_cell`, `list_cells`, `get_output`, `install_package`, `upload_file` | ✅ Production Ready |

---

## 🏗️ Architecture Overview

```
┌─────────────────┐
│  Amplify App    │
└────────┬────────┘
         │
         │ HTTP POST
         │
┌────────▼────────┐
│  API Gateway    │
└────────┬────────┘
         │
         │ Invoke
         │
┌────────▼────────────────┐
│  Lambda Function        │
│  (MCP Server)           │
│  ┌──────────────────┐   │
│  │ Docker Container │   │
│  │ - Python 3.12    │   │
│  │ - MCP Protocol   │   │
│  │ - Tool Logic     │   │
│  └──────────────────┘   │
└─────────┬───────────────┘
          │
          │ S3 (optional)
          │ for file storage
          │
┌─────────▼───────────┐
│  S3 Bucket          │
│  - Processed Files  │
│  - Presigned URLs   │
└─────────────────────┘
```

### How It Works

1. **Frontend Request**: User interacts with Amplify app, triggering an MCP tool request
2. **API Gateway**: Routes the request to the appropriate Lambda function
3. **Lambda Execution**:
   - Receives JSON-RPC 2.0 formatted request
   - Executes the requested tool with provided parameters
   - Processes data (transform, execute code, process image, etc.)
4. **Response**:
   - Returns results in MCP protocol format
   - Includes presigned S3 URLs for large files (24-hour expiry)
5. **Frontend Display**: Amplify app receives and displays the results to user

---

## 🚀 Quick Start

### Prerequisites

1. **AWS Account** with appropriate permissions:
   - Lambda function creation and management
   - ECR repository creation and image push
   - S3 bucket access (for file storage)
   - DynamoDB access (for Amplify MCP configuration)

2. **AWS CLI** configured:
   ```bash
   aws configure
   # Enter your Access Key ID, Secret Access Key, Region (us-east-1), and output format (json)
   ```

3. **Docker Desktop** installed and running

4. **Git** for cloning this repository

### Deployment Steps

Each server follows the same deployment pattern:

1. **Navigate to the server directory**:
   ```bash
   cd servers/[server-name]
   ```

2. **Build the Docker image**:
   ```bash
   docker build --platform linux/amd64 -t [server-name]-mcp-server -f Dockerfile.lambda .
   ```

3. **Create ECR repository** (if it doesn't exist):
   ```bash
   aws ecr create-repository --repository-name [server-name]-mcp-server --region us-east-1
   ```

4. **Tag and push to ECR**:
   ```bash
   # Use the provided push-to-ecr.sh script
   ./push-to-ecr.sh
   ```

5. **Deploy Lambda function**:
   ```bash
   # Use the deploy script
   ./deploy-lambda-ecr.sh
   ```

6. **Configure in Amplify**:
   - Lambda function URL is automatically created with CORS enabled
   - Add the function URL to your Amplify app's DynamoDB MCP configuration

---

## 📖 Detailed Server Documentation

### 1. Data Transformation MCP Server

**Location**: `servers/data-transformation/`

**Description**: Converts data between common formats (CSV, JSON, XML, YAML) with S3 persistence for large files.

#### Tools

| Tool | Input | Output | Use Case |
|------|-------|--------|----------|
| `csv_to_json` | CSV string | JSON string | Parse CSV data for processing |
| `json_to_csv` | JSON string | CSV string | Export data to spreadsheet format |
| `xml_to_json` | XML string | JSON string | Parse XML APIs/configs |
| `json_to_xml` | JSON string | XML string | Generate XML for legacy systems |
| `yaml_to_json` | YAML string | JSON string | Parse config files |
| `json_to_yaml` | JSON string | YAML string | Generate human-readable configs |

#### Environment Variables

```bash
S3_BUCKET=your-bucket-name  # Optional: for storing large files
```

#### Deployment

```bash
cd servers/data-transformation

# Build Docker image
docker build --platform linux/amd64 -t data-transformation-mcp-server -f Dockerfile.lambda .

# Create ECR repository
aws ecr create-repository --repository-name data-transformation-mcp-server --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh
```

#### Example Usage

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "csv_to_json",
    "arguments": {
      "csv_data": "name,age,city\nJohn,30,NYC\nJane,25,LA"
    }
  },
  "id": 1
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Converted 2 rows from CSV to JSON"
      },
      {
        "type": "text",
        "text": "[{\"name\":\"John\",\"age\":\"30\",\"city\":\"NYC\"},{\"name\":\"Jane\",\"age\":\"25\",\"city\":\"LA\"}]"
      }
    ]
  },
  "id": 1
}
```

---

### 2. Image Processing MCP Server

**Location**: `servers/image-processing/`

**Description**: Comprehensive image manipulation including resize, crop, rotate, filters, format conversion, and thumbnail generation.

#### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `resize_image` | `image_data`, `width`, `height`, `maintain_aspect` | Resize with aspect ratio preservation |
| `crop_image` | `image_data`, `left`, `top`, `right`, `bottom` | Crop to specific region |
| `rotate_image` | `image_data`, `degrees`, `expand` | Rotate by angle |
| `apply_filter` | `image_data`, `filter_type`, `intensity` | Apply filters (grayscale, blur, sharpen, etc.) |
| `convert_format` | `image_data`, `target_format`, `quality` | Convert between PNG, JPEG, WebP, GIF, BMP |
| `create_thumbnail` | `image_data`, `max_size` | Generate thumbnail |

#### Supported Filters

- `grayscale`: Convert to black and white
- `blur`: Gaussian blur with intensity control
- `sharpen`: Enhance edges
- `edge_enhance`: Emphasize edges
- `contour`: Extract contours
- `brightness`: Adjust brightness (intensity: 0.5 = darker, 1.5 = brighter)
- `contrast`: Adjust contrast (intensity: 0.5 = lower, 1.5 = higher)

#### Environment Variables

```bash
S3_BUCKET=your-bucket-name  # Optional: for storing processed images
```

#### Deployment

```bash
cd servers/image-processing

# Build Docker image
docker build --platform linux/amd64 -t image-processing-mcp-server -f Dockerfile.lambda .

# Create ECR repository
aws ecr create-repository --repository-name image-processing-mcp-server --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh
```

#### Example Usage

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "rotate_image",
    "arguments": {
      "image_data": "iVBORw0KGgoAAAANSUhEUgAAAAUA...",
      "degrees": 90,
      "expand": true
    }
  },
  "id": 1
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Rotated by 90 degrees"
      },
      {
        "type": "text",
        "text": "\n\n[Image] 800x600 PNG"
      },
      {
        "type": "image",
        "data": "iVBORw0KGgoAAAANSUhEUgAAA...",
        "mimeType": "image/png"
      },
      {
        "type": "text",
        "text": "\n\n[Download] 245 KB:\nhttps://bucket.s3.amazonaws.com/..."
      }
    ]
  },
  "id": 1
}
```

#### Important Notes

**Base64 Encoding**:
- Input images must be base64 encoded
- Data URI prefix (`data:image/png;base64,`) is automatically stripped
- Whitespace and newlines are automatically removed
- Padding is automatically added if needed

**Size Limits**:
- Images under 4MB: Returned as base64 in response
- Images over 4MB: Only S3 presigned URL provided (24-hour expiry)

---

### 3. Node.js Execution MCP Server

**Location**: `servers/nodejs-execution/`

**Description**: Executes JavaScript code in a safe, sandboxed environment with timeout protection.

#### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `execute_javascript` | `code`, `timeout` | Execute JS code with optional timeout (default: 5000ms) |

#### Features

- **Safe Execution**: Runs in isolated VM context
- **Timeout Protection**: Prevents infinite loops (default 5 seconds, max 30 seconds)
- **Console Capture**: Captures `console.log()` output
- **Error Handling**: Returns clear error messages with stack traces
- **Return Value**: Captures and returns the last expression value

#### Deployment

```bash
cd servers/nodejs-execution

# Build Docker image
docker build --platform linux/amd64 -t nodejs-execution-mcp-server -f Dockerfile.lambda .

# Create ECR repository
aws ecr create-repository --repository-name nodejs-execution-mcp-server --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh
```

#### Example Usage

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_javascript",
    "arguments": {
      "code": "function fibonacci(n) { return n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2); }\nfibonacci(10);",
      "timeout": 5000
    }
  },
  "id": 1
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Execution completed successfully"
      },
      {
        "type": "text",
        "text": "Result: 55\n\nExecution time: 12ms"
      }
    ]
  },
  "id": 1
}
```

#### Security Considerations

- Code runs in Node.js VM sandbox
- Limited to 30-second maximum timeout
- No filesystem access
- No network access from executed code
- Memory limited by Lambda constraints (configurable)

---

### 4. Jupyter Notebook MCP Server

**Location**: `servers/jupyter/`

**Description**: Interactive Python notebook execution with Jupyter kernel management, matplotlib plotting, and package installation.

#### Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_notebook` | `notebook_name` | Create new notebook with kernel |
| `execute_cell` | `notebook_id`, `code` | Execute Python code cell |
| `list_cells` | `notebook_id` | List all executed cells |
| `get_output` | `notebook_id`, `cell_index` | Get specific cell output |
| `install_package` | `notebook_id`, `package_name` | Install Python package |
| `upload_file` | `notebook_id`, `filename`, `content` | Upload file to notebook workspace |

#### Features

- **Persistent Kernels**: Each notebook maintains state across executions
- **Matplotlib Support**: Generates PNG images for plots
- **Package Management**: Install packages on-the-fly with pip
- **File Upload**: Upload data files to notebook workspace
- **S3 Integration**: Large outputs stored in S3 with presigned URLs
- **Output Capture**: Returns stdout, stderr, and display data

#### Environment Variables

```bash
S3_BUCKET=your-bucket-name  # Required for storing notebooks and outputs
```

#### Deployment

```bash
cd servers/jupyter

# Build Docker image
docker build --platform linux/amd64 -t jupyter-mcp-server -f Dockerfile.lambda .

# Create ECR repository
aws ecr create-repository --repository-name jupyter-mcp-server --region us-east-1

# Push to ECR
./push-to-ecr.sh

# Deploy Lambda
./deploy-lambda-ecr.sh
```

#### Example Usage

**1. Create Notebook**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "create_notebook",
    "arguments": {
      "notebook_name": "data_analysis"
    }
  },
  "id": 1
}
```

**2. Execute Code**:
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "execute_cell",
    "arguments": {
      "notebook_id": "nb_abc123",
      "code": "import matplotlib.pyplot as plt\nimport numpy as np\nx = np.linspace(0, 10, 100)\ny = np.sin(x)\nplt.plot(x, y)\nplt.title('Sine Wave')\nplt.show()"
    }
  },
  "id": 2
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Cell executed successfully (520ms)"
      },
      {
        "type": "image",
        "data": "iVBORw0KGgoAAAANSUhEUg...",
        "mimeType": "image/png"
      },
      {
        "type": "text",
        "text": "[Download Full Notebook]\nhttps://bucket.s3.amazonaws.com/..."
      }
    ]
  },
  "id": 2
}
```

#### Lambda Configuration

- **Memory**: 1024 MB (increase for data-intensive workloads)
- **Timeout**: 900 seconds (15 minutes maximum)
- **Ephemeral Storage**: 512 MB (for temporary files)

---

## 🔧 Amplify Integration

### DynamoDB MCP Server Configuration

After deploying your Lambda functions, you need to register them in your Amplify application's DynamoDB table.

#### Table Structure

**Table Name**: `amplify-v6-lambda-dev-user-data-storage` (or your configured table)

**Partition Key (PK)**: `{user_id}#amplify-mcp#mcp_servers`

**Item Structure**:
```json
{
  "PK": "84484458-a081-7063-5367-6f05668660ea#amplify-mcp#mcp_servers",
  "servers": {
    "data-transformation": {
      "name": "Data Transformation",
      "url": "https://[lambda-url].lambda-url.us-east-1.on.aws/",
      "enabled": true,
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
        }
        // ... other tools
      ]
    },
    "image-processing": {
      "name": "Image Processing",
      "url": "https://[lambda-url].lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "tools": [
        // ... image tools
      ]
    },
    "nodejs-execution": {
      "name": "JavaScript Executor",
      "url": "https://[lambda-url].lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "tools": [
        // ... nodejs tools
      ]
    },
    "jupyter": {
      "name": "Jupyter Notebooks",
      "url": "https://[lambda-url].lambda-url.us-east-1.on.aws/",
      "enabled": true,
      "tools": [
        // ... jupyter tools
      ]
    }
  }
}
```

### Getting Lambda Function URLs

After deployment, retrieve the function URL:

```bash
aws lambda get-function-url-config \
  --function-name [function-name]-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text
```

Or check in AWS Console:
1. Go to Lambda → Functions
2. Select your function
3. Go to Configuration → Function URL
4. Copy the URL

### Tool Schema Registration

Each tool needs its schema registered in DynamoDB. The schema follows the MCP protocol specification:

```json
{
  "name": "tool_name",
  "description": "What the tool does",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param1": {
        "type": "string",
        "description": "Parameter description"
      },
      "param2": {
        "type": "integer",
        "description": "Another parameter",
        "default": 100
      }
    },
    "required": ["param1"]
  }
}
```

**Important**: Do NOT use float types in schema - use integer with description of allowed range.

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Lambda 502 Errors

**Symptoms**: HTTP 502 Bad Gateway when calling Lambda

**Causes & Solutions**:

- **Python Syntax Errors**:
  ```bash
  # Validate syntax before deploying
  python3 -m py_compile server.py
  ```

- **Unicode/Encoding Issues**: Avoid emoji or special characters in source code

- **Missing Dependencies**: Check Dockerfile includes all required packages

- **Cold Start Timeout**: Increase Lambda timeout configuration

**Debugging**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/[function-name] --follow --region us-east-1

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/[function-name] \
  --filter-pattern "ERROR" \
  --region us-east-1
```

#### 2. Base64 Decoding Errors

**Symptoms**: "Invalid base64-encoded string: number of data characters cannot be 1 more than a multiple of 4"

**Solution**: Already handled in image-processing server - strips whitespace and adds padding

**Verification**:
```python
# Ensure your base64 string is clean
image_data = image_data.strip().replace('\n', '').replace('\r', '').replace(' ', '')
padding_needed = len(image_data) % 4
if padding_needed:
    image_data += '=' * (4 - padding_needed)
```

#### 3. DynamoDB Float Type Error

**Symptoms**: "Float types are not supported. Use Decimal types instead."

**Solution**: Remove default float values from tool schemas

**Wrong**:
```json
{
  "intensity": {
    "type": "number",
    "default": 1.0  // ❌ This causes error
  }
}
```

**Correct**:
```json
{
  "intensity": {
    "type": "number",
    "description": "Intensity value (default: 1.0)"  // ✅ Document in description
  }
}
```

#### 4. Docker Build Failures

**Symptoms**: Permission denied, unable to connect to Docker daemon

**Solutions**:
- Start Docker Desktop
- Run as administrator (Windows)
- Add user to docker group (Linux):
  ```bash
  sudo usermod -aG docker $USER
  ```

#### 5. ECR Push Authentication

**Symptoms**: "no basic auth credentials"

**Solution**:
```bash
# Re-authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  [account-id].dkr.ecr.us-east-1.amazonaws.com
```

#### 6. S3 Access Denied

**Symptoms**: S3 upload fails with 403 Forbidden

**Solution**: Update Lambda execution role with S3 permissions:

```json
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
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

---

## 📊 Performance Optimization

### Lambda Configuration

| Server | Memory | Timeout | Concurrent Executions |
|--------|--------|---------|----------------------|
| Data Transformation | 512 MB | 60s | 100 |
| Image Processing | 1024 MB | 120s | 50 |
| Node.js Execution | 512 MB | 60s | 100 |
| Jupyter | 1024 MB | 900s | 10 |

### Cold Start Mitigation

1. **Provisioned Concurrency**: Keep Lambda instances warm
   ```bash
   aws lambda put-provisioned-concurrency-config \
     --function-name [function-name] \
     --provisioned-concurrent-executions 2 \
     --region us-east-1
   ```

2. **Keep-Alive Pings**: Send periodic requests to prevent cold starts

3. **Optimize Docker Images**:
   - Use multi-stage builds
   - Minimize image size
   - Pre-compile Python bytecode

### S3 Optimization

1. **Presigned URL Expiry**: Default 24 hours (86400 seconds)
2. **Lifecycle Policies**: Auto-delete temporary files after 7 days
3. **Transfer Acceleration**: Enable for faster uploads (optional)

---

## 🔒 Security Best Practices

### Lambda Security

1. **Least Privilege IAM Roles**: Only grant necessary permissions
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "logs:CreateLogGroup",
           "logs:CreateLogStream",
           "logs:PutLogEvents"
         ],
         "Resource": "arn:aws:logs:*:*:*"
       },
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject"
         ],
         "Resource": "arn:aws:s3:::your-bucket/*"
       }
     ]
   }
   ```

2. **VPC Configuration**: Deploy Lambda in VPC for internal resources

3. **Environment Variables**: Use AWS Secrets Manager for sensitive data

4. **Function URLs**: Enable IAM authentication if needed (currently using NONE for Amplify integration)

### Input Validation

All servers implement input validation:

- **Type checking**: Ensures parameters match expected types
- **Size limits**: Prevents memory exhaustion
- **Timeout enforcement**: Prevents infinite execution
- **Sanitization**: Cleans user input before processing

### Code Execution Safety

**Node.js Execution Server**:
- Runs in isolated VM context
- No filesystem access
- No network access from executed code
- 30-second maximum timeout

**Jupyter Server**:
- Kernel isolation per notebook
- Package installation limited to pip
- Execution timeout enforced
- S3-only file persistence

---

## 📈 Monitoring & Logging

### CloudWatch Logs

Each Lambda function logs to CloudWatch:

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/[function-name] --follow

# Filter errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/[function-name] \
  --filter-pattern "ERROR"

# Get specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/[function-name] \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Metrics to Monitor

1. **Invocations**: Number of requests
2. **Duration**: Execution time (optimize if consistently high)
3. **Errors**: Failed executions (investigate immediately)
4. **Throttles**: Rate limiting (increase concurrent executions)
5. **Cold Starts**: Initial invocation delays (consider provisioned concurrency)

### CloudWatch Alarms

Set up alarms for critical metrics:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name "[function-name]-errors" \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=[function-name]
```

---

## 🧪 Testing

### Local Testing

Each server includes test files. Run locally before deploying:

```bash
# Data Transformation
cd servers/data-transformation
python3 -c "from data_mcp_server.server import handle_tools_call; print(handle_tools_call({'name': 'csv_to_json', 'arguments': {'csv_data': 'a,b\n1,2'}}))"

# Image Processing
cd servers/image-processing
python3 -c "from image_mcp_server.image_manager import ImageManager; print('✓ ImageManager imports')"

# Node.js Execution
cd servers/nodejs-execution
python3 -c "from nodejs_mcp_server.server import handle_tools_call; print(handle_tools_call({'name': 'execute_javascript', 'arguments': {'code': '2+2'}}))"

# Jupyter
cd servers/jupyter
python3 -c "from jupyter_mcp_server.kernel_manager import KernelManager; print('✓ KernelManager imports')"
```

### Lambda Testing

After deployment, test via AWS Console:

1. Go to Lambda → Functions → [your-function]
2. Click "Test" tab
3. Create test event:
   ```json
   {
     "body": "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"csv_to_json\",\"arguments\":{\"csv_data\":\"a,b\\n1,2\"}},\"id\":1}"
   }
   ```
4. Execute and check response

### Integration Testing

Test via Amplify frontend:
1. Ensure tool is registered in DynamoDB
2. Refresh Amplify app to load tools
3. Use LLM to invoke tool naturally
4. Verify results in UI

---

## 🚢 Deployment Scripts Reference

### deploy-lambda-ecr.sh

**Purpose**: Deploy Lambda function using ECR container image

**Usage**:
```bash
./deploy-lambda-ecr.sh
```

**What it does**:
1. Checks if Lambda function exists
2. If exists: Updates function code with latest ECR image
3. If not: Creates new function with:
   - Container image from ECR
   - 512 MB memory (configurable)
   - 60-second timeout (configurable)
   - IAM role with necessary permissions
   - Function URL with CORS enabled

**Environment Variables**:
- `AWS_REGION`: AWS region (default: us-east-1)
- `S3_BUCKET`: S3 bucket name (optional)

### push-to-ecr.sh

**Purpose**: Push Docker image to AWS ECR

**Usage**:
```bash
./push-to-ecr.sh
```

**What it does**:
1. Gets AWS account ID
2. Authenticates Docker with ECR
3. Tags image with ECR repository URL
4. Pushes image to ECR

### Full Deployment Example

```bash
# 1. Navigate to server directory
cd servers/image-processing

# 2. Build Docker image
docker build --platform linux/amd64 -t image-processing-mcp-server -f Dockerfile.lambda .

# 3. Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name image-processing-mcp-server \
  --region us-east-1

# 4. Push to ECR
./push-to-ecr.sh

# 5. Deploy Lambda
./deploy-lambda-ecr.sh

# 6. Get Function URL
aws lambda get-function-url-config \
  --function-name image-processing-mcp-lambda \
  --region us-east-1 \
  --query 'FunctionUrl' \
  --output text

# 7. Test the function
curl -X POST [function-url] \
  -H "Content-Type: application/json" \
  -d '{"body":"{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}"}'
```

---

## 📝 Example Use Cases

### 1. Data Analysis Pipeline

**Scenario**: User uploads CSV, transforms to JSON, analyzes with Jupyter, visualizes results

**Flow**:
1. User: "Analyze this sales data: [pastes CSV]"
2. LLM uses `csv_to_json` tool
3. LLM uses `create_notebook` tool
4. LLM uses `execute_cell` with pandas analysis
5. LLM uses `execute_cell` with matplotlib visualization
6. User sees chart and insights

### 2. Image Batch Processing

**Scenario**: User needs to resize and watermark 10 product images

**Flow**:
1. User: "Resize these product images to 800x600 and apply a blur filter"
2. LLM iterates over images using `resize_image` tool
3. LLM applies `apply_filter` tool with blur
4. User receives S3 download links for all processed images

### 3. Code Execution and Testing

**Scenario**: User wants to test a JavaScript algorithm

**Flow**:
1. User: "Test this sorting algorithm with sample data"
2. LLM uses `execute_javascript` tool with algorithm code
3. LLM analyzes output
4. User sees results and performance metrics

### 4. Interactive Data Science

**Scenario**: User explores machine learning model performance

**Flow**:
1. User: "Train a simple neural network on MNIST data"
2. LLM uses `create_notebook` tool
3. LLM uses `install_package` for TensorFlow
4. LLM uses `upload_file` for dataset
5. LLM uses `execute_cell` for training code
6. LLM uses `execute_cell` for visualization
7. User sees training curves and accuracy metrics

---

## 🔄 Updating Deployed Functions

### Code Changes

1. Modify source code in server directory
2. Rebuild Docker image:
   ```bash
   docker build --platform linux/amd64 -t [server-name] -f Dockerfile.lambda .
   ```
3. Push to ECR:
   ```bash
   ./push-to-ecr.sh
   ```
4. Update Lambda:
   ```bash
   aws lambda update-function-code \
     --function-name [function-name] \
     --image-uri [account-id].dkr.ecr.us-east-1.amazonaws.com/[server-name]:latest
   ```

### Configuration Changes

Update Lambda function configuration:

```bash
# Increase memory
aws lambda update-function-configuration \
  --function-name [function-name] \
  --memory-size 1024

# Increase timeout
aws lambda update-function-configuration \
  --function-name [function-name] \
  --timeout 120

# Add environment variables
aws lambda update-function-configuration \
  --function-name [function-name] \
  --environment "Variables={S3_BUCKET=my-bucket,DEBUG=true}"
```

### Rollback to Previous Version

```bash
# List versions
aws lambda list-versions-by-function --function-name [function-name]

# Rollback using image digest
aws lambda update-function-code \
  --function-name [function-name] \
  --image-uri [account-id].dkr.ecr.us-east-1.amazonaws.com/[server-name]@sha256:[digest]
```

---

## 🛠️ Development Guide

### Adding a New Tool

1. **Define tool schema** in `TOOLS` array:
   ```python
   {
       "name": "my_new_tool",
       "description": "What it does",
       "inputSchema": {
           "type": "object",
           "properties": {
               "param1": {"type": "string"}
           },
           "required": ["param1"]
       }
   }
   ```

2. **Implement handler** in `handle_tools_call()`:
   ```python
   elif tool_name == "my_new_tool":
       result = manager.my_new_method(
           arguments.get("param1")
       )
   ```

3. **Implement method** in manager class:
   ```python
   def my_new_method(self, param1: str) -> Dict[str, Any]:
       try:
           # Your logic here
           return {
               "success": True,
               "output": "Result description",
               "data": result_data
           }
       except Exception as e:
           return {"success": False, "error": str(e)}
   ```

4. **Test locally** before deploying

5. **Deploy** using standard deployment process

### Creating a New MCP Server

1. **Create directory structure**:
   ```
   servers/my-new-server/
   ├── my_mcp_server/
   │   ├── __init__.py
   │   ├── server.py
   │   └── manager.py
   ├── Dockerfile.lambda
   ├── lambda_handler.py
   ├── pyproject.toml
   ├── deploy-lambda-ecr.sh
   └── push-to-ecr.sh
   ```

2. **Implement MCP protocol** in `server.py`:
   - Handle `tools/list` method
   - Handle `tools/call` method
   - Return proper JSON-RPC 2.0 responses

3. **Create Lambda handler** in `lambda_handler.py`:
   ```python
   from my_mcp_server import server

   def lambda_handler(event, context):
       return server.handle_lambda(event)
   ```

4. **Define Dockerfile**:
   ```dockerfile
   FROM public.ecr.aws/lambda/python:3.12
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY my_mcp_server ${LAMBDA_TASK_ROOT}/my_mcp_server
   COPY lambda_handler.py ${LAMBDA_TASK_ROOT}
   CMD ["lambda_handler.lambda_handler"]
   ```

5. **Create deployment scripts** (copy from existing servers)

6. **Test and deploy** following standard process

---

## 📚 Additional Resources

### MCP Protocol

- [Model Context Protocol Specification](https://modelcontextprotocol.io/docs)
- [MCP SDK Documentation](https://github.com/anthropics/mcp)

### AWS Documentation

- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Amazon ECR User Guide](https://docs.aws.amazon.com/ecr/)
- [Lambda Function URLs](https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)

### Python Libraries

- [Pillow (PIL)](https://pillow.readthedocs.io/) - Image processing
- [Pandas](https://pandas.pydata.org/) - Data manipulation
- [Jupyter Client](https://jupyter-client.readthedocs.io/) - Kernel management
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - XML/HTML parsing

---

## 🤝 Contributing

This repository contains example implementations. To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request with detailed description

### Guidelines

- Follow existing code structure and naming conventions
- Add comprehensive documentation for new tools
- Include deployment scripts for new servers
- Test both locally and on AWS Lambda
- Update this README with any new features or changes

---

## 📄 License

MIT License - See individual server directories for specific licensing information.

---

## 🆘 Support

For issues and questions:

1. **Check Troubleshooting Section**: Most common issues covered above
2. **Review CloudWatch Logs**: Detailed error information
3. **Test Locally**: Isolate Lambda-specific vs code issues
4. **AWS Support**: For infrastructure issues

---

## 🎯 Summary

This repository provides production-ready MCP servers for Amplify integration:

✅ **4 Complete Servers**: Data Transformation, Image Processing, Node.js Execution, Jupyter
✅ **AWS Lambda Deployment**: Containerized, scalable, serverless
✅ **S3 Integration**: Large file handling with presigned URLs
✅ **Comprehensive Documentation**: Deployment, usage, troubleshooting
✅ **Security Best Practices**: IAM roles, input validation, sandboxing
✅ **Production Tested**: Handles edge cases, errors, and performance optimization

**Quick Start**: Pick a server, run `./deploy-lambda-ecr.sh`, get the Function URL, add to Amplify DynamoDB config, and start using powerful LLM tools!
