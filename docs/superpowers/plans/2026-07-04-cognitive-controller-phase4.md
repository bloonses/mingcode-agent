# CognitiveController Phase 4: Self-Ask 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SelfAsker 实现 LLM 不确定性检测 + 调 ask_user 工具，Executor 每轮 ReAct 后触发不确定性检测，uncertain 时自动向用户提问。

**Architecture:** SelfAsker.check_uncertainty 接收 last_observation + task，调 LLM ~100 token 判断 confident/uncertain。uncertain 时 SelfAsker.ask 调 registry.execute_tool("ask_user", ...) 向用户提问，回答塞回 memory 作为 clarification。Executor 默认开启不确定性检测（可通过 config 关闭）。

**Tech Stack:** Python 3.8+ / pytest / requests

**Spec:** [docs/superpowers/specs/2026-07-04-cognitive-controller-design.md](file:///c:/Users/bloon/Downloads/neon_agent/docs/superpowers/specs/2026-07-04-cognitive-controller-design.md)

**Prerequisite:** Phase 1 + 2 + 3 已完成（158 测试通过）

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `core/self_asker.py` | 修改 | 实现真实 LLM 不确定性检测 + 调 ask_user |
| `core/executor.py` | 修改 | 默认开启不确定性检测 |
| `tests/test_self_asker.py` | 新建 | SelfAsker 测试 |
| `tests/test_executor.py` | 修改 | 加不确定性检测触发测试 |

---

## Task 1: TDD - 写 SelfAsker 测试

**Files:**
- Create: `tests/test_self_asker.py`

- [ ] **Step 1: 写测试文件**

```python
"""SelfAsker 测试（Phase 4: 不确定性检测 + Self-Ask）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_self_asker():
    from core.self_asker import SelfAsker
    return SelfAsker(MagicMock(), MagicMock())


class TestSelfAskerCheck:
    def test_confident_response_returns_confident(self):
        """LLM 返回 confident 时应返回 confident。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_uncertain_response_returns_uncertain_with_reason(self):
        """LLM 返回 uncertain 时应返回 uncertain: <reason>。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "uncertain: 需要确认文件路径"}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict.startswith("uncertain")
        assert "文件路径" in verdict

    def test_llm_failure_returns_confident(self):
        """LLM 调用失败时应兜底返回 confident（不阻断执行）。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', side_effect=Exception("network error")):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_empty_response_returns_confident(self):
        """LLM 返回空时应兜底返回 confident。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": ""}):
            verdict = asker.check_uncertainty("obs", {"desc": "t1"})
        assert verdict == "confident"

    def test_prompt_contains_task_and_observation(self):
        """prompt 应包含任务描述和最新观察。"""
        asker = _make_self_asker()
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}) as mock_chat:
            asker.check_uncertainty("工具返回：文件不存在", {"desc": "读取配置文件"})
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "读取配置文件" in prompt_text
        assert "文件不存在" in prompt_text

    def test_truncates_long_observation(self):
        """observation 过长时应截断。"""
        asker = _make_self_asker()
        long_obs = "x" * 1000
        with patch.object(asker.llm, 'chat', return_value={"content": "confident"}) as mock_chat:
            asker.check_uncertainty(long_obs, {"desc": "t1"})
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        # 验证 observation 被截断（< 600 字符）
        assert len(prompt_text) < 800


class TestSelfAskerAsk:
    def test_ask_calls_ask_user_tool(self):
        """ask 应调 registry.execute_tool('ask_user', ...)。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答：路径是 /tmp") as mock_tool:
            result = asker.ask("任务描述", "uncertain: 需要确认文件路径")
        mock_tool.assert_called_once()
        # 验证调用 ask_user 工具
        assert mock_tool.call_args[0][0] == "ask_user" or mock_tool.call_args[1].get('tool_name') == "ask_user"

    def test_ask_returns_user_response(self):
        """ask 应返回用户的回答字符串。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答"):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == "用户回答"

    def test_ask_extracts_question_from_uncertain_reason(self):
        """ask 应从 'uncertain: <reason>' 提取问题传给 ask_user。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value="用户回答") as mock_tool:
            asker.ask("任务描述", "uncertain: 文件路径是什么？")
        # 验证 prompt 含提取的问题
        call_kwargs = mock_tool.call_args[1]
        prompt_arg = call_kwargs.get('prompt', '')
        assert "文件路径是什么" in prompt_arg

    def test_ask_user_failure_returns_empty_string(self):
        """ask_user 工具调用失败时应返回空字符串（不阻断）。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', side_effect=Exception("tool error")):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == ""

    def test_ask_user_cancelled_returns_empty_string(self):
        """用户取消 ask_user 时应返回空字符串。"""
        asker = _make_self_asker()
        with patch.object(asker.registry, 'execute_tool', return_value=""):
            result = asker.ask("任务", "uncertain: 问题")
        assert result == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_self_asker.py -v`
Expected: 11 FAIL（Phase 1 SelfAsker stub 不实现真实逻辑）

- [ ] **Step 3: Commit**

```bash
git add tests/test_self_asker.py
git commit -m "test: add failing SelfAsker tests (RED)"
```

---

## Task 2: 实现 SelfAsker（GREEN）

**Files:**
- Modify: `core/self_asker.py`

- [ ] **Step 1: 替换 core/self_asker.py 为真实实现**

```python
"""SelfAsker - 不确定性检测 + Self-Ask。

Phase 4: LLM 不确定性检测 + 调 ask_user 工具向用户提问。
- check_uncertainty: ~100 token 判断 confident/uncertain
- ask: 调 registry.execute_tool("ask_user", ...) 向用户提问
"""
from typing import Dict


class SelfAsker:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.registry = tool_registry

    def check_uncertainty(self, last_observation: str, task: Dict) -> str:
        """判断是否不确定。返回 'confident' 或 'uncertain: <reason>'。"""
        try:
            # 截断过长 observation
            obs = last_observation
            if len(obs) > 500:
                obs = obs[:500] + "...[truncated]"

            prompt = (
                f"当前任务: {task.get('desc', '')}\n"
                f"最新观察: {obs}\n\n"
                f"基于当前进度，任务是否清晰可继续？\n"
                f"- 如果观察显示任务正常进行（如工具返回有效结果、文件存在等），输出 'confident'\n"
                f"- 如果观察显示有歧义、缺少信息、或需要用户确认（如文件不存在、参数模糊等），输出 'uncertain: <需要澄清的问题>'\n"
                f"只输出 'confident' 或 'uncertain: <问题>'。"
            )
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = (response.get("content") or "").strip()
            if not content:
                return "confident"
            return content
        except Exception:
            # LLM 失败兜底 confident（不阻断）
            return "confident"

    def ask(self, task_desc: str, uncertainty_reason: str) -> str:
        """触发 Self-Ask：调 ask_user 工具向用户提问。"""
        try:
            # 从 "uncertain: <reason>" 提取问题
            question = uncertainty_reason
            if ":" in uncertainty_reason:
                question = uncertainty_reason.split(":", 1)[1].strip()

            prompt = f"[Self-Ask] 任务「{task_desc}」需要澄清：{question}"
            result = self.registry.execute_tool("ask_user", prompt=prompt)
            return result if result else ""
        except Exception:
            # ask_user 失败不阻断
            return ""
```

- [ ] **Step 2: 跑 SelfAsker 测试确认全 PASS**

Run: `python -m pytest tests/test_self_asker.py -v`
Expected: 11 PASSED

- [ ] **Step 3: Commit**

```bash
git add core/self_asker.py
git commit -m "feat(self_asker): implement uncertainty detection + ask_user (Phase 4)"
```

---

## Task 3: TDD - 写 Executor 不确定性检测触发测试

**Files:**
- Modify: `tests/test_executor.py`

- [ ] **Step 1: 在 test_executor.py 末尾追加测试**

```python
class TestExecutorUncertaintyCheck:
    """Phase 4: 不确定性检测触发测试。"""

    def test_uncertainty_check_triggers_self_ask_when_uncertain(self):
        """enable_uncertainty_check=True 且 uncertain 时应调 self_asker.ask。"""
        executor = _make_executor(enable_uncertainty_check=True)
        tool_calls = [{"id": "tc1", "name": "shell", "args": {"cmd": "ls"}}]
        # 第一次：有 tool_calls + uncertain → 触发 ask → 继续 ReAct
        # 第二次：final_answer → done
        with patch.object(executor, '_parse_stream', side_effect=[
            ("thought", tool_calls, None),
            ("thought2", [], "done"),
        ]):
            with patch.object(executor.registry, 'execute_tool', return_value="file not found"):
                with patch.object(executor.memory, 'add_message'):
                    with patch.object(executor.memory, 'get_last_message', return_value={"content": "file not found"}):
                        with patch.object(executor.self_asker, 'check_uncertainty', return_value="uncertain: 需要确认文件路径"):
                            with patch.object(executor.self_asker, 'ask', return_value="用户回答：/tmp/file") as mock_ask:
                                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                                result = executor.execute(task)
        mock_ask.assert_called_once()
        assert result["status"] == "done"

    def test_uncertainty_check_skipped_when_confident(self):
        """confident 时不应调 self_asker.ask。"""
        executor = _make_executor(enable_uncertainty_check=True)
        tool_calls = [{"id": "tc1", "name": "shell", "args": {"cmd": "ls"}}]
        with patch.object(executor, '_parse_stream', side_effect=[
            ("thought", tool_calls, None),
            ("thought2", [], "done"),
        ]):
            with patch.object(executor.registry, 'execute_tool', return_value="ok"):
                with patch.object(executor.memory, 'add_message'):
                    with patch.object(executor.memory, 'get_last_message', return_value={"content": "ok"}):
                        with patch.object(executor.self_asker, 'check_uncertainty', return_value="confident"):
                            with patch.object(executor.self_asker, 'ask') as mock_ask:
                                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                                executor.execute(task)
        mock_ask.assert_not_called()

    def test_uncertainty_check_disabled_by_default(self):
        """enable_uncertainty_check=False 时不应调 self_asker.check_uncertainty。"""
        executor = _make_executor(enable_uncertainty_check=False)
        with patch.object(executor, '_parse_stream', return_value=("", [], "done")):
            with patch.object(executor.self_asker, 'check_uncertainty') as mock_check:
                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                executor.execute(task)
        mock_check.assert_not_called()

    def test_clarification_added_to_memory(self):
        """uncertain 触发 ask 后，用户回答应作为 clarification 塞进 memory。"""
        executor = _make_executor(enable_uncertainty_check=True)
        tool_calls = [{"id": "tc1", "name": "shell", "args": {"cmd": "ls"}}]
        with patch.object(executor, '_parse_stream', side_effect=[
            ("thought", tool_calls, None),
            ("thought2", [], "done"),
        ]):
            with patch.object(executor.registry, 'execute_tool', return_value="file not found"):
                with patch.object(executor.memory, 'add_message') as mock_add:
                    with patch.object(executor.memory, 'get_last_message', return_value={"content": "file not found"}):
                        with patch.object(executor.self_asker, 'check_uncertainty', return_value="uncertain: 路径？"):
                            with patch.object(executor.self_asker, 'ask', return_value="用户回答：/tmp"):
                                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                                executor.execute(task)
        # 验证有 clarification 消息塞进 memory
        clarification_calls = [
            call for call in mock_add.call_args_list
            if len(call[0]) >= 2 and "[Clarification]" in str(call[0][1])
        ]
        assert len(clarification_calls) >= 1

    def test_self_asker_failure_does_not_block(self):
        """self_asker.ask 失败时不应阻断执行（继续 ReAct）。"""
        executor = _make_executor(enable_uncertainty_check=True)
        tool_calls = [{"id": "tc1", "name": "shell", "args": {"cmd": "ls"}}]
        with patch.object(executor, '_parse_stream', side_effect=[
            ("thought", tool_calls, None),
            ("thought2", [], "done"),
        ]):
            with patch.object(executor.registry, 'execute_tool', return_value="error"):
                with patch.object(executor.memory, 'add_message'):
                    with patch.object(executor.memory, 'get_last_message', return_value={"content": "error"}):
                        with patch.object(executor.self_asker, 'check_uncertainty', return_value="uncertain: 问题"):
                            with patch.object(executor.self_asker, 'ask', side_effect=Exception("ask_user failed")):
                                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                                result = executor.execute(task)
        # 应正常完成（不抛异常）
        assert result["status"] == "done"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_executor.py::TestExecutorUncertaintyCheck -v`
Expected: 5 FAIL（Phase 1 Executor 默认 enable_uncertainty_check=False）

- [ ] **Step 3: Commit**

```bash
git add tests/test_executor.py
git commit -m "test: add failing Executor uncertainty check tests (RED)"
```

---

## Task 4: 修改 Executor 默认开启不确定性检测（GREEN）

**Files:**
- Modify: `core/executor.py`

- [ ] **Step 1: 修改 Executor 默认值**

定位 `core/executor.py` 的 `__init__`，把 `enable_uncertainty_check: bool = False` 改为 `enable_uncertainty_check: bool = True`：

```python
def __init__(self, llm_client, memory, tool_registry,
             max_iterations: int = 25,
             self_asker=None,
             enable_uncertainty_check: bool = True):
    """Phase 4: 默认开启不确定性检测。"""
    self.llm = llm_client
    self.memory = memory
    self.registry = tool_registry
    self.max_iterations = max_iterations
    self.self_asker = self_asker
    self.enable_uncertainty_check = enable_uncertainty_check
```

- [ ] **Step 2: 确认不确定性检测逻辑已正确实现（Phase 1 已写，验证即可）**

读 `core/executor.py` 的 execute 方法，确认有以下代码（Phase 1 已实现）：

```python
# Phase 4 不确定性检测
if self.enable_uncertainty_check and self.self_asker:
    last_obs = self.memory.get_last_message().get("content", "") if hasattr(self.memory, 'get_last_message') else ""
    if last_obs:
        try:
            verdict = self.self_asker.check_uncertainty(last_obs, task)
            if verdict.startswith("uncertain"):
                user_clarification = self.self_asker.ask(task["desc"], verdict)
                self.memory.add_message("user", f"[Clarification] {user_clarification}")
        except Exception:
            pass  # SelfAsker 失败不阻断
```

- [ ] **Step 3: 跑 Executor 测试确认全 PASS**

Run: `python -m pytest tests/test_executor.py -v`
Expected: 10 PASSED（5 Phase 1 + 5 Phase 4）

**注意**：Phase 1 测试 `test_uncertainty_check_disabled_by_default` 断言默认关闭，Phase 4 改为默认开启后需更新该测试：

定位 `tests/test_executor.py` 中的 `test_uncertainty_check_disabled_by_default`，把断言改为验证关闭时的行为：

```python
def test_uncertainty_check_disabled(self):
    """enable_uncertainty_check=False 时不应调 self_asker。"""
    executor = _make_executor(enable_uncertainty_check=False)
    with patch.object(executor, '_parse_stream', return_value=("", [], "done")):
        with patch.object(executor.self_asker, 'check_uncertainty') as mock_check:
            task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
            executor.execute(task)
    mock_check.assert_not_called()
```

- [ ] **Step 4: 跑全套 Executor 测试确认 PASS**

Run: `python -m pytest tests/test_executor.py -v`
Expected: 10 PASSED

- [ ] **Step 5: Commit**

```bash
git add core/executor.py tests/test_executor.py
git commit -m "feat(executor): enable uncertainty check by default (Phase 4)"
```

---

## Task 5: 集成测试 + Phase 4 最终验证

- [ ] **Step 1: 跑全套测试**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 174 passed（158 + 11 SelfAsker + 5 Executor uncertainty = 174）

- [ ] **Step 2: 手动验证 Self-Ask 触发**

启动 `python main.py`，输入一个故意模糊的任务（如 "处理那个文件"），观察：
- Executor 执行后观察不确定
- SelfAsker 触发，调 ask_user 向用户提问
- 用户回答后塞进 memory 继续 ReAct

- [ ] **Step 3: 验证不确定性检测可关闭**

`/config` 设置 `cognitive.self_ask = false`，重启后输入模糊任务，观察不触发 ask_user。

- [ ] **Step 4: Commit（如有调整）**

```bash
git add -A
git commit -m "chore: Phase 4 integration verification"
```

---

## Phase 4 完成验收

- [ ] SelfAsker 实现 check_uncertainty（LLM ~100 token）
- [ ] SelfAsker 实现 ask（调 ask_user 工具）
- [ ] Executor 默认开启不确定性检测
- [ ] uncertain 时触发 ask_user 工具
- [ ] confident 时不触发
- [ ] 用户回答作为 clarification 塞回 memory
- [ ] SelfAsker 失败不阻断执行
- [ ] ask_user 失败不阻断执行
- [ ] 不确定性检测可通过 config 关闭
- [ ] 全部测试通过（174 个）
- [ ] 现有 158 个测试无回归

---

## CognitiveController 全部 Phase 完成总结

| Phase | 框架 | 新增测试 | 累计测试 |
|-------|------|---------|---------|
| 1 | Plan-and-Execute | 16 | 140 |
| 2 | Self-Reflection | 12 | 152 |
| 3 | Thinking (ToT) | 11 | 163 |
| 4 | Self-Ask | 16 | 174 |

四框架综合认知框架全部完成。建议下一步 bump 版本到 v1.2.0 并更新学习路线。
