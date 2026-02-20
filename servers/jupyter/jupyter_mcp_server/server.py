"""
Jupyter MCP Server

A Model Context Protocol (MCP) server that provides Jupyter kernel capabilities.
Allows LLMs to execute Python code, create notebooks, and interact with data.
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from .kernel_manager import JupyterKernelManager

app = Flask(__name__)
CORS(app)

# Global kernel manager instance
kernel_manager = None

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Server info
SERVER_INFO = {
    "name": "jupyter-mcp-server",
    "version": "0.1.0"
}

# Tool definitions
TOOLS = [
    {
        "name": "execute_code",
        "description": "Execute Python code in a Jupyter kernel and return the output. Supports rich outputs like plots, dataframes, and more.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "timeout": {
                    "type": "number",
                    "description": "Execution timeout in seconds (default: 60)",
                    "default": 60
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "get_kernel_status",
        "description": "Get the current status of the Jupyter kernel",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "restart_kernel",
        "description": "Restart the Jupyter kernel to clear all state",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_variables",
        "description": "Get a list of variables currently defined in the kernel namespace",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "inspect_variable",
        "description": "Get detailed information about a variable including its type, value, and shape (for arrays/dataframes)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the variable to inspect"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "install_package",
        "description": "Install a Python package using pip",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name to install (can include version specifier, e.g., 'pandas>=2.0')"
                }
            },
            "required": ["package"]
        }
    },
    {
        "name": "create_notebook",
        "description": "Create a new Jupyter notebook with the specified cells",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename for the notebook (without .ipynb extension)"
                },
                "cells": {
                    "type": "array",
                    "description": "Array of cell objects with 'type' (code/markdown) and 'source'",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["code", "markdown"]
                            },
                            "source": {
                                "type": "string"
                            }
                        },
                        "required": ["type", "source"]
                    }
                }
            },
            "required": ["filename", "cells"]
        }
    },
    {
        "name": "read_notebook",
        "description": "Read and return the contents of a Jupyter notebook file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Path to the notebook file"
                }
            },
            "required": ["filename"]
        }
    }
]


def generate_request_id():
    """Generate a unique request ID"""
    return f"resp_{datetime.now().timestamp():.0f}"


def create_json_rpc_response(request_id, result):
    """Create a JSON-RPC 2.0 response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }


def create_json_rpc_error(request_id, code, message):
    """Create a JSON-RPC 2.0 error response"""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }


def handle_initialize(params):
    """Handle MCP initialize request"""
    return {
        "protocolVersion": MCP_VERSION,
        "capabilities": {
            "tools": {}
        },
        "serverInfo": SERVER_INFO
    }


def handle_tools_list(params):
    """Handle tools/list request"""
    return {"tools": TOOLS}


def handle_tools_call(params):
    """Handle tools/call request"""
    # Handle case where params might be a string (double-encoded JSON)
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            return {
                "content": [{"type": "text", "text": f"Invalid params: expected object, got string"}],
                "isError": True
            }

    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    # Handle case where arguments might be a string (double-encoded JSON)
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            pass  # Keep as string if not valid JSON

    try:
        if tool_name == "execute_code":
            result = kernel_manager.execute_code(
                arguments.get("code", ""),
                timeout=arguments.get("timeout", 60)
            )

        elif tool_name == "get_kernel_status":
            result = kernel_manager.get_status()

        elif tool_name == "restart_kernel":
            result = kernel_manager.restart()

        elif tool_name == "get_variables":
            result = kernel_manager.get_variables()

        elif tool_name == "inspect_variable":
            result = kernel_manager.inspect_variable(arguments.get("name", ""))

        elif tool_name == "install_package":
            result = kernel_manager.install_package(arguments.get("package", ""))

        elif tool_name == "create_notebook":
            result = kernel_manager.create_notebook(
                arguments.get("filename", ""),
                arguments.get("cells", [])
            )

        elif tool_name == "read_notebook":
            result = kernel_manager.read_notebook(arguments.get("filename", ""))

        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True
            }

        # Format successful result
        if isinstance(result, dict):
            if result.get("success"):
                content = []

                # Add text output if present
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
                    files_info = []
                    for file_info in result["uploaded_files"]:
                        if "error" in file_info:
                            files_info.append(f"\n{file_info['filename']}: Error - {file_info['error']}")
                        else:
                            files_info.append(f"\n{file_info['filename']}")
                            files_info.append(f"Download (24h): {file_info['presigned_url']}")
                    if files_info:
                        content.append({"type": "text", "text": "\n".join(files_info)})

                # Add S3 upload for single files (like notebooks)
                if result.get("s3_upload"):
                    s3_info = result["s3_upload"]
                    s3_text = f"\nNotebook uploaded to S3\nDownload (24h): {s3_info['presigned_url']}"
                    content.append({"type": "text", "text": s3_text})

                # Add image outputs if present
                if result.get("images"):
                    for img in result["images"]:
                        content.append({
                            "type": "image",
                            "data": img["data"],
                            "mimeType": img.get("mimeType", "image/png")
                        })

                return {"content": content, "isError": False}
            else:
                return {
                    "content": [{"type": "text", "text": result.get("error", "Unknown error")}],
                    "isError": True
                }
        else:
            return {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False
            }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Error: {str(e)}\n{traceback.format_exc()}"}],
            "isError": True
        }


@app.route("/", methods=["POST"])
@app.route("/mcp", methods=["POST"])
def handle_request():
    """Handle MCP JSON-RPC requests"""
    try:
        data = request.get_json()

        if not data:
            return jsonify(create_json_rpc_error(None, -32700, "Parse error")), 400

        jsonrpc = data.get("jsonrpc")
        request_id = data.get("id")
        method = data.get("method")
        params = data.get("params", {})

        if jsonrpc != "2.0":
            return jsonify(create_json_rpc_error(request_id, -32600, "Invalid JSON-RPC version")), 400

        # Handle notifications (no id)
        if request_id is None and method.startswith("notifications/"):
            return "", 204

        # Route to appropriate handler
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
        return jsonify(create_json_rpc_error(
            request_id if 'request_id' in dir() else None,
            -32603,
            f"Internal error: {str(e)}"
        )), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "server": SERVER_INFO,
        "kernel": kernel_manager.get_status() if kernel_manager else {"status": "not initialized"}
    })


def main():
    """Main entry point"""
    global kernel_manager

    parser = argparse.ArgumentParser(description="Jupyter MCP Server")
    parser.add_argument("--port", type=int, default=8888, help="Port to listen on (default: 8888)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--working-dir", type=str, default=".", help="Working directory for notebooks")
    args = parser.parse_args()

    print(f"Starting Jupyter MCP Server v{SERVER_INFO['version']}")
    print(f"Working directory: {args.working_dir}")

    # Initialize kernel manager
    kernel_manager = JupyterKernelManager(working_dir=args.working_dir)

    print(f"Server listening on http://{args.host}:{args.port}")
    print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
    print("\nAvailable tools:")
    for tool in TOOLS:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
