# Quick Start - Deploy in 5 Minutes

Get all MCP servers deployed to AWS Lambda and integrated with Amplify in under 5 minutes.

## ⚠️ IMPORTANT: These are Example Templates

These servers are **demonstration examples** designed to show you how to build MCP servers for Amplify. They work out-of-the-box for demos and learning, but you should extend them with:
- User authentication and authorization
- Per-user storage isolation
- Custom security layers
- Your own domain-specific features
- Rate limiting and usage tracking
- Any other production requirements

**Feel free to customize extensively!** Use these as starting points to build production-grade servers for your specific needs.

---

## Prerequisites ✅

- [ ] AWS CLI configured (`aws configure`)
- [ ] Docker Desktop running
- [ ] S3 bucket created (recommended): `aws s3 mb s3://amplify-mcp-files`

## 1. One-Command Deployment 🚀

Run this from the repository root:

```bash
# Deploy all servers at once
for server in data-transformation image-processing nodejs-execution jupyter; do
  echo "========================================" && \
  echo "Deploying $server..." && \
  echo "========================================" && \
  cd servers/$server && \
  aws ecr create-repository --repository-name ${server}-mcp-server --region us-east-1 2>/dev/null || true && \
  docker build --platform linux/amd64 -t ${server}-mcp-server -f Dockerfile.lambda . && \
  ./push-to-ecr.sh && \
  ./deploy-lambda-ecr.sh && \
  cd ../.. && \
  echo "" && \
  echo "✅ $server deployed!" && \
  echo ""
done
```

**Time**: 10-15 minutes (first time includes Docker builds)

## 2. Configure S3 (Optional but Recommended) 📦

```bash
# Set S3 bucket for image processing
aws lambda update-function-configuration \
  --function-name image-processing-mcp-lambda \
  --environment "Variables={S3_BUCKET=amplify-mcp-files}" \
  --region us-east-1

# Set S3 bucket for Jupyter (required)
aws lambda update-function-configuration \
  --function-name jupyter-mcp-lambda \
  --environment "Variables={S3_BUCKET=amplify-mcp-files}" \
  --memory-size 1024 \
  --timeout 900 \
  --region us-east-1
```

## 3. Get Function URLs 🔗

```bash
echo "Copy these URLs for Amplify configuration:"
echo ""
for func in data-transformation-mcp-lambda image-processing-mcp-lambda nodejs-execution-mcp-lambda jupyter-mcp-lambda; do
  echo "$func:"
  aws lambda get-function-url-config --function-name $func --region us-east-1 --query 'FunctionUrl' --output text
  echo ""
done
```

**Save these URLs** - you'll need them in the next step!

## 4. Add to Amplify DynamoDB 💾

### Find Your Table and User ID

1. Check your Amplify configuration for:
   - **Table Name**: Usually `amplify-v6-lambda-dev-user-data-storage`
   - **User ID**: Found in Amplify authentication (format: UUID)

### Register Servers

Option A: **AWS Console** (Easiest)
1. Go to **DynamoDB** → **Tables** → Your table
2. Click **Explore items**
3. Create/update item with PK: `YOUR_USER_ID#amplify-mcp#mcp_servers`
4. Add `servers` attribute (Map type)
5. For each server, add:
   ```
   Key: "data-transformation" (or server name)
   Value: {
     "name": "Data Transformation",
     "url": "https://xxxxx.lambda-url.us-east-1.on.aws/",
     "enabled": true
   }
   ```

Option B: **Use Tool Schema Template**

See `DEPLOYMENT_GUIDE.md` for complete tool schemas with all parameters.

## 5. Test in Amplify 🎉

1. **Refresh Amplify**: Log out and log back in
2. **Verify tools loaded**: Check that MCP tools appear
3. **Try natural language commands**:
   - "Convert this CSV to JSON: name,age\nAlice,30\nBob,25"
   - "Execute JavaScript: Math.random() * 100"
   - "Create a notebook called test"
   - (Upload image) "Rotate this image 90 degrees"

## Verification Checklist ✅

- [ ] Docker Desktop is running
- [ ] AWS CLI is configured
- [ ] All 4 Lambda functions deployed
- [ ] All 4 Function URLs obtained
- [ ] DynamoDB item created/updated
- [ ] Amplify refreshed
- [ ] Tools appear in Amplify UI
- [ ] Test command works

## Common Issues 🔧

### "Cannot connect to Docker daemon"
→ Start Docker Desktop and wait for it to initialize

### "Repository already exists"
→ Ignore - this is fine, script continues

### "502 Error" from Lambda
→ Check logs: `aws logs tail /aws/lambda/[function-name] --follow`

### Tools not showing in Amplify
→ Verify DynamoDB item exists with correct PK format

## Next Steps 📚

- Read `DEPLOYMENT_GUIDE.md` for detailed configuration
- Check `README.md` for architecture and examples
- Review individual server READMEs for specific usage

## Update Deployed Servers 🔄

```bash
# Quick update for a single server
cd servers/[server-name]
docker build --platform linux/amd64 -t [server-name]-mcp-server -f Dockerfile.lambda .
./push-to-ecr.sh
# Lambda updates automatically via push script
```

## Cost Estimate 💰

**Free Tier**: First 1 million requests/month free
**After Free Tier**:
- ~$0.20 per 1 million requests
- Storage: Minimal (ECR images ~$0.10/GB/month)
- S3: Standard pricing (~$0.023/GB/month)

**Expected**: Under $5/month for typical usage

---

**That's it!** 🎉 You now have 4 powerful MCP servers enhancing your Amplify LLM with data transformation, image processing, code execution, and Python notebooks.
