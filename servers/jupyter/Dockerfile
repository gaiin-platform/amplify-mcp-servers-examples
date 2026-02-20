# Dockerfile for Jupyter MCP Server
# Deploys to AWS ECS Fargate for always-on availability

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml /app/
COPY jupyter_mcp_server /app/jupyter_mcp_server/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Install commonly used data science packages (pre-installed for faster execution)
# Users can still install additional packages dynamically via the install_package tool
RUN pip install --no-cache-dir \
    numpy>=1.24.0 \
    pandas>=2.0.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    scikit-learn>=1.3.0 \
    scipy>=1.11.0 \
    pillow>=10.0.0

# Create working directory for notebooks
RUN mkdir -p /app/notebooks
WORKDIR /app/notebooks

# Expose port
EXPOSE 8888

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Run the server
# Note: Binding to 0.0.0.0 is required for Docker networking
CMD ["jupyter-mcp-server", "--host", "0.0.0.0", "--port", "8888", "--working-dir", "/app/notebooks"]
