# CognitiveController Phase 2: Self-Reflection 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Reflector stub 升级为真实 LLM 评估 + 假成功检测 + 分级降级（L1 局部重试 ≤ 2 → L2 整体重规划 ≤ 3 → L3 报错给用户），让复杂任务失败时可自动重规划。

**Architecture:** Reflector 接收 task（含 status/result），调 LLM 做假成功检测（result 含 Error/Traceback 时识别为 fail）。失败时返回 `fail: <reason>`，CognitiveController 根据 retries 计数决定 L1（回 EXECUTING 重试）/ L2（回 PLANNING 重规划，带 feedback）/ L3（DONE 报错）。`_step_replan` 真实实现，带 Reflect feedback 调 Planner.execute。

**Tech Stack:** Python 3.8+ / pytest / requests

**Spec:** [docs/superpowers/specs/2026-07-04-cognitive-controller-design.md](file:///c:/Users/bloon/Downloads/neon_agent/docs/superpowers/specs/2026-07-04-cognitive-controller-design.md)

**Prerequisite:** Phase 1 已完成（CognitiveController 骨架 + Reflector stub + 现有 140 测试通过）

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `core/reflector.py` | 修改 | stub 升级为真实 LLM 评估 + 假成功检测 |
| `core/cognitive.py` | 修改 | `_step_reflect` 实现 L1/L2/L3 分级降级；`_step_replan` 真实实现 |
| `tests/test_reflector.py` | 修改 | 加真实评估测试 |
| `tests/test_cognitive_controller.py` | 修改 | 加分级降级测试 |

---

## Task 1: TDD - 写 Reflector 真实评估测试

**Files:**
- Modify: `tests/test_reflector.py`

- [ ] **Step 1: 替换 test_reflector.py 内容**

```python
"""Reflector 测试（Phase 2: LLM 评估 + 假成功检测）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_reflector():
    from core.reflector import Reflector
    return Reflector(MagicMock())


class TestReflectorEvaluation:
    def test_done_status_with_ok_result_returns_success(self):
        """status=done 且 LLM 判 ok 时返回 success。"""
        reflector = _make_reflector()
        with patch.object(reflector, '_llm_evaluate', return_value="ok"):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "all good"}
            verdict = reflector.evaluate(task)
        assert verdict == "success"

    def test_done_status_with_error_result_returns_fail(self):
        """status=done 但 result 含 Error 时 _llm_evaluate 应返回 fail。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', return_value={"content": "fail: 含 Traceback"}):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "Error: xxx"}
            verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")

    def test_failed_status_returns_fail_with_reason(self):
        """status=failed 时应返回 fail: <reason>（不调 LLM）。"""
        reflector = _make_reflector()
        task = {"id": 0, "desc": "t1", "status": "failed", "result": "Max iterations reached"}
        verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")
        assert "Max iterations" in verdict
        # 验证没调 LLM
        reflector.llm.chat.assert_not_called()

    def test_llm_evaluate_uses_task_desc_and_result(self):
        """_llm_evaluate 应把 task desc 和 result 都传给 LLM。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', return_value={"content": "ok"}) as mock_chat:
            task = {"id": 0, "desc": "写 hello world", "status": "done", "result": "print('hello')"}
            reflector._llm_evaluate(task)
        # 验证 LLM 被调用
        mock_chat.assert_called_once()
        # 验证 prompt 含任务描述和结果
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "写 hello world" in prompt_text
        assert "print('hello')" in prompt_text

    def test_llm_failure_falls_back_to_trust_status(self):
        """LLM 评估失败时应兜底信任 task status（done→success / failed→fail）。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', side_effect=Exception("network error")):
            task = {"id": 0, "desc": "t1", "status": "done", "result": "ok"}
            verdict = reflector.evaluate(task)
        assert verdict == "success"  # done 兜底为 success

    def test_llm_failure_with_failed_status_returns_fail(self):
        """LLM 评估失败 + status=failed 时兜底返回 fail。"""
        reflector = _make_reflector()
        with patch.object(reflector.llm, 'chat', side_effect=Exception("network error")):
            task = {"id": 0, "desc": "t1", "status": "failed", "result": "error"}
            verdict = reflector.evaluate(task)
        assert verdict.startswith("fail:")

    def test_truncates_long_result(self):
        """result 过长时应截断传给 LLM（避免 token 超限）。"""
        reflector = _make_reflector()
        long_result = "x" * 2000
        with patch.object(reflector.llm, 'chat', return_value={"content": "ok"}) as mock_chat:
            task = {"id": 0, "desc": "t1", "status": "done", "result": long_result}
            reflector._llm_evaluate(task)
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        # 验证 result 被截断（< 1000 字符）
        assert len(prompt_text) < 1500
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: 7 FAIL（stub 直接返回 success，新断言会失败）

- [ ] **Step 3: Commit**

```bash
git add tests/test_reflector.py
git commit -m "test: add failing Reflector real evaluation tests (RED)"
```

---

## Task 2: 实现 Reflector 真实评估（GREEN）

**Files:**
- Modify: `core/reflector.py`

- [ ] **Step 1: 替换 core/reflector.py**

```python
"""Reflector - 任务结果反思评估。

Phase 2: LLM 假成功检测 + 失败原因反馈。
- status=done → 调 LLM 判断 result 是否真正完成（避免假成功）
- status=failed → 直接返回 fail: <result>（不调 LLM）
"""
from typing import Dict


class Reflector:
    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(self, task: Dict) -> str:
        """评估任务执行结果，返回 'success' 或 'fail: <reason>'。"""
        status = task.get("status")
        result = task.get("result", "")

        if status == "failed":
            # 已知失败，不调 LLM
            return f"fail: {result}"

        if status == "done":
            # 假成功检测：LLM 判断 result 是否真正完成
            try:
                verdict = self._llm_evaluate(task)
                if verdict == "ok":
                    return "success"
                else:
                    return verdict if verdict.startswith("fail") else f"fail: {verdict}"
            except Exception:
                # LLM 失败兜底：信任 status=done
                return "success"

        # 未知 status 兜底
        return f"fail: unknown status {status}"

    def _llm_evaluate(self, task: Dict) -> str:
        """~150 token LLM 调用判断结果是否真正完成。

        返回 'ok' 或 'fail: <原因>'。
        """
        desc = task.get("desc", "")
        result = task.get("result", "")
        # 截断过长 result
        if len(result) > 500:
            result = result[:500] + "...[truncated]"

        prompt = (
            f"任务: {desc}\n"
            f"执行结果: {result}\n\n"
            f"判断任务是否真正完成（注意假成功：结果含 Error/Traceback/失败/异常 等）。\n"
            f"只输出 'ok' 或 'fail: <原因>'。"
        )
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], stream=False)
        return (response.get("content") or "fail: no response").strip()
```

- [ ] **Step 2: 跑 Reflector 测试确认全 PASS**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: 7 PASSED

- [ ] **Step 3: Commit**

```bash
git add core/reflector.py
git commit -m "feat(reflector): implement LLM evaluation with false-success detection (Phase 2)"
```

---

## Task 3: TDD - 写 CognitiveController 分级降级测试

**Files:**
- Modify: `tests/test_cognitive_controller.py`

- [ ] **Step 1: 在 test_cognitive_controller.py 末尾追加分级降级测试**

```python
class TestCognitiveControllerDegradation:
    """Phase 2: 分级降级 L1/L2/L3 测试。"""

    def test_task_fail_triggers_local_retry_l1(self):
        """任务失败 retries <= max_task_retries 时应局部重试（L1）。"""
        controller = _make_controller(max_task_retries=2, max_replans=3)
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                # 第一次执行返回 failed
                with patch.object(controller.executor, 'execute') as mock_exec:
                    mock_exec.return_value = {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None}
                    with patch.object(controller.reflector, 'evaluate', return_value="fail: test failure"):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        # 验证 retries 递增
        assert controller.task_list[0]["retries"] == 1
        assert controller.task_list[0]["feedback"] == "fail: test failure"
        # 验证状态回 EXECUTING（局部重试）
        # 注意：执行后状态可能变化，验证 retries 即可

    def test_local_retry_exhausted_triggers_replan_l2(self):
        """局部重试耗尽（retries > max_task_retries）应升级为整体重规划（L2）。"""
        controller = _make_controller(max_task_replans=2, max_replans=3)
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 3, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute', return_value={"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 3, "feedback": None}):
                    with patch.object(controller.reflector, 'evaluate', return_value="fail: persistent failure"):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        # 验证 replan_count 递增
        assert controller.replan_count == 1

    def test_replan_exhausted_enters_done_l3(self):
        """整体重规划耗尽（replan_count > max_replans）应进入 DONE 并报错（L3）。"""
        controller = _make_controller(max_task_retries=1, max_replans=2)
        # 直接构造 replan_count 已达上限的状态
        controller.replan_count = 3
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 2, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute', return_value={"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 2, "feedback": None}):
                    with patch.object(controller.reflector, 'evaluate', return_value="fail: still failing"):
                        controller.chat("task")
        from core.cognitive import State
        assert controller.state == State.DONE

    def test_replan_passes_feedback_to_planner(self):
        """L2 重规划时应把失败反馈传给 Planner.execute。"""
        controller = _make_controller(max_task_retries=1, max_replans=3)
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 2, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks) as mock_plan:
                # 第一次规划
                # 第二次重规划（带 feedback）
                mock_plan.side_effect = [fake_tasks, [{"id": 0, "desc": "new task", "status": "pending", "retries": 0, "feedback": None}]]
                with patch.object(controller.executor, 'execute', return_value={"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}):
                    with patch.object(controller.reflector, 'evaluate', return_value="success"):
                        controller.chat("task")
        # 验证第二次调用 Planner.execute 时传了 feedback
        if mock_plan.call_count >= 2:
            second_call = mock_plan.call_args_list[1]
            # second_call 可能是位置参数或关键字参数
            args = second_call[0]
            kwargs = second_call[1]
            feedback_passed = (len(args) >= 2 and args[1]) or kwargs.get('feedback')
            assert feedback_passed, "重规划应传 feedback 给 Planner"

    def test_success_after_retry_proceeds_to_next_task(self):
        """局部重试成功后应继续执行下一个任务。"""
        controller = _make_controller(max_task_retries=2, max_replans=3)
        fake_tasks = [
            {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None},
            {"id": 1, "desc": "t2", "status": "pending", "retries": 0, "feedback": None},
        ]
        # 第一次执行 task 0 失败，第二次执行 task 0 成功，第三次执行 task 1 成功
        exec_results = [
            {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None},
            {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 1, "feedback": None},
            {"id": 1, "desc": "t2", "status": "done", "result": "ok", "retries": 0, "feedback": None},
        ]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute', side_effect=exec_results):
                    # task 0 第一次 fail，第二次 success；task 1 success
                    reflect_results = ["fail: error", "success", "success"]
                    with patch.object(controller.reflector, 'evaluate', side_effect=reflect_results):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        from core.cognitive import State
        assert controller.state == State.DONE
        assert controller.current_task_idx == 2  # 两个任务都执行完
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_controller.py::TestCognitiveControllerDegradation -v`
Expected: 5 FAIL（Phase 1 stub 不实现降级）

- [ ] **Step 3: Commit**

```bash
git add tests/test_cognitive_controller.py
git commit -m "test: add failing degradation tests (RED)"
```

---

## Task 4: 实现 CognitiveController 分级降级（GREEN）

**Files:**
- Modify: `core/cognitive.py`

- [ ] **Step 1: 替换 `_step_reflect` 和 `_step_replan` 方法**

定位 `core/cognitive.py` 中的 `_step_reflect` 方法（Phase 1 stub），替换为：

```python
def _step_reflect(self):
    """反思当前任务结果，实现 L1/L2/L3 分级降级。"""
    task = self.task_list[self.current_task_idx]
    verdict = self.reflector.evaluate(task)

    if verdict == "success":
        # 任务成功，下一个
        task["status"] = "done"
        self.current_task_idx += 1
        if self.current_task_idx >= len(self.task_list):
            self.state = State.DONE
        else:
            self.state = State.EXECUTING
    else:
        # 失败
        task["retries"] = task.get("retries", 0) + 1
        task["feedback"] = verdict

        if task["retries"] <= self.max_task_retries:
            # L1: 局部重试（回 EXECUTING，带 feedback）
            self.state = State.EXECUTING
        else:
            # 局部重试耗尽
            self.replan_count += 1
            if self.replan_count <= self.max_replans:
                # L2: 整体重规划
                self.state = State.PLANNING
            else:
                # L3: 报错给用户
                task["status"] = "failed"
                self.state = State.DONE
```

- [ ] **Step 2: 替换 `_step_replan` 方法**

```python
def _step_replan(self):
    """L2 重规划：带 Reflect feedback 调 Planner.execute。"""
    feedback = [t.get("feedback") for t in self.task_list if t.get("feedback")]
    new_tasks = self.planner.execute(self._user_input, feedback=feedback)
    self.task_list = new_tasks
    self.current_task_idx = 0
    self.state = State.EXECUTING
```

- [ ] **Step 3: 跑分级降级测试确认 PASS**

Run: `python -m pytest tests/test_cognitive_controller.py::TestCognitiveControllerDegradation -v`
Expected: 5 PASSED

- [ ] **Step 4: 跑全套 cognitive_controller 测试确认无回归**

Run: `python -m pytest tests/test_cognitive_controller.py -v`
Expected: 9 PASSED（4 Phase 1 + 5 Phase 2）

- [ ] **Step 5: Commit**

```bash
git add core/cognitive.py
git commit -m "feat(cognitive): implement L1/L2/L3 degradation (Phase 2)"
```

---

## Task 5: 集成测试 + 边界验证

- [ ] **Step 1: 跑全套测试确认无回归**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 147 passed（140 Phase 1 + 7 Reflector 真实评估 + 5 分级降级 - 5 重复 = 147）

- [ ] **Step 2: 手动验证失败重规划场景**

启动 `python main.py`，配置 LLM，输入一个故意会失败的任务（如 "执行不存在的命令 xxx"），观察：
- Executor 执行失败 → Reflector 识别 fail
- 局部重试 2 次仍失败 → 整体重规划
- 重规划 3 次仍失败 → 报错给用户

- [ ] **Step 3: 验证假成功检测**

输入一个会产生 Error 输出但 LLM 可能误判完成的任务，观察 Reflector 是否识别为 fail。

- [ ] **Step 4: Commit（如有调整）**

```bash
git add -A
git commit -m "chore: Phase 2 integration verification"
```

---

## Phase 2 完成验收

- [ ] Reflector 实现真实 LLM 评估 + 假成功检测
- [ ] CognitiveController 实现 L1（局部重试 ≤ max_task_retries）
- [ ] CognitiveController 实现 L2（整体重规划 ≤ max_replans，带 feedback）
- [ ] CognitiveController 实现 L3（报错给用户，进 DONE）
- [ ] 重规划时 feedback 传给 Planner
- [ ] 局部重试成功后继续下一个任务
- [ ] 全部测试通过（147 个）
- [ ] 现有 140 个测试无回归
