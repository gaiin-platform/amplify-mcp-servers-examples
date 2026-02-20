# Jupyter MCP Server - AWS Deployment Guide

## Quick Start - Local Testing

### 1. Build and Test with Docker

```bash
# Build the Docker image
docker build -t jupyter-mcp-server .

# Run locally
docker run -p 8888:8888 jupyter-mcp-server

# Or use Docker Compose
docker-compose up
```

### 2. Test the Server

```bash
# Health check
curl http://localhost:8888/health

# MCP Initialize
curl -X POST http://localhost:8888/mcp \
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
  }'

# List tools
curl -X POST http://localhost:8888/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'

# Execute code
curl -X POST http://localhost:8888/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {"code": "print(\"Hello from Jupyter MCP!\")"}
    }
  }'
```

## AWS Deployment

### Prerequisites

1. AWS CLI configured: `aws configure`
2. Docker installed
3. Your AWS account ID

### Step 1: Push Image to ECR

```bash
# Set variables
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="your-account-id"
ECR_REPO="jupyter-mcp-server"

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag image
docker tag jupyter-mcp-server:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

# Push image
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

### Step 2: Deploy to ECS Fargate

#### Option A: Using Serverless Framework (Recommended)

Create `serverless.yml`:

```yaml
service: jupyter-mcp-server

provider:
  name: aws
  region: us-east-1

resources:
  Resources:
    # ECS Cluster
    JupyterMCPCluster:
      Type: AWS::ECS::Cluster
      Properties:
        ClusterName: jupyter-mcp-cluster

    # Task Definition
    JupyterMCPTaskDefinition:
      Type: AWS::ECS::TaskDefinition
      Properties:
        Family: jupyter-mcp-server
        NetworkMode: awsvpc
        RequiresCompatibilities:
          - FARGATE
        Cpu: 512
        Memory: 1024
        ExecutionRoleArn: !GetAtt JupyterMCPExecutionRole.Arn
        ContainerDefinitions:
          - Name: jupyter-mcp-server
            Image: ${aws:accountId}.dkr.ecr.us-east-1.amazonaws.com/jupyter-mcp-server:latest
            PortMappings:
              - ContainerPort: 8888
                Protocol: tcp
            LogConfiguration:
              LogDriver: awslogs
              Options:
                awslogs-group: /ecs/jupyter-mcp-server
                awslogs-region: us-east-1
                awslogs-stream-prefix: ecs
            HealthCheck:
              Command:
                - "CMD-SHELL"
                - "curl -f http://localhost:8888/health || exit 1"
              Interval: 30
              Timeout: 10
              Retries: 3
              StartPeriod: 40

    # ECS Service
    JupyterMCPService:
      Type: AWS::ECS::Service
      Properties:
        ServiceName: jupyter-mcp-service
        Cluster: !Ref JupyterMCPCluster
        TaskDefinition: !Ref JupyterMCPTaskDefinition
        DesiredCount: 1
        LaunchType: FARGATE
        NetworkConfiguration:
          AwsvpcConfiguration:
            AssignPublicIp: ENABLED
            Subnets:
              - !Ref PublicSubnet1
              - !Ref PublicSubnet2
            SecurityGroups:
              - !Ref JupyterMCPSecurityGroup
        LoadBalancers:
          - ContainerName: jupyter-mcp-server
            ContainerPort: 8888
            TargetGroupArn: !Ref JupyterMCPTargetGroup

    # VPC and Networking (simplified - use existing VPC in production)
    VPC:
      Type: AWS::EC2::VPC
      Properties:
        CidrBlock: 10.0.0.0/16
        EnableDnsHostnames: true
        EnableDnsSupport: true

    PublicSubnet1:
      Type: AWS::EC2::Subnet
      Properties:
        VpcId: !Ref VPC
        CidrBlock: 10.0.1.0/24
        AvailabilityZone: !Select [0, !GetAZs '']
        MapPublicIpOnLaunch: true

    PublicSubnet2:
      Type: AWS::EC2::Subnet
      Properties:
        VpcId: !Ref VPC
        CidrBlock: 10.0.2.0/24
        AvailabilityZone: !Select [1, !GetAZs '']
        MapPublicIpOnLaunch: true

    InternetGateway:
      Type: AWS::EC2::InternetGateway

    VPCGatewayAttachment:
      Type: AWS::EC2::VPCGatewayAttachment
      Properties:
        VpcId: !Ref VPC
        InternetGatewayId: !Ref InternetGateway

    # Application Load Balancer
    JupyterMCPALB:
      Type: AWS::ElasticLoadBalancingV2::LoadBalancer
      Properties:
        Name: jupyter-mcp-alb
        Type: application
        Scheme: internet-facing
        IpAddressType: ipv4
        Subnets:
          - !Ref PublicSubnet1
          - !Ref PublicSubnet2
        SecurityGroups:
          - !Ref ALBSecurityGroup

    JupyterMCPTargetGroup:
      Type: AWS::ElasticLoadBalancingV2::TargetGroup
      Properties:
        Name: jupyter-mcp-tg
        Port: 8888
        Protocol: HTTP
        TargetType: ip
        VpcId: !Ref VPC
        HealthCheckEnabled: true
        HealthCheckPath: /health
        HealthCheckIntervalSeconds: 30
        HealthCheckTimeoutSeconds: 10
        HealthyThresholdCount: 2
        UnhealthyThresholdCount: 3

    JupyterMCPListener:
      Type: AWS::ElasticLoadBalancingV2::Listener
      Properties:
        LoadBalancerArn: !Ref JupyterMCPALB
        Port: 80
        Protocol: HTTP
        DefaultActions:
          - Type: forward
            TargetGroupArn: !Ref JupyterMCPTargetGroup

    # Security Groups
    ALBSecurityGroup:
      Type: AWS::EC2::SecurityGroup
      Properties:
        GroupDescription: Security group for Jupyter MCP ALB
        VpcId: !Ref VPC
        SecurityGroupIngress:
          - IpProtocol: tcp
            FromPort: 80
            ToPort: 80
            CidrIp: 0.0.0.0/0

    JupyterMCPSecurityGroup:
      Type: AWS::EC2::SecurityGroup
      Properties:
        GroupDescription: Security group for Jupyter MCP ECS tasks
        VpcId: !Ref VPC
        SecurityGroupIngress:
          - IpProtocol: tcp
            FromPort: 8888
            ToPort: 8888
            SourceSecurityGroupId: !Ref ALBSecurityGroup

    # IAM Roles
    JupyterMCPExecutionRole:
      Type: AWS::IAM::Role
      Properties:
        AssumeRolePolicyDocument:
          Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Principal:
                Service: ecs-tasks.amazonaws.com
              Action: 'sts:AssumeRole'
        ManagedPolicyArns:
          - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    # CloudWatch Logs
    JupyterMCPLogGroup:
      Type: AWS::Logs::LogGroup
      Properties:
        LogGroupName: /ecs/jupyter-mcp-server
        RetentionInDays: 7

  Outputs:
    LoadBalancerDNS:
      Description: DNS name of the load balancer
      Value: !GetAtt JupyterMCPALB.DNSName
      Export:
        Name: JupyterMCPServerEndpoint
```

Deploy:
```bash
serverless deploy
```

#### Option B: Using AWS Console

1. **Create ECS Cluster**
   - Go to ECS Console → Create Cluster
   - Choose "Networking only" (Fargate)
   - Name: `jupyter-mcp-cluster`

2. **Create Task Definition**
   - Choose Fargate
   - Task memory: 1GB
   - Task CPU: 0.5 vCPU
   - Container definition:
     - Image: `<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/jupyter-mcp-server:latest`
     - Port mapping: 8888
     - Health check command: `CMD-SHELL,curl -f http://localhost:8888/health || exit 1`

3. **Create Application Load Balancer**
   - Type: Application Load Balancer
   - Scheme: Internet-facing
   - Target group: Port 8888, health check `/health`

4. **Create ECS Service**
   - Launch type: Fargate
   - Number of tasks: 1
   - Load balancer: Attach to ALB

### Step 3: Get the Endpoint URL

```bash
# Get ALB DNS name (if using Serverless Framework)
serverless info --verbose

# Or from AWS Console
aws elbv2 describe-load-balancers \
  --names jupyter-mcp-alb \
  --query 'LoadBalancers[0].DNSName' \
  --output text
```

The URL will be something like: `http://jupyter-mcp-alb-1234567890.us-east-1.elb.amazonaws.com`

### Step 4: Update DynamoDB MCP Server Config

Add the MCP server to your DynamoDB USER_STORAGE_TABLE:

```json
{
  "PK": "user@example.com#amplify-mcp#mcp_servers",
  "SK": "mcp_1708368000000_jupyter",
  "data": {
    "name": "Jupyter MCP Server",
    "url": "http://jupyter-mcp-alb-1234567890.us-east-1.elb.amazonaws.com/mcp",
    "transport": "http",
    "enabled": true,
    "deploymentTier": "managed-container",
    "tools": [],
    "status": "running",
    "createdAt": "2025-02-19T15:00:00Z",
    "updatedAt": "2025-02-19T15:00:00Z"
  }
}
```

Or use the Python API:

```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('YOUR_USER_STORAGE_TABLE')

table.put_item(
    Item={
        'PK': 'user@example.com#amplify-mcp#mcp_servers',
        'SK': 'mcp_1708368000000_jupyter',
        'data': {
            'name': 'Jupyter MCP Server (AWS)',
            'url': 'http://your-alb-dns/mcp',
            'transport': 'http',
            'enabled': True,
            'deploymentTier': 'managed-container',
            'tools': [],
            'status': 'running'
        }
    }
)
```

## Testing with Your Amplify Service

### Test from Lambda

Your Lambda function should now be able to connect:

```javascript
import { MCPClient } from './mcp/mcpClient.js';

const client = new MCPClient({
  id: 'jupyter-test',
  name: 'Jupyter MCP Server',
  url: 'http://your-alb-dns/mcp',
  transport: 'http'
});

await client.connect();
console.log('Tools:', client.tools);

// Execute some Python code
const result = await client.executeTool('execute_code', {
  code: 'import numpy as np\nprint(np.array([1,2,3]).mean())'
});
console.log('Result:', result);
```

## Security Considerations

### 1. Add Authentication (Recommended for Production)

Update your Flask server to require an API key:

```python
# In server.py
import os

API_KEY = os.environ.get('MCP_API_KEY', 'change-me-in-production')

@app.before_request
def check_api_key():
    if request.endpoint not in ['health_check']:
        auth_header = request.headers.get('X-MCP-API-Key')
        if auth_header != API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
```

Add to Dockerfile:
```dockerfile
ENV MCP_API_KEY="your-secure-api-key-here"
```

Update Lambda to send API key:
```javascript
headers: {
  'X-MCP-API-Key': process.env.JUPYTER_MCP_API_KEY
}
```

### 2. Use HTTPS (Production)

- Add HTTPS listener to ALB with ACM certificate
- Update security groups to allow 443

### 3. Restrict Access

Update security group to only allow Lambda security group:

```yaml
SecurityGroupIngress:
  - IpProtocol: tcp
    FromPort: 8888
    ToPort: 8888
    SourceSecurityGroupId: !Ref LambdaSecurityGroup
```

## Monitoring

### CloudWatch Metrics

- ECS Service CPU/Memory utilization
- ALB request count and latency
- Target health checks

### Logs

View logs:
```bash
aws logs tail /ecs/jupyter-mcp-server --follow
```

### Alarms

Create CloudWatch alarms for:
- High CPU usage (>80%)
- High memory usage (>90%)
- Unhealthy target count
- High error rate

## Cost Estimation

**Monthly Cost (single instance):**
- Fargate (0.5 vCPU, 1GB RAM, 24/7): ~$15
- ALB: ~$20
- Data transfer: ~$5
- **Total: ~$40/month**

**Cost optimization:**
- Use Fargate Spot for 70% savings (acceptable for non-critical)
- Scale down to 0 tasks during off-hours if not needed 24/7
- Consider Reserved Capacity for 1-year commitment (30% savings)

## Troubleshooting

### Container won't start
```bash
# Check ECS task logs
aws ecs describe-tasks --cluster jupyter-mcp-cluster --tasks <task-id>

# Check CloudWatch logs
aws logs tail /ecs/jupyter-mcp-server --follow
```

### Health checks failing
```bash
# SSH into ECS task (if enabled)
aws ecs execute-command --cluster jupyter-mcp-cluster --task <task-id> --interactive --command "/bin/bash"

# Test health endpoint
curl localhost:8888/health
```

### Can't connect from Lambda
- Check security group rules
- Verify ALB DNS resolves
- Check Lambda VPC configuration (if Lambda is in VPC)
- Test with curl from another EC2 instance in same VPC

## Next Steps

1. ✅ Deploy Jupyter MCP server to AWS
2. ⬜ Add authentication
3. ⬜ Set up HTTPS with custom domain
4. ⬜ Configure autoscaling (if high usage)
5. ⬜ Add monitoring dashboard
6. ⬜ Document API usage for team
