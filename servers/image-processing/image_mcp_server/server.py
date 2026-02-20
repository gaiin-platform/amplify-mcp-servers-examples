"""
Image Processing MCP Server

A Model Context Protocol (MCP) server that provides image processing capabilities.
Supports resize, crop, rotate, filters, format conversion, thumbnails.
"""

import json
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from .image_manager import ImageManager
import os

app = Flask(__name__)
CORS(app)

# Global image manager instance
image_manager = None

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Server info
SERVER_INFO = {
    "name": "image-processing-mcp-server",
    "version": "0.1.0"
}

# Tool definitions
TOOLS = [
    {
        "name": "resize_image",
        "description": "Resize an image uploaded by the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string", "description": "Base64 encoded image"},
                "width": {"type": "integer", "description": "Target width in pixels"},
                "height": {"type": "integer", "description": "Target height in pixels"},
                "maintain_aspect": {"type": "boolean", "description": "Maintain aspect ratio", "default": True}
            },
            "required": ["image_data", "width", "height"]
        }
    },
    {
        "name": "crop_image",
        "description": "Crop an image uploaded by the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string", "description": "Base64 encoded image"},
                "left": {"type": "integer"},
                "top": {"type": "integer"},
                "right": {"type": "integer"},
                "bottom": {"type": "integer"}
            },
            "required": ["image_data", "left", "top", "right", "bottom"]
        }
    },
    {
        "name": "rotate_image",
        "description": "Rotate an image uploaded by the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string", "description": "Base64 encoded image"},
                "degrees": {"type": "number", "description": "Rotation angle"},
                "expand": {"type": "boolean", "default": True}
            },
            "required": ["image_data", "degrees"]
        }
    },
    {
        "name": "apply_filter",
        "description": "Apply filter to an image uploaded by the user",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string"},
                "filter_type": {"type": "string", "enum": ["grayscale", "blur", "sharpen", "edge_enhance", "contour", "brightness", "contrast"]},
                "intensity": {"type": "number"}
            },
            "required": ["image_data", "filter_type"]
        }
    },
    {
        "name": "convert_format",
        "description": "Convert image format",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string"},
                "target_format": {"type": "string", "enum": ["PNG", "JPEG", "WebP", "GIF", "BMP"]},
                "quality": {"type": "integer", "default": 85}
            },
            "required": ["image_data", "target_format"]
        }
    },
    {
        "name": "create_thumbnail",
        "description": "Create thumbnail of an image",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_data": {"type": "string"},
                "max_size": {"type": "integer", "default": 200}
            },
            "required": ["image_data"]
        }
    }
]

def create_json_rpc_response(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}

def create_json_rpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

def handle_initialize(params):
    return {"protocolVersion": MCP_VERSION, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}

def handle_tools_list(params):
    return {"tools": TOOLS}

def handle_tools_call(params):
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            return {"content": [{"type": "text", "text": "Invalid params"}], "isError": True}

    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except:
            pass

    try:
        if tool_name == "resize_image":
            result = image_manager.resize_image(
                arguments.get("image_data", ""),
                arguments.get("width", 0),
                arguments.get("height", 0),
                arguments.get("maintain_aspect", True)
            )
        elif tool_name == "crop_image":
            result = image_manager.crop_image(
                arguments.get("image_data", ""),
                arguments.get("left", 0),
                arguments.get("top", 0),
                arguments.get("right", 0),
                arguments.get("bottom", 0)
            )
        elif tool_name == "rotate_image":
            result = image_manager.rotate_image(
                arguments.get("image_data", ""),
                arguments.get("degrees", 0),
                arguments.get("expand", True)
            )
        elif tool_name == "apply_filter":
            result = image_manager.apply_filter(
                arguments.get("image_data", ""),
                arguments.get("filter_type", ""),
                arguments.get("intensity", 1.0)
            )
        elif tool_name == "convert_format":
            result = image_manager.convert_format(
                arguments.get("image_data", ""),
                arguments.get("target_format", ""),
                arguments.get("quality", 85)
            )
        elif tool_name == "create_thumbnail":
            result = image_manager.create_thumbnail(
                arguments.get("image_data", ""),
                arguments.get("max_size", 200)
            )
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

        if isinstance(result, dict):
            if result.get("success"):
                content = []
                if result.get("output"):
                    content.append({"type": "text", "text": result["output"]})
                if result.get("metadata"):
                    m = result["metadata"]
                    content.append({"type": "text", "text": f"\n\n[Image] {m.get('width')}x{m.get('height')} {m.get('format')}"})
                if result.get("image_base64"):
                    content.append({"type": "image", "data": result["image_base64"], "mimeType": "image/png"})
                if result.get("s3_upload"):
                    s3 = result["s3_upload"]
                    content.append({"type": "text", "text": f"\n\n[Download] {s3.get('size_bytes', 0) // 1024} KB:\n{s3.get('presigned_url', '')}"})
                return {"content": content, "isError": False}
            else:
                return {"content": [{"type": "text", "text": result.get("error", "Error")}], "isError": True}
        return {"content": [{"type": "text", "text": str(result)}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {str(e)}\n{traceback.format_exc()}"}], "isError": True}

@app.route("/", methods=["POST"])
@app.route("/mcp", methods=["POST"])
def handle_request():
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_json_rpc_error(None, -32700, "Parse error")), 400

        jsonrpc = data.get("jsonrpc")
        request_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})

        if jsonrpc != "2.0":
            return jsonify(create_json_rpc_error(request_id, -32600, "Invalid JSON-RPC")), 400

        if request_id is None and method.startswith("notifications/"):
            return "", 204

        if method == "initialize":
            result = handle_initialize(params)
        elif method == "tools/list":
            result = handle_tools_list(params)
        elif method == "tools/call":
            result = handle_tools_call(params)
        else:
            return jsonify(create_json_rpc_error(request_id, -32601, f"Method not found: {method}")), 400

        return jsonify(create_json_rpc_response(request_id, result))
    except Exception as e:
        return jsonify(create_json_rpc_error(None, -32603, f"Internal error: {str(e)}")), 500

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "server": SERVER_INFO})

def initialize_image_manager():
    global image_manager
    print("Initializing Image Manager...")
    s3_bucket = os.environ.get("S3_BUCKET")
    image_manager = ImageManager(working_dir="/tmp", s3_bucket=s3_bucket, enable_s3=(s3_bucket is not None))
    print("Image Manager initialized")

initialize_image_manager()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
