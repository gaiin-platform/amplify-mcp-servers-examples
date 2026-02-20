"""
Image Manager - Handles image processing operations with S3 persistence
"""
import os
import io
import uuid
import base64
import shutil
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageFilter, ImageEnhance
import boto3
from botocore.config import Config


class ImageManager:
    """Manages image processing operations with S3 persistence"""

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

    def _decode_image(self, image_data: str) -> Image.Image:
        """Decode base64 image data to PIL Image"""
        try:
            # Strip data URI prefix if present
            if ',' in image_data and image_data.startswith('data:'):
                image_data = image_data.split(',', 1)[1]

            # Remove all whitespace and newlines
            image_data = image_data.strip().replace('\n', '').replace('\r', '').replace(' ', '')

            # Add padding if needed (base64 must be multiple of 4)
            padding_needed = len(image_data) % 4
            if padding_needed:
                image_data += '=' * (4 - padding_needed)

            img_bytes = base64.b64decode(image_data)
            return Image.open(io.BytesIO(img_bytes))
        except Exception as e:
            raise ValueError(f"Failed to decode image: {str(e)}")

    def _encode_image(self, img: Image.Image, format_type: str = "PNG") -> str:
        """Encode PIL Image to base64 string"""
        buffer = io.BytesIO()
        img.save(buffer, format=format_type.upper())
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')

    def _get_image_info(self, img: Image.Image) -> Dict:
        """Get image metadata"""
        return {
            "width": img.width,
            "height": img.height,
            "format": img.format or "Unknown",
            "mode": img.mode
        }

    def _save_and_upload(self, img: Image.Image, filename: str, format_type: str = "PNG") -> Tuple[str, Optional[Dict]]:
        """Save image and upload to S3, return base64 and S3 info"""
        output_path = os.path.join(self.workspace_path, filename)
        img.save(output_path, format=format_type.upper())
        file_size = os.path.getsize(output_path)

        base64_data = None
        if file_size < 4 * 1024 * 1024:
            base64_data = self._encode_image(img, format_type)

        s3_info = None
        if self.enable_s3:
            try:
                s3_key = f"images/{self.session_id}/{filename}"
                self.s3_client.upload_file(output_path, self.s3_bucket, s3_key)
                presigned_url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.s3_bucket, 'Key': s3_key},
                    ExpiresIn=86400
                )
                s3_info = {
                    "s3_uri": f"s3://{self.s3_bucket}/{s3_key}",
                    "presigned_url": presigned_url,
                    "filename": filename,
                    "size_bytes": file_size,
                    "expires_in_hours": 24
                }
            except Exception as e:
                print(f"S3 upload failed: {e}")

        return base64_data, s3_info

    def resize_image(self, image_data: str, width: int, height: int, maintain_aspect: bool = True) -> Dict[str, Any]:
        """Resize image to specified dimensions"""
        try:
            img = self._decode_image(image_data)
            original_info = self._get_image_info(img)

            if maintain_aspect:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            else:
                img = img.resize((width, height), Image.Resampling.LANCZOS)

            base64_data, s3_info = self._save_and_upload(img, "resized.png", "PNG")
            new_info = self._get_image_info(img)

            return {
                "success": True,
                "output": f"Resized from {original_info['width']}x{original_info['height']} to {new_info['width']}x{new_info['height']}",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def crop_image(self, image_data: str, left: int, top: int, right: int, bottom: int) -> Dict[str, Any]:
        """Crop image to specified region"""
        try:
            img = self._decode_image(image_data)
            original_info = self._get_image_info(img)
            cropped = img.crop((left, top, right, bottom))
            base64_data, s3_info = self._save_and_upload(cropped, "cropped.png", "PNG")
            new_info = self._get_image_info(cropped)
            return {
                "success": True,
                "output": f"Cropped from {original_info['width']}x{original_info['height']} to {new_info['width']}x{new_info['height']}",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rotate_image(self, image_data: str, degrees: float, expand: bool = True) -> Dict[str, Any]:
        """Rotate image by specified degrees"""
        try:
            img = self._decode_image(image_data)
            rotated = img.rotate(degrees, expand=expand, fillcolor=(255, 255, 255))
            base64_data, s3_info = self._save_and_upload(rotated, "rotated.png", "PNG")
            new_info = self._get_image_info(rotated)
            return {
                "success": True,
                "output": f"Rotated by {degrees} degrees",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_filter(self, image_data: str, filter_type: str, intensity: float = 1.0) -> Dict[str, Any]:
        """Apply filter to image"""
        try:
            img = self._decode_image(image_data)
            if filter_type == "grayscale":
                filtered = img.convert("L").convert("RGB")
            elif filter_type == "blur":
                filtered = img.filter(ImageFilter.GaussianBlur(radius=intensity * 5))
            elif filter_type == "sharpen":
                filtered = img.filter(ImageFilter.SHARPEN)
            elif filter_type == "edge_enhance":
                filtered = img.filter(ImageFilter.EDGE_ENHANCE)
            elif filter_type == "contour":
                filtered = img.filter(ImageFilter.CONTOUR)
            elif filter_type == "brightness":
                enhancer = ImageEnhance.Brightness(img)
                filtered = enhancer.enhance(intensity)
            elif filter_type == "contrast":
                enhancer = ImageEnhance.Contrast(img)
                filtered = enhancer.enhance(intensity)
            else:
                return {"success": False, "error": f"Unknown filter: {filter_type}"}
            base64_data, s3_info = self._save_and_upload(filtered, f"filtered_{filter_type}.png", "PNG")
            new_info = self._get_image_info(filtered)
            return {
                "success": True,
                "output": f"Applied {filter_type} filter",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert_format(self, image_data: str, target_format: str, quality: int = 85) -> Dict[str, Any]:
        """Convert image to different format"""
        try:
            img = self._decode_image(image_data)
            original_info = self._get_image_info(img)
            if target_format.upper() == "JPEG" and img.mode == "RGBA":
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
                img = rgb_img
            filename = f"converted.{target_format.lower()}"
            base64_data, s3_info = self._save_and_upload(img, filename, target_format)
            new_info = self._get_image_info(img)
            return {
                "success": True,
                "output": f"Converted from {original_info['format']} to {target_format}",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_thumbnail(self, image_data: str, max_size: int = 200) -> Dict[str, Any]:
        """Create thumbnail version of image"""
        try:
            img = self._decode_image(image_data)
            original_info = self._get_image_info(img)
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            base64_data, s3_info = self._save_and_upload(img, "thumbnail.png", "PNG")
            new_info = self._get_image_info(img)
            return {
                "success": True,
                "output": f"Created thumbnail: {original_info['width']}x{original_info['height']} -> {new_info['width']}x{new_info['height']}",
                "image_base64": base64_data,
                "s3_upload": s3_info,
                "metadata": new_info
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        """Clean up workspace"""
        if self.enable_s3 and self.workspace_path and os.path.exists(self.workspace_path):
            try:
                shutil.rmtree(self.workspace_path)
            except:
                pass
