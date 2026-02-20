# Read server.py
with open('jupyter_mcp_server/server.py', 'r') as f:
    content = f.read()

# Find and replace the response formatting section
old_response = '''                # Add text output if present
                if result.get("output"):
                    content.append({"type": "text", "text": result["output"]})
                elif result.get("result"):
                    content.append({"type": "text", "text": str(result["result"])})
                elif result.get("message"):
                    content.append({"type": "text", "text": result["message"]})
                else:
                    content.append({"type": "text", "text": json.dumps(result, indent=2)})

                # Add image outputs if present
                if result.get("images"):
                    for img in result["images"]:
                        content.append({
                            "type": "image",
                            "data": img["data"],
                            "mimeType": img.get("mimeType", "image/png")
                        })

                return {"content": content, "isError": False}'''

new_response = '''                # Add text output if present
                if result.get("output"):
                    content.append({"type": "text", "text": result["output"]})
                elif result.get("result"):
                    content.append({"type": "text", "text": str(result["result"])})
                elif result.get("message"):
                    content.append({"type": "text", "text": result["message"]})
                else:
                    content.append({"type": "text", "text": json.dumps(result, indent=2)})

                # Add S3 uploaded files with pre-signed URLs
                if result.get("uploaded_files"):
                    files_text = "\n\nUploaded Files:\n"
                    for file_info in result["uploaded_files"]:
                        if "error" in file_info:
                            files_text += f"  - {file_info["filename"]}: Error - {file_info["error"]}\n"
                        else:
                            files_text += f"  - {file_info["filename"]}\n"
                            files_text += f"    S3 URI: {file_info["s3_uri"]}\n"
                            files_text += f"    Download: {file_info["presigned_url"]}\n"
                            files_text += f"    Expires: {file_info["expires_in_hours"]} hours\n"
                    content.append({"type": "text", "text": files_text})
                
                # Add S3 upload for single files (like notebooks)
                if result.get("s3_upload"):
                    s3_info = result["s3_upload"]
                    s3_text = "\n\nS3 Upload:\n"
                    s3_text += f"  S3 URI: {s3_info["s3_uri"]}\n"
                    s3_text += f"  Download: {s3_info["presigned_url"]}\n"
                    s3_text += f"  Expires: {s3_info["expires_in_hours"]} hours\n"
                    content.append({"type": "text", "text": s3_text})

                # Add image outputs if present
                if result.get("images"):
                    for img in result["images"]:
                        content.append({
                            "type": "image",
                            "data": img["data"],
                            "mimeType": img.get("mimeType", "image/png")
                        })

                return {"content": content, "isError": False}'''

content = content.replace(old_response, new_response)

# Write back
with open('jupyter_mcp_server/server.py', 'w') as f:
    f.write(content)

print('Updated server.py to include S3 URLs in response')
