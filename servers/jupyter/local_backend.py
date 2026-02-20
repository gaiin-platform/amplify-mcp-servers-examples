"""
Minimal Local Backend for MCP Testing

This simulates the backend MCP endpoints for local development/testing.
Run this alongside the Jupyter MCP server to test the frontend end-to-end.

Usage:
  1. Start Jupyter MCP server: jupyter-mcp-server --port 8890
  2. Start this backend: python local_backend.py
  3. Set in frontend .env.local: NEXT_PUBLIC_LOCAL_SERVICES=websearch:3001
  4. Restart frontend and test MCP configuration

The frontend sends requests to: http://localhost:3001/dev/integrations/mcp/servers
"""

import json
import uuid
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# In-memory storage for MCP servers (simulates DynamoDB)
mcp_servers = {}


def get_user_id():
    """Extract user ID from request (simplified - real backend uses JWT)"""
    return "local-test-user"


def lzw_decompress(compressed_data):
    """LZW decompression matching frontend's lzwUncompress"""
    if not compressed_data or len(compressed_data) == 0:
        return ''

    dictionary = {i: chr(i) for i in range(256)}

    decompressed = ''
    previous_entry = dictionary.get(compressed_data[0], '')
    if not previous_entry:
        return ''

    decompressed += previous_entry
    next_code = 256

    for i in range(1, len(compressed_data)):
        current_code = compressed_data[i]

        if current_code in dictionary:
            current_entry = dictionary[current_code]
        elif current_code == next_code:
            current_entry = previous_entry + previous_entry[0]
        else:
            raise ValueError('Invalid compressed data')

        decompressed += current_entry
        dictionary[next_code] = previous_entry + current_entry[0]
        next_code += 1
        previous_entry = current_entry

    # Convert Unicode tags back to characters
    import re
    def unicode_replacer(match):
        return chr(int(match.group(1), 16))

    output = re.sub(r'U\+([0-9a-fA-F]{4})', unicode_replacer, decompressed)
    return output


def decode_payload(raw_data):
    """Decode the payload from frontend (handles LZW compression)"""
    if raw_data is None:
        return {}

    # The frontend wraps the payload as { data: <compressed> }
    data = raw_data.get('data') if isinstance(raw_data, dict) else raw_data

    if data is None:
        return raw_data if isinstance(raw_data, dict) else {}

    # Check if it's LZW compressed (array of numbers)
    if isinstance(data, list) and len(data) > 0 and all(isinstance(x, (int, float)) for x in data):
        try:
            decompressed = lzw_decompress(data)
            return json.loads(decompressed)
        except Exception as e:
            print(f"[DECODE] LZW decompression failed: {e}")
            return {}

    # Check if it's base64 encoded string
    if isinstance(data, str):
        try:
            import base64
            decoded = base64.b64decode(data).decode('utf-8')
            return json.loads(decoded)
        except:
            pass

    # Return as-is if it's already a dict
    if isinstance(data, dict):
        return data

    return {}


def encode_response(data):
    """Encode response in the format the frontend expects"""
    import base64
    return base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')


# ============== MCP Server Management Endpoints ==============

@app.route('/integrations/mcp/servers', methods=['GET'])
@app.route('/<stage>/integrations/mcp/servers', methods=['GET'])
def list_mcp_servers(stage=None):
    """List all MCP servers for the user"""
    user_id = get_user_id()
    user_servers = [s for s in mcp_servers.values() if s.get('userId') == user_id]
    return jsonify({
        "success": True,
        "data": user_servers
    })


@app.route('/integrations/mcp/servers', methods=['POST'])
@app.route('/<stage>/integrations/mcp/servers', methods=['POST'])
def add_mcp_server(stage=None):
    """Add a new MCP server"""
    user_id = get_user_id()
    raw_data = request.get_json()
    data = decode_payload(raw_data) if raw_data else {}

    server_id = str(uuid.uuid4())[:8]
    server = {
        "id": server_id,
        "userId": user_id,
        "name": data.get("name", "Unnamed Server"),
        "url": data.get("url"),
        "description": data.get("description", ""),
        "enabled": data.get("enabled", True),
        "tools": [],
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat()
    }

    mcp_servers[server_id] = server
    print(f"[ADD] Created server: {server_id} -> {server['name']} @ {server['url']}")

    return jsonify({
        "success": True,
        "data": server
    })


@app.route('/integrations/mcp/servers/<server_id>', methods=['PUT'])
@app.route('/<stage>/integrations/mcp/servers/<server_id>', methods=['PUT'])
def update_mcp_server(server_id, stage=None):
    """Update an MCP server"""
    if server_id not in mcp_servers:
        return jsonify({"success": False, "error": "Server not found"}), 404

    raw_data = request.get_json()
    data = decode_payload(raw_data) if raw_data else {}
    server = mcp_servers[server_id]

    for key in ["name", "url", "description", "enabled"]:
        if key in data:
            server[key] = data[key]

    server["updatedAt"] = datetime.utcnow().isoformat()
    print(f"[UPDATE] Server {server_id}: {data}")

    return jsonify({
        "success": True,
        "data": server
    })


@app.route('/integrations/mcp/servers/<server_id>', methods=['DELETE'])
@app.route('/<stage>/integrations/mcp/servers/<server_id>', methods=['DELETE'])
def delete_mcp_server(server_id, stage=None):
    """Delete an MCP server"""
    if server_id not in mcp_servers:
        return jsonify({"success": False, "error": "Server not found"}), 404

    del mcp_servers[server_id]
    print(f"[DELETE] Server {server_id}")

    return jsonify({"success": True})


@app.route('/integrations/mcp/servers/test', methods=['POST'])
@app.route('/<stage>/integrations/mcp/servers/test', methods=['POST'])
def test_mcp_connection(stage=None):
    """Test connection to an MCP server"""
    raw_data = request.get_json()
    data = decode_payload(raw_data) if raw_data else {}
    url = data.get("url")

    print(f"[TEST] Testing connection to: {url}")

    if not url:
        return jsonify({
            "success": False,
            "error": "URL is required"
        }), 400

    try:
        # Try to connect and initialize
        response = requests.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "amplify-test",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            },
            timeout=10
        )

        if response.status_code != 200:
            return jsonify({
                "success": False,
                "data": {"success": False, "error": f"Server returned status {response.status_code}"}
            })

        result = response.json()

        if "error" in result:
            return jsonify({
                "success": False,
                "data": {"success": False, "error": result["error"].get("message", "Unknown error")}
            })

        server_info = result.get("result", {}).get("serverInfo", {})
        print(f"[TEST] Success: {server_info}")

        return jsonify({
            "success": True,
            "data": {
                "success": True,
                "serverInfo": server_info,
                "protocolVersion": result.get("result", {}).get("protocolVersion")
            }
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "success": False,
            "data": {"success": False, "error": "Connection timeout"}
        })
    except requests.exceptions.ConnectionError as e:
        error_msg = str(e)
        if "Connection refused" in error_msg:
            error_msg = "Connection refused - is the MCP server running?"
        return jsonify({
            "success": False,
            "data": {"success": False, "error": error_msg}
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "data": {"success": False, "error": str(e)}
        })


@app.route('/integrations/mcp/servers/<server_id>/tools', methods=['GET'])
@app.route('/<stage>/integrations/mcp/servers/<server_id>/tools', methods=['GET'])
def get_mcp_server_tools(server_id, stage=None):
    """Get tools from an MCP server"""
    if server_id not in mcp_servers:
        return jsonify({"success": False, "error": "Server not found"}), 404

    server = mcp_servers[server_id]
    url = server.get("url")

    if not url:
        return jsonify({
            "success": False,
            "error": "Server URL not configured"
        })

    try:
        print(f"[TOOLS] Getting tools from: {url}")
        response = requests.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 1
            },
            timeout=10
        )

        result = response.json()
        tools = result.get("result", {}).get("tools", [])

        # Update server with tools
        server["tools"] = tools
        server["updatedAt"] = datetime.utcnow().isoformat()
        print(f"[TOOLS] Found {len(tools)} tools")

        return jsonify({
            "success": True,
            "data": tools
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route('/integrations/mcp/servers/<server_id>/refresh', methods=['POST'])
@app.route('/<stage>/integrations/mcp/servers/<server_id>/refresh', methods=['POST'])
def refresh_mcp_server_tools(server_id, stage=None):
    """Refresh tools from an MCP server"""
    result = get_mcp_server_tools(server_id, stage)
    # Convert response format for refresh endpoint
    response_data = result.get_json()
    if response_data.get("success") and "data" in response_data:
        response_data["data"] = {"tools": response_data["data"]}
    return jsonify(response_data)


@app.route('/integrations/mcp/call', methods=['POST'])
@app.route('/<stage>/integrations/mcp/call', methods=['POST'])
def call_mcp_tool(stage=None):
    """Call a tool on an MCP server"""
    raw_data = request.get_json()
    data = decode_payload(raw_data) if raw_data else {}
    server_id = data.get("serverId")
    tool_name = data.get("toolName")
    arguments = data.get("arguments", {})

    print(f"[CALL] Server: {server_id}, Tool: {tool_name}")

    if server_id not in mcp_servers:
        return jsonify({"success": False, "error": "Server not found"}), 404

    server = mcp_servers[server_id]
    url = server.get("url")

    try:
        response = requests.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": 1
            },
            timeout=120  # Longer timeout for code execution
        )

        result = response.json()

        if "error" in result:
            return jsonify({
                "success": False,
                "error": result["error"].get("message", "Unknown error")
            })

        print(f"[CALL] Success")
        return jsonify({
            "success": True,
            "data": result.get("result", {})
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "local-mcp-backend"})


if __name__ == '__main__':
    print("="*60)
    print("Local MCP Backend Server for Testing")
    print("="*60)
    print()
    print("To use this with the frontend:")
    print()
    print("  1. Start the Jupyter MCP server:")
    print("     cd /home/jaggu/work/vanderbilt/jupyter-mcp-server")
    print("     source venv/bin/activate")
    print("     jupyter-mcp-server --port 8890")
    print()
    print("  2. Start this local backend (in another terminal):")
    print("     cd /home/jaggu/work/vanderbilt/jupyter-mcp-server")
    print("     source venv/bin/activate")
    print("     python local_backend.py")
    print()
    print("  3. Add to frontend .env.local:")
    print("     NEXT_PUBLIC_LOCAL_SERVICES=websearch:3001")
    print()
    print("  4. Restart the frontend (npm run dev)")
    print()
    print("  5. Go to Settings -> MCP Servers and add:")
    print("     URL: http://localhost:8890/mcp")
    print()
    print("="*60)
    print(f"Server listening on http://localhost:3002")
    print("="*60)

    app.run(host='0.0.0.0', port=3002, debug=False)
