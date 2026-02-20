# Node.js Execution MCP Server

A Model Context Protocol (MCP) server for executing Node.js and TypeScript code with npm package support.

## 🔒 Security Notice

**CRITICAL SECURITY FIX APPLIED**: This server now sanitizes the execution environment to prevent user code from accessing AWS Lambda execution role credentials. User-executed JavaScript/TypeScript code cannot access `process.env.AWS_ACCESS_KEY_ID`, `process.env.AWS_SECRET_ACCESS_KEY`, or other sensitive AWS credentials.

**What was fixed**: Previously, user code had access to the full Lambda environment including AWS credentials through `process.env`. The execution environment is now sanitized before running user code, removing all AWS credentials and sensitive Lambda metadata while preserving essential variables (PATH, HOME, LANG, NODE_PATH) needed for Node.js execution.

## Features

- **Execute JavaScript**: Run Node.js code with full ES6+ support
- **Execute TypeScript**: Run TypeScript code with automatic compilation
- **NPM Packages**: Install and use any npm package
- **Session Isolation**: Each execution gets its own isolated environment
- **Output Capture**: Captures stdout, stderr, and return values
- **S3 Storage**: Automatic upload of generated files with pre-signed URLs

## Tools

1. `execute_javascript` - Execute JavaScript/Node.js code
2. `execute_typescript` - Execute TypeScript code
3. `install_package` - Install npm packages for use in code

## Deployment

```bash
# Build Docker image
sudo docker build -f Dockerfile.lambda -t nodejs-mcp-lambda:latest .

# Push to ECR
./push-to-ecr.sh

# Deploy to Lambda
./deploy-lambda-direct.sh
```

## Usage Examples

### Execute JavaScript
```javascript
const data = [1, 2, 3, 4, 5];
const sum = data.reduce((a, b) => a + b, 0);
console.log(`Sum: ${sum}`);
```

### Execute TypeScript
```typescript
interface User {
  name: string;
  age: number;
}

const users: User[] = [
  { name: "Alice", age: 30 },
  { name: "Bob", age: 25 }
];

console.log(users);
```

### Install and Use Packages
```javascript
// First install: lodash
// Then execute:
const _ = require('lodash');
const numbers = [1, 2, 3, 4, 5];
console.log(_.chunk(numbers, 2));
```
