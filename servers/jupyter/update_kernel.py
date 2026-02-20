import re

# Read the current kernel_manager.py
with open('jupyter_mcp_server/kernel_manager.py', 'r') as f:
    content = f.read()

# 1. Add import for S3WorkspaceManager
content = content.replace(
    'from jupyter_client import KernelManager',
    'from jupyter_client import KernelManager\nfrom .s3_workspace import S3WorkspaceManager'
)

# 2. Update __init__ method signature and implementation
old_init = '''    def __init__(self, working_dir="."):
        self.working_dir = os.path.abspath(working_dir)
        # Ensure working directory exists (important for Lambda's ephemeral /tmp)
        os.makedirs(self.working_dir, exist_ok=True)
        self.km = None
        self.kc = None
        self._initialize_kernel()'''

new_init = '''    def __init__(self, working_dir=".", s3_bucket=None, enable_s3=False):
        """Initialize Jupyter Kernel Manager

        Args:
            working_dir: Base working directory (default: current directory)
            s3_bucket: S3 bucket name for file persistence (optional)
            enable_s3: Enable S3 workspace features (default: False)
        """
        self.base_working_dir = os.path.abspath(working_dir)
        self.enable_s3 = enable_s3 and s3_bucket is not None
        self.s3_workspace = None

        # Setup workspace
        if self.enable_s3:
            # Create S3 workspace with random session directory
            self.s3_workspace = S3WorkspaceManager(bucket_name=s3_bucket, base_path=self.base_working_dir)
            self.working_dir = self.s3_workspace.create_workspace()
            print(f"S3 workspace enabled: session {self.s3_workspace.session_id}")
        else:
            # Use regular working directory
            self.working_dir = self.base_working_dir
            os.makedirs(self.working_dir, exist_ok=True)

        self.km = None
        self.kc = None
        self._initialize_kernel()'''

content = content.replace(old_init, new_init)

# 3. Update get_status method
old_status = '''    def get_status(self):
        """Get kernel status"""
        if self.km is None or not self.km.is_alive():
            return {"status": "dead", "alive": False}

        return {
            "status": "running",
            "alive": True,
            "kernel_name": "python3",
            "working_dir": self.working_dir
        }'''

new_status = '''    def get_status(self):
        """Get kernel status"""
        if self.km is None or not self.km.is_alive():
            return {"status": "dead", "alive": False}

        status = {
            "status": "running",
            "alive": True,
            "kernel_name": "python3",
            "working_dir": self.working_dir,
            "s3_enabled": self.enable_s3
        }

        if self.enable_s3 and self.s3_workspace:
            status["session_info"] = self.s3_workspace.get_session_info()

        return status'''

content = content.replace(old_status, new_status)

# 4. Update execute_code return statement
old_execute_return = '''            return {
                "success": True,
                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",
                "images": images if images else None
            }

        except Exception as e:
            return {"success": False, "error": str(e)}'''

new_execute_return = '''            result = {
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
            return {"success": False, "error": str(e)}'''

content = content.replace(old_execute_return, new_execute_return)

# 5. Update create_notebook return statement
old_notebook_return = '''            return {
                "success": True,
                "message": f"Notebook created: {filepath}",
                "result": {"path": filepath, "cells": len(cells)}
            }

        except Exception as e:
            return {"success": False, "error": str(e)}'''

new_notebook_return = '''            result = {
                "success": True,
                "message": f"Notebook created: {filepath}",
                "result": {"path": filepath, "cells": len(cells)}
            }

            # Upload notebook to S3 if enabled
            if self.enable_s3 and self.s3_workspace:
                try:
                    # Get relative path from workspace
                    relpath = os.path.relpath(filepath, self.working_dir)
                    upload_result = self.s3_workspace.upload_file_to_s3(filepath)
                    result["s3_upload"] = upload_result
                    print(f"Uploaded notebook to S3: {upload_result['s3_uri']}")
                except Exception as e:
                    print(f"Warning: Failed to upload notebook to S3: {e}")
                    result["s3_upload_error"] = str(e)

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}'''

content = content.replace(old_notebook_return, new_notebook_return)

# 6. Update shutdown method
old_shutdown = '''    def shutdown(self):
        """Shutdown the kernel"""
        if self.km:
            self.km.shutdown_kernel(now=True)
            print("Kernel shutdown complete")'''

new_shutdown = '''    def shutdown(self):
        """Shutdown the kernel and cleanup workspace"""
        if self.km:
            self.km.shutdown_kernel(now=True)
            print("Kernel shutdown complete")

        # Cleanup S3 workspace
        if self.enable_s3 and self.s3_workspace:
            self.s3_workspace.cleanup_workspace()
            print("S3 workspace cleaned up")'''

content = content.replace(old_shutdown, new_shutdown)

# Write the updated content
with open('jupyter_mcp_server/kernel_manager.py', 'w') as f:
    f.write(content)

print("Updated kernel_manager.py successfully!")
