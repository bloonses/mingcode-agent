# CognitiveController Phase 1: Plan-and-Execute 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 CognitiveController 状态机骨架 + Planner（简单单次规划，不做 ToT）+ Executor（复用现有 ReAct）+ Reflector stub，让 complex 输入能走通"拆任务 → 逐个 ReAct 执行 → done"端到端流程。

**Architecture:** CognitiveController 调度 5 状态机（CLASSIFY → PLANNING → EXECUTING → REFLECTING → DONE）。Phase 1 的 Reflector 是 stub（直接返回 success），Planner 是单次 LLM 调用（不做 ToT，ToT 在 Phase 3 加）。Executor 复用 [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) 现有的 ReAct 串行循环逻辑。NeonAgent 改为：simple 输入走现有 ReAct，complex 输入委托 CognitiveController。

**Tech Stack:** Python 3.8+ / pytest / requests / Rich

**Spec:** [docs/superpowers/specs/2026-07-04-cognitive-controller-design.md](file:///c:/Users/bloon/Downloads/neon_agent/docs/superpowers/specs/2026-07-04-cognitive-controller-design.md)

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `core/cognitive.py` | 新建 | CognitiveController + State 枚举 |
| `core/planner.py` | 新建 | Planner（Phase 1 简单单次调用，无 ToT） |
| `core/executor.py` | 新建 | Executor（复用现有 ReAct 逻辑） |
| `core/reflector.py` | 新建 | Reflector stub（直接返回 success） |
| `core/agent.py` | 修改 | NeonAgent 加 cognitive_controller property + chat 分支 |
| `config/config.py` | 修改 | DEFAULT_CONFIG 加 cognitive 节 |
| `main.py` | 修改 | 加 /cognitive on\|off 命令 |
| `tests/test_cognitive_controller.py` | 新建 | 状态机测试 |
| `tests/test_planner.py` | 新建 | Planner 测试 |
| `tests/test_executor.py` | 新建 | Executor 测试 |
| `tests/test_reflector.py` | 新建 | Reflector stub 测试 |

---

## Task 1: TDD - 写 CognitiveController 状态机测试

**Files:**
- Create: `tests/test_cognitive_controller.py`

- [ ] **Step 1: 写测试文件**

```python
"""CognitiveController 状态机测试（Phase 1: Plan-and-Execute）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_controller(planner=None, executor=None, reflector=None,
                     max_replans=3, max_task_retries=2):
    """构造 CognitiveController，所有子模块用 MagicMock 默认值。"""
    from core.cognitive import CognitiveController
    return CognitiveController(
        llm_client=MagicMock(),
        memory=MagicMock(),
        tool_registry=MagicMock(),
        planner=planner or MagicMock(),
        executor=executor or MagicMock(),
        reflector=reflector or MagicMock(),
        self_asker=MagicMock(),
        max_replans=max_replans,
        max_task_retries=max_task_retries,
    )


class TestCognitiveControllerState:
    def test_initial_state_is_classify(self):
        """构造后初始状态应为 CLASSIFY。"""
        controller = _make_controller()
        from core.cognitive import State
        assert controller.state == State.CLASSIFY

    def test_simple_input_falls_back_to_react(self):
        """简单输入应走 fallback ReAct，不进 PLANNING。"""
        controller = _make_controller()
        with patch.object(controller, '_classify', return_value="simple"):
            with patch.object(controller, '_fallback_to_react', return_value="ok") as mock_fb:
                result = controller.chat("你好")
        mock_fb.assert_called_once_with("你好")
        assert result == "ok"

    def test_complex_input_enters_planning(self):
        """复杂输入应进入 PLANNING 并最终到 DONE。"""
        controller = _make_controller()
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute') as mock_exec:
                    mock_exec.return_value = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
                    with patch.object(controller.reflector, 'evaluate', return_value="success"):
                        controller.chat("写个贪吃蛇")
        from core.cognitive import State
        assert controller.state == State.DONE

    def test_dependency_injection(self):
        """构造参数应正确注入子模块。"""
        mock_planner = MagicMock()
        mock_executor = MagicMock()
        mock_reflector = MagicMock()
        controller = _make_controller(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
        assert controller.planner is mock_planner
        assert controller.executor is mock_executor
        assert controller.reflector is mock_reflector
```

- [ ] **Step 2: 跑测试确认全失败（CognitiveController 还不存在）**

Run: `python -m pytest tests/test_cognitive_controller.py -v`
Expected: 4 个 FAIL，错误 `ModuleNotFoundError: No module named 'core.cognitive'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_cognitive_controller.py
git commit -m "test: add failing CognitiveController state machine tests (RED)"
```

---

## Task 2: 实现 CognitiveController 骨架（GREEN）

**Files:**
- Create: `core/cognitive.py`

- [ ] **Step 1: 写 core/cognitive.py**

```python
"""CognitiveController - 综合认知框架状态机。

综合 4 种认知框架：
- Plan-and-Execute: 先拆任务再逐个执行
- Self-Reflection: 执行后反思（Phase 2 实现）
- Thinking (ToT): 规划时多候选（Phase 3 实现）
- Self-Ask: 执行中遇不确定向用户提问（Phase 4 实现）

Phase 1: 仅 Plan-and-Execute，Reflector 为 stub。
"""
from enum import Enum
from typing import Optional, List, Dict, Any


class State(Enum):
    CLASSIFY = "classify"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    DONE = "done"


class CognitiveController:
    def __init__(self, llm_client, memory, tool_registry,
                 planner=None, executor=None, reflector=None, self_asker=None,
                 max_replans: int = 3, max_task_retries: int = 2):
        self.llm = llm_client
        self.memory = memory
        self.registry = tool_registry
        # 延迟 import 避免循环依赖
        from core.planner import Planner
        from core.executor import Executor
        from core.reflector import Reflector
        from core.self_asker import SelfAsker
        self.planner = planner or Planner(llm_client)
        self.executor = executor or Executor(llm_client, memory, tool_registry)
        self.reflector = reflector or Reflector(llm_client)
        self.self_asker = self_asker or SelfAsker(llm_client, tool_registry)
        self.max_replans = max_replans
        self.max_task_retries = max_task_retries
        self.state = State.CLASSIFY
        self.task_list: List[Dict] = []
        self.current_task_idx = 0
        self.replan_count = 0
        self._user_input = ""

    def chat(self, user_input: str) -> str:
        """主入口：分类 → PLANNING → EXECUTING → REFLECTING → DONE。"""
        self._user_input = user_input
        if self._classify(user_input) == "simple":
            return self._fallback_to_react(user_input)

        self.state = State.PLANNING
        self.task_list = self.planner.execute(user_input)

        while self.state != State.DONE:
            if self.state == State.PLANNING:
                self._step_replan()
            elif self.state == State.EXECUTING:
                self._step_execute()
            elif self.state == State.REFLECTING:
                self._step_reflect()

        return self._build_answer()

    def _classify(self, input: str) -> str:
        """LLM 轻量分类 simple/complex。失败兜底 simple。"""
        try:
            prompt = (
                f"用户输入: {input}\n\n"
                f"这是简单对话（SIMPLE）还是复杂任务（COMPLEX）？\n"
                f"- SIMPLE: 问候、闲聊、单步问答\n"
                f"- COMPLEX: 需要拆分多步、写代码、分析、创建\n"
                f"只输出一个词：SIMPLE 或 COMPLEX"
            )
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = (response.get("content") or "").strip().upper()
            if "COMPLEX" in content:
                return "complex"
            return "simple"
        except Exception:
            return "simple"

    def _fallback_to_react(self, input: str) -> str:
        """简单输入走现有 ReAct（Phase 1 暂返回 placeholder，Task 5 接入 NeonAgent）。"""
        return f"[React fallback] {input}"

    def _step_execute(self):
        """执行当前任务。"""
        task = self.task_list[self.current_task_idx]
        task["status"] = "executing"
        result_task = self.executor.execute(task)
        # 把执行结果回写到 task_list
        self.task_list[self.current_task_idx] = result_task
        self.state = State.REFLECTING

    def _step_reflect(self):
        """反思当前任务结果。Phase 1 Reflector 是 stub 直接返回 success。"""
        task = self.task_list[self.current_task_idx]
        verdict = self.reflector.evaluate(task)
        if verdict == "success":
            task["status"] = "done"
            self.current_task_idx += 1
            if self.current_task_idx >= len(self.task_list):
                self.state = State.DONE
            else:
                self.state = State.EXECUTING
        else:
            # Phase 2 才实现降级，Phase 1 直接标记 failed 跳过
            task["status"] = "failed"
            task["feedback"] = verdict
            self.current_task_idx += 1
            if self.current_task_idx >= len(self.task_list):
                self.state = State.DONE
            else:
                self.state = State.EXECUTING

    def _step_replan(self):
        """重规划（Phase 2 实现，Phase 1 不触发）。"""
        self.state = State.EXECUTING

    def _build_answer(self) -> str:
        """汇总所有任务结果生成最终回答。"""
        results = []
        for task in self.task_list:
            status = task.get("status", "unknown")
            desc = task.get("desc", "")
            result = task.get("result", "")
            results.append(f"[{status}] {desc}: {result}")
        return "\n".join(results) if results else "No tasks executed"
```

- [ ] **Step 2: 跑测试确认部分通过（Planner/Executor/Reflector 还不存在会报错）**

Run: `python -m pytest tests/test_cognitive_controller.py -v`
Expected: 测试仍失败（因为 `from core.planner import Planner` 等还没建），但 `State` 相关断言可通过

- [ ] **Step 3: Commit**

```bash
git add core/cognitive.py
git commit -m "feat(cognitive): add CognitiveController state machine skeleton"
```

---

## Task 3: TDD - 写 Planner 测试

**Files:**
- Create: `tests/test_planner.py`

- [ ] **Step 1: 写测试文件**

```python
"""Planner 测试（Phase 1: 简单单次规划，无 ToT）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_planner(tot_candidates=3):
    from core.planner import Planner
    return Planner(MagicMock(), tot_candidates=tot_candidates)


class TestPlanner:
    def test_execute_returns_task_list(self):
        """execute 应返回任务列表（每个任务是 dict 含 id/desc/status/retries/feedback）。"""
        planner = _make_planner()
        fake_response = {"content": "1. 第一步\n2. 第二步\n3. 第三步"}
        with patch.object(planner.llm, 'chat', return_value=fake_response):
            tasks = planner.execute("写个贪吃蛇")
        assert isinstance(tasks, list)
        assert len(tasks) >= 1
        for task in tasks:
            assert "id" in task
            assert "desc" in task
            assert "status" in task
            assert task["status"] == "pending"
            assert task["retries"] == 0
            assert task["feedback"] is None

    def test_execute_with_feedback_calls_replan(self):
        """带 feedback 参数时应走重规划路径。"""
        planner = _make_planner()
        fake_response = {"content": "1. 重新规划的任务"}
        with patch.object(planner.llm, 'chat', return_value=fake_response) as mock_chat:
            tasks = planner.execute("input", feedback=["上次失败：xxx"])
        assert len(tasks) >= 1
        # 验证 feedback 出现在 prompt 中
        call_args = mock_chat.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1].get('messages', [])
        prompt_text = str(messages)
        assert "上次失败" in prompt_text or "feedback" in prompt_text.lower()

    def test_empty_response_returns_single_task(self):
        """LLM 返回空内容时应兜底返回单任务（desc 为原输入）。"""
        planner = _make_planner()
        with patch.object(planner.llm, 'chat', return_value={"content": ""}):
            tasks = planner.execute("做点什么")
        assert len(tasks) == 1
        assert tasks[0]["desc"] == "做点什么"

    def test_llm_failure_returns_single_task(self):
        """LLM 调用异常时应兜底返回单任务。"""
        planner = _make_planner()
        with patch.object(planner.llm, 'chat', side_effect=Exception("network error")):
            tasks = planner.execute("做点什么")
        assert len(tasks) == 1
        assert tasks[0]["desc"] == "做点什么"
```

- [ ] **Step 2: 跑测试确认全失败**

Run: `python -m pytest tests/test_planner.py -v`
Expected: 4 FAIL（`ModuleNotFoundError: No module named 'core.planner'`）

- [ ] **Step 3: Commit**

```bash
git add tests/test_planner.py
git commit -m "test: add failing Planner tests (RED)"
```

---

## Task 4: 实现 Planner（GREEN）

**Files:**
- Create: `core/planner.py`

- [ ] **Step 1: 写 core/planner.py（Phase 1 简单版，无 ToT）**

```python
"""Planner - 任务规划器。

Phase 1: 简单单次 LLM 调用生成任务列表。
Phase 3 会扩展为 ToT（多候选 → 评估 → 筛选）。
"""
from typing import List, Dict, Optional


class Planner:
    def __init__(self, llm_client, tot_candidates: int = 3):
        """tot_candidates 在 Phase 1 不使用，Phase 3 ToT 才用。"""
        self.llm = llm_client
        self.tot_candidates = tot_candidates

    def execute(self, user_input: str, feedback: Optional[List[str]] = None) -> List[Dict]:
        """生成任务列表。feedback 非空时为重规划（带反思反馈）。"""
        try:
            prompt = self._build_plan_prompt(user_input, feedback)
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = response.get("content", "")
            tasks = self._parse_to_tasks(content, user_input)
            if not tasks:
                # 兜底：返回单任务
                return [self._make_task(0, user_input)]
            return tasks
        except Exception:
            # 兜底：返回单任务
            return [self._make_task(0, user_input)]

    def _build_plan_prompt(self, user_input: str, feedback: Optional[List[str]]) -> str:
        """构造规划 prompt。"""
        feedback_section = ""
        if feedback:
            feedback_section = "\n\n上次执行失败的反馈：\n"
            for i, fb in enumerate(feedback, 1):
                feedback_section += f"{i}. {fb}\n"
            feedback_section += "请基于反馈重新规划。\n"

        return (
            f"用户需求: {user_input}{feedback_section}\n\n"
            f"请把需求拆分成可独立执行的子任务，每行一个，格式：\n"
            f"1. <任务描述>\n"
            f"2. <任务描述>\n"
            f"...\n\n"
            f"要求：\n"
            f"- 每个任务可由 ReAct Agent 独立完成\n"
            f"- 任务顺序合理（前置依赖在前）\n"
            f"- 任务数量 1-5 个\n"
            f"- 不要过度拆分简单任务"
        )

    def _parse_to_tasks(self, content: str, original_input: str) -> List[Dict]:
        """解析 LLM 输出为任务列表。"""
        if not content or not content.strip():
            return []
        tasks = []
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 解析 "1. 任务描述" 或 "- 任务描述" 或 "* 任务描述" 格式
            desc = line
            for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "- ", "* "]:
                if line.startswith(prefix):
                    desc = line[len(prefix):].strip()
                    break
            if desc:
                tasks.append(self._make_task(len(tasks), desc))
        return tasks

    def _make_task(self, task_id: int, desc: str) -> Dict:
        """构造任务 dict。"""
        return {
            "id": task_id,
            "desc": desc,
            "status": "pending",
            "retries": 0,
            "feedback": None,
        }
```

- [ ] **Step 2: 跑 Planner 测试确认全 PASS**

Run: `python -m pytest tests/test_planner.py -v`
Expected: 4 PASSED

- [ ] **Step 3: Commit**

```bash
git add core/planner.py
git commit -m "feat(planner): add simple Planner (Phase 1, no ToT)"
```

---

## Task 5: TDD - 写 Reflector stub 测试

**Files:**
- Create: `tests/test_reflector.py`

- [ ] **Step 1: 写测试文件**

```python
"""Reflector 测试（Phase 1: stub 直接返回 success）。"""
import pytest
from unittest.mock import MagicMock


def _make_reflector():
    from core.reflector import Reflector
    return Reflector(MagicMock())


class TestReflectorStub:
    def test_done_status_returns_success(self):
        """status=done 时 stub 应返回 success。"""
        reflector = _make_reflector()
        task = {"id": 0, "desc": "t1", "status": "done", "result": "ok"}
        verdict = reflector.evaluate(task)
        assert verdict == "success"

    def test_failed_status_returns_success_still(self):
        """Phase 1 stub：即使 status=failed 也返回 success（跳过降级）。"""
        reflector = _make_reflector()
        task = {"id": 0, "desc": "t1", "status": "failed", "result": "error"}
        verdict = reflector.evaluate(task)
        assert verdict == "success"

    def test_no_llm_call_in_stub(self):
        """Phase 1 stub 不应调 LLM。"""
        reflector = _make_reflector()
        task = {"id": 0, "desc": "t1", "status": "done", "result": "ok"}
        reflector.evaluate(task)
        # 验证 LLM 没被调用
        reflector.llm.chat.assert_not_called()
```

- [ ] **Step 2: 跑测试确认全失败**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: 3 FAIL（`ModuleNotFoundError: No module named 'core.reflector'`）

- [ ] **Step 3: Commit**

```bash
git add tests/test_reflector.py
git commit -m "test: add failing Reflector stub tests (RED)"
```

---

## Task 6: 实现 Reflector stub（GREEN）

**Files:**
- Create: `core/reflector.py`

- [ ] **Step 1: 写 core/reflector.py（Phase 1 stub）**

```python
"""Reflector - 任务结果反思评估。

Phase 1: stub 实现，直接返回 success（不调 LLM，跳过降级）。
Phase 2 会扩展为 LLM 评估 + 假成功检测 + 分级降级反馈。
"""


class Reflector:
    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(self, task: dict) -> str:
        """评估任务执行结果。

        Phase 1 stub: 直接返回 success，不调 LLM。
        Phase 2 会改为：status=done → LLM 假成功检测；status=failed → fail: <reason>
        """
        return "success"
```

- [ ] **Step 2: 跑 Reflector 测试确认全 PASS**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add core/reflector.py
git commit -m "feat(reflector): add Reflector stub (Phase 1)"
```

---

## Task 7: TDD - 写 Executor 测试

**Files:**
- Create: `tests/test_executor.py`

- [ ] **Step 1: 写测试文件**

```python
"""Executor 测试（Phase 1: ReAct + 串行工具执行）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_executor(self_asker=None, enable_uncertainty_check=False):
    """构造 Executor。Phase 1 默认关闭不确定性检测。"""
    from core.executor import Executor
    return Executor(
        llm_client=MagicMock(),
        memory=MagicMock(),
        tool_registry=MagicMock(),
        max_iterations=25,
        self_asker=self_asker or MagicMock(),
        enable_uncertainty_check=enable_uncertainty_check,
    )


class TestExecutor:
    def test_final_answer_completes_task(self):
        """LLM 返回 final_answer 且无 tool_calls 时任务应标记 done。"""
        executor = _make_executor()
        # 模拟 _parse_stream 返回 (thought, tool_calls, final_answer)
        with patch.object(executor, '_parse_stream', return_value=("thought", [], "done")):
            task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
            result = executor.execute(task)
        assert result["status"] == "done"
        assert result["result"] == "done"

    def test_tool_calls_executed_serially(self):
        """有 tool_calls 时应串行执行并塞回 memory。"""
        executor = _make_executor()
        tool_calls = [
            {"id": "tc1", "name": "shell", "args": {"cmd": "ls"}},
            {"id": "tc2", "name": "files", "args": {"path": "/tmp"}},
        ]
        # 第一次返回 tool_calls，第二次返回 final_answer
        with patch.object(executor, '_parse_stream', side_effect=[
            ("thought", tool_calls, None),
            ("thought2", [], "done"),
        ]):
            with patch.object(executor.registry, 'execute_tool', return_value="tool result") as mock_exec:
                with patch.object(executor.memory, 'add_message') as mock_add:
                    task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                    result = executor.execute(task)
        # 验证工具串行执行 2 次
        assert mock_exec.call_count == 2
        assert result["status"] == "done"

    def test_max_iterations_marks_failed(self):
        """达到 max_iterations 仍未完成应标记 failed。"""
        executor = _make_executor(max_iterations=2)
        # 每次都返回 tool_calls，永不返回 final_answer
        with patch.object(executor, '_parse_stream', return_value=("thought", [{"id": "tc", "name": "shell", "args": {}}], None)):
            with patch.object(executor.registry, 'execute_tool', return_value="ok"):
                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                result = executor.execute(task)
        assert result["status"] == "failed"

    def test_feedback_added_to_memory_on_retry(self):
        """重试时 task 的 feedback 应塞进 memory。"""
        executor = _make_executor()
        with patch.object(executor, '_parse_stream', return_value=("", [], "done")):
            with patch.object(executor.memory, 'add_message') as mock_add:
                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 1, "feedback": "上次失败：xxx"}
                executor.execute(task)
        # 验证 feedback 被加入 memory（应至少调用 2 次：task desc + feedback）
        assert mock_add.call_count >= 2

    def test_uncertainty_check_disabled_by_default(self):
        """Phase 1 默认关闭不确定性检测，不应调 self_asker。"""
        executor = _make_executor(enable_uncertainty_check=False)
        with patch.object(executor, '_parse_stream', return_value=("", [], "done")):
            with patch.object(executor.self_asker, 'check_uncertainty') as mock_check:
                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                executor.execute(task)
        mock_check.assert_not_called()
```

- [ ] **Step 2: 跑测试确认全失败**

Run: `python -m pytest tests/test_executor.py -v`
Expected: 5 FAIL（`ModuleNotFoundError: No module named 'core.executor'`）

- [ ] **Step 3: Commit**

```bash
git add tests/test_executor.py
git commit -m "test: add failing Executor tests (RED)"
```

---

## Task 8: 实现 Executor（GREEN）

**Files:**
- Create: `core/executor.py`

- [ ] **Step 1: 写 core/executor.py**

```python
"""Executor - 单任务 ReAct 执行器。

复用现有 agent.py 的 ReAct 串行循环逻辑。
Phase 4 会扩展不确定性检测（Self-Ask）。
"""
from typing import Dict, Optional, List, Any


class Executor:
    def __init__(self, llm_client, memory, tool_registry,
                 max_iterations: int = 25,
                 self_asker=None,
                 enable_uncertainty_check: bool = False):
        """Phase 1 默认 enable_uncertainty_check=False，Phase 4 才开启。"""
        self.llm = llm_client
        self.memory = memory
        self.registry = tool_registry
        self.max_iterations = max_iterations
        self.self_asker = self_asker
        self.enable_uncertainty_check = enable_uncertainty_check

    def execute(self, task: Dict) -> Dict:
        """执行单个任务，返回更新后的 task（含 result / status）。"""
        # 把任务描述塞进 memory
        self.memory.add_message("user", f"[Task {task['id']}] {task['desc']}")
        # 重试时带反思反馈
        if task.get("feedback"):
            self.memory.add_message("user", f"[Retry feedback] {task['feedback']}")

        for iteration in range(self.max_iterations):
            try:
                stream_response = self.llm.chat(
                    messages=self.memory.get_messages(),
                    tools=self.registry.get_all_schemas(),
                    stream=True,
                )
            except Exception as e:
                task["result"] = f"LLM error: {e}"
                task["status"] = "failed"
                return task

            # 解析 Thought + tool_calls + final_answer
            thought, tool_calls, final_answer = self._parse_stream(stream_response)

            # 如果有 final_answer 且无 tool_calls，任务完成
            if final_answer and not tool_calls:
                task["result"] = final_answer
                task["status"] = "done"
                return task

            # 串行执行 tool_calls
            for tc in tool_calls:
                try:
                    result = self.registry.execute_tool(tc["name"], **tc.get("args", {}))
                except Exception as e:
                    result = f"Tool error: {e}"
                self.memory.add_message("tool", result, tool_call_id=tc.get("id", ""))

            # Phase 4 不确定性检测（Phase 1 默认关闭）
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

        # 达到 max_iterations 仍未完成
        task["result"] = "Max iterations reached"
        task["status"] = "failed"
        return task

    def _parse_stream(self, stream_response) -> tuple:
        """解析 LLM 流式响应，返回 (thought, tool_calls, final_answer)。

        复用现有 agent.py 的解析逻辑。tool_calls 为 list of dict：
        [{"id": str, "name": str, "args": dict}]
        """
        thought = ""
        tool_calls: List[Dict] = []
        final_answer: Optional[str] = None

        # 处理流式或非流式响应
        if hasattr(stream_response, '__iter__'):
            for chunk in stream_response:
                if isinstance(chunk, str):
                    thought += chunk
                elif isinstance(chunk, dict):
                    # 兼容非流式 dict 响应
                    content = chunk.get("content", "")
                    if content:
                        thought += content
                    tcs = chunk.get("tool_calls")
                    if tcs:
                        tool_calls.extend(tcs)
        else:
            # dict 响应
            if isinstance(stream_response, dict):
                thought = stream_response.get("content", "")
                tcs = stream_response.get("tool_calls")
                if tcs:
                    tool_calls = tcs

        # 如果有内容且无 tool_calls，认为是 final_answer
        if thought and not tool_calls:
            final_answer = thought

        return thought, tool_calls, final_answer
```

- [ ] **Step 2: 跑 Executor 测试确认全 PASS**

Run: `python -m pytest tests/test_executor.py -v`
Expected: 5 PASSED

- [ ] **Step 3: Commit**

```bash
git add core/executor.py
git commit -m "feat(executor): add Executor with ReAct loop (Phase 1)"
```

---

## Task 9: 创建 SelfAsker 占位模块

**Files:**
- Create: `core/self_asker.py`

- [ ] **Step 1: 写 core/self_asker.py（Phase 1 占位，Phase 4 实现）**

```python
"""SelfAsker - 不确定性检测 + Self-Ask。

Phase 1: 占位实现，check_uncertainty 永远返回 confident，ask 不调 ask_user。
Phase 4 会扩展为 LLM 不确定性检测 + 调 ask_user 工具。
"""


class SelfAsker:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.registry = tool_registry

    def check_uncertainty(self, last_observation: str, task: dict) -> str:
        """Phase 1 占位：永远返回 confident。"""
        return "confident"

    def ask(self, task_desc: str, uncertainty_reason: str) -> str:
        """Phase 1 占位：不调 ask_user，返回空字符串。"""
        return ""
```

- [ ] **Step 2: Commit**

```bash
git add core/self_asker.py
git commit -m "feat(self_asker): add SelfAsker placeholder (Phase 1)"
```

---

## Task 10: 跑全套测试确认 CognitiveController 集成

- [ ] **Step 1: 跑 cognitive_controller 测试**

Run: `python -m pytest tests/test_cognitive_controller.py -v`
Expected: 4 PASSED

- [ ] **Step 2: 跑全部新增测试**

Run: `python -m pytest tests/test_cognitive_controller.py tests/test_planner.py tests/test_executor.py tests/test_reflector.py -v`
Expected: 16 PASSED（4+4+5+3）

- [ ] **Step 3: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 140 passed（124 现有 + 16 新增）

- [ ] **Step 4: Commit（如有修复）**

```bash
git add -A
git commit -m "fix(cognitive): integration test pass"
```

---

## Task 11: 集成 NeonAgent + config + /cognitive 命令

**Files:**
- Modify: `config/config.py`（DEFAULT_CONFIG 加 cognitive 节）
- Modify: `core/agent.py`（加 cognitive_controller property + chat 分支）
- Modify: `main.py`（加 /cognitive 命令）

- [ ] **Step 1: 改 config/config.py 加 cognitive 节**

定位 `DEFAULT_CONFIG` 字典（约第 27 行），在 `qq` 节后加：

```python
"cognitive": {
    "enabled": True,
    "tot_candidates": 3,
    "max_replans": 3,
    "max_task_retries": 2,
    "self_ask": True
},
```

- [ ] **Step 2: 改 core/agent.py 加 cognitive_controller property**

在 NeonAgent 类中加（参考现有属性模式）：

```python
@property
def cognitive_controller(self):
    """延迟构造 CognitiveController。"""
    if self._cognitive_controller is None and self._cognitive_enabled:
        from core.cognitive import CognitiveController
        from core.planner import Planner
        from core.executor import Executor
        from core.reflector import Reflector
        from core.self_asker import SelfAsker

        cog_config = self.config.get("cognitive", {})
        self_asker = SelfAsker(self.llm, self.registry)
        executor = Executor(
            self.llm, self.memory, self.registry,
            self_asker=self_asker,
            enable_uncertainty_check=cog_config.get("self_ask", True),
        )
        self._cognitive_controller = CognitiveController(
            llm_client=self.llm,
            memory=self.memory,
            tool_registry=self.registry,
            planner=Planner(self.llm, tot_candidates=cog_config.get("tot_candidates", 3)),
            executor=executor,
            reflector=Reflector(self.llm),
            self_asker=self_asker,
            max_replans=cog_config.get("max_replans", 3),
            max_task_retries=cog_config.get("max_task_retries", 2),
        )
    return self._cognitive_controller
```

在 `__init__` 末尾加：

```python
self._cognitive_controller = None
self._cognitive_enabled = config.get("cognitive", {}).get("enabled", True)
```

- [ ] **Step 3: 改 core/agent.py 的 chat 方法**

定位现有 `chat` 方法（约第 78 行），改为：

```python
def chat(self, user_input: str):
    if self._cognitive_enabled:
        try:
            result = self.cognitive_controller.chat(user_input)
            yield result
            return
        except Exception as e:
            # 兜底：异常时 fallback 走现有 ReAct
            pass
    # 现有 ReAct 逻辑（保留作 fallback）
    # ... 原有代码 ...
```

**注意**：需要把现有 ReAct 逻辑抽到 `_react_loop(self, user_input)` 方法，便于 fallback 调用。

- [ ] **Step 4: 改 main.py 加 /cognitive 命令**

在 `/reasoning` 命令后加：

```python
elif cmd == '/cognitive':
    if not arg:
        enabled = config.get('cognitive', {}).get('enabled', True)
        status = "on" if enabled else "off"
        console.print(f"[{NEON_TEAL}]Cognitive controller: {status}[/{NEON_TEAL}]")
        console.print(f"[{NEON_TEAL}]Options: on / off[/{NEON_TEAL}]")
        return True
    val = arg.strip().lower()
    if val in ("on", "off"):
        config['cognitive']['enabled'] = (val == "on")
        save_config(config)
        agent._cognitive_enabled = (val == "on")
        agent._cognitive_controller = None
        console.print(f"[{NEON_TEAL}]Cognitive controller: {val}[/{NEON_TEAL}]")
    else:
        console.print(f"[{NEON_TEAL}]Invalid value. Use: on / off[/{NEON_TEAL}]")
    return True
```

- [ ] **Step 5: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 140 passed

- [ ] **Step 6: Commit**

```bash
git add config/config.py core/agent.py main.py
git commit -m "feat: integrate CognitiveController into NeonAgent + /cognitive command"
```

---

## Task 12: Phase 1 最终验证

- [ ] **Step 1: 跑全套测试**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 140 passed

- [ ] **Step 2: 手动验证 /cognitive 命令**

启动 `python main.py`，依次执行：
- `/cognitive` → 显示 "Cognitive controller: on" + Options
- `/cognitive off` → 显示 "Cognitive controller: off"
- `/cognitive on` → 显示 "Cognitive controller: on"
- `/cognitive garbage` → 显示 "Invalid value. Use: on / off"

- [ ] **Step 3: 手动验证 simple/complex 分流**

启动 `python main.py`，配置一个 LLM，输入：
- "你好" → 应走 simple ReAct（直接回答）
- "写一个 hello world Python 脚本" → 应走 complex Plan-Execute（拆任务）

- [ ] **Step 4: 验证 config 持久化**

读取 user_data_dir/config.yaml，确认含 `cognitive: enabled: true` 等字段。

- [ ] **Step 5: Commit（如有调整）**

```bash
git add -A
git commit -m "chore: Phase 1 final verification"
```

---

## Phase 1 完成验收

- [ ] 全部测试通过（124 + 16 = 140 个）
- [ ] CognitiveController 状态机骨架完成
- [ ] Planner 简单单次规划（无 ToT）
- [ ] Executor 复用现有 ReAct 串行循环
- [ ] Reflector stub 直接返回 success
- [ ] SelfAsker 占位（Phase 4 实现）
- [ ] NeonAgent 集成 CognitiveController（simple fallback ReAct）
- [ ] `/cognitive on|off` 命令可运行时切换
- [ ] config cognitive 节可配
- [ ] 端到端：complex 输入能走通 Plan → Execute → Reflect → Done

---

## 后续 Phase 预告

- **Phase 2**: 实现 Reflector 真实评估 + 分级降级（L1 局部重试 / L2 整体重规划 / L3 报错）
- **Phase 3**: Planner 内嵌 ToT（多候选 → 评估 → 筛选）+ plan_tot 工具改薄包装
- **Phase 4**: SelfAsker 实现 LLM 不确定性检测 + 调 ask_user 工具
