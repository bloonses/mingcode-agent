"""Git 版本控制工具。"""
import subprocess
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GitCommandInput(BaseModel):
    args: str = Field(description="Git args (e.g. 'status', 'log --oneline -5', 'add .')")


@tool
def git_status() -> str:
    """Run git status and return output."""
    try:
        result = subprocess.run(["git", "status"], capture_output=True, text=True, timeout=10)
        return result.stdout or result.stderr or "(no output)"
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=GitCommandInput)
def git_command(args: str) -> str:
    """Run a git command (e.g. 'log --oneline -5', 'add .', 'commit -m \"msg\"'). Does NOT support push/force."""
    forbidden = ["push", "force", "reset --hard", "clean -f"]
    for word in forbidden:
        if word in args:
            return f"Error: Forbidden git operation: {word}"
    try:
        cmd = ["git"] + args.split()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout or result.stderr or "(no output)"
    except Exception as e:
        return f"Error: {e}"
