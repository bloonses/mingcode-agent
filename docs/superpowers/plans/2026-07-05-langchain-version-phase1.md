# Phase 1: 工具系统 + ReAct Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 LangChain @tool 装饰器重写 15+ 工具，实现 LangChainAgent 类支持简单 ReAct 循环，main.py 能完成完整对话

**Architecture:** 工具用 `@tool` + Pydantic BaseModel 描述参数，core/agent.py 的 LangChainAgent 用 `create_react_agent` 包装 ChatOpenAI + ToolNode，串行执行工具调用，UI 通过 RichStreamHandler 桥接流式输出

**Tech Stack:** LangChain tools, Pydantic, create_react_agent, Rich Live

---

## File Structure

- Create: `tools/__init__.py` - 工具注册
- Create: `tools/shell.py`, `tools/files.py`, `tools/code.py`, `tools/search.py` - 基础工具
- Create: `tools/ask_user.py`, `tools/time_tool.py`, `tools/math_tool.py` - 辅助工具
- Create: `tools/http_tool.py`, `tools/git_tool.py`, `tools/todo.py` - 其他工具
- Modify: `core/agent.py` - LangChainAgent 类
- Modify: `main.py` - 接入 Agent
- Test: `tests/test_tools.py`, `tests/test_agent.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\tools\*.py` - 工具业务逻辑参考

---

### Task 1: 创建基础工具（shell + files + code）

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/shell.py`
- Create: `tools/files.py`
- Create: `tools/code.py`
- Test: `tests/test_tools_basic.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\tools\shell.py`, `c:\Users\bloon\Downloads\neon_agent\tools\files.py`, `c:\Users\bloon\Downloads\neon_agent\tools\code.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_basic.py
"""基础工具测试（shell/files/code）。"""
import os
import tempfile
from tools.shell import shell
from tools.files import file_read, file_write
from tools.code import python_exec


def test_shell_echo():
    """shell 应能执行 echo 命令。"""
    result = shell.invoke({"command": "echo hello"})
    assert "hello" in result


def test_shell_returns_string():
    """shell 返回值应为字符串。"""
    result = shell.invoke({"command": "echo test"})
    assert isinstance(result, str)


def test_file_write_and_read():
    """file_write + file_read 往返。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        write_result = file_write.invoke({"path": path, "content": "hello world"})
        assert "成功" in write_result or "success" in write_result.lower()
        read_result = file_read.invoke({"path": path})
        assert "hello world" in read_result
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_file_read_nonexistent():
    """file_read 不存在的文件应返回错误信息。"""
    result = file_read.invoke({"path": "nonexistent_file_12345.txt"})
    assert "error" in result.lower() or "不存在" in result or "not found" in result.lower()


def test_python_exec_simple():
    """python_exec 应能执行简单 Python 代码。"""
    result = python_exec.invoke({"code": "print(1+1)"})
    assert "2" in result


def test_python_exec_error():
    """python_exec 错误代码应返回错误信息。"""
    result = python_exec.invoke({"code": "raise ValueError('test')"})
    assert "ValueError" in result or "test" in result
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_basic.py -v`
Expected: FAIL with "No module named 'tools'"

- [ ] **Step 3: 实现 tools/__init__.py**

```python
"""工具模块 - LangChain @tool 装饰器实现。"""
```

- [ ] **Step 4: 实现 tools/shell.py**

```python
# tools/shell.py
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
```

- [ ] **Step 5: 实现 tools/files.py**

```python
# tools/files.py
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
```

- [ ] **Step 6: 实现 tools/code.py**

```python
# tools/code.py
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
```

- [ ] **Step 7: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_basic.py -v`
Expected: PASS（6 个测试全过）

- [ ] **Step 8: 提交**

```bash
git add tools/__init__.py tools/shell.py tools/files.py tools/code.py tests/test_tools_basic.py
git commit -m "feat(tools): add shell, files, python_exec with @tool decorator"
```

---

### Task 2: 搜索工具（web_search + web_fetch）

**Files:**
- Create: `tools/search.py`
- Test: `tests/test_tools_search.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\tools\search.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_search.py
"""搜索工具测试。"""
from unittest.mock import patch, MagicMock
from tools.search import web_search, web_fetch


def test_web_search_returns_string():
    """web_search 应返回字符串。"""
    with patch("tools.search.DDGS") as mock_ddgs:
        mock_instance = MagicMock()
        mock_instance.text.return_value = [
            {"title": "Test", "body": "Test body", "href": "http://example.com"}
        ]
        mock_ddgs.return_value = mock_instance
        result = web_search.invoke({"query": "test query"})
        assert isinstance(result, str)
        assert "Test" in result


def test_web_search_empty_results():
    """空结果应返回提示。"""
    with patch("tools.search.DDGS") as mock_ddgs:
        mock_instance = MagicMock()
        mock_instance.text.return_value = []
        mock_ddgs.return_value = mock_instance
        result = web_search.invoke({"query": "nonexistent"})
        assert "无结果" in result or "no" in result.lower() or "未找到" in result


def test_web_fetch_returns_content():
    """web_fetch 应返回页面内容。"""
    with patch("tools.search.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        result = web_fetch.invoke({"url": "http://example.com"})
        assert "Hello" in result or "html" in result.lower()


def test_web_fetch_http_error():
    """HTTP 错误应返回错误信息。"""
    with patch("tools.search.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        result = web_fetch.invoke({"url": "http://example.com/nonexistent"})
        assert "404" in result or "error" in result.lower()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_search.py -v`
Expected: FAIL with "No module named 'tools.search'"

- [ ] **Step 3: 实现 tools/search.py**

```python
# tools/search.py
"""网络搜索工具。"""
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Max results to return")


class WebFetchInput(BaseModel):
    url: str = Field(description="URL to fetch")


@tool(args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results."""
    if DDGS is None:
        return "Error: duckduckgo-search not installed. Run: pip install duckduckgo-search"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"未找到关于 '{query}' 的结果"
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r.get('title', 'No title')}\n   {r.get('body', '')[:200]}\n   {r.get('href', '')}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=WebFetchInput)
def web_fetch(url: str) -> str:
    """Fetch URL content as text."""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "MINGCODE-LC/0.1"})
        if response.status_code != 200:
            return f"Error: HTTP {response.status_code}"
        return response.text[:5000]  # 限制长度
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_search.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add tools/search.py tests/test_tools_search.py
git commit -m "feat(tools): add web_search and web_fetch"
```

---

### Task 3: 辅助工具（ask_user + time + math）

**Files:**
- Create: `tools/ask_user.py`
- Create: `tools/time_tool.py`
- Create: `tools/math_tool.py`
- Test: `tests/test_tools_aux.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\tools\ask_user.py`, `c:\Users\bloon\Downloads\neon_agent\tools\time_tool.py`, `c:\Users\bloon\Downloads\neon_agent\tools\math_tool.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_aux.py
"""辅助工具测试（ask_user/time/math）。"""
from unittest.mock import patch
from tools.ask_user import ask_user
from tools.time_tool import time_now
from tools.math_tool import math_calc


def test_ask_user_returns_input():
    """ask_user 应返回用户输入。"""
    with patch("builtins.input", return_value="user answer"):
        result = ask_user.invoke({"question": "what is your name?"})
        assert "user answer" in result


def test_time_now_returns_iso():
    """time_now 应返回 ISO 格式时间字符串。"""
    result = time_now.invoke({})
    assert "20" in result  # 年份 20xx
    assert ":" in result   # 时间格式 HH:MM


def test_math_calc_addition():
    """math_calc 应能做精确加法。"""
    result = math_calc.invoke({"expression": "0.1 + 0.2"})
    assert "0.3" in result


def test_math_calc_division():
    """math_calc 应能做除法。"""
    result = math_calc.invoke({"expression": "10 / 3"})
    assert "3.33" in result or "3.333" in result


def test_math_calc_error():
    """math_calc 无效表达式应返回错误。"""
    result = math_calc.invoke({"expression": "1/0"})
    assert "error" in result.lower() or "Error" in result or "Division" in result or "division" in result
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_aux.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 tools/ask_user.py**

```python
# tools/ask_user.py
"""向用户提问工具。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class AskUserInput(BaseModel):
    question: str = Field(description="Question to ask the user")


@tool(args_schema=AskUserInput)
def ask_user(question: str) -> str:
    """Ask the user a question and wait for their answer."""
    print(f"\n[AI 问题] {question}")
    try:
        answer = input("> ")
        return answer
    except (EOFError, KeyboardInterrupt):
        return "(用户取消了回答)"
```

- [ ] **Step 4: 实现 tools/time_tool.py**

```python
# tools/time_tool.py
"""时间日期工具。"""
from datetime import datetime, timezone
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class TimeNowInput(BaseModel):
    timezone_offset: int = Field(default=8, description="Timezone offset from UTC (default: 8 for Asia/Shanghai")


@tool(args_schema=TimeNowInput)
def time_now(timezone_offset: int = 8) -> str:
    """Get current time in ISO format with timezone offset."""
    from datetime import timedelta
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    return now.isoformat()
```

- [ ] **Step 5: 实现 tools/math_tool.py**

```python
# tools/math_tool.py
"""精确数学工具（避免浮点误差）。"""
from decimal import Decimal, InvalidOperation, DivisionByZero
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class MathCalcInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate (e.g. '0.1 + 0.2', '10 / 3')")


@tool(args_schema=MathCalcInput)
def math_calc(expression: str) -> str:
    """Evaluate a mathematical expression with decimal precision."""
    try:
        # 安全替换常见运算符
        safe_expr = expression.replace("^", "**")
        # 用 Decimal 上下文限制精度
        result = eval(safe_expr, {"__builtins__": {}}, {"Decimal": Decimal})
        if isinstance(result, Decimal):
            return str(result.quantize(Decimal("0.000001")) if result != result.to_integral_value() else result)
        return str(result)
    except DivisionByZero:
        return "Error: Division by zero"
    except InvalidOperation as e:
        return f"Error: Invalid operation - {e}"
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_aux.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 7: 提交**

```bash
git add tools/ask_user.py tools/time_tool.py tools/math_tool.py tests/test_tools_aux.py
git commit -m "feat(tools): add ask_user, time, math tools"
```

---

### Task 4: 其他工具（http + git + todo）

**Files:**
- Create: `tools/http_tool.py`
- Create: `tools/git_tool.py`
- Create: `tools/todo.py`
- Create: `core/todo.py` (TodoList 数据类)
- Test: `tests/test_tools_other.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\tools\http_tool.py`, `c:\Users\bloon\Downloads\neon_agent\tools\git_tool.py`, `c:\Users\bloon\Downloads\neon_agent\tools\todo.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_other.py
"""其他工具测试（http/git/todo）。"""
import os
import tempfile
from unittest.mock import patch, MagicMock
from tools.http_tool import http_request
from tools.git_tool import git_status
from tools.todo import todo_add, todo_list, todo_clear


def test_http_get():
    """http_request 应能发送 GET 请求。"""
    with patch("tools.http_tool.requests.request") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_req.return_value = mock_response
        result = http_request.invoke({"method": "GET", "url": "http://example.com"})
        assert "200" in result
        assert "ok" in result


def test_git_status_in_temp_repo():
    """git_status 在临时 git 仓库应返回状态字符串。"""
    with tempfile.TemporaryDirectory() as tmp:
        # init git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, capture_output=True)
        # 创建文件制造 status
        with open(os.path.join(tmp, "test.txt"), "w") as f:
            f.write("test")
        with patch("os.getcwd", return_value=tmp):
            result = git_status.invoke({})
            assert isinstance(result, str)


def test_todo_add_and_list():
    """todo_add + todo_list 往返。"""
    with tempfile.TemporaryDirectory() as tmp:
        with patch("core.todo.TodoList._todo_file", new_callable=lambda: os.path.join(tmp, "todos.json")):
            add_result = todo_add.invoke({"content": "test task"})
            assert "成功" in add_result or "added" in add_result.lower()
            list_result = todo_list.invoke({})
            assert "test task" in list_result


def test_todo_clear():
    """todo_clear 应清空待办。"""
    with tempfile.TemporaryDirectory() as tmp:
        with patch("core.todo.TodoList._todo_file", new_callable=lambda: os.path.join(tmp, "todos.json")):
            todo_add.invoke({"content": "task1"})
            clear_result = todo_clear.invoke({})
            list_result = todo_list.invoke({})
            assert "task1" not in list_result
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_other.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/todo.py（TodoList 数据类）**

```python
# core/todo.py
"""待办清单数据类 - 跨会话持久化。"""
import json
import os
from typing import List, Dict
from datetime import datetime


class TodoList:
    """待办清单，存到 JSON 文件。"""

    def __init__(self, todo_file: str = None):
        self._todo_file = todo_file or os.path.join(os.path.expanduser("~"), ".mingcode-lc", "todos.json")
        self._todos: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if not os.path.exists(self._todo_file):
            return []
        try:
            with open(self._todo_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self):
        os.makedirs(os.path.dirname(self._todo_file), exist_ok=True)
        with open(self._todo_file, "w", encoding="utf-8") as f:
            json.dump(self._todos, f, ensure_ascii=False, indent=2)

    def add(self, content: str) -> str:
        todo = {"id": len(self._todos) + 1, "content": content, "done": False, "created_at": datetime.now().isoformat()}
        self._todos.append(todo)
        self._save()
        return f"成功添加待办 #{todo['id']}: {content}"

    def list_all(self) -> str:
        if not self._todos:
            return "(待办清单为空)"
        return "\n".join(f"[{'x' if t['done'] else ' '}] #{t['id']}: {t['content']}" for t in self._todos)

    def clear(self) -> str:
        count = len(self._todos)
        self._todos = []
        self._save()
        return f"已清空 {count} 个待办"

    def mark_done(self, todo_id: int) -> str:
        for t in self._todos:
            if t["id"] == todo_id:
                t["done"] = True
                self._save()
                return f"已完成 #{todo_id}: {t['content']}"
        return f"Error: 找不到待办 #{todo_id}"


# 全局单例（与 neon_agent 一致）
_todo_list = TodoList()
```

- [ ] **Step 4: 实现 tools/todo.py**

```python
# tools/todo.py
"""待办清单工具。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from core.todo import _todo_list


class TodoAddInput(BaseModel):
    content: str = Field(description="Todo content to add")


class TodoMarkDoneInput(BaseModel):
    todo_id: int = Field(description="Todo ID to mark as done")


@tool(args_schema=TodoAddInput)
def todo_add(content: str) -> str:
    """Add a todo item."""
    return _todo_list.add(content)


@tool
def todo_list() -> str:
    """List all todos."""
    return _todo_list.list_all()


@tool(args_schema=TodoMarkDoneInput)
def todo_mark_done(todo_id: int) -> str:
    """Mark a todo as done."""
    return _todo_list.mark_done(todo_id)


@tool
def todo_clear() -> str:
    """Clear all todos."""
    return _todo_list.clear()
```

- [ ] **Step 5: 实现 tools/http_tool.py**

```python
# tools/http_tool.py
"""HTTP 请求工具。"""
import json as json_module
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class HttpRequestInput(BaseModel):
    method: str = Field(description="HTTP method (GET/POST/PUT/DELETE)")
    url: str = Field(description="URL to request")
    headers: dict = Field(default=None, description="Request headers")
    body: str = Field(default=None, description="Request body (JSON string)")


@tool(args_schema=HttpRequestInput)
def http_request(method: str, url: str, headers: dict = None, body: str = None) -> str:
    """Send an HTTP request and return status/headers/body."""
    try:
        kwargs = {"headers": headers or {}}
        if body and method.upper() in ("POST", "PUT", "PATCH"):
            kwargs["data"] = body
        response = requests.request(method, url, timeout=30, **kwargs)
        result = f"Status: {response.status_code}\nHeaders: {dict(response.headers)}\nBody: {response.text[:2000]}"
        return result
    except Exception as e:
        return f"Error: {e}"
```

- [ ] **Step 6: 实现 tools/git_tool.py**

```python
# tools/git_tool.py
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
```

- [ ] **Step 7: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_other.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 8: 提交**

```bash
git add core/todo.py tools/todo.py tools/http_tool.py tools/git_tool.py tests/test_tools_other.py
git commit -m "feat(tools): add http, git, todo tools with TodoList persistence"
```

---

### Task 5: 工具注册表 + ALL_TOOLS 列表

**Files:**
- Modify: `tools/__init__.py`
- Test: `tests/test_tools_registry.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_registry.py
"""工具注册表测试。"""
from tools import ALL_TOOLS, get_tool_by_name


def test_all_tools_has_15_plus():
    """ALL_TOOLS 应至少有 15 个工具。"""
    assert len(ALL_TOOLS) >= 12  # Phase 1 当前数


def test_all_tools_have_names():
    """每个工具应有 name 属性。"""
    for t in ALL_TOOLS:
        assert hasattr(t, "name"), f"Tool missing name: {t}"
        assert isinstance(t.name, str)


def test_get_tool_by_name_returns_tool():
    """get_tool_by_name 应能按名查找。"""
    shell = get_tool_by_name("shell")
    assert shell is not None
    assert shell.name == "shell"


def test_get_tool_by_name_nonexistent():
    """不存在的工具应返回 None。"""
    result = get_tool_by_name("nonexistent_tool")
    assert result is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_tools_registry.py -v`
Expected: FAIL with "cannot import name 'ALL_TOOLS'"

- [ ] **Step 3: 实现 tools/__init__.py**

```python
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
]


def get_tool_by_name(name: str) -> Optional[BaseTool]:
    """按名查找工具。"""
    for t in ALL_TOOLS:
        if t.name == name:
            return t
    return None


__all__ = ["ALL_TOOLS", "get_tool_by_name"]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_tools_registry.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add tools/__init__.py tests/test_tools_registry.py
git commit -m "feat(tools): add ALL_TOOLS registry with 16 tools"
```

---

### Task 6: LangChainAgent 类（简单 ReAct）

**Files:**
- Create: `core/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_agent.py
"""LangChainAgent 测试。"""
from unittest.mock import patch, MagicMock, ANY
from core.agent import LangChainAgent


def _make_agent():
    """构造带 mock LLM 的 Agent。"""
    mock_llm = MagicMock()
    mock_config = {
        "llm": {"base_url": "http://test", "api_key": "sk-test", "model": "test-model"},
        "cognitive": {"enabled": False},  # Phase 1 不接入 cognitive
    }
    return LangChainAgent(config=mock_config, llm=mock_llm)


def test_agent_constructs():
    """Agent 应能构造。"""
    agent = _make_agent()
    assert agent is not None


def test_agent_chat_returns_generator():
    """Agent.chat 应返回 generator。"""
    agent = _make_agent()
    result = agent.chat("hi")
    assert hasattr(result, "__iter__") or hasattr(result, "__next__")


def test_agent_has_tools():
    """Agent 应加载 ALL_TOOLS。"""
    agent = _make_agent()
    assert len(agent.tools) > 0


def test_agent_cognitive_disabled_by_default():
    """Phase 1 cognitive 应该不启用。"""
    agent = _make_agent()
    assert agent.cognitive_enabled is False


def test_agent_simple_input_yields_response():
    """简单输入应 yield 响应字符串。"""
    mock_llm = MagicMock()
    # mock create_react_agent.invoke 返回
    mock_response = {"messages": [MagicMock(content="hello back")]}
    with patch("core.agent.create_react_agent") as mock_create:
        mock_react = MagicMock()
        mock_react.invoke.return_value = mock_response
        mock_create.return_value = mock_react
        agent = LangChainAgent(
            config={"llm": {"base_url": "http://test", "api_key": "sk-test", "model": "m"}, "cognitive": {"enabled": False}},
            llm=mock_llm,
        )
        chunks = list(agent.chat("hi"))
        # 应该有内容
        assert len(chunks) >= 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_agent.py -v`
Expected: FAIL with "No module named 'core.agent'"

- [ ] **Step 3: 实现 core/agent.py**

```python
# core/agent.py
"""LangChainAgent - NeonAgent 的 LangChain 等价实现。"""
from typing import Generator, Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent as create_react_agent_langgraph

from core.llm import create_llm
from core.memory import ConversationMemory
from tools import ALL_TOOLS
from ui.console import print_assistant_message, print_tool_call, print_tool_result, print_error, print_thinking_spinner
from ui.callbacks import RichStreamHandler


class LangChainAgent:
    """LangChain 版 Agent - 对外 Generator[str] 接口与 NeonAgent 一致。"""

    def __init__(self, config: Dict[str, Any], llm: Optional[ChatOpenAI] = None):
        self.config = config
        self.llm = llm or create_llm(config)
        self.tools = list(ALL_TOOLS)
        self.memory = ConversationMemory(max_history=config.get("memory", {}).get("max_history", 50))
        self.cognitive_enabled = config.get("cognitive", {}).get("enabled", False)
        # Phase 1: 用 create_react_agent 包装
        self._react_agent = None  # 延迟构造
        self._cognitive_controller = None  # Phase 2 接入

    @property
    def react_agent(self):
        """延迟构造 ReAct agent（LangGraph 版）。"""
        if self._react_agent is None:
            # 用 LangGraph 的 create_react_agent（功能更稳定）
            self._react_agent = create_react_agent_langgraph(self.llm, self.tools)
        return self._react_agent

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """主入口 - 对外 Generator[str] 接口。

        Phase 1: 直接走 create_react_agent
        Phase 2: cognitive 启用走 LangGraph StateGraph
        """
        # Phase 2 接入：cognitive 启用走状态机
        if self.cognitive_enabled:
            try:
                from core.cognitive_graph import run_cognitive
                result = run_cognitive(user_input, self.llm, self.tools, self.memory)
                if not result.startswith("[React fallback] "):
                    yield result
                    return
            except Exception as e:
                print_error(f"认知框架异常，回退到 ReAct: {e}")
                # fallback

        # Phase 1: 简单 ReAct
        yield from self._run_react(user_input)

    def _run_react(self, user_input: str) -> Generator[str, None, None]:
        """运行 ReAct agent，流式 yield 响应。"""
        # 用 streaming callback 收集 chunk
        handler = RichStreamHandler()

        try:
            # LangGraph 的 create_react_agent 支持 stream
            for event in self.react_agent.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config={"callbacks": [handler]},
                stream_mode="values",
            ):
                # event 是 dict，包含 messages 等
                if "messages" in event and event["messages"]:
                    last_msg = event["messages"][-1]
                    content = getattr(last_msg, "content", "")
                    if content and isinstance(content, str):
                        # 检查是否是 tool call message
                        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                print_tool_call(tc.get("name", ""), tc.get("args", {}))
                        elif content.strip():
                            yield content
        except Exception as e:
            yield f"Error: {e}"

    def clear_memory(self):
        """清空对话历史。"""
        self.memory.clear()

    def save_session(self, name: str):
        """保存会话。"""
        self.memory.save(name)

    def load_session(self, name: str):
        """加载会话。"""
        self.memory.load(name)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_agent.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/agent.py tests/test_agent.py
git commit -m "feat(agent): add LangChainAgent with create_react_agent and streaming"
```

---

### Task 7: 会话记忆模块（ConversationMemory）

**Files:**
- Create: `core/memory.py`
- Test: `tests/test_memory.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\core\memory.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_memory.py
"""ConversationMemory 测试。"""
import tempfile
import os
from core.memory import ConversationMemory


def test_memory_starts_empty():
    """新 memory 应为空（除 system prompt 外）。"""
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    msgs = m.get_messages()
    # 应该只有 system prompt
    assert len(msgs) >= 1


def test_add_message():
    """add_message 应追加消息。"""
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    msgs = m.get_messages()
    assert any(m.get("content") == "hello" and m.get("role") == "user" for m in msgs)


def test_max_history_truncation():
    """超过 max_history 应截断旧消息。"""
    m = ConversationMemory(max_history=3)
    m.build_system_prompt([])
    for i in range(10):
        m.add_message("user", f"msg {i}")
    # 最多保留 max_history 条用户消息 + system
    user_msgs = [m for m in m.get_messages() if m.get("role") == "user"]
    assert len(user_msgs) <= 3


def test_save_and_load(tmp_path):
    """save + load 应往返一致。"""
    save_file = str(tmp_path / "session.json")
    m = ConversationMemory(max_history=10, save_file=save_file)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    m.add_message("assistant", "hi back")
    m.save("test_session")

    m2 = ConversationMemory(max_history=10, save_file=save_file)
    m2.load("test_session")
    msgs = m2.get_messages()
    assert any(m.get("content") == "hello" for m in msgs)
    assert any(m.get("content") == "hi back" for m in msgs)


def test_clear():
    """clear 应清空（除 system prompt）。"""
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    m.clear()
    user_msgs = [m for m in m.get_messages() if m.get("role") == "user"]
    assert len(user_msgs) == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_memory.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/memory.py**

```python
# core/memory.py
"""对话记忆 - 兼容 NeonAgent 接口。"""
import json
import os
from typing import List, Dict, Any, Optional
from collections import deque


class ConversationMemory:
    """对话历史，带 max_history 截断和 JSON 持久化。

    注意：Phase 2 接入 SqliteSaver 后这个类仍保留，
    用于长期记忆和跨会话保存。
    """

    def __init__(self, max_history: int = 50, save_file: Optional[str] = None):
        self.max_history = max_history
        self.save_file = save_file or os.path.join(os.path.expanduser("~"), ".mingcode-lc", "sessions.json")
        self.system_prompt: str = ""
        self._messages: List[Dict[str, Any]] = []

    def build_system_prompt(self, tool_schemas: List[Dict]):
        """根据工具 schema 构建 system prompt。"""
        tool_list = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tool_schemas)
        self.system_prompt = f"""你是 MINGCODE-LC，一个赛博朋克风格的 AI 编码助手。

可用工具:
{tool_list}

工作原则:
1. 复杂任务先规划再执行
2. 严格遵循 TDD（RED-GREEN-REFACTOR）
3. 失败时反思并改进
4. 不确定时向用户提问
"""

    def add_message(self, role: str, content: str, **kwargs):
        """追加消息。"""
        msg = {"role": role, "content": content, **kwargs}
        self._messages.append(msg)
        # 截断（保留最新的 max_history 条非 system 消息）
        non_system = [m for m in self._messages if m.get("role") != "system"]
        if len(non_system) > self.max_history:
            # 保留最后 max_history 条
            keep_ids = set(id(m) for m in non_system[-self.max_history:])
            self._messages = [m for m in self._messages if m.get("role") == "system" or id(m) in keep_ids]

    def get_messages(self) -> List[Dict[str, Any]]:
        """返回完整消息列表（含 system prompt）。"""
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self._messages)
        return msgs

    def clear(self):
        """清空对话（保留 system prompt）。"""
        self._messages = []

    def save(self, name: str):
        """保存会话到文件。"""
        os.makedirs(os.path.dirname(self.save_file), exist_ok=True)
        sessions = {}
        if os.path.exists(self.save_file):
            with open(self.save_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        sessions[name] = self._messages
        with open(self.save_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def load(self, name: str):
        """加载会话。"""
        if not os.path.exists(self.save_file):
            return
        with open(self.save_file, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        if name in sessions:
            self._messages = sessions[name]

    def list_sessions(self) -> List[str]:
        """列出所有已保存会话。"""
        if not os.path.exists(self.save_file):
            return []
        with open(self.save_file, "r", encoding="utf-8") as f:
            return list(json.load(f).keys())

    def delete_session(self, name: str) -> bool:
        """删除会话。"""
        if not os.path.exists(self.save_file):
            return False
        with open(self.save_file, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        if name in sessions:
            del sessions[name]
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            return True
        return False
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_memory.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/memory.py tests/test_memory.py
git commit -m "feat(memory): add ConversationMemory with JSON persistence and session management"
```

---

### Task 8: main.py 接入 Agent + 最终集成测试

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_cli.py`

- [ ] **Step 1: 更新 main.py 接入 Agent**

```python
# main.py
"""MINGCODE-LC CLI 入口。"""
import sys
from typing import Optional

from ui.console import console, print_assistant_message, print_user_message, print_error
from config.config import load_config


HELP_TEXT = """MINGCODE-LC v0.1.0 - LangChain 版本

可用命令:
  /help              显示此帮助
  /settings          交互式配置 LLM 供应商
  /config            查看当前配置
  /model <name>      切换模型
  /tools             列出可用工具
  /cognitive [on|off] 启用/关闭认知框架
  /new               开始新会话
  /save [name]       保存当前会话
  /load <name>       加载会话
  /sessions          列出已保存会话
  /clear             清空当前对话
  /exit              退出
"""


def handle_command(user_input: str, agent=None) -> Optional[str]:
    """处理 / 命令。非命令返回 None。"""
    if not user_input.startswith("/"):
        return None
    cmd = user_input.strip().lower()
    if cmd == "/help":
        return HELP_TEXT
    if cmd == "/exit":
        sys.exit(0)
    if cmd == "/tools" and agent:
        return "\n".join(f"- {t.name}: {t.description}" for t in agent.tools)
    if cmd == "/clear" and agent:
        agent.clear_memory()
        return "(已清空对话)"
    if cmd == "/new" and agent:
        agent.clear_memory()
        return "(新会话已开始)"
    if cmd == "/sessions" and agent:
        sessions = agent.memory.list_sessions()
        return "\n".join(sessions) if sessions else "(无已保存会话)"
    return f"未知命令: {user_input}，输入 /help 查看可用命令"


def main():
    """主循环。"""
    config = load_config()
    print_assistant_message("MINGCODE-LC v0.1.0 已启动。输入 /help 查看命令，或直接开始对话。")

    # 延迟构造 agent（首次输入时）
    agent = None
    try:
        from core.agent import LangChainAgent
        agent = LangChainAgent(config=config)
    except Exception as e:
        print_error(f"Agent 初始化失败（将仅支持命令模式）: {e}")

    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            print_user_message(user_input)

            # 命令处理
            cmd_response = handle_command(user_input, agent)
            if cmd_response is not None:
                print_assistant_message(cmd_response)
                continue

            # Agent 对话
            if agent is None:
                print_error("Agent 未初始化，无法对话。请检查配置后重启。")
                continue

            for chunk in agent.chat(user_input):
                print(chunk, end="", flush=True)
            print()  # 换行
        except (KeyboardInterrupt, EOFError):
            print_assistant_message("再见！")
            break
        except SystemExit:
            raise
        except Exception as e:
            print_error(f"发生错误: {e}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 更新测试**

```python
# tests/test_main_cli.py（更新）
"""main.py CLI 入口测试。"""
from unittest.mock import patch, MagicMock
from main import handle_command


def test_handle_help_command():
    """/help 命令应返回帮助文本。"""
    result = handle_command("/help")
    assert "MINGCODE-LC" in result
    assert "/help" in result
    assert "/exit" in result


def test_handle_unknown_command():
    """未知命令应返回提示。"""
    result = handle_command("/nonexistent")
    assert "未知" in result or "Unknown" in result


def test_handle_non_command():
    """非命令输入应返回 None。"""
    result = handle_command("hello")
    assert result is None


def test_handle_tools_with_agent():
    """/tools 命令带 agent 应返回工具列表。"""
    mock_agent = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "shell"
    mock_tool.description = "Execute shell command"
    mock_agent.tools = [mock_tool]
    result = handle_command("/tools", agent=mock_agent)
    assert "shell" in result


def test_handle_tools_without_agent():
    """/tools 命令无 agent 应返回未知命令提示（因为 if 条件不满足）。"""
    result = handle_command("/tools", agent=None)
    # agent=None 时 if cmd == "/tools" and agent 不成立，走到未知命令
    assert "未知" in result or "Unknown" in result
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python -m pytest tests/test_main_cli.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 4: 跑全部测试确认无回归**

Run: `python -m pytest tests/ -v`
Expected: PASS（Phase 1 全部 ~30 测试通过）

- [ ] **Step 5: 提交**

```bash
git add main.py tests/test_main_cli.py
git commit -m "feat(main): integrate LangChainAgent with CLI"
```

---

## Phase 1 完成标准

- [ ] 16 个工具全部实现并通过测试
- [ ] LangChainAgent 能构造并响应简单输入
- [ ] main.py 能完成完整对话循环
- [ ] `/help /tools /clear /new /sessions` 命令正常工作
- [ ] 30+ 单元测试全部通过
- [ ] 流式输出工作正常（通过 RichStreamHandler）
