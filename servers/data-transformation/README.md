# Data Transformation MCP Server

A Model Context Protocol (MCP) server that provides data format transformation capabilities. Supports CSV, JSON, XML, YAML conversions and common data operations.

## Features

- **Format Conversions**: CSV ↔ JSON ↔ XML ↔ YAML
- **Data Cleaning**: Remove duplicates, handle nulls, strip whitespace
- **Data Operations**: Merge datasets, filter rows, get statistics
- **Inline Previews**: See results directly in chat (first 100 rows)
- **S3 Persistence**: Download full files via pre-signed URLs (24h expiry)
- **Session Isolation**: Random temp directories for multi-user safety

## Tools

### 1. `csv_to_json`
Convert CSV data to JSON format.

**Example:**
```
User: Convert this CSV to JSON
[CSV data]

Response:
✅ Converted 1000 rows to JSON
📊 Preview: [First 100 objects shown inline]
💾 Download full file: [S3 URL]
```

### 2. `json_to_csv`
Convert JSON data to CSV format.

### 3. `json_to_yaml`
Convert JSON to YAML format.

### 4. `yaml_to_json`
Convert YAML to JSON format.

### 5. `xml_to_json`
Convert XML to JSON format.

### 6. `clean_data`
Clean CSV data with operations:
- `remove_duplicates`: Remove duplicate rows
- `remove_nulls`: Remove rows with null values
- `fill_nulls_zero`: Fill null values with 0
- `strip_whitespace`: Strip whitespace from strings
- `lowercase_columns`: Convert column names to lowercase

**Example:**
```
User: Clean this CSV - remove duplicates and nulls
[CSV data]

Response:
✅ Cleaned data: 5000 → 4500 rows
Removed 300 duplicate rows
Removed 200 rows with null values
```

### 7. `merge_data`
Merge two CSV datasets on a common column.

**Merge types:**
- `inner`: Only matching rows
- `left`: All rows from first dataset
- `right`: All rows from second dataset
- `outer`: All rows from both datasets

### 8. `filter_data`
Filter CSV data based on a condition.

**Operators:**
- `equals`: Column == value
- `not_equals`: Column != value
- `greater_than`: Column > value
- `less_than`: Column < value
- `contains`: Column contains substring

### 9. `get_stats`
Get statistical summary of CSV data (row count, column types, basic statistics).

## Deployment to AWS Lambda

### Prerequisites
- AWS CLI configured
- Docker installed
- AWS account ID: 654654422653

### Deploy

```bash
# 1. Build Docker image
sudo docker build -f Dockerfile.lambda -t data-mcp-lambda:latest .

# 2. Push to ECR
chmod +x push-to-ecr.sh
./push-to-ecr.sh

# 3. Deploy to Lambda
chmod +x deploy-lambda-ecr.sh
./deploy-lambda-ecr.sh
```

### Lambda Configuration
- **Function Name**: `data-transformation-mcp-server-dev`
- **Memory**: 2048 MB
- **Timeout**: 300 seconds (5 minutes)
- **S3 Bucket**: `jupyter-mcp-workspaces-654654422653`

## Architecture

```
User → Chat UI → Backend → API Gateway → Lambda (Container)
                                           ↓
                                    Data Manager
                                    (pandas, xmltodict, pyyaml)
                                           ↓
                                  /tmp/session_{uuid}/
                                           ↓
                                   S3 (presigned URLs)
```

## Response Format

All tools return:
1. **Success message**: Summary of operation
2. **Inline preview**: First 100 rows/objects (code block in chat)
3. **Statistics**: Row counts, column info, etc.
4. **Download link**: Pre-signed S3 URL (24h expiry) for full file

## Development

### Local Testing

```bash
# Install dependencies
pip install -e .

# Run server locally
python -m data_mcp_server.server --port 8889

# Test
curl http://localhost:8889/health
```

### Test MCP Request

```bash
curl -X POST http://localhost:8889/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "tools/list"
  }'
```

## License

MIT License
