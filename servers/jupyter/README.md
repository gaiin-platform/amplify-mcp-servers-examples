# Jupyter MCP Server

A Model Context Protocol (MCP) server that provides Jupyter kernel capabilities for LLM interactions.

## Features

- Execute Python code with rich outputs (text, images, plots)
- Create and read Jupyter notebooks
- Inspect variables and kernel state
- Install Python packages on the fly

## Installation

```bash
pip install -e .
```

## Usage

```bash
jupyter-mcp-server --port 8888
```

The server will start listening on `http://localhost:8888/mcp`.

## Available Tools

| Tool | Description |
|------|-------------|
| `execute_code` | Execute Python code and return output |
| `get_kernel_status` | Get current kernel status |
| `restart_kernel` | Restart the kernel to clear state |
| `get_variables` | List variables in kernel namespace |
| `inspect_variable` | Get detailed info about a variable |
| `install_package` | Install a Python package via pip |
| `create_notebook` | Create a new .ipynb notebook |
| `read_notebook` | Read contents of a notebook file |

## Configuration

- `--port`: Port to listen on (default: 8888)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--working-dir`: Working directory for notebooks (default: current directory)

## MCP Protocol

This server implements the Model Context Protocol (MCP) over HTTP JSON-RPC 2.0.
Compatible with any MCP client that supports HTTP transport.
