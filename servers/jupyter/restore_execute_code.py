# Read the entire file
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    content = f.read()

# Find the execute_code method and fix it completely
# Look for the method start
import_section = content[:content.find('class JupyterKernelManager:')]
class_start = content[content.find('class JupyterKernelManager:'):content.find('    def execute_code(')]
method_start = content[content.find('    def execute_code('):content.find('    def get_variables(')]

# Reconstruct the execute_code method correctly
fixed_execute_code = '''    def execute_code(self, code, timeout=60):
        """Execute Python code and return the result"""
        if not self.km or not self.km.is_alive():
            return {"success": False, "error": "Kernel is not running"}

        try:
            # Execute the code
            msg_id = self.kc.execute(code)

            # Collect outputs
            outputs = []
            images = []
            errors = []

            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    return {"success": False, "error": f"Execution timeout after {timeout} seconds"}

                try:
                    msg = self.kc.get_iopub_msg(timeout=1)
                except queue.Empty:
                    continue

                msg_type = msg["msg_type"]
                content = msg["content"]

                if msg_type == "status" and content.get("execution_state") == "idle":
                    break

                elif msg_type == "stream":
                    outputs.append(content.get("text", ""))

                elif msg_type == "execute_result":
                    data = content.get("data", {})
                    if "text/plain" in data:
                        outputs.append(data["text/plain"])
                    if "text/html" in data:
                        outputs.append(f"[HTML Output]\n{data['text/html'][:500]}...")
                    if "image/png" in data:
                        images.append({
                            "data": data["image/png"],
                            "mimeType": "image/png"
                        })

                elif msg_type == "display_data":
                    data = content.get("data", {})
                    if "text/plain" in data:
                        outputs.append(data["text/plain"])
                    if "text/html" in data:
                        outputs.append(f"[HTML Output]\n{data['text/html'][:500]}...")
                    if "image/png" in data:
                        images.append({
                            "data": data["image/png"],
                            "mimeType": "image/png"
                        })
                    if "image/svg+xml" in data:
                        # Convert SVG to base64
                        svg_data = data["image/svg+xml"]
                        images.append({
                            "data": base64.b64encode(svg_data.encode()).decode(),
                            "mimeType": "image/svg+xml"
                        })

                elif msg_type == "error":
                    errors.append("\n".join(content.get("traceback", [])))

            if errors:
                return {
                    "success": False,
                    "error": "\n".join(errors),
                    "output": "\n".join(outputs) if outputs else None
                }

            result = {
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

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

'''

# Find the rest of the file after execute_code
rest_of_file = content[content.find('    def get_variables('):]

# Reconstruct the entire file
new_content = import_section + class_start + fixed_execute_code + rest_of_file

# Write back
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.write(new_content)

print("Fixed execute_code method!")
