# Phase 0: 项目初始化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 mingcode-langchain 项目骨架，复用 NeonAgent UI，配置 LLM 客户端，确保 `python main.py` 能启动并响应 `/help` 命令

**Architecture:** uv 管理依赖，pyproject.toml 配置包元数据，config.py 兼容 NeonAgent 结构，core/llm.py 用 ChatOpenAI 工厂函数支持多供应商，ui/ 直接 copy neon_agent/ui/ 保持赛博极简风格

**Tech Stack:** Python 3.8+, uv, langchain-openai, langgraph, rich, pydantic, pyyaml

---

## File Structure

- Create: `pyproject.toml` - uv 包配置
- Create: `config/__init__.py`, `config/config.py` - 配置加载（复用 NeonAgent 结构）
- Create: `core/__init__.py`, `core/llm.py` - LLM 客户端工厂
- Create: `ui/__init__.py`, `ui/console.py`, `ui/theme.py`, `ui/callbacks.py` - Rich UI（复用 + LangChain 桥接）
- Create: `main.py` - CLI 入口（最小版，仅 /help /exit）
- Create: `tests/__init__.py`, `tests/conftest.py`, `tests/test_llm.py`, `tests/test_config.py` - 测试
- Create: `.gitignore`, `README.md` - 项目元数据
- Reference: `c:\Users\bloon\Downloads\neon_agent\ui\*` - UI 复用源
- Reference: `c:\Users\bloon\Downloads\neon_agent\config\config.py` - 配置参考

---

### Task 1: 创建 pyproject.toml + 初始化 uv 项目

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mingcode-lc"
version = "lc-v0.1.0"
description = "MINGCODE-LC - LangChain version of cyberpunk AI coding assistant"
requires-python = ">=3.10"
dependencies = [
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",
    "langgraph>=0.2.0",
    "langgraph-checkpoint-sqlite>=2.0.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "requests>=2.28.0",
    "duckduckgo-search>=3.0.0",
    "pygments>=2.10.0",
    "qrcode>=7.3.1",
    "websocket-client>=1.6.0",
    "cryptography>=41.0.0",
    "pyautogui>=0.9.54",
    "Pillow>=9.0.0",
    "pygetwindows>=0.0.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
mingcode-lc = "main:main"

[tool.hatch.build.targets.wheel]
packages = ["config", "core", "tools", "ui"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: 创建 .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg

# uv
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project
config.yaml
checkpoints.db
checkpoints.db-journal
todos.json
screenshots/
*.log

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: init uv project with pyproject.toml"
```

---

### Task 2: 复用 NeonAgent UI 模块

**Files:**
- Create: `ui/__init__.py`
- Create: `ui/theme.py`
- Create: `ui/console.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\ui\theme.py`, `c:\Users\bloon\Downloads\neon_agent\ui\console.py`

- [ ] **Step 1: 创建 ui/__init__.py**

```python
"""UI 模块 - 赛博极简 Rich 主题（复用自 NeonAgent）。"""
```

- [ ] **Step 2: 创建 ui/theme.py**

```python
"""赛博极简主题 - 霓虹青绿色调。"""
from rich.theme import Theme

NEON_THEME = Theme({
    "primary": "#00ff88",
    "secondary": "#00d9ff",
    "accent": "#ff00aa",
    "muted": "#5a8a7a",
    "background": "#050510",
    "panel.border": "#00ff88",
    "panel.title": "#00ff88 bold",
    "tool.name": "#00d9ff bold",
    "thinking": "#5a8a7a italic",
    "error": "#ff3366",
    "warning": "#ffaa00",
    "success": "#00ff88",
    "user": "#00ff88 bold",
    "assistant": "#ffffff",
})
```

- [ ] **Step 3: 创建 ui/console.py**

```python
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
    # 由 callbacks.py 的 RichStreamHandler 管理 Live
    pass
```

- [ ] **Step 4: 提交**

```bash
git add ui/
git commit -m "feat(ui): reuse neon_agent cyberpunk UI"
```

---

### Task 3: LangChain StreamingCallback 桥接 Rich

**Files:**
- Create: `ui/callbacks.py`
- Test: `tests/test_callbacks.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_callbacks.py
"""LangChain StreamingCallback 桥接 Rich 测试。"""
from ui.callbacks import RichStreamHandler


def test_handler_collects_tokens():
    """handler 应能收集所有 token 并形成完整文本。"""
    handler = RichStreamHandler()
    handler.on_llm_new_token("Hello")
    handler.on_llm_new_token(" ")
    handler.on_llm_new_token("World")
    assert handler.collected_text == "Hello World"


def test_handler_starts_and_ends():
    """handler 应有 start/end 钩子，不抛异常。"""
    handler = RichStreamHandler()
    handler.on_llm_start(serialized={}, messages=[{"content": "hi"}])
    handler.on_llm_end(response={"generations": []})
    assert handler.collected_text == ""


def test_handler_handles_error():
    """handler on_llm_error 不应抛异常。"""
    handler = RichStreamHandler()
    handler.on_llm_error(error=Exception("test"))
    # 不抛即通过
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_callbacks.py -v`
Expected: FAIL with "No module named 'ui.callbacks'"

- [ ] **Step 3: 实现 callbacks.py**

```python
# ui/callbacks.py
"""LangChain StreamingCallback 桥接 Rich Live 区域。"""
from typing import Optional
from rich.live import Live
from rich.text import Text
from langchain_core.callbacks import BaseCallbackHandler


class RichStreamHandler(BaseCallbackHandler):
    """收集 LLM 流式 token，可桥接到 Rich Live 区域。"""

    def __init__(self, live: Optional[Live] = None):
        self.live = live
        self.collected_text = ""
        self._text = Text()

    def on_llm_start(self, serialized, messages, **kwargs):
        self.collected_text = ""
        self._text = Text()

    def on_llm_new_token(self, token, **kwargs):
        self.collected_text += token
        self._text.append(token)
        if self.live is not None:
            self.live.update(self._text)

    def on_llm_end(self, response, **kwargs):
        pass

    def on_llm_error(self, error, **kwargs):
        # 不抛异常，由调用方处理
        pass
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_callbacks.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add ui/callbacks.py tests/test_callbacks.py
git commit -m "feat(ui): add RichStreamHandler bridging LangChain streaming to Rich"
```

---

### Task 4: 配置模块（兼容 NeonAgent 结构）

**Files:**
- Create: `config/__init__.py`
- Create: `config/config.py`
- Test: `tests/test_config.py`
- Reference: `c:\Users\bloon\Downloads\neon_agent\config\config.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
"""配置加载测试。"""
import os
import tempfile
from config.config import load_config, DEFAULT_CONFIG


def test_default_config_has_llm_section():
    assert "llm" in DEFAULT_CONFIG
    assert "base_url" in DEFAULT_CONFIG["llm"]
    assert "api_key" in DEFAULT_CONFIG["llm"]
    assert "model" in DEFAULT_CONFIG["llm"]


def test_default_config_has_cognitive_section():
    assert "cognitive" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["cognitive"]["enabled"] is True
    assert DEFAULT_CONFIG["cognitive"]["self_ask"] is False
    assert DEFAULT_CONFIG["cognitive"]["tot_candidates"] == 3


def test_load_config_returns_default_when_no_file():
    """无配置文件时应返回默认配置。"""
    config = load_config("nonexistent.yaml")
    assert config["llm"]["base_url"] == "http://localhost:11434/v1"
    assert config["cognitive"]["enabled"] is True


def test_load_config_reads_yaml(tmp_path):
    """有配置文件时应读取并合并默认。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
llm:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-test"
  model: "deepseek-chat"
""")
    config = load_config(str(config_file))
    assert config["llm"]["model"] == "deepseek-chat"
    # 默认值应保留
    assert config["cognitive"]["enabled"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with "No module named 'config'"

- [ ] **Step 3: 实现 config/__init__.py 和 config/config.py**

```python
# config/__init__.py
"""配置管理模块。"""
```

```python
# config/config.py
"""配置加载 - 兼容 NeonAgent 结构。"""
import os
from typing import Dict, Any
import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 4096,
        "reasoning_effort": None,
    },
    "ui": {
        "theme": "neon",
        "animation": True,
        "show_thinking": True,
        "show_tools": True,
    },
    "tools": {
        "shell": {"enabled": True, "timeout": 30},
        "file": {"enabled": True},
        "python": {"enabled": True, "timeout": 10},
        "search": {"enabled": True, "max_results": 5},
    },
    "memory": {
        "max_history": 50,
    },
    "cognitive": {
        "enabled": True,
        "tot_candidates": 3,
        "max_replans": 3,
        "max_task_retries": 2,
        "self_ask": False,
    },
    "wechat": {"enabled": False, "auto_start": False},
    "qq": {
        "onebot": {"enabled": False, "ws_url": "ws://127.0.0.1:3001", "access_token": "", "auto_start": False},
        "official": {"enabled": False, "appid": "", "secret": "", "auto_start": False},
    },
}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """递归合并 override 到 base。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """加载配置文件，与 DEFAULT_CONFIG 深合并。"""
    config = dict(DEFAULT_CONFIG)
    if not os.path.exists(config_path):
        return config
    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}
    return _deep_merge(config, user_config)


def save_config(config: Dict[str, Any], config_path: str = "config.yaml"):
    """保存配置到文件。"""
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add config/ tests/test_config.py
git commit -m "feat(config): add config loader with neon_agent-compatible structure"
```

---

### Task 5: LLM 客户端工厂（ChatOpenAI）

**Files:**
- Create: `core/__init__.py`
- Create: `core/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm.py
"""LLM 客户端工厂测试。"""
from unittest.mock import patch, MagicMock
from core.llm import create_llm, LLMClientWrapper


def test_create_llm_returns_chat_openai():
    """create_llm 应返回 ChatOpenAI 实例。"""
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-chat",
            "temperature": 0.5,
            "max_tokens": 2048,
            "reasoning_effort": None,
        }
    }
    llm = create_llm(config)
    assert llm is not None
    assert llm.model_name == "deepseek-chat"
    assert llm.temperature == 0.5
    assert llm.max_tokens == 2048


def test_create_llm_with_reasoning_effort():
    """reasoning_effort 应通过 model_kwargs 透传。"""
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-r1",
            "reasoning_effort": "high",
        }
    }
    llm = create_llm(config)
    assert llm.model_kwargs.get("reasoning_effort") == "high"


def test_create_llm_without_reasoning_effort():
    """reasoning_effort=None 时不应设置 model_kwargs。"""
    config = {
        "llm": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-test",
            "model": "deepseek-chat",
            "reasoning_effort": None,
        }
    }
    llm = create_llm(config)
    assert "reasoning_effort" not in llm.model_kwargs


def test_llm_wrapper_chat_returns_content():
    """LLMClientWrapper.chat 应返回包含 content 的 dict。"""
    mock_chat = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "hello back"
    mock_chat.invoke.return_value = mock_response
    wrapper = LLMClientWrapper(mock_chat)
    result = wrapper.chat([{"role": "user", "content": "hi"}])
    assert result["content"] == "hello back"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_llm.py -v`
Expected: FAIL with "No module named 'core.llm'"

- [ ] **Step 3: 实现 core/llm.py**

```python
# core/llm.py
"""LLM 客户端工厂 - 用 ChatOpenAI 兼容多供应商。"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI


def create_llm(config: Dict[str, Any]) -> ChatOpenAI:
    """根据 config 创建 ChatOpenAI 实例。

    兼容 Ollama / OpenAI / DeepSeek / Qwen / Zhipu / Moonshot 等 OpenAI 格式 API。
    """
    llm_config = config.get("llm", config)
    base_url = llm_config["base_url"].rstrip("/")
    api_key = llm_config.get("api_key", "ollama")
    model = llm_config["model"]
    temperature = llm_config.get("temperature", 0.7)
    max_tokens = llm_config.get("max_tokens", 4096)

    raw_effort = llm_config.get("reasoning_effort")
    reasoning_effort = raw_effort if raw_effort in ("low", "medium", "high") else None

    model_kwargs = {}
    if reasoning_effort:
        model_kwargs["reasoning_effort"] = reasoning_effort

    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True,
        model_kwargs=model_kwargs,
    )


class LLMClientWrapper:
    """包装 ChatOpenAI 提供 NeonAgent 兼容的 chat 接口。

    用于 Reflector / Planner / SelfAsker 等内部模块，
    它们期望 chat(messages) -> {"content": str, "tool_calls": list} 格式。
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List] = None,
             stream: bool = False) -> Dict[str, Any]:
        """同步调用 LLM，返回 dict 格式响应。"""
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        response = self.llm.invoke(messages, **kwargs)
        return {
            "content": getattr(response, "content", "") or "",
            "tool_calls": getattr(response, "tool_calls", None),
            "raw": response,
        }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_llm.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/__init__.py core/llm.py tests/test_llm.py
git commit -m "feat(llm): add ChatOpenAI factory with reasoning_effort support"
```

---

### Task 6: main.py CLI 入口（最小版）

**Files:**
- Create: `main.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_main_cli.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_main_cli.py
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
    """非命令输入应返回 None（交给 Agent 处理）。"""
    result = handle_command("hello")
    assert result is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_main_cli.py -v`
Expected: FAIL with "No module named 'main'"

- [ ] **Step 3: 实现 main.py**

```python
# main.py
"""MINGCODE-LC CLI 入口。"""
import sys
from typing import Optional

from ui.console import console, print_assistant_message, print_user_message, print_error


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


def handle_command(user_input: str) -> Optional[str]:
    """处理 / 命令，返回响应字符串。非命令返回 None。"""
    if not user_input.startswith("/"):
        return None
    cmd = user_input.strip().lower()
    if cmd == "/help":
        return HELP_TEXT
    if cmd == "/exit":
        sys.exit(0)
    return f"未知命令: {user_input}，输入 /help 查看可用命令"


def main():
    """主循环。"""
    print_assistant_message("MINGCODE-LC v0.1.0 已启动。输入 /help 查看命令，或直接开始对话。")
    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            print_user_message(user_input)
            response = handle_command(user_input)
            if response is not None:
                print_assistant_message(response)
            else:
                # Phase 1 接入 Agent，Phase 0 占位
                print_assistant_message("(Phase 0: Agent 尚未接入，请等待 Phase 1)")
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

```python
# tests/__init__.py
```

```python
# tests/conftest.py
"""pytest 配置。"""
import sys
import os

# 让 tests 能 import 项目根的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_main_cli.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 跑全部测试确认无回归**

Run: `python -m pytest tests/ -v`
Expected: PASS（10 个测试全过：3+3+4+3+3）

- [ ] **Step 6: 提交**

```bash
git add main.py tests/__init__.py tests/conftest.py tests/test_main_cli.py
git commit -m "feat(main): add minimal CLI entry with /help and /exit"
```

---

### Task 7: README 初版 + 最终验证

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 README.md**

```markdown
# MINGCODE-LC <img src="https://img.shields.io/badge/version-lc--v0.1.0-neon?style=flat-square&color=%2300ff88" alt="version"> <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square" alt="python"> <img src="https://img.shields.io/badge/stack-LangChain%20%2B%20LangGraph-9cf?style=flat-square" alt="stack">

> ⚡ MINGCODE 的 LangChain 版本，用 LangGraph StateGraph 重写认知框架

**MINGCODE-LC** 是 [MINGCODE](../neon_agent) 的 LangChain 等价实现，用 LangGraph StateGraph 替代手撸状态机，用 @tool 装饰器替代 BaseTool ABC，用 SqliteSaver 替代手动会话持久化。

## 状态：Phase 0 已完成（项目骨架 + UI + 配置 + LLM 客户端）

## 快速开始

```bash
# 安装 uv
pip install uv

# 同步依赖
uv sync

# 运行
python main.py

# 或安装到 PATH
uv pip install -e .
mingcode-lc
```

## 与 NeonAgent 对比

| 维度 | NeonAgent | MINGCODE-LC |
|------|-----------|-------------|
| 状态机 | while/if 循环 | LangGraph StateGraph |
| 工具 | BaseTool ABC + 自定义 Registry | @tool + Pydantic |
| 记忆 | 手动 list + JSON 持久化 | SqliteSaver checkpointer |
| LLM | requests 手撸 | ChatOpenAI |
| 流式 | 自定义 generator | LangChain BaseCallbackHandler |
| 依赖大小 | ~10 MB | ~200 MB（LangChain 生态） |

## 项目结构

详见 [pyproject.toml](pyproject.toml) 和 [docs/superpowers/specs/2026-07-05-langchain-version-design.md](docs/superpowers/specs/2026-07-05-langchain-version-design.md)

## 测试

```bash
python -m pytest tests/ -v
```
```

- [ ] **Step 2: 跑全部测试最终确认**

Run: `python -m pytest tests/ -v`
Expected: PASS（10 个测试全过）

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs: add Phase 0 README with neon_agent comparison"
```

---

## Phase 0 完成标准

- [ ] `python main.py` 能启动，显示欢迎信息
- [ ] `/help` 命令显示帮助文本
- [ ] `/exit` 命令正常退出
- [ ] 10 个单元测试全部通过
- [ ] pyproject.toml 配置完整，`uv sync` 能安装依赖
- [ ] README.md 有项目说明和与 NeonAgent 的对比
