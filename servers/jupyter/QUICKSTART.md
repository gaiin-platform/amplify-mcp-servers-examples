# Jupyter MCP Server - Quick Start Guide

## 🚀 Deploy to AWS in 5 Steps

### Step 1: Test Locally with Docker

```bash
# Make test script executable
chmod +x test-deployment.sh

# Run the test
./test-deployment.sh
```

This will:
- Build Docker image
- Start container
- Run comprehensive tests
- Verify all tools work

**Expected output:** All green checkmarks ✓

---

### Step 2: Push to Amazon ECR

```bash
# Set your AWS account ID
export AWS_ACCOUNT_ID="your-account-id-here"
export AWS_REGION="us-east-1"

# Create ECR repository (first time only)
aws ecr create-repository \
  --repository-name jupyter-mcp-server \
  --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag image
docker tag jupyter-mcp-server:test \
  $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/jupyter-mcp-server:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/jupyter-mcp-server:latest
```

---

### Step 3: Create ECS Cluster

**Option A: AWS Console**
1. Go to ECS Console
2. Click "Create Cluster"
3. Choose "Networking only (Fargate)"
4. Name: `jupyter-mcp-cluster`
5. Create

**Option B: AWS CLI**
```bash
aws ecs create-cluster --cluster-name jupyter-mcp-cluster
```

---

### Step 4: Deploy with CloudFormation

Create `cloudformation-stack.yml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Jupyter MCP Server on ECS Fargate

Parameters:
  ImageUri:
    Type: String
    Description: ECR image URI
    Default: YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jupyter-mcp-server:latest

Resources:
  # VPC
  VPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsHostnames: true
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: jupyter-mcp-vpc

  # Internet Gateway
  InternetGateway:
    Type: AWS::EC2::InternetGateway

  AttachGateway:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      VpcId: !Ref VPC
      InternetGatewayId: !Ref InternetGateway

  # Public Subnets
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

  # Route Table
  PublicRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref VPC

  PublicRoute:
    Type: AWS::EC2::Route
    DependsOn: AttachGateway
    Properties:
      RouteTableId: !Ref PublicRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway

  SubnetRouteTableAssociation1:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet1
      RouteTableId: !Ref PublicRouteTable

  SubnetRouteTableAssociation2:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet2
      RouteTableId: !Ref PublicRouteTable

  # Security Groups
  ALBSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow HTTP access to ALB
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0

  ECSSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow access from ALB
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 8888
          ToPort: 8888
          SourceSecurityGroupId: !Ref ALBSecurityGroup

  # Application Load Balancer
  LoadBalancer:
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

  TargetGroup:
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
      Matcher:
        HttpCode: 200

  Listener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties:
      LoadBalancerArn: !Ref LoadBalancer
      Port: 80
      Protocol: HTTP
      DefaultActions:
        - Type: forward
          TargetGroupArn: !Ref TargetGroup

  # ECS Task Execution Role
  TaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

  # CloudWatch Logs
  LogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: /ecs/jupyter-mcp-server
      RetentionInDays: 7

  # ECS Task Definition
  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: jupyter-mcp-server
      NetworkMode: awsvpc
      RequiresCompatibilities:
        - FARGATE
      Cpu: 512
      Memory: 1024
      ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
      ContainerDefinitions:
        - Name: jupyter-mcp-server
          Image: !Ref ImageUri
          PortMappings:
            - ContainerPort: 8888
              Protocol: tcp
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref LogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: ecs
          HealthCheck:
            Command:
              - CMD-SHELL
              - curl -f http://localhost:8888/health || exit 1
            Interval: 30
            Timeout: 10
            Retries: 3
            StartPeriod: 40

  # ECS Service
  Service:
    Type: AWS::ECS::Service
    DependsOn: Listener
    Properties:
      ServiceName: jupyter-mcp-service
      Cluster: jupyter-mcp-cluster
      TaskDefinition: !Ref TaskDefinition
      DesiredCount: 1
      LaunchType: FARGATE
      NetworkConfiguration:
        AwsvpcConfiguration:
          AssignPublicIp: ENABLED
          Subnets:
            - !Ref PublicSubnet1
            - !Ref PublicSubnet2
          SecurityGroups:
            - !Ref ECSSecurityGroup
      LoadBalancers:
        - ContainerName: jupyter-mcp-server
          ContainerPort: 8888
          TargetGroupArn: !Ref TargetGroup

Outputs:
  LoadBalancerURL:
    Description: URL of the load balancer
    Value: !Sub http://${LoadBalancer.DNSName}
    Export:
      Name: JupyterMCPServerURL

  MCPEndpoint:
    Description: MCP protocol endpoint
    Value: !Sub http://${LoadBalancer.DNSName}/mcp
    Export:
      Name: JupyterMCPEndpoint
```

Deploy:
```bash
# Update ImageUri parameter with your ECR image URI
aws cloudformation create-stack \
  --stack-name jupyter-mcp-server \
  --template-body file://cloudformation-stack.yml \
  --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=ImageUri,ParameterValue=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/jupyter-mcp-server:latest

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name jupyter-mcp-server

# Get the endpoint URL
aws cloudformation describe-stacks \
  --stack-name jupyter-mcp-server \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPEndpoint`].OutputValue' \
  --output text
```

---

### Step 5: Add to Your Amplify Service

**Update DynamoDB:**

```javascript
// Add to your USER_STORAGE_TABLE
const AWS = require('aws-sdk');
const dynamodb = new AWS.DynamoDB.DocumentClient();

const mcpServerConfig = {
  PK: 'your-user-id#amplify-mcp#mcp_servers',
  SK: `mcp_${Date.now()}_jupyter`,
  data: {
    name: 'Jupyter Code Execution',
    url: 'http://YOUR-ALB-DNS/mcp', // From Step 4 output
    transport: 'http',
    enabled: true,
    deploymentTier: 'managed-container',
    tools: [],
    status: 'running',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  }
};

await dynamodb.put({
  TableName: process.env.USER_STORAGE_TABLE,
  Item: mcpServerConfig
}).promise();
```

**Or use the Python API:**

```bash
curl -X POST https://your-api-gateway/dev/integrations/mcp/servers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jupyter Code Execution",
    "url": "http://YOUR-ALB-DNS/mcp",
    "transport": "http"
  }'
```

---

## ✅ Verification

Test from Lambda:

```javascript
import { getMCPToolDefinitions, executeMCPTool } from './mcp/mcpRegistry.js';

// Get tools
const tools = await getMCPToolDefinitions('your-user-id');
console.log('Available tools:', tools.length);

// Execute code
const result = await executeMCPTool(
  'your-user-id',
  'mcp_YOUR_SERVER_ID_execute_code',
  { code: 'print("Hello from AWS!")' }
);
console.log('Result:', result);
```

---

## 📊 Cost Estimate

**Monthly Cost:**
- Fargate (0.5 vCPU, 1GB RAM, 24/7): **~$15**
- Application Load Balancer: **~$20**
- Data transfer: **~$5**
- **Total: ~$40/month**

---

## 🔧 Common Commands

### View Logs
```bash
aws logs tail /ecs/jupyter-mcp-server --follow
```

### Restart Service
```bash
aws ecs update-service \
  --cluster jupyter-mcp-cluster \
  --service jupyter-mcp-service \
  --force-new-deployment
```

### Scale Up/Down
```bash
# Scale to 2 tasks
aws ecs update-service \
  --cluster jupyter-mcp-cluster \
  --service jupyter-mcp-service \
  --desired-count 2
```

### Delete Everything
```bash
aws cloudformation delete-stack --stack-name jupyter-mcp-server
```

---

## 🛟 Troubleshooting

### Container won't start
```bash
# Check task status
aws ecs describe-services \
  --cluster jupyter-mcp-cluster \
  --services jupyter-mcp-service

# View container logs
aws logs tail /ecs/jupyter-mcp-server --follow
```

### Health checks failing
- Verify container listens on port 8888
- Check `/health` endpoint responds with 200
- Ensure security groups allow traffic

### Can't connect from Lambda
- Verify ALB DNS name resolves
- Check security group allows Lambda → ALB
- Test with curl from EC2 in same VPC

---

## 📚 Next Steps

- [ ] Add API key authentication (see DEPLOYMENT.md)
- [ ] Set up HTTPS with ACM certificate
- [ ] Configure auto-scaling
- [ ] Add CloudWatch alarms
- [ ] Create custom domain name
- [ ] Document for team usage

---

## 🎯 That's it!

Your Jupyter MCP server is now:
✅ Running in AWS ECS Fargate
✅ Accessible via Application Load Balancer
✅ Integrated with your Amplify chat service
✅ Ready to execute Python code for your users

Need help? Check `DEPLOYMENT.md` for detailed documentation.
