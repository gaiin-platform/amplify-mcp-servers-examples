# Read the file
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    content = f.read()

# Fix broken f-strings - replace literal newlines with \n
# Fix line 138-139
content = content.replace(
    '                        outputs.append(f"[HTML Output]\n{data[\'text/html\'][:500]}...")',
    '                        outputs.append(f"[HTML Output]\n{data[\'text/html\'][:500]}...")'
)

# Fix line 151-152
content = content.replace(
    '                        outputs.append(f"[HTML Output]\n{data[\'text/html\'][:500]}...")',
    '                        outputs.append(f"[HTML Output]\n{data[\'text/html\'][:500]}...")'
)

# Fix line 167-168
content = content.replace(
    '                    errors.append("\n".join(content.get("traceback", [])))',
    '                    errors.append("\n".join(content.get("traceback", [])))'
)

# Fix line 173-174
content = content.replace(
    '                    "error": "\n".join(errors),',
    '                    "error": "\n".join(errors),'
)

# Fix line 175-176
content = content.replace(
    '                    "output": "\n".join(outputs) if outputs else None',
    '                    "output": "\n".join(outputs) if outputs else None'
)

# Fix line 181-182
content = content.replace(
    '                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",',
    '                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",'
)

# Write back
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.write(content)

print("Fixed f-strings!")
