"""
S3 Workspace Manager

Manages temporary workspaces with S3 file persistence and pre-signed URLs.
Creates isolated random temp directories for each session and uploads files to S3.
"""

import os
import uuid
import shutil
import boto3
from datetime import datetime, timedelta
from botocore.config import Config
from typing import List, Dict, Optional


class S3WorkspaceManager:
    """Manages temporary workspaces with S3 file persistence"""

    def __init__(self, bucket_name: str, base_path: str = "/tmp", url_expiry_hours: int = 24):
        """
        Initialize S3 workspace manager

        Args:
            bucket_name: S3 bucket name for file storage
            base_path: Base path for temporary directories (default: /tmp)
            url_expiry_hours: Expiry time for pre-signed URLs in hours (default: 24)
        """
        self.bucket_name = bucket_name
        self.base_path = base_path
        self.url_expiry_seconds = url_expiry_hours * 3600
        self.session_id = self._generate_session_id()
        self.workspace_path = None

        # Initialize S3 client with signature version for pre-signed URLs
        self.s3_client = boto3.client(
            's3',
            config=Config(signature_version='s3v4')
        )

    def _generate_session_id(self) -> str:
        """Generate a random session ID"""
        return str(uuid.uuid4())

    def create_workspace(self) -> str:
        """
        Create a new isolated workspace directory

        Returns:
            Path to the workspace directory
        """
        # Create random workspace directory
        workspace_name = f"session_{self.session_id}"
        self.workspace_path = os.path.join(self.base_path, workspace_name)

        # Ensure parent directory exists
        os.makedirs(self.base_path, exist_ok=True)

        # Create workspace directory
        os.makedirs(self.workspace_path, exist_ok=True)

        print(f"Created workspace: {self.workspace_path}")
        return self.workspace_path

    def get_workspace_path(self) -> Optional[str]:
        """Get the current workspace path"""
        return self.workspace_path

    def scan_workspace_files(self) -> List[str]:
        """
        Scan workspace for created files

        Returns:
            List of file paths relative to workspace
        """
        if not self.workspace_path or not os.path.exists(self.workspace_path):
            return []

        files = []
        for root, _, filenames in os.walk(self.workspace_path):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                # Get relative path from workspace
                relpath = os.path.relpath(filepath, self.workspace_path)
                files.append(relpath)

        return files

    def upload_file_to_s3(self, local_path: str, s3_key: str = None) -> Dict[str, str]:
        """
        Upload a file to S3 and generate pre-signed URL

        Args:
            local_path: Local file path (can be absolute or relative to workspace)
            s3_key: Optional S3 key. If not provided, uses session_id/filename

        Returns:
            Dictionary with s3_key, s3_uri, and presigned_url
        """
        # Handle relative paths
        if not os.path.isabs(local_path) and self.workspace_path:
            local_path = os.path.join(self.workspace_path, local_path)

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"File not found: {local_path}")

        # Generate S3 key if not provided
        if s3_key is None:
            filename = os.path.basename(local_path)
            s3_key = f"jupyter-workspaces/{self.session_id}/{filename}"

        # Upload file to S3
        self.s3_client.upload_file(local_path, self.bucket_name, s3_key)

        # Generate pre-signed URL
        presigned_url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': s3_key
            },
            ExpiresIn=self.url_expiry_seconds
        )

        s3_uri = f"s3://{self.bucket_name}/{s3_key}"

        print(f"Uploaded {local_path} to {s3_uri}")

        return {
            "local_path": local_path,
            "s3_key": s3_key,
            "s3_uri": s3_uri,
            "presigned_url": presigned_url,
            "expires_in_hours": self.url_expiry_seconds // 3600
        }

    def upload_workspace_files(self) -> List[Dict[str, str]]:
        """
        Upload all files in workspace to S3

        Returns:
            List of file upload results with pre-signed URLs
        """
        files = self.scan_workspace_files()
        results = []

        for relpath in files:
            try:
                # Generate S3 key preserving directory structure
                s3_key = f"jupyter-workspaces/{self.session_id}/{relpath}"
                local_path = os.path.join(self.workspace_path, relpath)

                result = self.upload_file_to_s3(local_path, s3_key)
                result["filename"] = relpath
                results.append(result)
            except Exception as e:
                print(f"Failed to upload {relpath}: {e}")
                results.append({
                    "filename": relpath,
                    "error": str(e)
                })

        return results

    def cleanup_workspace(self):
        """Remove the workspace directory and all its contents"""
        if self.workspace_path and os.path.exists(self.workspace_path):
            try:
                shutil.rmtree(self.workspace_path)
                print(f"Cleaned up workspace: {self.workspace_path}")
            except Exception as e:
                print(f"Failed to cleanup workspace: {e}")

    def get_session_info(self) -> Dict:
        """Get information about the current session"""
        return {
            "session_id": self.session_id,
            "workspace_path": self.workspace_path,
            "bucket_name": self.bucket_name,
            "base_path": self.base_path,
            "url_expiry_hours": self.url_expiry_seconds // 3600
        }
