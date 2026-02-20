# Read the file
with open('jupyter_mcp_server/server.py', 'r') as f:
    lines = f.readlines()

# Find line numbers to keep/delete
new_lines = []
i = 0
while i < len(lines):
    line_num = i + 1
    
    # Keep everything up to line 271
    if line_num <= 271:
        new_lines.append(lines[i])
        i += 1
        continue
    
    # DELETE lines 272-320 (all corrupted code)
    if 272 <= line_num <= 320:
        # On line 272, INSERT the clean code
        if line_num == 272:
            new_lines.append('\n')
            new_lines.append('                # Add S3 uploaded files with pre-signed URLs\n')
            new_lines.append('                if result.get("uploaded_files"):\n')
            new_lines.append('                    files_info = []\n')
            new_lines.append('                    for file_info in result["uploaded_files"]:\n')
            new_lines.append('                        if "error" in file_info:\n')
            new_lines.append('                            files_info.append(f"\\n{file_info[\'filename\']}: Error - {file_info[\'error\']}")\n')
            new_lines.append('                        else:\n')
            new_lines.append('                            files_info.append(f"\\n{file_info[\'filename\']}")\n')
            new_lines.append('                            files_info.append(f"Download (24h): {file_info[\'presigned_url\']}")\n')
            new_lines.append('                    if files_info:\n')
            new_lines.append('                        content.append({"type": "text", "text": "\\n".join(files_info)})\n')
            new_lines.append('\n')
            new_lines.append('                # Add S3 upload for single files (like notebooks)\n')
            new_lines.append('                if result.get("s3_upload"):\n')
            new_lines.append('                    s3_info = result["s3_upload"]\n')
            new_lines.append('                    s3_text = f"\\nNotebook uploaded to S3\\nDownload (24h): {s3_info[\'presigned_url\']}"\n')
            new_lines.append('                    content.append({"type": "text", "text": s3_text})\n')
            new_lines.append('\n')
        # Skip all lines 272-320
        i += 1
        continue
    
    # Keep everything after line 320
    new_lines.append(lines[i])
    i += 1

# Write back
with open('jupyter_mcp_server/server.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed server.py - deleted corrupted lines 272-320 and inserted clean code")
