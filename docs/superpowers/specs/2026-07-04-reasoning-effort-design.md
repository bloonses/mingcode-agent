# Reasoning Effort（可调整思考深度）设计文档

**日期**：2026-07-04
**版本**：v1.1.1
**作者**：MINGCODE

---

## 1. 背景与目标

### 1.1 现状

MINGCODE v1.1.0 的 `LLMClient` 仅接受 `temperature` 和 `max_tokens` 两个采样参数（[core/llm.py#L22-L30](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py#L22-L30)），请求 payload 中不含任何 `reasoning` / `thinking` / `effort` 字段。这意味着用户无法在 CLI 中切换推理模型的思考深度。

### 1.2 目标

新增 `reasoning_effort` 参数支持，遵循 OpenAI o-series 标准（`low` / `medium` / `high`），让用户通过 `/reasoning` 斜杠命令或 `/settings` wizard 动态调整推理模型的思考深度。

### 1.3 非目标（YAGNI）

- 不做多供应商字段适配（智谱 GLM-Z1 的 `thinking` 对象、Qwen3 的 `enable_thinking` 等）
- 不给 `chat()` 方法加 `reasoning_effort` 单次调用覆盖参数（运行时改实例属性即可）
- 不更新 `MINGCODE_LEARNING_ROADMAP.md`（这是工程改进，不是新阶段）
- 不调整 ReAct 循环最大轮数（用户已选不做）

---

## 2. 数据模型

### 2.1 `reasoning_effort` 状态机

| 值 | 含义 | payload 行为 |
|----|------|--------------|
| `None` | 未设置（默认，等价于 "off"） | 不传该字段到 API payload |
| `"low"` | 浅思考 | `payload["reasoning_effort"] = "low"` |
| `"medium"` | 中等思考 | `payload["reasoning_effort"] = "medium"` |
| `"high"` | 深思考 | `payload["reasoning_effort"] = "high"` |

**设计决策**：选 `None` 而非字符串 `"off"` 作默认值，原因：
1. API payload 中需要"缺省"而非"传 off"（传 `off` 非推理模型会报 400）
2. `None` 在 Python 里更自然表达"未设置"
3. YAML 持久化为 `null`，加载时 `config.get(...)` 返回 `None`，循环无 bug

### 2.2 兼容性

- **非推理模型 + 设置 high**：API 会报 400 错误，由现有 `LLMError` 处理链捕获，不阻断设置过程
- **`None` vs 空字符串**：`if self.reasoning_effort:` 同时过滤 `None` 和 `""`
- **SubAgent / plan_tot 等内部调用**：它们调 `self.llm.chat()` 时自动应用当前 `reasoning_effort`，无需特殊处理

---

## 3. 涉及文件改动

### 3.1 `config/config.py`

**位置**：第 27-34 行 `DEFAULT_CONFIG["llm"]` 字典

```python
"llm": {
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "model": "qwen2.5:7b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "reasoning_effort": None  # 新增：None / "low" / "medium" / "high"
},
```

`CONFIG_TEMPLATE`（YAML 模板字符串）同步加注释行：

```yaml
llm:
  base_url: http://localhost:11434/v1
  api_key: ollama
  model: qwen2.5:7b
  temperature: 0.7
  max_tokens: 4096
  reasoning_effort: null  # 推理模型思考深度：null / low / medium / high（仅推理模型生效）
```

### 3.2 `core/llm.py`

**位置 1**：构造函数（第 22-30 行）加一行：

```python
def __init__(self, config: Dict[str, Any]):
    llm_config = config.get("llm", config)
    self.base_url = llm_config["base_url"].rstrip("/")
    self.api_key = llm_config["api_key"]
    self.model = llm_config["model"]
    self.temperature = llm_config.get("temperature", 0.7)
    self.max_tokens = llm_config.get("max_tokens", 4096)
    self.timeout = 60
    # 新增：推理模型思考深度（None / "low" / "medium" / "high"）
    raw_effort = llm_config.get("reasoning_effort")
    self.reasoning_effort = raw_effort if raw_effort in ("low", "medium", "high") else None
```

**位置 2**：`_build_payload`（第 100-111 行）加字段注入：

```python
def _build_payload(self, messages, tools=None, stream=False):
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

### 3.3 `main.py`

**位置 1**：新增 `/reasoning` 命令分支（参考 `/model` 第 386-394 行模式，插入到 `/model` 分支之后）：

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

**位置 2**：`run_settings_wizard`（第 771-855 行）在 `max_tokens` 询问后加一步：

```python
# 在第 823 行 max_tokens 解析后插入
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

**位置 3**：`run_settings_wizard` 的 summary + 双层更新（第 825-852 行）加该项：

```python
# Summary 块加一行
console.print(f"  Reasoning:   {reasoning_effort or 'off'}")

# 双层更新块加两行
config['llm']['reasoning_effort'] = reasoning_effort
agent.llm.reasoning_effort = reasoning_effort
```

**位置 4**：`/help` 输出（第 164-220 行）加一行：

```
  /reasoning [off|low|medium|high]  - 查看或设置推理模型思考深度
```

**位置 5**：`/config` 输出（第 395-409 行）加一行：

```python
console.print(f"  Reasoning:   {llm_config.get('reasoning_effort') or 'off'}")
```

**位置 6**：`/debug` 输出（搜索 `Version: 1.1.0` 附近）加一行：

```python
console.print(f"  Reasoning:   {agent.llm.reasoning_effort or 'off'}")
```

### 3.4 `tests/test_reasoning_effort.py`（新文件）

6 个测试覆盖：

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

---

## 4. 边界处理

| 场景 | 处理 |
|------|------|
| 非推理模型 + 设置 high | API 报 400，由 LLMError 链捕获，不阻断设置过程；`/reasoning` 切换时打印提示"仅推理模型生效" |
| 配置文件值为 `"garbage"` | 构造时兜底为 `None`（白名单过滤） |
| 配置文件值为空字符串 `""` | `if self.reasoning_effort:` 过滤，等同 `None` |
| YAML 持久化 `None` | 写为 `null`，加载时 `config.get(...)` 返回 `None` |
| SubAgent 内部调用 | 自动应用当前 `reasoning_effort`，无需特殊处理 |
| `chat_with_image` 调用 | 同上，走 `self.chat()` 自动应用 |

---

## 5. 验收标准

- [ ] 全部测试通过（118 + 6 = 124 个）
- [ ] `LLMClient()` 无参配置构造时 `reasoning_effort is None`
- [ ] 配置 `reasoning_effort="high"` 时构造后 `== "high"`
- [ ] 配置无效值时构造后兜底为 `None`
- [ ] `reasoning_effort=None` 时 payload 不含该字段
- [ ] `reasoning_effort="high"` 时 payload 含 `reasoning_effort="high"`
- [ ] 运行时改 `reasoning_effort="medium"` 后下次 payload 反映新值
- [ ] `/reasoning` 无 arg 显示当前值
- [ ] `/reasoning high` 切换成功并持久化到 config
- [ ] `/reasoning off` 切换为 None 并持久化
- [ ] `/reasoning garbage` 拒绝并提示可用值
- [ ] `/settings` wizard 包含 reasoning effort 询问步骤
- [ ] `/help`、`/config`、`/debug` 输出包含 reasoning effort 字段
- [ ] 现有 118 个测试无回归

---

## 6. 实现顺序

1. **RED**：写 `tests/test_reasoning_effort.py` 6 个测试，全部失败
2. **GREEN**：改 `config/config.py` 加默认字段
3. **GREEN**：改 `core/llm.py` 构造函数 + `_build_payload`，6 个测试全过
4. **GREEN**：改 `main.py` 加 `/reasoning` 命令、wizard 步骤、`/help` `/config` `/debug` 输出
5. **REFACTOR**：跑全套测试确认无回归
6. **COMMIT**：`feat: add reasoning_effort support for reasoning models (v1.1.1)`
