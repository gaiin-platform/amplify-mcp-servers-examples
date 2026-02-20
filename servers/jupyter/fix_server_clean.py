# Read the file
with open('jupyter_mcp_server/server.py', 'r') as f:
    lines = f.readlines()

# Find and remove the corrupted section (lines 272-320 approx)
# Keep everything up to line 271, then skip to line 321
new_lines = []
skip = False
for i, line in enumerate(lines, 1):
    # Skip lines 272-320 (the corrupted S3 code)
    if i == 272:
        skip = True
        # Insert the CLEAN S3 code here
        new_lines.append('\n')
        new_lines.append('                # Add S3 uploaded files with pre-signed URLs\n')
        new_lines.append('                if result.get("uploaded_files"):\n')
        new_lines.append('                    files_info = []\n')
        new_lines.append('                    for file_info in result["uploaded_files"]:\n')
        new_lines.append('                        if "error" in file_info:\n')
        new_lines.append('                            files_info.append(f"\\n❌ {file_info[\\'filename\\']}: {file_info[\\'error\\']}")\n')
        new_lines.append('                        else:\n')
        new_lines.append('                            files_info.append(f"\\n📁 {file_info[\\'filename\\']}")\n')
        new_lines.append('                            files_info.append(f"   🔗 Download (24h): {file_info[\\'presigned_url\\']}")\n')
        new_lines.append('                    if files_info:\n')
        new_lines.append('                        content.append({"type": "text", "text": "\\n".join(files_info)})\n')
        new_lines.append('\n')
        new_lines.append('                # Add S3 upload for single files (like notebooks)\n')
        new_lines.append('                if result.get("s3_upload"):\n')
        new_lines.append('                    s3_info = result["s3_upload"]\n')
        new_lines.append('                    s3_text = f"\\n📓 Notebook uploaded to S3\\n   🔗 Download (24h): {s3_info[\\'presigned_url\\']}"\n')
        new_lines.append('                    content.append({"type": "text", "text": s3_text})\n')
        new_lines.append('\n')
        continue
    if skip and i == 321:
        skip = False
    if skip:
        continue
    new_lines.append(line)

# Write back
with open('jupyter_mcp_server/server.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed server.py")
