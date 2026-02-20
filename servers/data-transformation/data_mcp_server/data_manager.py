"""
Data Manager - Handles data transformations with S3 persistence
"""
import os
import json
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
    
    def _generate_preview(self, data: Any, format_type: str, max_rows: int = 100) -> str:
        try:
            if format_type == "json":
                json_str = json.dumps(data, indent=2)
                if len(json_str) > 5000:
                    return json_str[:5000] + "\n\n... (truncated, download full file)"
                return json_str
            elif format_type in ["csv", "dataframe"] and isinstance(data, pd.DataFrame):
                preview = data.head(max_rows).to_string()
                if len(data) > max_rows:
                    preview += f"\n\n... ({len(data) - max_rows} more rows, download full file)"
                return preview
            else:
                s = str(data)
                return s[:5000] + ("...(truncated)" if len(s) > 5000 else "")
        except:
            return "Preview unavailable"
    
    def _upload_to_s3(self, local_path: str, filename: str) -> Optional[Dict]:
        if not self.enable_s3:
            return None
        try:
            s3_key = f"data-transformations/{self.session_id}/{filename}"
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
    
    def csv_to_json(self, csv_data: str) -> Dict[str, Any]:
        try:
            df = pd.read_csv(StringIO(csv_data))
            json_data = df.to_dict(orient='records')
            output_file = os.path.join(self.workspace_path, "output.json")
            with open(output_file, 'w') as f:
                json.dump(json_data, f, indent=2)
            preview = self._generate_preview(json_data, "json")
            s3_info = self._upload_to_s3(output_file, "output.json")
            return {
                "success": True,
                "output": f"Converted {len(df)} rows to JSON",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info,
                "stats": {"rows": len(df), "columns": len(df.columns), "column_names": df.columns.tolist()}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def json_to_csv(self, json_data: str) -> Dict[str, Any]:
        try:
            data = json.loads(json_data)
            df = pd.DataFrame(data if isinstance(data, list) else [data])
            output_file = os.path.join(self.workspace_path, "output.csv")
            df.to_csv(output_file, index=False)
            preview = self._generate_preview(df, "csv")
            s3_info = self._upload_to_s3(output_file, "output.csv")
            return {
                "success": True,
                "output": f"Converted to CSV with {len(df)} rows",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info,
                "stats": {"rows": len(df), "columns": len(df.columns), "column_names": df.columns.tolist()}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def json_to_yaml(self, json_data: str) -> Dict[str, Any]:
        try:
            data = json.loads(json_data)
            output_file = os.path.join(self.workspace_path, "output.yaml")
            with open(output_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            with open(output_file, 'r') as f:
                yaml_content = f.read()
            s3_info = self._upload_to_s3(output_file, "output.yaml")
            preview = yaml_content[:5000] + ("...(truncated)" if len(yaml_content) > 5000 else "")
            return {
                "success": True,
                "output": "Converted JSON to YAML",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def yaml_to_json(self, yaml_data: str) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(yaml_data)
            output_file = os.path.join(self.workspace_path, "output.json")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            preview = self._generate_preview(data, "json")
            s3_info = self._upload_to_s3(output_file, "output.json")
            return {
                "success": True,
                "output": "Converted YAML to JSON",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def xml_to_json(self, xml_data: str) -> Dict[str, Any]:
        try:
            data = xmltodict.parse(xml_data)
            output_file = os.path.join(self.workspace_path, "output.json")
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            preview = self._generate_preview(data, "json")
            s3_info = self._upload_to_s3(output_file, "output.json")
            return {
                "success": True,
                "output": "Converted XML to JSON",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def clean_data(self, csv_data: str, operations: List[str]) -> Dict[str, Any]:
        try:
            df = pd.read_csv(StringIO(csv_data))
            original_rows = len(df)
            applied = []
            for op in operations:
                if op == "remove_duplicates":
                    before = len(df)
                    df = df.drop_duplicates()
                    applied.append(f"Removed {before - len(df)} duplicates")
                elif op == "remove_nulls":
                    before = len(df)
                    df = df.dropna()
                    applied.append(f"Removed {before - len(df)} rows with nulls")
                elif op == "fill_nulls_zero":
                    df = df.fillna(0)
                    applied.append("Filled nulls with 0")
            output_file = os.path.join(self.workspace_path, "cleaned.csv")
            df.to_csv(output_file, index=False)
            preview = self._generate_preview(df, "csv")
            s3_info = self._upload_to_s3(output_file, "cleaned.csv")
            return {
                "success": True,
                "output": f"Cleaned: {original_rows} → {len(df)} rows\n" + "\n".join(applied),
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def merge_data(self, csv1: str, csv2: str, merge_column: str, how: str = "inner") -> Dict[str, Any]:
        try:
            df1 = pd.read_csv(StringIO(csv1))
            df2 = pd.read_csv(StringIO(csv2))
            merged = pd.merge(df1, df2, on=merge_column, how=how)
            output_file = os.path.join(self.workspace_path, "merged.csv")
            merged.to_csv(output_file, index=False)
            preview = self._generate_preview(merged, "csv")
            s3_info = self._upload_to_s3(output_file, "merged.csv")
            return {
                "success": True,
                "output": f"Merged: {len(df1)} + {len(df2)} → {len(merged)} rows",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def filter_data(self, csv_data: str, column: str, operator: str, value: Any) -> Dict[str, Any]:
        try:
            df = pd.read_csv(StringIO(csv_data))
            original = len(df)
            if operator == "equals":
                filtered = df[df[column] == value]
            elif operator == "not_equals":
                filtered = df[df[column] != value]
            elif operator == "greater_than":
                filtered = df[df[column] > float(value)]
            elif operator == "less_than":
                filtered = df[df[column] < float(value)]
            elif operator == "contains":
                filtered = df[df[column].str.contains(str(value), na=False)]
            else:
                return {"success": False, "error": f"Unknown operator: {operator}"}
            output_file = os.path.join(self.workspace_path, "filtered.csv")
            filtered.to_csv(output_file, index=False)
            preview = self._generate_preview(filtered, "csv")
            s3_info = self._upload_to_s3(output_file, "filtered.csv")
            return {
                "success": True,
                "output": f"Filtered: {original} → {len(filtered)} rows",
                "preview": {"type": "text", "data": preview},
                "s3_upload": s3_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_stats(self, csv_data: str) -> Dict[str, Any]:
        try:
            df = pd.read_csv(StringIO(csv_data))
            stats = df.describe(include='all').to_string()
            return {
                "success": True,
                "output": f"Stats for {len(df)} rows, {len(df.columns)} columns",
                "preview": {"type": "text", "data": stats},
                "stats": {"rows": len(df), "columns": len(df.columns), "column_names": df.columns.tolist()}
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        if self.enable_s3 and self.workspace_path and os.path.exists(self.workspace_path):
            try:
                shutil.rmtree(self.workspace_path)
            except:
                pass
