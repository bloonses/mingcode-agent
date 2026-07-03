import time
import math
import re
import sys
from contextlib import contextmanager
from typing import Generator, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich import box
from .theme import (
    NEON_TEAL, NEON_PURPLE, NEON_BLUE, NEON_RED,
    style_neon_teal, style_neon_purple, style_neon_blue, style_neon_red,
    style_panel_border_teal, style_panel_border_blue,
    style_text, style_text_muted, style_spinner, style_prompt,
    PULSE_DURATION
)

# 可选依赖，运行时检测（与 computer_use.py 一致）
try:
    from PIL import Image
    pil_available = True
except ImportError:
    pil_available = False

console = Console(
    force_terminal=True,
    color_system="truecolor",
    highlight=False
)

LOGO = ""
LOGO_SMALL = ""
CYBER_LINES = []

MINGCODE_BIG = r"""
 ███╗   ███╗██╗███╗   ██╗ ██████╗  ██████╗ ██████╗ ██████╗ ███████╗
 ████╗ ████║██║████╗  ██║██╔════╝ ██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ██╔████╔██║██║██╔██╗ ██║██║  ███╗██║     ██║   ██║██║  ██║█████╗  
 ██║╚██╔╝██║██║██║╚██╗██║██║   ██║██║     ██║   ██║██║  ██║██╔══╝  
 ██║ ╚═╝ ██║██║██║ ╚████║╚██████╔╝╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"""

def _pulse_color(base_color: str, t: float) -> str:
    hex_r = int(base_color[1:3], 16)
    hex_g = int(base_color[3:5], 16)
    hex_b = int(base_color[5:7], 16)
    pulse = 0.5 + 0.5 * math.sin(2 * math.pi * t / PULSE_DURATION)
    factor = 0.5 + 0.5 * pulse
    r = int(hex_r * factor)
    g = int(hex_g * factor)
    b = int(hex_b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"

def print_logo() -> None:
    console.print()
    big_logo = Text(MINGCODE_BIG, style=f"bold {NEON_TEAL}")
    console.print(big_logo)
    console.print()
    version = Text("v1.0.9", style=style_text_muted)
    console.print(version, justify="center")
    console.print()
    console.print(Text("Welcome to MINGCODE - Your AI coding assistant.", style=style_text))
    console.print(Text("Enter /help for available commands, or just start chatting.", style=style_text_muted))
    console.print()
    console.print(Text("Ready to help. What would you like to do?", style=style_text_muted))
    console.print()

def _render_markdown(text: str) -> Group:
    parts = []
    pattern = r"```(\w*)\n(.*?)```"
    last_end = 0
    for match in re.finditer(pattern, text, re.DOTALL):
        if match.start() > last_end:
            parts.append(Text(text[last_end:match.start()], style=style_text))
        language = match.group(1) or "text"
        code = match.group(2)
        parts.append(Syntax(code, language, theme="monokai", line_numbers=False, word_wrap=True))
        last_end = match.end()
    if last_end < len(text):
        parts.append(Text(text[last_end:], style=style_text))
    return Group(*parts)

def print_user_message(text: str) -> None:
    console.print()
    content = Text(text, style=style_text)
    panel = Panel(
        content,
        box=box.SQUARE,
        border_style=style_panel_border_blue,
        padding=(0, 1),
        title=Text(" YOU ", style=style_neon_blue),
        title_align="left"
    )
    console.print(panel)

def print_assistant_message(text: str, stream: bool = False) -> None:
    console.print()
    if stream:
        content = Text("", style=style_text)
        panel = Panel(
            content,
            box=box.SQUARE,
            border_style=style_panel_border_teal,
            padding=(0, 1),
            title=Text(" MINGCODE ", style=style_neon_teal),
            title_align="left"
        )
        with Live(panel, refresh_per_second=30, console=console) as live:
            for char in text:
                content.append(char)
                time.sleep(0.005)
                live.update(panel)
        console.print()
    else:
        renderable = _render_markdown(text)
        panel = Panel(
            renderable,
            box=box.SQUARE,
            border_style=style_panel_border_teal,
            padding=(0, 1),
            title=Text(" MINGCODE ", style=style_neon_teal),
            title_align="left"
        )
        console.print(panel)
        console.print()

def print_tool_call(tool_name: str, args: Optional[dict] = None) -> None:
    console.print()
    content_lines = [Text(f"Calling: {tool_name}", style=style_neon_purple)]
    if args:
        args_str = str(args)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."
        for line in args_str.split('\n'):
            content_lines.append(Text(f"  {line}", style=style_text_muted))
    panel = Panel(
        Group(*content_lines),
        box=box.SQUARE,
        border_style=style_neon_purple,
        padding=(0, 1),
        title=Text(" TOOL ", style=style_neon_purple),
        title_align="left"
    )
    console.print(panel)

def print_tool_result(text: str) -> None:
    if len(text) > 500:
        text = text[:500] + "..."
    content = Text(text, style=style_text_muted)
    panel = Panel(
        content,
        box=box.SQUARE,
        border_style=style_text_muted,
        padding=(0, 1),
        title=Text(" RESULT ", style=style_text_muted),
        title_align="left"
    )
    console.print(panel)

def print_error(text: str) -> None:
    console.print()
    err = Text(f"✖ {text}", style=style_neon_red)
    console.print(err)
    console.print()

@contextmanager
def print_thinking_spinner() -> Generator[Progress, None, None]:
    progress = Progress(
        SpinnerColumn(spinner_name="dots", style=style_spinner),
        TextColumn("[{0}]Thinking...".format(NEON_TEAL)),
        console=console,
        transient=True
    )
    progress.add_task("thinking", total=None)
    with progress:
        yield progress

def get_prompt() -> Text:
    prompt = Text("> ", style=style_prompt)
    return prompt


def print_screenshot_thumbnail(image_path: str, max_width: int = 80) -> None:
    """用 ANSI truecolor 半块字符在终端渲染截图缩略图（codex 风格）。

    半块字符 ▀ 一次显示两行像素：上像素做前景色，下像素做背景色。
    渲染失败不抛异常，只打印提示行。
    """
    if not pil_available:
        console.print("[thumbnail unavailable: Pillow not installed]", markup=False)
        return
    try:
        img = Image.open(image_path).convert("RGB")
        # 计算缩放：宽 = max_width，高 = max_width × (h/w) / 2（半块合并两行）
        scale = max_width / img.width
        new_w = max_width
        new_h = max(1, int(img.height * scale / 2))
        resized = img.resize((new_w, new_h * 2))
        # 标题行
        console.print(Text("SCREENSHOT THUMBNAIL", style=style_neon_teal))
        # 双重循环渲染（用内置 print，因为 Rich 会把 ANSI 转义码当文本显示）
        for y in range(0, resized.height, 2):
            line = ""
            for x in range(new_w):
                upper = resized.getpixel((x, y))
                lower = resized.getpixel((x, y + 1)) if y + 1 < resized.height else (0, 0, 0)
                line += f"\x1b[38;2;{upper[0]};{upper[1]};{upper[2]}m\x1b[48;2;{lower[0]};{lower[1]};{lower[2]}m▀"
            line += "\x1b[0m"
            print(line)
    except Exception as e:
        console.print(f"[thumbnail error: {e}]", markup=False)
