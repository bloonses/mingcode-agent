# tools/computer_use.py
"""桌面控制工具 - 截屏 + 鼠标键盘（简化版，复用 NeonAgent 逻辑）。"""
import os
import tempfile
import time
from langchain_core.tools import tool
from pydantic import BaseModel, Field

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False


@tool
def computer_screenshot() -> str:
    """Take a screenshot and return file path."""
    if not PYAUTOGUI_AVAILABLE:
        return "Error: pyautogui not installed. Run: pip install pyautogui Pillow"
    try:
        temp_path = os.path.join(tempfile.gettempdir(), f"mingcode_shot_{int(time.time())}.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(temp_path)
        return f"Screenshot saved: {temp_path}"
    except Exception as e:
        return f"Error: {e}"


class ClickInput(BaseModel):
    x: int = Field(description="X coordinate")
    y: int = Field(description="Y coordinate")


@tool(args_schema=ClickInput)
def computer_click(x: int, y: int) -> str:
    """Click at the given coordinates."""
    if not PYAUTOGUI_AVAILABLE:
        return "Error: pyautogui not installed"
    try:
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error: {e}"


class TypeInput(BaseModel):
    text: str = Field(description="Text to type")


@tool(args_schema=TypeInput)
def computer_type(text: str) -> str:
    """Type the given text."""
    if not PYAUTOGUI_AVAILABLE:
        return "Error: pyautogui not installed"
    try:
        pyautogui.typewrite(text)
        return f"Typed: {text}"
    except Exception as e:
        return f"Error: {e}"
