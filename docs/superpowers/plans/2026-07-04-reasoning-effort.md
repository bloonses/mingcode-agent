# Reasoning Effort 实现计划

> **For agentic workers:** REQUIRED SUB-SILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 MINGCODE 加 `reasoning_effort` 参数支持，让用户通过 `/reasoning` 斜杠命令或 `/settings` wizard 动态调整 OpenAI o-series / DeepSeek-R1 / GLM-4.5 / Qwen3 等推理模型的思考深度（low/medium/high）。

**Architecture:** 在 `LLMClient` 实例属性上加 `reasoning_effort`（None/"low"/"medium"/"high"），`_build_payload` 仅在非 None 时把字段塞进 payload 顶层。CLI 入口加 `/reasoning` 斜杠命令 + settings wizard 加一步询问 + `/help` `/config` `/debug` 输出加该字段。TDD：先写 6 个测试，再改 config 和 llm，最后改 main.py。

**Tech Stack:** Python 3.8+ / pytest / requests / Rich / PyYAML

**Spec:** [docs/superpowers/specs/2026-07-04-reasoning-effort-design.md](file:///c:/Users/bloon/Downloads/neon_agent/docs/superpowers/specs/2026-07-04-reasoning-effort-design.md)

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `tests/test_reasoning_effort.py` | 新建 | 6 个测试覆盖构造、payload 行为、运行时修改、无效值兜底 |
| `config/config.py` | 修改 | `DEFAULT_CONFIG["llm"]` 加 `reasoning_effort: None`；`CONFIG_TEMPLATE` 加注释行 |
| `core/llm.py` | 修改 | 构造函数读 `reasoning_effort`（白名单过滤）；`_build_payload` 仅在非 None 时注入字段 |
| `main.py` | 修改 | 新增 `/reasoning` 命令；`run_settings_wizard` 加一步；`/help` `/config` `/debug` 加输出 |
| `MINGCODE_LEARNING_ROADMAP.md` | 不改 | 工程改进，不是新阶段 |

---

## Task 1: TDD - 写 reasoning_effort 测试文件

**Files:**
- Create: `tests/test_reasoning_effort.py`

- [ ] **Step 1: 写 6 个测试到新文件**

```python
"""reasoning_effort 参数的单元测试。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_llm(config=None):
    """构造 LLMClient，config 缺省时用最小配置。"""
    from core.llm import LLMClient
    cfg = config or {
        "base_url": "http://localhost:11434/v1",
        "api_key": "test-key",
        "model": "test-model",
    }
    return LLMClient(cfg)


class TestReasoningEffortConstruction:
    def test_default_reasoning_effort_is_none(self):
        """无配置构造时 reasoning_effort 应为 None。"""
        llm = _make_llm()
        assert llm.reasoning_effort is None

    def test_explicit_reasoning_effort_from_config(self):
        """配置 reasoning_effort='high' 时构造后应等于 'high'。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "high",
        })
        assert llm.reasoning_effort == "high"

    def test_invalid_config_value_falls_back_to_none(self):
        """配置无效值（如 'garbage'）时构造后应兜底为 None。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "garbage",
        })
        assert llm.reasoning_effort is None


class TestReasoningEffortPayload:
    def test_build_payload_omits_field_when_none(self):
        """reasoning_effort=None 时 payload 不应含 reasoning_effort 键。"""
        llm = _make_llm()
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert "reasoning_effort" not in payload

    def test_build_payload_includes_field_when_set(self):
        """reasoning_effort='high' 时 payload 应含 reasoning_effort='high'。"""
        llm = _make_llm({
            "base_url": "http://localhost:11434/v1",
            "api_key": "test-key",
            "model": "test-model",
            "reasoning_effort": "high",
        })
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert payload["reasoning_effort"] == "high"

    def test_runtime_change_reflects_in_next_payload(self):
        """运行时改 reasoning_effort='medium' 后下次 payload 应含该值。"""
        llm = _make_llm()
        llm.reasoning_effort = "medium"
        payload = llm._build_payload(messages=[{"role": "user", "content": "hi"}])
        assert payload["reasoning_effort"] == "medium"
```

- [ ] **Step 2: 跑测试确认全失败（LLMClient 还没 reasoning_effort 属性）**

Run: `python -m pytest tests/test_reasoning_effort.py -v`
Expected: 6 个测试全 FAIL，错误信息含 `AttributeError: 'LLMClient' object has no attribute 'reasoning_effort'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_reasoning_effort.py
git commit -m "test: add failing tests for reasoning_effort (RED)"
```

---

## Task 2: 在 config 默认配置里加 reasoning_effort 字段

**Files:**
- Modify: `config/config.py:27-34`（`DEFAULT_CONFIG["llm"]`）
- Modify: `config/config.py:77-125`（`CONFIG_TEMPLATE` YAML 字符串）

- [ ] **Step 1: 改 DEFAULT_CONFIG["llm"] 加 reasoning_effort: None**

定位 `config/config.py` 第 27-34 行：

```python
DEFAULT_CONFIG = {
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 4096
    },
```

改为（在 `max_tokens` 后加一行）：

```python
DEFAULT_CONFIG = {
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 4096,
        "reasoning_effort": None
    },
```

- [ ] **Step 2: 改 CONFIG_TEMPLATE YAML 字符串加注释行**

定位 `config/config.py` 第 77-125 行 `CONFIG_TEMPLATE`，找到 `max_tokens:` 那一行后加一行：

```yaml
  max_tokens: 4096
  reasoning_effort: null  # 推理模型思考深度：null / low / medium / high（仅推理模型生效）
```

- [ ] **Step 3: 跑测试确认仍是 6 个 FAIL（这一步还没改 LLMClient）**

Run: `python -m pytest tests/test_reasoning_effort.py -v`
Expected: 6 个 FAIL（仍因 `LLMClient` 无 `reasoning_effort` 属性）

- [ ] **Step 4: Commit**

```bash
git add config/config.py
git commit -m "feat(config): add reasoning_effort default field"
```

---

## Task 3: 在 LLMClient 加 reasoning_effort 属性和 payload 注入

**Files:**
- Modify: `core/llm.py:22-30`（构造函数）
- Modify: `core/llm.py:100-111`（`_build_payload`）

- [ ] **Step 1: 改构造函数读取 reasoning_effort 并白名单过滤**

定位 `core/llm.py` 第 22-30 行：

```python
class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", config)
        self.base_url = llm_config["base_url"].rstrip("/")
        self.api_key = llm_config["api_key"]
        self.model = llm_config["model"]
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.timeout = 60
```

改为（在 `self.timeout = 60` 后加两行）：

```python
class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", config)
        self.base_url = llm_config["base_url"].rstrip("/")
        self.api_key = llm_config["api_key"]
        self.model = llm_config["model"]
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.timeout = 60
        # 推理模型思考深度（None / "low" / "medium" / "high"）
        raw_effort = llm_config.get("reasoning_effort")
        self.reasoning_effort = raw_effort if raw_effort in ("low", "medium", "high") else None
```

- [ ] **Step 2: 改 _build_payload 在非 None 时注入字段**

定位 `core/llm.py` 第 100-111 行：

```python
def _build_payload(self, messages: List[Dict[str, Any]], tools: Optional[List] = None, stream: bool = False) -> Dict[str, Any]:
    payload = {
        "model": self.model,
        "messages": self._sanitize_messages(messages),
        "temperature": self.temperature,
        "max_tokens": self.max_tokens,
        "stream": stream
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload
```

改为（在 `if tools:` 块后、`return payload` 前加一个 if 块）：

```python
def _build_payload(self, messages: List[Dict[str, Any]], tools: Optional[List] = None, stream: bool = False) -> Dict[str, Any]:
    payload = {
        "model": self.model,
        "messages": self._sanitize_messages(messages),
        "temperature": self.temperature,
        "max_tokens": self.max_tokens,
        "stream": stream
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if self.reasoning_effort:  # None 或空字符串都不传
        payload["reasoning_effort"] = self.reasoning_effort
    return payload
```

- [ ] **Step 3: 跑 6 个测试确认全 PASS**

Run: `python -m pytest tests/test_reasoning_effort.py -v`
Expected: 6 PASS

- [ ] **Step 4: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 124 passed（118 原有 + 6 新增）

- [ ] **Step 5: Commit**

```bash
git add core/llm.py
git commit -m "feat(llm): add reasoning_effort support (GREEN)"
```

---

## Task 4: 在 main.py 加 /reasoning 斜杠命令

**Files:**
- Modify: `main.py:386-394`（在 `/model` 分支后插入 `/reasoning` 分支）

- [ ] **Step 1: 定位 /model 分支作为参照**

Run: `grep -n "elif cmd == '/model'" main.py`
Expected: 显示 `/model` 分支所在行号（约 386 行）

读取 `main.py` 第 386-394 行确认 `/model` 分支结构：

```python
elif cmd == '/model':
    if not arg:
        console.print(f"[{NEON_TEAL}]Current model: {agent.llm.model}[/{NEON_TEAL}]")
        return True
    agent.llm.model = arg.strip()
    config['llm']['model'] = arg.strip()
    save_config(config)
    console.print(f"[{NEON_TEAL}]Switched to model: {agent.llm.model}[/{NEON_TEAL}]")
    return True
```

- [ ] **Step 2: 在 /model 分支后插入 /reasoning 分支**

在第 394 行 `return True` 之后、下一个 `elif` 之前插入：

```python
elif cmd == '/reasoning':
    if not arg:
        current = agent.llm.reasoning_effort or "off"
        console.print(f"[{NEON_TEAL}]Reasoning effort: {current}[/{NEON_TEAL}]")
        console.print(f"[{NEON_DIM}]Options: off / low / medium / high[/{NEON_DIM}]")
        console.print(f"[{NEON_DIM}]Note: 仅推理模型（如 o1/r1/qwen3-thinking）生效[/{NEON_DIM}]")
        return True
    val = arg.strip().lower()
    if val == "off":
        val = None
    if val not in (None, "low", "medium", "high"):
        console.print(f"[{NEON_RED}]Invalid value. Use: off / low / medium / high[/{NEON_RED}]")
        return True
    agent.llm.reasoning_effort = val
    config['llm']['reasoning_effort'] = val
    save_config(config)
    display = val or "off"
    console.print(f"[{NEON_TEAL}]Reasoning effort set to: {display}[/{NEON_TEAL}]")
    return True
```

**注意**：若 `NEON_DIM` 或 `NEON_RED` 未在该文件顶部 import，先 grep 确认。如果只有 `NEON_TEAL`，把 `NEON_DIM` 改为 `NEON_TEAL`、`NEON_RED` 改为 `NEON_TEAL` 即可。

- [ ] **Step 3: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 124 passed

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(cli): add /reasoning slash command"
```

---

## Task 5: 在 settings wizard 加 reasoning_effort 询问步骤

**Files:**
- Modify: `main.py:771-855`（`run_settings_wizard` 函数）

- [ ] **Step 1: 定位 max_tokens 询问位置**

Run: `grep -n "Max tokens" main.py`
Expected: 显示 `Prompt.ask("  Max tokens", ...)` 所在行号（约 820 行）

读取 `main.py` 第 819-823 行确认 max_tokens 询问结构：

```python
try:
    tokens_str = Prompt.ask("  Max tokens", default=str(config['llm'].get('max_tokens', 4096)))
    max_tokens = int(tokens_str)
except ValueError:
    max_tokens = 4096
```

- [ ] **Step 2: 在 max_tokens 解析后加 reasoning_effort 询问**

在第 823 行 `max_tokens = 4096` 之后插入：

```python
effort_str = Prompt.ask("  Reasoning effort (off/low/medium/high)",
                        default=str(config['llm'].get('reasoning_effort') or "off"))
effort_str = effort_str.strip().lower()
if effort_str in ("off", "", "none"):
    reasoning_effort = None
elif effort_str in ("low", "medium", "high"):
    reasoning_effort = effort_str
else:
    reasoning_effort = None  # 兜底
```

- [ ] **Step 3: 在 Summary 块加一行显示 reasoning**

Run: `grep -n "Max History:" main.py` 找 summary 块位置，或 `grep -n "Max Tokens:" main.py`。

读取 summary 块（约第 825-836 行），在 `console.print(f"  Max Tokens:  {max_tokens}")` 之后加：

```python
console.print(f"  Reasoning:   {reasoning_effort or 'off'}")
```

- [ ] **Step 4: 在双层更新块加 reasoning_effort**

读取双层更新块（约第 836-848 行）：

```python
if confirm:
    config['llm']['base_url'] = base_url
    config['llm']['api_key'] = api_key
    config['llm']['model'] = model
    config['llm']['temperature'] = temperature
    config['llm']['max_tokens'] = max_tokens
    save_config(config)

    agent.llm.base_url = base_url
    agent.llm.api_key = api_key
    agent.llm.model = model
    agent.llm.temperature = temperature
    agent.llm.max_tokens = max_tokens
```

改为（在 `config['llm']['max_tokens']` 后加一行，在 `agent.llm.max_tokens` 后加一行）：

```python
if confirm:
    config['llm']['base_url'] = base_url
    config['llm']['api_key'] = api_key
    config['llm']['model'] = model
    config['llm']['temperature'] = temperature
    config['llm']['max_tokens'] = max_tokens
    config['llm']['reasoning_effort'] = reasoning_effort
    save_config(config)

    agent.llm.base_url = base_url
    agent.llm.api_key = api_key
    agent.llm.model = model
    agent.llm.temperature = temperature
    agent.llm.max_tokens = max_tokens
    agent.llm.reasoning_effort = reasoning_effort
```

- [ ] **Step 5: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 124 passed

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat(cli): add reasoning_effort step in settings wizard"
```

---

## Task 6: 在 /help、/config、/debug 输出加 reasoning_effort 字段

**Files:**
- Modify: `main.py:164-220`（`/help` 输出）
- Modify: `main.py:395-409`（`/config` 输出）
- Modify: `main.py:433-473`（`/debug` 输出）

- [ ] **Step 1: 在 /help 输出加 /reasoning 行**

Run: `grep -n "/model " main.py` 找 `/help` 列表里 `/model` 行所在位置。

读取 `/help` 块（约第 164-220 行），找到 `/model` 描述行：

```
  /model [name]                     - 切换或显示当前模型
```

在 `/model` 行后加一行：

```
  /reasoning [off|low|medium|high]  - 查看或设置推理模型思考深度
```

**注意**：保持列对齐（与 `/model` 行的空格数一致）。

- [ ] **Step 2: 在 /config 输出加 reasoning 行**

Run: `grep -n "Max History:" main.py` 找 `/config` 输出位置。

读取 `/config` 块（约第 395-409 行）：

```python
elif cmd == '/config':
    console.print()
    console.print(f"[{NEON_TEAL} bold]Configuration[/{NEON_TEAL} bold]")
    llm_config = config.get('llm', {})
    mem_config = config.get('memory', {})
    console.print(f"  Base URL:    {llm_config.get('base_url', 'N/A')}")
    ...
    console.print(f"  Max Tokens:  {llm_config.get('max_tokens', 4096)}")
    ...
```

在 `Max Tokens:` 行后加：

```python
    console.print(f"  Reasoning:   {llm_config.get('reasoning_effort') or 'off'}")
```

- [ ] **Step 3: 在 /debug 输出加 reasoning 行**

Run: `grep -n "Version: 1.1.0" main.py` 找 `/debug` 块位置。

读取 `/debug` 块（约第 433-473 行），找到 `Model:` 或 `Temperature:` 行，在其后加：

```python
    console.print(f"  Reasoning:   {agent.llm.reasoning_effort or 'off'}")
```

- [ ] **Step 4: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 124 passed

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(cli): show reasoning_effort in /help /config /debug"
```

---

## Task 7: 最终验证

- [ ] **Step 1: 跑全套测试**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 124 passed

- [ ] **Step 2: 手动验证 /reasoning 命令**

启动 `python main.py`，依次执行：
- `/reasoning` → 显示 "Reasoning effort: off" + Options 提示
- `/reasoning high` → 显示 "Reasoning effort set to: high"
- `/reasoning` → 显示 "Reasoning effort: high"
- `/reasoning off` → 显示 "Reasoning effort set to: off"
- `/reasoning garbage` → 显示 "Invalid value. Use: off / low / medium / high"
- `/config` → 输出含 "Reasoning: off" 行
- `/help` → 列表含 `/reasoning` 行
- `/debug` → 输出含 "Reasoning:" 行

- [ ] **Step 3: 手动验证 /settings wizard**

启动 `python main.py`，执行 `/settings`，走完 wizard，确认：
- 出现 "Reasoning effort (off/low/medium/high)" 询问
- Summary 块显示 "Reasoning:" 行
- 保存后 `/config` 显示新值

- [ ] **Step 4: 确认 config.yaml 持久化**

读取 user_data_dir/config.yaml，确认含 `reasoning_effort: null` 或 `reasoning_effort: high` 字段。

- [ ] **Step 5: Final commit（如需版本号 bump）**

如果需要 bump 到 v1.1.1：

修改 `pyproject.toml`、`setup.iss`、`main.py`（`/debug` 输出的 Version）、`ui/console.py`（logo）、`build.bat`、`README.md` 中的版本号从 `1.1.0` 改为 `1.1.1`。

```bash
git add -A
git commit -m "chore: bump version to 1.1.1"
```

（这一步可选，spec 未强制要求 bump。）

---

## Self-Review 检查

**Spec coverage**：
- ✅ 2.1 状态机（None/low/medium/high）→ Task 3 `_build_payload` + Task 1 测试
- ✅ 2.2 兼容性（None vs ""、白名单过滤、SubAgent 自动应用）→ Task 3 构造函数白名单 + `if self.reasoning_effort:`
- ✅ 3.1 config 默认字段 → Task 2
- ✅ 3.2 llm.py 构造 + payload → Task 3
- ✅ 3.3 main.py /reasoning 命令 + wizard + /help /config /debug → Task 4 + Task 5 + Task 6
- ✅ 3.4 测试文件 → Task 1
- ✅ 4 边界处理（无效值兜底、None 过滤、YAML 持久化、SubAgent 自动应用）→ Task 3 + Task 1 测试覆盖
- ✅ 5 验收标准 → Task 7 验证

**Placeholder scan**：无 TBD/TODO，所有步骤含完整代码。

**Type consistency**：`reasoning_effort` 属性名在所有 Task 中一致；`_make_llm` 测试辅助函数在 Task 1 定义、Task 1 内所有测试复用，无跨 Task 类型不一致。
