import re

# Read the current kernel_manager.py
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    content = f.read()

# Fix execute_code method - find and replace the return statement
old_pattern = r'            return \{\s*"success": True,\s*"output": "\n"\.join\(outputs\) if outputs else "Code executed successfully \(no output\)",\s*"images": images if images else None\s*\}'

new_code = '''            result = {
                "success": True,
                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",
                "images": images if images else None
            }

            # Upload created files to S3 if enabled
            if self.enable_s3 and self.s3_workspace:
                try:
                    uploaded_files = self.s3_workspace.upload_workspace_files()
                    if uploaded_files:
                        result["uploaded_files"] = uploaded_files
                        print(f"Uploaded {len(uploaded_files)} file(s) to S3")
                except Exception as e:
                    print(f"Warning: Failed to upload files to S3: {e}")
                    result["s3_upload_error"] = str(e)

            return result'''

content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)

# Write the updated content
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.write(content)

print("Fixed execute_code method successfully!")
