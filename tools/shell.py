"""Shell 命令执行工具。"""
import subprocess
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ShellInput(BaseModel):
    command: str = Field(description="Shell command to execute")


@tool(args_schema=ShellInput)
def shell(command: str) -> str:
    """Execute shell command and return stdout/stderr."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr] {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code] {result.returncode}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (30s)"
    except Exception as e:
        return f"Error: {e}"
