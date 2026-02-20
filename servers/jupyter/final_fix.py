# Read the file
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    lines = f.readlines()

# Find and fix the execute_code method's return block (around lines 180-200)
fixed_lines = []
skip_until = None

for i, line in enumerate(lines):
    line_num = i + 1
    
    # Skip malformed lines in the 180-200 range
    if skip_until and line_num <= skip_until:
        continue
    
    # Fix the specific problematic section (lines 180-196)
    if line_num == 180 and 'result = {' in line:
        # Replace the entire malformed block with correct code
        fixed_lines.append('            result = {\n')
        fixed_lines.append('                "success": True,\n')
        fixed_lines.append('                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",\n')
        fixed_lines.append('                "images": images if images else None\n')
        fixed_lines.append('            }\n')
        fixed_lines.append('\n')
        fixed_lines.append('            # Upload created files to S3 if enabled\n')
        fixed_lines.append('            if self.enable_s3 and self.s3_workspace:\n')
        fixed_lines.append('                try:\n')
        fixed_lines.append('                    uploaded_files = self.s3_workspace.upload_workspace_files()\n')
        fixed_lines.append('                    if uploaded_files:\n')
        fixed_lines.append('                        result["uploaded_files"] = uploaded_files\n')
        fixed_lines.append('                        print(f"Uploaded {len(uploaded_files)} file(s) to S3")\n')
        fixed_lines.append('                except Exception as e:\n')
        fixed_lines.append('                    print(f"Warning: Failed to upload files to S3: {e}")\n')
        fixed_lines.append('                    result["s3_upload_error"] = str(e)\n')
        fixed_lines.append('\n')
        fixed_lines.append('            return result\n')
        # Skip lines until we reach the exception handler
        skip_until = 197
        continue
    
    fixed_lines.append(line)

# Write back
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.writelines(fixed_lines)

print("Fixed execute_code method!")
