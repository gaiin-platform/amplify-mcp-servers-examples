# Image Processing MCP Server

A Model Context Protocol (MCP) server for image processing and transformations.

## Features

- **Resize**: Scale images to specific dimensions
- **Crop**: Extract regions from images
- **Rotate**: Rotate images by degrees
- **Filters**: Apply grayscale, blur, sharpen, etc.
- **Format Conversion**: Convert between PNG, JPEG, WebP, etc.
- **Thumbnails**: Generate thumbnail versions
- **Inline Display**: Base64 encoding for small images
- **S3 Storage**: Automatic upload with pre-signed URLs

## Tools

1. `resize_image` - Resize image to specified dimensions
2. `crop_image` - Crop image to region
3. `rotate_image` - Rotate image by degrees
4. `apply_filter` - Apply filters (grayscale, blur, sharpen, etc.)
5. `convert_format` - Convert image format
6. `create_thumbnail` - Generate thumbnail

## Deployment

```bash
# Build Docker image
sudo docker build -f Dockerfile.lambda -t image-mcp-lambda:latest .

# Push to ECR
./push-to-ecr.sh

# Deploy to Lambda
./deploy-lambda-direct.sh
```

## Usage

Images can be provided as:
- Base64 encoded string
- URL to existing image
- Previously uploaded S3 file

Results include:
- Base64 inline preview (for images < 4MB)
- S3 download URL (24-hour expiry)
- Image metadata (dimensions, format, size)
