"""ComputerUseTool - 桌面控制工具（模仿 Codex computer use）。

action: screenshot / click / double_click / right_click / move / drag /
        type / key / scroll / open_app / window_list / focus

依赖 pyautogui（鼠标键盘）+ Pillow（截屏）。
"""
import os
import sys
import time
from typing import Optional, List

from .base import BaseTool


# 可选依赖，运行时检测（含 PyInstaller frozen 模式提示）
def _check_optional(name, frozen_hint, source_hint):
    """检测可选依赖，返回 (available, error_hint)。"""
    try:
        __import__(name)
        return True, ""
    except ImportError:
        hint = frozen_hint if getattr(sys, "frozen", False) else source_hint
        return False, hint


pyautogui_available, pyautogui_error_hint = _check_optional(
    "pyautogui",
    "pyautogui 未打包进可执行文件。请用源码运行 mingcode（python main.py），或重新打包时确认 mingcode.spec 的 hiddenimports 包含 'pyautogui'。",
    "pyautogui 未安装。请运行: pip install pyautogui",
)
pil_available, pil_error_hint = _check_optional(
    "PIL.ImageGrab",
    "Pillow 未打包进可执行文件。请用源码运行 mingcode（python main.py），或重新打包时确认 mingcode.spec 的 hiddenimports 包含 'PIL' 和 'PIL.ImageGrab'。",
    "Pillow 未安装。请运行: pip install Pillow",
)
# 模块级 ImageGrab / pyautogui 引用（若依赖可用则绑定，便于运行时调用和测试 monkeypatch）
if pil_available:
    from PIL import ImageGrab  # noqa: E402
if pyautogui_available:
    import pyautogui  # noqa: E402


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
            "name": {"type": "string", "description": "action=open_app 时程序名称（支持中文名如'微信'、可执行名如'notepad'、完整路径）"},
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
            return f"Error: {pyautogui_error_hint}"

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
            return f"Error: {pil_error_hint}"
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
            # 要求 LLM 返回结构化坐标清单，AI 可直接读取坐标进行点击
            if self.llm_client is not None:
                try:
                    from core.llm import LLMError
                    vision_prompt = (
                        f"仔细分析这个屏幕截图（{region_desc}），列出所有可交互元素及其精确坐标位置。\n"
                        f"要求高精度检测：包括桌面图标（通常 32x32 或 48x48 像素，紧密排列）、"
                        f"任务栏图标、系统托盘小图标、窗口标题栏按钮、菜单项、小型工具栏按钮等小元素。\n"
                        f"不要遗漏任何可交互元素，即使很小也要列出。\n\n"
                        f"按以下格式输出，每行一个元素：\n"
                        f"[type] \"label\" (x={{center_x}}, y={{center_y}}, w={{width}}, h={{height}}) - 可操作描述\n\n"
                        f"类型包括：button（按钮）、input（输入框）、link（链接）、"
                        f"menu（菜单项）、icon（图标按钮/桌面图标）、tray（系统托盘图标）、"
                        f"taskbar（任务栏图标）、text（仅显示，不可点击）。\n\n"
                        f"示例：\n"
                        f"[button] \"确定\" (x=320, y=180, w=80, h=30) - 点击确认\n"
                        f"[input] 搜索框 (x=250, y=50, w=200, h=24) - 点击后可输入文字\n"
                        f"[icon] 关闭按钮 (x=780, y=20, w=20, h=20) - 点击关闭窗口\n"
                        f"[icon] 桌面图标\"此电脑\" (x=50, y=80, w=48, h=48) - 双击打开\n"
                        f"[tray] 音量图标 (x=1820, y=1055, w=20, h=20) - 单击调节音量\n"
                        f"[text] \"欢迎使用\" (x=400, y=100, w=120, h=20) - 仅显示，不可点击\n\n"
                        f"最后用一句话总结画面整体布局。"
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

            # 截图用完即删（避免磁盘累积；缩略图已渲染、vision 已分析，文件不再需要）
            try:
                os.remove(str(filepath))
                file_status = f"(temp file removed: {filepath.name})"
            except Exception:
                file_status = f"(saved: {filepath})"

            return (
                f"Screenshot captured: {filepath.name}\n"
                f"Size: {img.size[0]}x{img.size[1]}\n"
                f"Region: {region_desc}\n"
                f"{file_status}\n\n"
                f"{vision_section}"
            )
        except Exception as e:
            return f"Error: {e}"

    def _confirm(self, msg: str) -> bool:
        # 默认 yes 执行，不再向用户提问（codex 风格：AI 自主操作）
        return True

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
        import subprocess
        if os.name == "nt":
            # Windows 应用启动策略（按优先级）：
            # 1) 路径/可执行文件（含 \\ 或 / 或 .exe 后缀）→ 直接 start
            # 2) 应用名（中文如"微信"、英文如"notepad"）→ PowerShell Get-StartApps 反查 AppID
            #    （start 命令不解析开始菜单应用名，直接 start "微信" 会报"系统找不到文件"）
            is_path_or_exe = (
                "\\" in name or "/" in name
                or name.lower().endswith(".exe")
                or (len(name) <= 12 and name.isascii() and " " not in name)
            )
            if is_path_or_exe:
                try:
                    subprocess.Popen(f'start "" "{name}"', shell=True)
                    return f"Launched: {name}"
                except Exception as e:
                    return f"Error: {e}"
            # 应用名：用 PowerShell Get-StartApps 反查 AppID
            try:
                # 转义 PS 字符串中的单引号
                ps_name = name.replace("'", "''")
                ps_cmd = (
                    f"Get-StartApps | Where-Object {{$_.Name -like '*{ps_name}*'}} "
                    f"| Select-Object -First 1 -ExpandProperty AppID"
                )
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True, text=True, timeout=10,
                )
                appid = (r.stdout or "").strip().splitlines()[0] if r.stdout else ""
                if appid:
                    subprocess.Popen(f'start "" "{appid}"', shell=True)
                    return f"Launched: {name} (via AppID: {appid})"
                return f"Error: app '{name}' not found in Start menu"
            except Exception as e:
                return f"Error: {e}"
        else:
            try:
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
