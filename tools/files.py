"""文件读写工具。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class FileReadInput(BaseModel):
    path: str = Field(description="File path to read")


class FileWriteInput(BaseModel):
    path: str = Field(description="File path to write")
    content: str = Field(description="Content to write")


@tool(args_schema=FileReadInput)
def file_read(path: str) -> str:
    """Read file content as text."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=FileWriteInput)
def file_write(path: str, content: str) -> str:
    """Write content to file (overwrite)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入 {path}"
    except Exception as e:
        return f"Error: {e}"
