"""
Node.js Execution MCP Server

A Model Context Protocol (MCP) server that provides Node.js/TypeScript execution capabilities.
Supports npm package installation and full Node.js runtime.
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from .execution_manager import ExecutionManager

app = Flask(__name__)
CORS(app)

# Global execution manager instance
execution_manager = None

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Server info
SERVER_INFO = {
    "name": "nodejs-execution-mcp-server",
    "version": "0.1.0"
}

# Tool definitions
TOOLS = [
    {
        "name": "execute_javascript",
        "description": "Execute JavaScript/Node.js code. Captures stdout, stderr, and exit code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "JavaScript code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "execute_typescript",
        "description": "Execute TypeScript code. Automatically compiles and runs with ts-node.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "TypeScript code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "install_package",
        "description": "Install npm package for use in subsequent code execution. Packages persist for the session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "package_name": {
                    "type": "string",
                    "description": "NPM package name (e.g., 'lodash', 'axios')"
                },
                "version": {
                    "type": "string",
                    "description": "Package version (default: 'latest')",
                    "default": "latest"
                }
            },
            "required": ["package_name"]
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

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            pass

    try:
        # Route to appropriate tool
        if tool_name == "execute_javascript":
            result = execution_manager.execute_javascript(
                arguments.get("code", ""),
                arguments.get("timeout", 30)
            )

        elif tool_name == "execute_typescript":
            result = execution_manager.execute_typescript(
                arguments.get("code", ""),
                arguments.get("timeout", 30)
            )

        elif tool_name == "install_package":
            result = execution_manager.install_package(
                arguments.get("package_name", ""),
                arguments.get("version", "latest")
            )

        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True
            }

        # Format successful result
        if isinstance(result, dict):
            if result.get("success"):
                content = []

                # Add main output text
                if result.get("output"):
                    content.append({"type": "text", "text": result["output"]})

                # Add stdout if present
                if result.get("stdout"):
                    stdout_text = f"\n\n>> stdout:\n```\n{result['stdout']}\n```"
                    content.append({"type": "text", "text": stdout_text})

                # Add stderr if present
                if result.get("stderr"):
                    stderr_text = f"\n\n!! stderr:\n```\n{result['stderr']}\n```"
                    content.append({"type": "text", "text": stderr_text})

                # Add S3 download link
                if result.get("s3_upload"):
                    s3_info = result["s3_upload"]
                    size_kb = s3_info.get('size_bytes', 0) // 1024
                    url = s3_info.get('presigned_url', '')
                    s3_text = f"\n\n[Download Code File] ({size_kb} KB, expires in 24h):\n{url}"
                    content.append({"type": "text", "text": s3_text})

                return {"content": content, "isError": False}
            else:
                error_content = [{"type": "text", "text": result.get("error", "Unknown error")}]

                # Include stdout/stderr even on failure
                if result.get("stdout"):
                    error_content.append({"type": "text", "text": f"\n\nstdout:\n```\n{result['stdout']}\n```"})
                if result.get("stderr"):
                    error_content.append({"type": "text", "text": f"\n\nstderr:\n```\n{result['stderr']}\n```"})

                return {
                    "content": error_content,
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
        "server": SERVER_INFO
    })


def main():
    """Main entry point"""
    global execution_manager

    parser = argparse.ArgumentParser(description="Node.js Execution MCP Server")
    parser.add_argument("--port", type=int, default=8891, help="Port to listen on (default: 8891)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--working-dir", type=str, default="/tmp", help="Working directory")
    args = parser.parse_args()

    print(f"Starting Node.js Execution MCP Server v{SERVER_INFO['version']}")
    print(f"Working directory: {args.working_dir}")

    # Initialize execution manager
    execution_manager = ExecutionManager(working_dir=args.working_dir)

    print(f"Server listening on http://{args.host}:{args.port}")
    print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
    print("\nAvailable tools:")
    for tool in TOOLS:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
