# Read the current kernel_manager.py
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    lines = f.readlines()

# Find the specific return statement in execute_code and replace it
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Look for the specific return block in execute_code (around line 180-184)
    if '            return {' in line and i > 170 and i < 190:
        # Check if this is the success return (not error return)
        if i + 3 < len(lines) and '"success": True' in lines[i+1]:
            # Replace this return block with result assignment + S3 upload
            new_lines.append('            result = {\n')
            new_lines.append('                "success": True,\n')
            new_lines.append('                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",\n')
            new_lines.append('                "images": images if images else None\n')
            new_lines.append('            }\n')
            new_lines.append('\n')
            new_lines.append('            # Upload created files to S3 if enabled\n')
            new_lines.append('            if self.enable_s3 and self.s3_workspace:\n')
            new_lines.append('                try:\n')
            new_lines.append('                    uploaded_files = self.s3_workspace.upload_workspace_files()\n')
            new_lines.append('                    if uploaded_files:\n')
            new_lines.append('                        result["uploaded_files"] = uploaded_files\n')
            new_lines.append('                        print(f"Uploaded {len(uploaded_files)} file(s) to S3")\n')
            new_lines.append('                except Exception as e:\n')
            new_lines.append('                    print(f"Warning: Failed to upload files to S3: {e}")\n')
            new_lines.append('                    result["s3_upload_error"] = str(e)\n')
            new_lines.append('\n')
            new_lines.append('            return result\n')
            # Skip the original return block lines
            i += 4
            continue
    
    new_lines.append(line)
    i += 1

# Write the updated content
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed execute_code method successfully!")
