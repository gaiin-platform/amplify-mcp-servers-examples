#!/bin/bash

FUNCTION_NAME="nodejs-execution-mcp-server-dev"
AWS_REGION="us-east-1"

echo "========================================"
echo "Testing Node.js MCP Security Fix"
echo "========================================"

# Create test payload with simpler code
cat > /tmp/nodejs-security-test.json << 'PAYLOAD'
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "execute_javascript",
    "arguments": {
      "code": "console.log('Testing AWS credentials access...');\nconsole.log('AWS_ACCESS_KEY_ID:', process.env.AWS_ACCESS_KEY_ID || 'NOT_FOUND');\nconsole.log('AWS_SECRET_ACCESS_KEY:', process.env.AWS_SECRET_ACCESS_KEY || 'NOT_FOUND');\nconsole.log('AWS_SESSION_TOKEN:', process.env.AWS_SESSION_TOKEN ? 'PRESENT' : 'NOT_FOUND');\nif (!process.env.AWS_ACCESS_KEY_ID) { console.log('SECURITY FIX VERIFIED'); } else { console.log('SECURITY ISSUE DETECTED'); }"
    }
  }
}
PAYLOAD

echo ""
echo "Invoking Lambda function..."
aws lambda invoke \
  --function-name ${FUNCTION_NAME} \
  --region ${AWS_REGION} \
  --cli-binary-format raw-in-base64-out \
  --payload file:///tmp/nodejs-security-test.json \
  /tmp/nodejs-security-response.json

echo ""
echo "========================================"
echo "Test Results:"
echo "========================================"

# Extract and display the result
python3 << 'PYEOF'
import json

with open('/tmp/nodejs-security-response.json', 'r') as f:
    data = json.load(f)

body = json.loads(data['body'])
result = body.get('result', {})
content = result.get('content', [])
is_error = result.get('isError', False)

print()
if is_error:
    print("❌ ERROR occurred during execution:")
    for item in content:
        if item.get('type') == 'text':
            print(item.get('text', ''))
else:
    print("✅ Execution successful!")
    for item in content:
        if item.get('type') == 'text':
            text = item.get('text', '')
            # Print stdout section
            if '>> stdout:' in text:
                stdout_lines = text.split('>> stdout:')[1].split('```')[1].strip()
                print("\nOutput:")
                print(stdout_lines)
                
                # Check for security verification
                if 'NOT_FOUND' in stdout_lines and 'SECURITY FIX VERIFIED' in stdout_lines:
                    print("\n" + "="*50)
                    print("🎉 SECURITY FIX CONFIRMED!")
                    print("="*50)
                    print("AWS credentials are NOT accessible in Node.js code")
                elif 'ASIAZQ' in stdout_lines or 'AWS_ACCESS_KEY_ID: A' in stdout_lines:
                    print("\n" + "="*50)
                    print("⚠️  SECURITY ISSUE STILL PRESENT!")
                    print("="*50)
                    print("AWS credentials ARE accessible in Node.js code")
PYEOF

echo ""
echo "Full response saved to: /tmp/nodejs-security-response.json"
