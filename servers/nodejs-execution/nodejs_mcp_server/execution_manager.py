"""
Execution Manager - Handles Node.js/TypeScript code execution with S3 persistence
"""
import os
import uuid
import shutil
import subprocess
import json
from typing import Dict, Any, Optional
import boto3
from botocore.config import Config


class ExecutionManager:
    """Manages Node.js/TypeScript code execution with S3 persistence"""

    def __init__(self, working_dir="/tmp", s3_bucket=None, enable_s3=False):
        self.base_working_dir = os.path.abspath(working_dir)
        self.enable_s3 = enable_s3 and s3_bucket is not None
        self.s3_bucket = s3_bucket
        self.session_id = str(uuid.uuid4())

        if self.enable_s3:
            self.s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
            self.workspace_path = os.path.join(self.base_working_dir, f"session_{self.session_id}")
            os.makedirs(self.workspace_path, exist_ok=True)
            print(f"S3 workspace enabled: session {self.session_id}")
        else:
            self.workspace_path = self.base_working_dir
            os.makedirs(self.workspace_path, exist_ok=True)

        # Initialize package.json if not exists
        self._init_package_json()

    def _init_package_json(self):
        """Initialize package.json for npm"""
        package_json_path = os.path.join(self.workspace_path, "package.json")
        if not os.path.exists(package_json_path):
            package_json = {
                "name": "mcp-nodejs-execution",
                "version": "1.0.0",
                "type": "commonjs",
                "dependencies": {}
            }
            with open(package_json_path, 'w') as f:
                json.dump(package_json, f, indent=2)

    def _sanitize_environment(self):
        """Remove sensitive AWS credentials from environment

        SECURITY: Prevents user code from accessing Lambda execution role credentials.
        Users should not be able to use the Lambda's AWS credentials to access resources.
        """
        # List of sensitive environment variables to remove
        sensitive_keys = [
            'AWS_ACCESS_KEY_ID',
            'AWS_SECRET_ACCESS_KEY',
            'AWS_SESSION_TOKEN',
            'AWS_SECURITY_TOKEN',
            # Also remove other potentially sensitive Lambda metadata
            'AWS_LAMBDA_FUNCTION_NAME',
            'AWS_LAMBDA_FUNCTION_VERSION',
            'AWS_LAMBDA_LOG_GROUP_NAME',
            'AWS_LAMBDA_LOG_STREAM_NAME',
            'AWS_LAMBDA_FUNCTION_MEMORY_SIZE',
            '_AWS_XRAY_DAEMON_ADDRESS',
            '_AWS_XRAY_DAEMON_PORT',
        ]

        # Create copy of environment without sensitive keys
        sanitized = {k: v for k, v in os.environ.items() if k not in sensitive_keys}

        # Keep essential environment variables for Node.js
        essential_vars = {
            'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
            'HOME': os.environ.get('HOME', '/tmp'),
            'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
            'NODE_PATH': os.environ.get('NODE_PATH', ''),
        }

        sanitized.update(essential_vars)

        print(f"SECURITY: Sanitized environment - removed {len(sensitive_keys)} sensitive variables")
        return sanitized

    def _upload_to_s3(self, local_path: str, filename: str) -> Optional[Dict]:
        """Upload file to S3 and return pre-signed URL"""
        if not self.enable_s3:
            return None
        try:
            s3_key = f"nodejs-execution/{self.session_id}/{filename}"
            self.s3_client.upload_file(local_path, self.s3_bucket, s3_key)
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.s3_bucket, 'Key': s3_key},
                ExpiresIn=86400
            )
            return {
                "s3_uri": f"s3://{self.s3_bucket}/{s3_key}",
                "presigned_url": presigned_url,
                "filename": filename,
                "size_bytes": os.path.getsize(local_path),
                "expires_in_hours": 24
            }
        except Exception as e:
            print(f"S3 upload failed: {e}")
            return None

    def execute_javascript(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute JavaScript/Node.js code"""
        try:
            # Write code to file
            code_file = os.path.join(self.workspace_path, "script.js")
            with open(code_file, 'w') as f:
                f.write(code)

            # SECURITY: Execute with Node.js using sanitized environment
            # This prevents user code from accessing Lambda execution role credentials
            sanitized_env = self._sanitize_environment()
            result = subprocess.run(
                ['node', 'script.js'],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=sanitized_env
            )

            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode

            # Upload code file to S3
            s3_info = self._upload_to_s3(code_file, "script.js")

            return {
                "success": exit_code == 0,
                "output": f"Exit Code: {exit_code}",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "s3_upload": s3_info
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Execution timed out after {timeout} seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_typescript(self, code: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute TypeScript code"""
        try:
            # Write code to file
            code_file = os.path.join(self.workspace_path, "script.ts")
            with open(code_file, 'w') as f:
                f.write(code)

            # SECURITY: Execute with ts-node using sanitized environment
            # This prevents user code from accessing Lambda execution role credentials
            sanitized_env = self._sanitize_environment()
            result = subprocess.run(
                ['ts-node', 'script.ts'],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=sanitized_env
            )

            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode

            # Upload code file to S3
            s3_info = self._upload_to_s3(code_file, "script.ts")

            return {
                "success": exit_code == 0,
                "output": f"Exit Code: {exit_code}",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "s3_upload": s3_info
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Execution timed out after {timeout} seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def install_package(self, package_name: str, version: str = "latest") -> Dict[str, Any]:
        """Install npm package"""
        try:
            package_spec = f"{package_name}@{version}" if version != "latest" else package_name

            result = subprocess.run(
                ['npm', 'install', package_spec, '--save'],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=120
            )

            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode

            if exit_code == 0:
                return {
                    "success": True,
                    "output": f"Successfully installed {package_spec}",
                    "stdout": stdout,
                    "stderr": stderr
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to install {package_spec}",
                    "stdout": stdout,
                    "stderr": stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Package installation timed out after 120 seconds"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        """Clean up workspace"""
        if self.enable_s3 and self.workspace_path and os.path.exists(self.workspace_path):
            try:
                shutil.rmtree(self.workspace_path)
            except:
                pass
