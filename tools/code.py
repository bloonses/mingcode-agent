"""Python 代码执行工具。"""
import subprocess
import sys
import tempfile
import os
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class PythonExecInput(BaseModel):
    code: str = Field(description="Python code to execute")


@tool(args_schema=PythonExecInput)
def python_exec(code: str) -> str:
    """Execute Python code and return output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr] {result.stderr}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Python code timed out (10s)"
    except Exception as e:
        return f"Error: {e}"
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
