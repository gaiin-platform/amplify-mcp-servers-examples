"""
Data Transformation MCP Server

A Model Context Protocol (MCP) server that provides data transformation capabilities.
Supports CSV, JSON, XML, YAML conversions and data operations.
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from .data_manager import DataManager

app = Flask(__name__)
CORS(app)

# Global data manager instance
data_manager = None

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# Server info
SERVER_INFO = {
    "name": "data-transformation-mcp-server",
    "version": "0.1.0"
}

# Tool definitions
TOOLS = [
    {
        "name": "csv_to_json",
        "description": "Convert CSV data to JSON format. Returns inline preview and downloadable file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV data as string"
                }
            },
            "required": ["csv_data"]
        }
    },
    {
        "name": "json_to_csv",
        "description": "Convert JSON data to CSV format. Handles arrays of objects.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_data": {
                    "type": "string",
                    "description": "JSON data as string (array or object)"
                }
            },
            "required": ["json_data"]
        }
    },
    {
        "name": "json_to_yaml",
        "description": "Convert JSON data to YAML format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "json_data": {
                    "type": "string",
                    "description": "JSON data as string"
                }
            },
            "required": ["json_data"]
        }
    },
    {
        "name": "yaml_to_json",
        "description": "Convert YAML data to JSON format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "yaml_data": {
                    "type": "string",
                    "description": "YAML data as string"
                }
            },
            "required": ["yaml_data"]
        }
    },
    {
        "name": "xml_to_json",
        "description": "Convert XML data to JSON format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "xml_data": {
                    "type": "string",
                    "description": "XML data as string"
                }
            },
            "required": ["xml_data"]
        }
    },
    {
        "name": "clean_data",
        "description": "Clean CSV data with operations like removing duplicates, handling nulls, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV data as string"
                },
                "operations": {
                    "type": "array",
                    "description": "List of cleaning operations: remove_duplicates, remove_nulls, fill_nulls_zero, strip_whitespace, lowercase_columns",
                    "items": {
                        "type": "string",
                        "enum": ["remove_duplicates", "remove_nulls", "fill_nulls_zero", "strip_whitespace", "lowercase_columns"]
                    }
                }
            },
            "required": ["csv_data", "operations"]
        }
    },
    {
        "name": "merge_data",
        "description": "Merge two CSV datasets on a common column.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv1": {
                    "type": "string",
                    "description": "First CSV dataset"
                },
                "csv2": {
                    "type": "string",
                    "description": "Second CSV dataset"
                },
                "merge_column": {
                    "type": "string",
                    "description": "Column name to merge on (must exist in both datasets)"
                },
                "how": {
                    "type": "string",
                    "description": "Merge type: inner, left, right, outer",
                    "enum": ["inner", "left", "right", "outer"],
                    "default": "inner"
                }
            },
            "required": ["csv1", "csv2", "merge_column"]
        }
    },
    {
        "name": "filter_data",
        "description": "Filter CSV data based on a condition.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV data as string"
                },
                "column": {
                    "type": "string",
                    "description": "Column name to filter on"
                },
                "operator": {
                    "type": "string",
                    "description": "Comparison operator",
                    "enum": ["equals", "not_equals", "greater_than", "less_than", "contains"]
                },
                "value": {
                    "description": "Value to compare against (string or number)"
                }
            },
            "required": ["csv_data", "column", "operator", "value"]
        }
    },
    {
        "name": "get_stats",
        "description": "Get statistical summary of CSV data (row count, column types, basic statistics).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "csv_data": {
                    "type": "string",
                    "description": "CSV data as string"
                }
            },
            "required": ["csv_data"]
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
        if tool_name == "csv_to_json":
            result = data_manager.csv_to_json(arguments.get("csv_data", ""))

        elif tool_name == "json_to_csv":
            result = data_manager.json_to_csv(arguments.get("json_data", ""))

        elif tool_name == "json_to_yaml":
            result = data_manager.json_to_yaml(arguments.get("json_data", ""))

        elif tool_name == "yaml_to_json":
            result = data_manager.yaml_to_json(arguments.get("yaml_data", ""))

        elif tool_name == "xml_to_json":
            result = data_manager.xml_to_json(arguments.get("xml_data", ""))

        elif tool_name == "clean_data":
            result = data_manager.clean_data(
                arguments.get("csv_data", ""),
                arguments.get("operations", [])
            )

        elif tool_name == "merge_data":
            result = data_manager.merge_data(
                arguments.get("csv1", ""),
                arguments.get("csv2", ""),
                arguments.get("merge_column", ""),
                arguments.get("how", "inner")
            )

        elif tool_name == "filter_data":
            result = data_manager.filter_data(
                arguments.get("csv_data", ""),
                arguments.get("column", ""),
                arguments.get("operator", ""),
                arguments.get("value")
            )

        elif tool_name == "get_stats":
            result = data_manager.get_stats(arguments.get("csv_data", ""))

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

                # Add inline preview
                if result.get("preview"):
                    preview_text = f"\n📊 Preview:\n```\n{result['preview']['data']}\n```"
                    content.append({"type": "text", "text": preview_text})

                # Add statistics if present
                if result.get("stats"):
                    stats_text = "\n📈 Stats:\n" + "\n".join([f"  • {k}: {v}" for k, v in result["stats"].items()])
                    content.append({"type": "text", "text": stats_text})

                # Add S3 download link
                if result.get("s3_upload"):
                    s3_info = result["s3_upload"]
                    size_kb = s3_info.get('size_bytes', 0) // 1024
                    url = s3_info.get('presigned_url', '')
                    s3_text = f"\n\n💾 **Download Full File** ({size_kb} KB, expires in 24h):\n{url}"
                    content.append({"type": "text", "text": s3_text})

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
        "server": SERVER_INFO
    })


def main():
    """Main entry point"""
    global data_manager

    parser = argparse.ArgumentParser(description="Data Transformation MCP Server")
    parser.add_argument("--port", type=int, default=8889, help="Port to listen on (default: 8889)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--working-dir", type=str, default="/tmp", help="Working directory")
    args = parser.parse_args()

    print(f"Starting Data Transformation MCP Server v{SERVER_INFO['version']}")
    print(f"Working directory: {args.working_dir}")

    # Initialize data manager
    data_manager = DataManager(working_dir=args.working_dir)

    print(f"Server listening on http://{args.host}:{args.port}")
    print(f"MCP endpoint: http://{args.host}:{args.port}/mcp")
    print("\nAvailable tools:")
    for tool in TOOLS:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
