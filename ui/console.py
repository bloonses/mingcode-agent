"""Rich 渲染组件 - 打字机流式、工具调用、错误提示。"""
from contextlib import contextmanager
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.spinner import Spinner
from rich.live import Live
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.theme import Theme
from .theme import NEON_THEME

console = Console(theme=NEON_THEME)


def print_assistant_message(text: str):
    """打印助手消息（Markdown 渲染）。"""
    console.print(Panel(Markdown(text), title="[panel.title]MINGCODE-LC[/]", border_style="panel.border"))


def print_user_message(text: str):
    """打印用户消息。"""
    console.print(Panel(text, title="[user]YOU[/]", border_style="user"))


def print_tool_call(name: str, args: dict):
    """打印工具调用。"""
    args_str = " ".join(f"{k}={v!r}" for k, v in args.items())
    console.print(f"[tool.name]🔧 {name}[/] [muted]{args_str}[/]")


def print_tool_result(result: str):
    """打印工具结果。"""
    if len(result) > 500:
        result = result[:500] + "... [truncated]"
    console.print(Panel(result, border_style="muted", expand=True))


def print_error(msg: str):
    """打印错误。"""
    console.print(f"[error]✗ {msg}[/]")


def print_thinking(text: str = ""):
    """打印思考。"""
    if text:
        console.print(f"[thinking]💭 {text}[/]")


@contextmanager
def print_thinking_spinner(text: str = "Thinking"):
    """显示思考 spinner 的上下文管理器。"""
    spinner = Spinner("dots", text=f"[thinking]{text}...[/]", style="thinking")
    with Live(spinner, console=console, refresh_per_second=10):
        yield


def print_streaming_chunk(chunk: str, live: Live):
    """流式输出 chunk 到 Live 区域。"""
    pass
