# Read the file
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    content = f.read()

# Fix syntax errors
# 1. Remove duplicate "success": True
content = content.replace(
    '            result = {\n                "success": True,\n                "success": True,',
    '            result = {\n                "success": True,'
)

# 2. Fix the 'n' character at start of comment line
content = content.replace(
    '            }\nn            # Upload created files to S3 if enabled',
    '            }\n\n            # Upload created files to S3 if enabled'
)

# 3. Remove extra closing brace
content = content.replace(
    '            return result\n            }',
    '            return result'
)

# Write back
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.write(content)

print("Fixed syntax errors!")
