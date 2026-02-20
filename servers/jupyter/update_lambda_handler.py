# Read lambda_handler.py
with open('lambda_handler.py', 'r') as f:
    content = f.read()

# Find and replace the kernel manager initialization
old_init = '''    server_module.kernel_manager = JupyterKernelManager(
        working_dir=os.environ.get('JUPYTER_WORKING_DIR', '/tmp/notebooks')
    )'''

new_init = '''    # S3 bucket for persistent file storage
    S3_BUCKET = 'jupyter-mcp-workspaces-654654422653'
    
    server_module.kernel_manager = JupyterKernelManager(
        working_dir=os.environ.get('JUPYTER_WORKING_DIR', '/tmp/notebooks'),
        s3_bucket=S3_BUCKET,
        enable_s3=True
    )'''

content = content.replace(old_init, new_init)

# Write back
with open('lambda_handler.py', 'w') as f:
    f.write(content)

print('Updated lambda_handler.py with S3 configuration')
