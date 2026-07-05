# Phase 3: Reflector 真实评估 + L1/L2/L3 分级降级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 升级 Reflector 为 LLM 假成功检测，实现 LangGraph 条件边的 L1/L2/L3 分级降级（局部重试 → 整体重规划带 feedback → 报错给用户）

**Architecture:** Reflector 用 Pydantic 输出 verdict 字段，cognitive_graph 的 reflecting 节点根据 verdict 更新 task_list 和 replan_count，条件边 `route_after_reflect` 路由到 executing（L1）/planning（L2）/done（L3/all_done）

**Tech Stack:** LangGraph conditional_edges, Pydantic, ChatOpenAI structured output

---

## File Structure

- Modify: `core/reflector.py` - 升级为 LLM 评估
- Modify: `core/cognitive_graph.py` - 实现 L1/L2/L3 路由
- Test: `tests/test_reflector.py`, `tests/test_cognitive_graph.py`

---

### Task 1: Reflector 升级为 LLM 假成功检测

**Files:**
- Modify: `core/reflector.py`
- Modify: `tests/test_reflector.py`

- [ ] **Step 1: 添加测试（保留原 stub 测试，追加 LLM 评估测试）**

```python
# tests/test_reflector.py 追加
def test_reflector_llm_evaluates_apparent_success():
    """status=done 且无错误关键词时应调 LLM 评估。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SUCCESS"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "看起来完成了，但实际可能有 bug", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"
    mock_llm.invoke.assert_called_once()


def test_reflector_llm_detects_apparent_failure():
    """LLM 应能识别假成功。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "FAIL: result contains syntax error"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "代码已生成", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")
    assert "syntax error" in verdict


def test_reflector_llm_exception_falls_back_to_success():
    """LLM 异常应兜底为 success（避免阻塞流程）。"""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API error")
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"


def test_reflector_truncates_long_result():
    """result > 500 字符应截断。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SUCCESS"
    mock_llm.invoke.return_value = mock_response
    reflector = Reflector(llm=mock_llm)
    long_result = "x" * 1000
    task = {"id": 0, "desc": "t1", "status": "done", "result": long_result, "retries": 0, "feedback": None}
    reflector.invoke(task)
    # 验证 LLM prompt 包含截断后的内容
    call_args = mock_llm.invoke.call_args
    messages = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
    # 应该不包含完整 1000 字符
    prompt_content = str(messages)
    assert "x" * 1000 not in prompt_content
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: FAIL（新测试失败）

- [ ] **Step 3: 升级 core/reflector.py**

```python
# core/reflector.py
"""Reflector - 反思任务结果，LLM 假成功检测。

Phase 3: LLM 评估 + 失败兜底
"""
from langchain_core.messages import HumanMessage, SystemMessage


class Reflector:
    """Reflector - 评估任务结果是否真的成功。"""

    def __init__(self, llm=None):
        self.llm = llm

    def invoke(self, task: dict) -> str:
        """评估任务结果。

        Returns:
            "success" 或 "fail: <reason>"
        """
        status = task.get("status", "")
        result = task.get("result", "") or ""

        # 规则 1：status=failed 直接 fail
        if status == "failed":
            return f"fail: {result[:200]}"

        # 规则 2：result 含错误关键词
        error_keywords = ("error", "traceback", "exception", "failed", "失败", "错误")
        lower_result = result.lower()
        for kw in error_keywords:
            if kw in lower_result:
                return f"fail: result contains '{kw}'"

        # 规则 3：LLM 假成功检测
        if self.llm is None:
            return "success"
        try:
            return self._llm_evaluate(task)
        except Exception:
            # 兜底：LLM 异常时不阻塞流程
            return "success"

    def _llm_evaluate(self, task: dict) -> str:
        """LLM 评估 result 是否真的成功。"""
        result = task.get("result", "") or ""
        # 截断长 result
        if len(result) > 500:
            result = result[:500] + "... [truncated]"

        prompt = f"""评估以下任务结果是否真的成功：

任务描述: {task.get('desc', '')}
状态: {task.get('status', '')}
结果:
{result}

判断标准:
- SUCCESS: 结果确实完成了任务，无遗留问题
- FAIL: <reason>: 结果有问题（如代码语法错误、逻辑漏洞、未处理边界情况等）

只输出 SUCCESS 或 FAIL: <reason>，不要其他文字。"""

        response = self.llm.invoke([
            SystemMessage(content="你是任务结果评估助手，识别假成功。"),
            HumanMessage(content=prompt),
        ])
        content = getattr(response, "content", "") or ""
        content = content.strip()

        if content.upper().startswith("SUCCESS"):
            return "success"
        if content.upper().startswith("FAIL"):
            # 提取 reason
            if ":" in content:
                reason = content.split(":", 1)[1].strip()
                return f"fail: {reason}"
            return "fail: LLM 判定失败"
        # 兜底
        return "success"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: PASS（8 个测试全过：原 4 + 新 4）

- [ ] **Step 5: 提交**

```bash
git add core/reflector.py tests/test_reflector.py
git commit -m "feat(reflector): upgrade to LLM apparent-success detection with fallback"
```

---

### Task 2: 实现条件边路由 route_after_reflect

**Files:**
- Modify: `core/cognitive_graph.py`
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加路由函数测试**

```python
# tests/test_cognitive_graph.py 追加
from core.cognitive_graph import route_after_reflect


def test_route_after_reflect_success_next():
    """verdict=success_next 应路由到 executing。"""
    state = {"verdict": "success_next"}
    assert route_after_reflect(state) == "success_next"


def test_route_after_reflect_retry_l1():
    """verdict=retry_l1 应路由到 executing。"""
    state = {"verdict": "retry_l1"}
    assert route_after_reflect(state) == "retry_l1"


def test_route_after_reflect_replan_l2():
    """verdict=replan_l2 应路由到 planning。"""
    state = {"verdict": "replan_l2"}
    assert route_after_reflect(state) == "replan_l2"


def test_route_after_reflect_fail_l3():
    """verdict=fail_l3 应路由到 done。"""
    state = {"verdict": "fail_l3"}
    assert route_after_reflect(state) == "fail_l3"


def test_route_after_reflect_all_done():
    """verdict=all_done 应路由到 done。"""
    state = {"verdict": "all_done"}
    assert route_after_reflect(state) == "all_done"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_graph.py::test_route_after_reflect_success_next -v`
Expected: FAIL with "cannot import name 'route_after_reflect'"

- [ ] **Step 3: 实现 route_after_reflect**

在 `core/cognitive_graph.py` 添加：

```python
def route_after_reflect(state: AgentState) -> str:
    """reflecting 后的路由函数。"""
    return state.get("verdict", "fail_l3")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（5 个新测试 + 原有）

- [ ] **Step 5: 提交**

```bash
git add core/cognitive_graph.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): add route_after_reflect for L1/L2/L3 routing"
```

---

### Task 3: 升级 reflecting 节点实现 L1/L2/L3 降级

**Files:**
- Modify: `core/cognitive_graph.py`
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加降级测试**

```python
# tests/test_cognitive_graph.py 追加
def test_reflecting_node_success_advances_to_next_task():
    """success 应推进到下个任务。"""
    from core.cognitive_graph import make_reflecting_node
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "success"
    node = make_reflecting_node(mock_reflector)
    state = _initial_state("task")
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "executing", "retries": 0, "feedback": None},
        {"id": 1, "desc": "t2", "status": "pending", "retries": 0, "feedback": None},
    ]
    state["current_task_idx"] = 0
    result = node(state)
    assert result["verdict"] == "success_next"
    assert result["current_task_idx"] == 1
    assert result["task_list"][0]["status"] == "done"


def test_reflecting_node_success_last_task_all_done():
    """success 最后一个任务应判定 all_done。"""
    from core.cognitive_graph import make_reflecting_node
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "success"
    node = make_reflecting_node(mock_reflector)
    state = _initial_state("task")
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "executing", "retries": 0, "feedback": None},
    ]
    state["current_task_idx"] = 0
    result = node(state)
    assert result["verdict"] == "all_done"


def test_reflecting_node_l1_local_retry():
    """失败 + retries <= max_task_retries 应触发 L1 局部重试。"""
    from core.cognitive_graph import make_reflecting_node
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "fail: test error"
    node = make_reflecting_node(mock_reflector)
    state = _initial_state("task", max_task_retries=2, max_replans=3)
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "executing", "retries": 0, "feedback": None},
    ]
    state["current_task_idx"] = 0
    result = node(state)
    assert result["verdict"] == "retry_l1"
    assert result["task_list"][0]["retries"] == 1
    assert result["task_list"][0]["feedback"] == "fail: test error"


def test_reflecting_node_l2_replan_when_retries_exhausted():
    """失败 + retries > max_task_retries + replan_count <= max_replans 应触发 L2 重规划。"""
    from core.cognitive_graph import make_reflecting_node
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "fail: persistent error"
    node = make_reflecting_node(mock_reflector)
    state = _initial_state("task", max_task_retries=1, max_replans=3)
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "executing", "retries": 2, "feedback": None},
    ]
    state["current_task_idx"] = 0
    result = node(state)
    assert result["verdict"] == "replan_l2"
    assert result["replan_count"] == 1
    assert "persistent error" in result["last_feedback"]


def test_reflecting_node_l3_fail_when_replans_exhausted():
    """失败 + replan_count > max_replans 应触发 L3 报错。"""
    from core.cognitive_graph import make_reflecting_node
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "fail: still failing"
    node = make_reflecting_node(mock_reflector)
    state = _initial_state("task", max_task_retries=1, max_replans=2)
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "executing", "retries": 2, "feedback": None},
    ]
    state["current_task_idx"] = 0
    state["replan_count"] = 3  # 已超 max_replans
    result = node(state)
    assert result["verdict"] == "fail_l3"
    assert result["task_list"][0]["status"] == "failed"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: FAIL（5 个新测试失败）

- [ ] **Step 3: 升级 make_reflecting_node**

替换 `core/cognitive_graph.py` 中的 `make_reflecting_node`：

```python
def make_reflecting_node(reflector):
    """构造 reflecting 节点函数 - 实现 L1/L2/L3 分级降级。"""
    def reflecting_node(state: AgentState) -> AgentState:
        task = state["task_list"][state["current_task_idx"]]
        verdict = reflector.invoke(task)

        if verdict == "success":
            task["status"] = "done"
            state["current_task_idx"] += 1
            if state["current_task_idx"] >= len(state["task_list"]):
                state["verdict"] = "all_done"
            else:
                state["verdict"] = "success_next"
        else:
            # 失败：递增 retries，记录 feedback
            task["retries"] = task.get("retries", 0) + 1
            task["feedback"] = verdict

            if task["retries"] <= state["max_task_retries"]:
                # L1: 局部重试
                state["verdict"] = "retry_l1"
            else:
                # 局部重试耗尽，考虑 L2 重规划
                state["replan_count"] += 1
                if state["replan_count"] <= state["max_replans"]:
                    # L2: 整体重规划，收集所有 feedback
                    state["last_feedback"] = [
                        t.get("feedback") for t in state["task_list"] if t.get("feedback")
                    ]
                    state["verdict"] = "replan_l2"
                else:
                    # L3: 报错给用户
                    task["status"] = "failed"
                    state["verdict"] = "fail_l3"
        return state
    return reflecting_node
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（5 个新测试 + 原有）

- [ ] **Step 5: 提交**

```bash
git add core/cognitive_graph.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): implement L1/L2/L3 degradation in reflecting node"
```

---

### Task 4: 更新 build_cognitive_graph 使用条件边

**Files:**
- Modify: `core/cognitive_graph.py`
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加集成测试**

```python
# tests/test_cognitive_graph.py 追加
def test_full_flow_l1_retry_then_success():
    """L1 重试后成功。"""
    mock_planner = MagicMock()
    mock_planner.invoke.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
    ]
    mock_executor = MagicMock()
    # 第一次 fail，第二次 success
    mock_executor.invoke.side_effect = [
        {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None},
        {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None},
    ]
    mock_reflector = MagicMock()
    mock_reflector.invoke.side_effect = ["fail: test", "success"]
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("task", max_task_retries=2, max_replans=3)
    result = g.invoke(state)
    assert "ok" in result["final_answer"]
    assert mock_executor.invoke.call_count == 2


def test_full_flow_l2_replan_with_feedback():
    """L2 重规划应带 feedback 调 Planner。"""
    mock_planner = MagicMock()
    mock_planner.invoke.side_effect = [
        [{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}],
        [{"id": 0, "desc": "new task", "status": "pending", "retries": 0, "feedback": None}],
        [{"id": 0, "desc": "new task", "status": "pending", "retries": 0, "feedback": None}],
    ]
    mock_executor = MagicMock()
    mock_executor.invoke.side_effect = [
        {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None},
        {"id": 0, "desc": "new task", "status": "done", "result": "ok", "retries": 0, "feedback": None},
    ]
    mock_reflector = MagicMock()
    mock_reflector.invoke.side_effect = ["fail: test", "success"]
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("task", max_task_retries=1, max_replans=3)
    result = g.invoke(state)
    # 第二次 planner.invoke 应带 feedback
    assert mock_planner.invoke.call_count >= 2
    second_call = mock_planner.invoke.call_args_list[1]
    kwargs = second_call[1] if len(second_call) > 1 else {}
    args = second_call[0] if second_call[0] else ()
    feedback_passed = (len(args) >= 2 and args[1]) or kwargs.get('feedback')
    assert feedback_passed, "重规划应传 feedback"
    assert "ok" in result["final_answer"]


def test_full_flow_l3_fail():
    """L3 报错给用户。"""
    mock_planner = MagicMock()
    mock_planner.invoke.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
    ]
    mock_executor = MagicMock()
    mock_executor.invoke.return_value = {
        "id": 0, "desc": "t1", "status": "failed", "result": "persistent error", "retries": 0, "feedback": None
    }
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "fail: still failing"
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("task", max_task_retries=1, max_replans=1)
    result = g.invoke(state)
    assert "failed" in result["final_answer"]
    assert result["task_list"][0]["status"] == "failed"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_graph.py::test_full_flow_l1_retry_then_success -v`
Expected: FAIL（条件边未配置）

- [ ] **Step 3: 更新 build_cognitive_graph**

替换 `core/cognitive_graph.py` 中的 `build_cognitive_graph`：

```python
def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
    """构建 LangGraph StateGraph - 实现 L1/L2/L3 分级降级。"""
    g = StateGraph(AgentState)

    # 节点
    g.add_node("classify", classify_node)
    g.add_node("planning", make_planning_node(planner))
    g.add_node("executing", make_executing_node(executor))
    g.add_node("reflecting", make_reflecting_node(reflector))
    g.add_node("done", done_node)

    # 入口
    g.set_entry_point("classify")

    # 条件边
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": "done",
        "complex": "planning",
    })
    g.add_edge("planning", "executing")
    g.add_edge("executing", "reflecting")
    # reflecting 后用条件边路由 L1/L2/L3
    g.add_conditional_edges("reflecting", route_after_reflect, {
        "success_next": "executing",
        "retry_l1": "executing",
        "replan_l2": "planning",
        "fail_l3": "done",
        "all_done": "done",
    })
    g.add_edge("done", END)

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（所有测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/cognitive_graph.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): add conditional edges for L1/L2/L3 degradation routing"
```

---

### Task 5: 完整集成测试 + 多任务场景

**Files:**
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加多任务测试**

```python
# tests/test_cognitive_graph.py 追加
def test_full_flow_multi_task_success():
    """多任务全部成功。"""
    mock_planner = MagicMock()
    mock_planner.invoke.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None},
        {"id": 1, "desc": "t2", "status": "pending", "retries": 0, "feedback": None},
    ]
    mock_executor = MagicMock()
    mock_executor.invoke.side_effect = [
        {"id": 0, "desc": "t1", "status": "done", "result": "r1", "retries": 0, "feedback": None},
        {"id": 1, "desc": "t2", "status": "done", "result": "r2", "retries": 0, "feedback": None},
    ]
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "success"
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("task", max_task_retries=2, max_replans=3)
    result = g.invoke(state)
    assert "r1" in result["final_answer"]
    assert "r2" in result["final_answer"]
    assert mock_executor.invoke.call_count == 2


def test_full_flow_first_fail_second_success():
    """第一个任务失败 L1 重试后成功，第二个任务也成功。"""
    mock_planner = MagicMock()
    mock_planner.invoke.return_value = [
        {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None},
        {"id": 1, "desc": "t2", "status": "pending", "retries": 0, "feedback": None},
    ]
    mock_executor = MagicMock()
    mock_executor.invoke.side_effect = [
        {"id": 0, "desc": "t1", "status": "failed", "result": "err", "retries": 0, "feedback": None},
        {"id": 0, "desc": "t1", "status": "done", "result": "r1", "retries": 0, "feedback": None},
        {"id": 1, "desc": "t2", "status": "done", "result": "r2", "retries": 0, "feedback": None},
    ]
    mock_reflector = MagicMock()
    mock_reflector.invoke.side_effect = ["fail: test", "success", "success"]
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("task", max_task_retries=2, max_replans=3)
    result = g.invoke(state)
    assert "r1" in result["final_answer"]
    assert "r2" in result["final_answer"]


def test_full_flow_simple_skips_planning():
    """simple 输入不应调 planner。"""
    mock_planner = MagicMock()
    mock_executor = MagicMock()
    mock_reflector = MagicMock()
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("hi", max_task_retries=2, max_replans=3)
    result = g.invoke(state)
    assert result["verdict"] == "simple"
    mock_planner.invoke.assert_not_called()
    mock_executor.invoke.assert_not_called()
    mock_reflector.invoke.assert_not_called()
```

- [ ] **Step 2: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS

- [ ] **Step 3: 跑全部测试确认无回归**

Run: `python -m pytest tests/ -v`
Expected: PASS（Phase 1 + Phase 2 + Phase 3 全部 ~70 测试通过）

- [ ] **Step 4: 提交**

```bash
git add tests/test_cognitive_graph.py
git commit -m "test(cognitive): add multi-task and L1 retry integration tests"
```

---

## Phase 3 完成标准

- [ ] Reflector 升级为 LLM 假成功检测，异常兜底为 success
- [ ] L1 局部重试正常工作（retries <= max_task_retries）
- [ ] L2 整体重规划带 feedback（replan_count <= max_replans）
- [ ] L3 报错给用户（task.status = failed）
- [ ] 多任务场景：第一个失败 L1 重试成功，第二个继续执行
- [ ] simple 输入跳过 planning/executing/reflecting
- [ ] 70+ 单元测试全部通过
