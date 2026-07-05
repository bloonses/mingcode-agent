"""工具模块 - LangChain @tool 装饰器实现。"""
from typing import List, Optional
from langchain_core.tools import BaseTool

from .shell import shell
from .files import file_read, file_write
from .code import python_exec
from .search import web_search, web_fetch
from .ask_user import ask_user
from .time_tool import time_now
from .math_tool import math_calc
from .http_tool import http_request
from .git_tool import git_status, git_command
from .todo import todo_add, todo_list, todo_mark_done, todo_clear
from .subagent import subagent
from .plan_tot import plan_tot
from .computer_use import computer_screenshot, computer_click, computer_type


ALL_TOOLS: List[BaseTool] = [
    shell,
    file_read,
    file_write,
    python_exec,
    web_search,
    web_fetch,
    ask_user,
    time_now,
    math_calc,
    http_request,
    git_status,
    git_command,
    todo_add,
    todo_list,
    todo_mark_done,
    todo_clear,
    subagent,
    plan_tot,
    computer_screenshot,
    computer_click,
    computer_type,
]


def get_tool_by_name(name: str) -> Optional[BaseTool]:
    """按名查找工具。"""
    for t in ALL_TOOLS:
        if t.name == name:
            return t
    return None


__all__ = ["ALL_TOOLS", "get_tool_by_name"]
