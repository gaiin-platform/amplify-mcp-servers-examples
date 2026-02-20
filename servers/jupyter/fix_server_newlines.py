import re

# Read the file
with open('jupyter_mcp_server/server.py', 'r') as f:
    lines = f.readlines()

# Find and fix the broken string literals (lines ~262-290)
fixed_lines = []
skip_next = False

for i, line in enumerate(lines):
    if skip_next:
        skip_next = False
        continue
    
    # Fix lines with broken strings - look for pattern: files_text = "
    if 'files_text = "' in line and line.strip().endswith('"'):
        # This is a broken multi-line string, fix it
        fixed_lines.append('                    files_text = "\n\nUploaded Files:\n"\n')
        skip_next = True  # Skip the next few lines that are part of this broken string
        continue
    
    # Fix lines with files_text += that have broken newlines  
    if 'files_text +=' in line and ('filename' in line or 'S3 URI' in line or 'Download' in line or 'Expires' in line):
        # Extract the content and fix the newline
        content = line.strip()
        if content.endswith('"'):
            # This line ends with quote but has literal newline
            # Skip it and the next line
            skip_next = True
            continue
    
    # Fix s3_text lines similarly
    if 's3_text = "' in line and line.strip().endswith('"'):
        fixed_lines.append('                    s3_text = "\n\nS3 Upload:\n"\n')
        skip_next = True
        continue
        
    if 's3_text +=' in line and ('S3 URI' in line or 'Download' in line or 'Expires' in line):
        content = line.strip()
        if content.endswith('"'):
            skip_next = True
            continue
    
    # Keep all other lines
    fixed_lines.append(line)

# Write back
with open('jupyter_mcp_server/server.py', 'w') as f:
    f.writelines(fixed_lines)

print('Fixed newlines in server.py')
