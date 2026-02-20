"""
Data Manager

Handles data transformations, format conversions, and data operations.
Integrates with S3 for file storage and provides inline previews.
"""

import os
import json
import csv
import yaml
import uuid
import shutil
import pandas as pd
import xmltodict
from io import StringIO
from typing import Dict, List, Any, Optional
import boto3
from botocore.config import Config


class DataManager:
    """Manages data transformations with S3 persistence"""

    def __init__(self, working_dir="/tmp", s3_bucket=None, enable_s3=False):
        """Initialize Data Manager

        Args:
            working_dir: Base working directory (default: /tmp)
            s3_bucket: S3 bucket name for file persistence
            enable_s3: Enable S3 workspace features (default: False)
        """
        self.base_working_dir = os.path.abspath(working_dir)
        self.enable_s3 = enable_s3 and s3_bucket is not None
        self.s3_bucket = s3_bucket
        self.session_id = str(uuid.uuid4())
        self.workspace_path = None

        # Initialize S3 client if enabled
        if self.enable_s3:
            self.s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))
            self.workspace_path = os.path.join(self.base_working_dir, f"session_{self.session_id}")
            os.makedirs(self.workspace_path, exist_ok=True)
            print(f"S3 workspace enabled: session {self.session_id}")
        else:
            self.workspace_path = self.base_working_dir
            os.makedirs(self.workspace_path, exist_ok=True)
