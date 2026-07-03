"""ComputerUseTool - 桌面控制工具（模仿 Codex computer use）。

action: screenshot / click / double_click / right_click / move / drag /
        type / key / scroll / open_app / window_list / focus

依赖 pyautogui（鼠标键盘）+ Pillow（截屏）。
"""
import os
import time
from typing import Optional, List

from .base import BaseTool


# 可选依赖，运行时检测
try:
    import pyautogui
    pyautogui_available = True
except ImportError:
    pyautogui_available = False

try:
    from PIL import ImageGrab
    pil_available = True
except ImportError:
    pil_available = False


# 安全键白名单（避免 LLM 乱按系统组合键）
_SAFE_KEYS = {
    "enter", "tab", "escape", "backspace", "delete", "space",
    "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown",
    "ctrl", "alt", "shift", "win",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
}


class ComputerUseTool(BaseTool):
    def __init__(self, llm_client=None):
        """llm_client 可选。若注入则 screenshot action 会调 vision；
        若不注入（None）则 screenshot 返回 placeholder 描述。"""
        self.llm_client = llm_client

    name = "computer"
    description = (
        "桌面控制（模仿 Codex computer use）。支持 action："
        "screenshot（截屏，保存到 user_data_dir，返回路径）/ "
        "click / double_click / right_click（需 x, y 坐标）/ "
        "move（移动鼠标到 x,y）/ "
        "drag（从 x1,y1 拖到 x2,y2）/ "
        "type（输入文本，需 text）/ "
        "key（按键组合，如 'ctrl+c'，需 keys）/ "
        "scroll（滚动，需 clicks 正负数）/ "
        "open_app（启动程序，需 name）/ "
        "window_list（列出当前打开窗口）/ "
        "focus（聚焦窗口，需 title）。"
        "所有写操作执行前会确认。需安装 pyautogui 和 Pillow。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "screenshot", "click", "double_click", "right_click",
                    "move", "drag", "type", "key", "scroll",
                    "open_app", "window_list", "focus"
                ],
                "description": "操作类型"
            },
            "x": {"type": "integer", "description": "X 坐标（点击/移动目标，或区域截屏左上角）"},
            "y": {"type": "integer", "description": "Y 坐标（点击/移动目标，或区域截屏左上角）"},
            "w": {"type": "integer", "description": "区域截屏宽度（与 x/y/h 一起使用）"},
            "h": {"type": "integer", "description": "区域截屏高度（与 x/y/w 一起使用）"},
            "x1": {"type": "integer", "description": "drag 起点 X"},
            "y1": {"type": "integer", "description": "drag 起点 Y"},
            "x2": {"type": "integer", "description": "drag 终点 X"},
            "y2": {"type": "integer", "description": "drag 终点 Y"},
            "text": {"type": "string", "description": "action=type 时要输入的文本"},
            "keys": {"type": "string", "description": "action=key 时按键组合如 'ctrl+c' 或 'enter'"},
            "clicks": {"type": "integer", "description": "action=scroll 时滚动次数，正向上负向下"},
            "name": {"type": "string", "description": "action=open_app 时程序名称"},
            "title": {"type": "string", "description": "action=focus 时窗口标题（部分匹配）"}
        },
        "required": ["action"]
    }

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()

        # 截屏不需要 pyautogui，只要 PIL
        if action == "screenshot":
            return self._screenshot(
                x=kwargs.get("x"),
                y=kwargs.get("y"),
                w=kwargs.get("w"),
                h=kwargs.get("h"),
            )

        if not pyautogui_available:
            return "Error: pyautogui not installed. Run: pip install pyautogui"

        if action in ("click", "double_click", "right_click"):
            return self._click(action, kwargs.get("x"), kwargs.get("y"))
        if action == "move":
            return self._move(kwargs.get("x"), kwargs.get("y"))
        if action == "drag":
            return self._drag(kwargs.get("x1"), kwargs.get("y1"), kwargs.get("x2"), kwargs.get("y2"))
        if action == "type":
            return self._type(kwargs.get("text"))
        if action == "key":
            return self._key(kwargs.get("keys"))
        if action == "scroll":
            return self._scroll(kwargs.get("clicks"))
        if action == "open_app":
            return self._open_app(kwargs.get("name"))
        if action == "window_list":
            return self._window_list()
        if action == "focus":
            return self._focus(kwargs.get("title"))
        return f"Error: unknown action '{action}'"

    def _screenshot(self, x=None, y=None, w=None, h=None) -> str:
        if not pil_available:
            return "Error: Pillow not installed. Run: pip install Pillow"
        try:
            from config.config import get_user_data_dir
            from ui.console import print_screenshot_thumbnail

            # 判断是否为区域截屏（四参数全有且为正）
            is_region = all(v is not None and v >= 0 for v in (x, y, w, h)) and (w or 0) > 0 and (h or 0) > 0
            if is_region:
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox=bbox)
                region_desc = f"region ({x},{y}) {w}x{h}"
            elif any(v is not None for v in (x, y, w, h)) and not is_region:
                # 部分参数缺失，降级为全屏
                img = ImageGrab.grab()
                region_desc = "fullscreen (region params incomplete, fell back)"
            else:
                img = ImageGrab.grab()
                region_desc = "fullscreen"

            shots_dir = get_user_data_dir() / "screenshots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            filename = f"shot_{int(time.time())}.png"
            filepath = shots_dir / filename
            img.save(str(filepath))

            # 渲染终端缩略图（失败不影响主流程）
            try:
                print_screenshot_thumbnail(str(filepath))
            except Exception as thumb_err:
                # 缩略图渲染失败仅打印提示，不抛
                try:
                    from ui.console import console
                    console.print(f"[thumbnail render failed: {thumb_err}]", markup=False)
                except Exception:
                    pass

            # 调用 vision LLM 分析画面（失败降级为提示，不影响截屏结果）
            if self.llm_client is not None:
                try:
                    from core.llm import LLMError
                    vision_prompt = (
                        f"描述这个屏幕截图（{region_desc}）的主要元素："
                        f"窗口布局、可见文本、可点击元素的位置"
                    )
                    description = self.llm_client.chat_with_image(
                        prompt=vision_prompt,
                        image_path=str(filepath),
                    )
                    vision_section = f"Vision analysis:\n{description}"
                except LLMError as e:
                    vision_section = f"Vision analysis:\n(vision unavailable: {e})"
                except Exception as e:
                    vision_section = f"Vision analysis:\n(vision error: {e})"
            else:
                vision_section = "Vision analysis:\n(llm_client not configured)"

            return (
                f"Screenshot saved: {filepath}\n"
                f"Size: {img.size[0]}x{img.size[1]}\n"
                f"Region: {region_desc}\n\n"
                f"{vision_section}"
            )
        except Exception as e:
            return f"Error: {e}"

    def _confirm(self, msg: str) -> bool:
        try:
            ans = input(f"\nConfirm: {msg}? [y/N] ").strip().lower()
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _click(self, action: str, x, y) -> str:
        if x is None or y is None:
            return "Error: x and y are required for click actions"
        if not self._confirm(f"{action} at ({x}, {y})"):
            return "Cancelled."
        try:
            pyautogui.click(x, y)
            if action == "double_click":
                pyautogui.doubleClick(x, y)
            elif action == "right_click":
                pyautogui.rightClick(x, y)
            return f"{action} at ({x}, {y})"
        except Exception as e:
            return f"Error: {e}"

    def _move(self, x, y) -> str:
        if x is None or y is None:
            return "Error: x and y are required for move"
        try:
            pyautogui.moveTo(x, y, duration=0.3)
            return f"Moved to ({x}, {y})"
        except Exception as e:
            return f"Error: {e}"

    def _drag(self, x1, y1, x2, y2) -> str:
        if None in (x1, y1, x2, y2):
            return "Error: x1, y1, x2, y2 are required for drag"
        if not self._confirm(f"drag ({x1},{y1}) -> ({x2},{y2})"):
            return "Cancelled."
        try:
            pyautogui.moveTo(x1, y1, duration=0.2)
            pyautogui.dragTo(x2, y2, duration=0.5)
            return f"Dragged ({x1},{y1}) -> ({x2},{y2})"
        except Exception as e:
            return f"Error: {e}"

    def _type(self, text: Optional[str]) -> str:
        if not text:
            return "Error: text is required for type action"
        if not self._confirm(f"type '{text[:40]}...'"):
            return "Cancelled."
        try:
            pyautogui.typewrite(text, interval=0.02) if text.isascii() else self._type_unicode(text)
            return f"Typed {len(text)} chars"
        except Exception as e:
            return f"Error: {e}"

    def _type_unicode(self, text: str) -> None:
        """中文等非 ASCII 文本用剪贴板粘贴。"""
        import subprocess
        subprocess.run(["clip"], input=text.encode("utf-16-le"), check=False)
        pyautogui.hotkey("ctrl", "v")

    def _key(self, keys: Optional[str]) -> str:
        if not keys:
            return "Error: keys is required for key action"
        keys_lower = keys.lower().strip()
        # 校验键
        parts = [k.strip() for k in keys_lower.split("+")]
        for p in parts:
            if p not in _SAFE_KEYS and not (len(p) == 1 and p.isalnum()):
                return f"Error: disallowed key '{p}'. Safe keys: {sorted(_SAFE_KEYS)} + single chars"
        if not self._confirm(f"press {keys}"):
            return "Cancelled."
        try:
            if len(parts) == 1:
                pyautogui.press(parts[0])
            else:
                pyautogui.hotkey(*parts)
            return f"Pressed: {keys}"
        except Exception as e:
            return f"Error: {e}"

    def _scroll(self, clicks) -> str:
        if clicks is None:
            return "Error: clicks is required for scroll (positive=up, negative=down)"
        try:
            pyautogui.scroll(int(clicks))
            return f"Scrolled {clicks} clicks"
        except Exception as e:
            return f"Error: {e}"

    def _open_app(self, name: Optional[str]) -> str:
        if not name:
            return "Error: name is required for open_app"
        if not self._confirm(f"open app '{name}'"):
            return "Cancelled."
        try:
            import subprocess
            if os.name == "nt":
                subprocess.Popen(["start", "", name], shell=True)
            else:
                subprocess.Popen([name])
            return f"Launched: {name}"
        except Exception as e:
            return f"Error: {e}"

    def _window_list(self) -> str:
        try:
            import pygetwindows as gw
            windows = gw.getAllWindows()
            lines = []
            for w in windows[:20]:
                if w.title:
                    lines.append(f"- {w.title[:80]}  ({w.left},{w.top} {w.width}x{w.height})")
            return "\n".join(lines) if lines else "(no windows)"
        except ImportError:
            return "Error: pygetwindows not installed. Run: pip install pygetwindows"
        except Exception as e:
            return f"Error: {e}"

    def _focus(self, title: Optional[str]) -> str:
        if not title:
            return "Error: title is required for focus"
        try:
            import pygetwindows as gw
            matches = [w for w in gw.getWindowsWithTitle(title) if w.title]
            if not matches:
                return f"No window found matching '{title}'"
            w = matches[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            return f"Focused: {w.title}"
        except ImportError:
            return "Error: pygetwindows not installed. Run: pip install pygetwindows"
        except Exception as e:
            return f"Error: {e}"
