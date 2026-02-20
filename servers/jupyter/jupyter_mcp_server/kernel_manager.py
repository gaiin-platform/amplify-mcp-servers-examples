"""
Jupyter Kernel Manager

Manages a Jupyter kernel for code execution and notebook operations.
"""

import base64
import json
import os
import queue
import time
import nbformat
from jupyter_client import KernelManager
from .s3_workspace import S3WorkspaceManager


class JupyterKernelManager:
    """Manages a Jupyter kernel for code execution"""

    def __init__(self, working_dir=".", s3_bucket=None, enable_s3=False):
        """Initialize Jupyter Kernel Manager

        Args:
            working_dir: Base working directory (default: current directory)
            s3_bucket: S3 bucket name for file persistence (optional)
            enable_s3: Enable S3 workspace features (default: False)
        """
        self.base_working_dir = os.path.abspath(working_dir)
        self.enable_s3 = enable_s3 and s3_bucket is not None
        self.s3_workspace = None

        # Setup workspace
        if self.enable_s3:
            # Create S3 workspace with random session directory
            self.s3_workspace = S3WorkspaceManager(bucket_name=s3_bucket, base_path=self.base_working_dir)
            self.working_dir = self.s3_workspace.create_workspace()
            print(f"S3 workspace enabled: session {self.s3_workspace.session_id}")
        else:
            # Use regular working directory
            self.working_dir = self.base_working_dir
            os.makedirs(self.working_dir, exist_ok=True)

        self.km = None
        self.kc = None
        self._initialize_kernel()

    def _initialize_kernel(self):
        """Initialize the Jupyter kernel"""
        try:
            self.km = KernelManager(kernel_name="python3")
            self.km.start_kernel(cwd=self.working_dir)
            self.kc = self.km.client()
            self.kc.start_channels()
            self.kc.wait_for_ready(timeout=30)
            # Enable matplotlib inline mode for plot capture
            self._setup_matplotlib_inline()
            print("Jupyter kernel started successfully")
        except Exception as e:
            print(f"Failed to start kernel: {e}")
            raise

    def _setup_matplotlib_inline(self):
        """Configure matplotlib for inline display with PNG output"""
        setup_code = """
import warnings
warnings.filterwarnings('ignore')
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from IPython import get_ipython
    ipython = get_ipython()
    if ipython:
        ipython.run_line_magic('matplotlib', 'inline')
    # Configure matplotlib for high-quality PNG output
    import matplotlib as mpl
    mpl.rcParams['figure.dpi'] = 100
    mpl.rcParams['savefig.dpi'] = 100
    mpl.rcParams['figure.figsize'] = [8.0, 6.0]
except ImportError:
    pass
"""
        # Execute silently
        self.kc.execute(setup_code, silent=True)
        # Wait for completion
        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=5)
                if msg["msg_type"] == "status" and msg["content"].get("execution_state") == "idle":
                    break
            except queue.Empty:
                break

    def get_status(self):
        """Get kernel status"""
        if self.km is None or not self.km.is_alive():
            return {"status": "dead", "alive": False}

        status = {
            "status": "running",
            "alive": True,
            "kernel_name": "python3",
            "working_dir": self.working_dir,
            "s3_enabled": self.enable_s3
        }

        if self.enable_s3 and self.s3_workspace:
            status["session_info"] = self.s3_workspace.get_session_info()

        return status

    def restart(self):
        """Restart the kernel"""
        try:
            if self.km:
                self.km.restart_kernel(now=True)
                self.kc.wait_for_ready(timeout=30)
            else:
                self._initialize_kernel()

            return {"success": True, "message": "Kernel restarted successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_code(self, code, timeout=60):
        """Execute Python code and return the result"""
        if not self.km or not self.km.is_alive():
            return {"success": False, "error": "Kernel is not running"}

        try:
            # Execute the code
            msg_id = self.kc.execute(code)

            # Collect outputs
            outputs = []
            images = []
            errors = []

            start_time = time.time()

            while True:
                if time.time() - start_time > timeout:
                    return {"success": False, "error": f"Execution timeout after {timeout} seconds"}

                try:
                    msg = self.kc.get_iopub_msg(timeout=1)
                except queue.Empty:
                    continue

                msg_type = msg["msg_type"]
                content = msg["content"]

                if msg_type == "status" and content.get("execution_state") == "idle":
                    break

                elif msg_type == "stream":
                    outputs.append(content.get("text", ""))

                elif msg_type == "execute_result":
                    data = content.get("data", {})
                    if "text/plain" in data:
                        outputs.append(data["text/plain"])
                    if "text/html" in data:
                        outputs.append(f"[HTML Output]\n{data['text/html'][:500]}...")
                    if "image/png" in data:
                        images.append({
                            "data": data["image/png"],
                            "mimeType": "image/png"
                        })

                elif msg_type == "display_data":
                    data = content.get("data", {})
                    if "text/plain" in data:
                        outputs.append(data["text/plain"])
                    if "text/html" in data:
                        outputs.append(f"[HTML Output]\n{data['text/html'][:500]}...")
                    if "image/png" in data:
                        images.append({
                            "data": data["image/png"],
                            "mimeType": "image/png"
                        })
                    if "image/svg+xml" in data:
                        # Convert SVG to base64
                        svg_data = data["image/svg+xml"]
                        images.append({
                            "data": base64.b64encode(svg_data.encode()).decode(),
                            "mimeType": "image/svg+xml"
                        })

                elif msg_type == "error":
                    errors.append("\n".join(content.get("traceback", [])))

            if errors:
                return {
                    "success": False,
                    "error": "\n".join(errors),
                    "output": "\n".join(outputs) if outputs else None
                }

            result = {
                "success": True,
                "output": "\n".join(outputs) if outputs else "Code executed successfully (no output)",
                "images": images if images else None
            }

            # Upload created files to S3 if enabled
            if self.enable_s3 and self.s3_workspace:
                try:
                    uploaded_files = self.s3_workspace.upload_workspace_files()
                    if uploaded_files:
                        result["uploaded_files"] = uploaded_files
                        print(f"Uploaded {len(uploaded_files)} file(s) to S3")
                except Exception as e:
                    print(f"Warning: Failed to upload files to S3: {e}")
                    result["s3_upload_error"] = str(e)

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_variables(self):
        """Get list of variables in the kernel namespace"""
        code = """
import json
_vars = {}
for _name in dir():
    if not _name.startswith('_'):
        try:
            _obj = eval(_name)
            _type = type(_obj).__name__
            if _type in ('int', 'float', 'str', 'bool', 'list', 'dict', 'tuple', 'set'):
                _vars[_name] = {'type': _type, 'value': repr(_obj)[:100]}
            elif hasattr(_obj, 'shape'):
                _vars[_name] = {'type': _type, 'shape': str(_obj.shape)}
            elif hasattr(_obj, '__len__'):
                _vars[_name] = {'type': _type, 'length': len(_obj)}
            else:
                _vars[_name] = {'type': _type}
        except:
            pass
print(json.dumps(_vars))
"""
        result = self.execute_code(code, timeout=10)

        if result.get("success") and result.get("output"):
            try:
                variables = json.loads(result["output"].strip())
                return {"success": True, "result": variables}
            except json.JSONDecodeError:
                return {"success": True, "result": {}}

        return result

    def inspect_variable(self, name):
        """Get detailed info about a variable"""
        code = f"""
import json
try:
    _obj = {name}
    _info = {{
        'name': '{name}',
        'type': type(_obj).__name__,
        'repr': repr(_obj)[:500]
    }}
    if hasattr(_obj, 'shape'):
        _info['shape'] = str(_obj.shape)
    if hasattr(_obj, 'dtype'):
        _info['dtype'] = str(_obj.dtype)
    if hasattr(_obj, '__len__'):
        _info['length'] = len(_obj)
    if hasattr(_obj, 'columns'):
        _info['columns'] = list(_obj.columns)[:20]
    if hasattr(_obj, 'head'):
        _info['head'] = _obj.head().to_string()
    print(json.dumps(_info))
except Exception as e:
    print(json.dumps({{'error': str(e)}}))
"""
        result = self.execute_code(code, timeout=10)

        if result.get("success") and result.get("output"):
            try:
                info = json.loads(result["output"].strip())
                if "error" in info:
                    return {"success": False, "error": info["error"]}
                return {"success": True, "result": info}
            except json.JSONDecodeError:
                return {"success": True, "result": result["output"]}

        return result

    def install_package(self, package):
        """Install a Python package"""
        code = f"!pip install {package}"
        return self.execute_code(code, timeout=120)

    def create_notebook(self, filename, cells):
        """Create a new Jupyter notebook"""
        try:
            # Handle case where cells might be a JSON string (double-encoded)
            if isinstance(cells, str):
                try:
                    cells = json.loads(cells)
                except json.JSONDecodeError:
                    return {"success": False, "error": "Invalid cells format: expected array"}

            # Create notebook structure
            nb = nbformat.v4.new_notebook()

            for cell in cells:
                # Handle case where individual cell might be a JSON string
                if isinstance(cell, str):
                    try:
                        cell = json.loads(cell)
                    except json.JSONDecodeError:
                        # Treat as code cell with the string as source
                        cell = {"type": "code", "source": cell}
                cell_type = cell.get("type", "code")
                source = cell.get("source", "")

                if cell_type == "markdown":
                    nb.cells.append(nbformat.v4.new_markdown_cell(source))
                else:
                    nb.cells.append(nbformat.v4.new_code_cell(source))

            # Ensure filename has .ipynb extension
            if not filename.endswith(".ipynb"):
                filename += ".ipynb"

            filepath = os.path.join(self.working_dir, filename)

            # Write the notebook
            with open(filepath, "w") as f:
                nbformat.write(nb, f)

            result = {
                "success": True,
                "message": f"Notebook created: {filepath}",
                "result": {"path": filepath, "cells": len(cells)}
            }

            # Upload notebook to S3 if enabled
            if self.enable_s3 and self.s3_workspace:
                try:
                    # Get relative path from workspace
                    relpath = os.path.relpath(filepath, self.working_dir)
                    upload_result = self.s3_workspace.upload_file_to_s3(filepath)
                    result["s3_upload"] = upload_result
                    print(f"Uploaded notebook to S3: {upload_result['s3_uri']}")
                except Exception as e:
                    print(f"Warning: Failed to upload notebook to S3: {e}")
                    result["s3_upload_error"] = str(e)

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_notebook(self, filename):
        """Read a Jupyter notebook"""
        try:
            filepath = filename
            if not os.path.isabs(filepath):
                filepath = os.path.join(self.working_dir, filename)

            with open(filepath, "r") as f:
                nb = nbformat.read(f, as_version=4)

            cells_info = []
            for i, cell in enumerate(nb.cells):
                cell_info = {
                    "index": i,
                    "type": cell.cell_type,
                    "source": cell.source[:500] + ("..." if len(cell.source) > 500 else "")
                }

                # Include outputs for code cells
                if cell.cell_type == "code" and hasattr(cell, "outputs"):
                    outputs = []
                    for output in cell.outputs:
                        if output.output_type == "stream":
                            outputs.append({"type": "stream", "text": output.get("text", "")[:200]})
                        elif output.output_type == "execute_result":
                            outputs.append({"type": "result", "data": str(output.get("data", {}))[:200]})
                        elif output.output_type == "error":
                            outputs.append({"type": "error", "ename": output.get("ename", "")})
                    cell_info["outputs"] = outputs

                cells_info.append(cell_info)

            return {
                "success": True,
                "result": {
                    "path": filepath,
                    "cell_count": len(nb.cells),
                    "cells": cells_info
                }
            }

        except FileNotFoundError:
            return {"success": False, "error": f"Notebook not found: {filename}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shutdown(self):
        """Shutdown the kernel and cleanup workspace"""
        if self.km:
            self.km.shutdown_kernel(now=True)
            print("Kernel shutdown complete")

        # Cleanup S3 workspace
        if self.enable_s3 and self.s3_workspace:
            self.s3_workspace.cleanup_workspace()
            print("S3 workspace cleaned up")
