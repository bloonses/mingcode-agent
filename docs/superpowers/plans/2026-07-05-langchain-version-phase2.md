# Phase 2: LangGraph 认知框架基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 LangGraph StateGraph 实现 CognitiveController 状态机（5 节点：CLASSIFY → PLANNING → EXECUTING → REFLECTING → DONE），集成 Plan-and-Execute 框架，Reflector 暂为 stub

**Architecture:** StateGraph 节点是纯函数 `(state) -> state`，条件边用路由函数实现状态转换，SqliteSaver 自动持久化，复用 Phase 1 的工具和 LLM 客户端

**Tech Stack:** LangGraph StateGraph, SqliteSaver, langchain-core, Pydantic

---

## File Structure

- Create: `core/cognitive_graph.py` - LangGraph StateGraph 主图
- Create: `core/planner.py` - Planner（Phase 2 简单单次 LLM 调用）
- Create: `core/executor.py` - Executor 包装 ReAct
- Create: `core/reflector.py` - Reflector stub（只看 status）
- Create: `core/self_asker.py` - SelfAsker 占位
- Modify: `core/agent.py` - 接入 cognitive_controller
- Test: `tests/test_cognitive_graph.py`, `tests/test_planner.py`, `tests/test_executor.py`, `tests/test_reflector.py`, `tests/test_self_asker.py`

---

### Task 1: CognitiveGraph 基础结构和状态定义

**Files:**
- Create: `core/cognitive_graph.py`
- Test: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cognitive_graph.py
"""CognitiveGraph (LangGraph StateGraph) 测试。"""
from unittest.mock import patch, MagicMock
from core.cognitive_graph import AgentState, build_cognitive_graph, classify_node


def test_agent_state_typed_dict_fields():
    """AgentState 应包含所有必需字段。"""
    # TypedDict 是 dict 子类，可直接构造
    state: AgentState = {
        "user_input": "hi",
        "messages": [],
        "task_list": [],
        "current_task_idx": 0,
        "replan_count": 0,
        "last_feedback": [],
        "final_answer": "",
        "verdict": "",
        "max_task_retries": 2,
        "max_replans": 3,
    }
    assert state["user_input"] == "hi"
    assert state["max_replans"] == 3


def test_classify_node_short_input():
    """短输入应判定 simple。"""
    state = {
        "user_input": "hi",
        "messages": [],
        "task_list": [],
        "current_task_idx": 0,
        "replan_count": 0,
        "last_feedback": [],
        "final_answer": "",
        "verdict": "",
        "max_task_retries": 2,
        "max_replans": 3,
    }
    result = classify_node(state)
    assert result["verdict"] == "simple"


def test_classify_node_greeting():
    """问候词应判定 simple。"""
    state = {
        "user_input": "你好世界",
        "messages": [],
        "task_list": [],
        "current_task_idx": 0,
        "replan_count": 0,
        "last_feedback": [],
        "final_answer": "",
        "verdict": "",
        "max_task_retries": 2,
        "max_replans": 3,
    }
    result = classify_node(state)
    assert result["verdict"] == "simple"


def test_build_graph_returns_compiled():
    """build_cognitive_graph 应返回编译后的图。"""
    mock_planner = MagicMock()
    mock_executor = MagicMock()
    mock_reflector = MagicMock()
    mock_classifier = MagicMock()
    g = build_cognitive_graph(
        planner=mock_planner,
        executor=mock_executor,
        reflector=mock_reflector,
        classifier=mock_classifier,
    )
    assert g is not None
    # 编译后的图应有 invoke 方法
    assert hasattr(g, "invoke")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: FAIL with "No module named 'core.cognitive_graph'"

- [ ] **Step 3: 实现 core/cognitive_graph.py（基础结构）**

```python
# core/cognitive_graph.py
"""CognitiveGraph - LangGraph StateGraph 实现的综合认知框架。

替代 NeonAgent 的 CognitiveController 状态机：
- 节点函数纯函数式 (state) -> state
- 条件边用路由函数实现 L1/L2/L3 分级降级
- SqliteSaver 自动持久化
"""
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    """LangGraph 状态容器。"""
    user_input: str
    messages: List[Dict[str, Any]]
    task_list: List[Dict]
    current_task_idx: int
    replan_count: int
    last_feedback: List[str]
    final_answer: str
    verdict: str  # success / fail: xxx / simple / complex
    max_task_retries: int
    max_replans: int


def _initial_state(user_input: str, max_task_retries: int = 2, max_replans: int = 3) -> AgentState:
    """构造初始状态。"""
    return {
        "user_input": user_input,
        "messages": [],
        "task_list": [],
        "current_task_idx": 0,
        "replan_count": 0,
        "last_feedback": [],
        "final_answer": "",
        "verdict": "",
        "max_task_retries": max_task_retries,
        "max_replans": max_replans,
    }


def classify_node(state: AgentState) -> AgentState:
    """分类节点 - 本地预过滤 + LLM 分类。"""
    user_input = state["user_input"]
    stripped = user_input.strip()

    # 规则 1：短输入直接 simple
    if len(stripped) <= 6:
        state["verdict"] = "simple"
        return state

    # 规则 2：问候词
    greeting_patterns = (
        "你好", "您好", "嗨", "哈喽", "在吗", "在不在",
        "thanks", "thank you", "谢谢", "辛苦", "再见", "bye",
    )
    lower = stripped.lower()
    if any(p in lower for p in greeting_patterns):
        state["verdict"] = "simple"
        return state

    # 规则 3：复杂输入（Phase 2 简化版，不调 LLM，直接 complex）
    # Phase 3+ 接入 LLM classifier
    state["verdict"] = "complex"
    return state


def route_after_classify(state: AgentState) -> str:
    """分类后路由。"""
    return "simple" if state.get("verdict") == "simple" else "complex"


def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
    """构建 LangGraph StateGraph。

    Args:
        planner: 有 invoke(user_input, feedback) -> List[Dict] 的对象
        executor: 有 invoke(task) -> dict 的对象
        reflector: 有 invoke(task) -> str 的对象
        classifier: 可选，有 invoke(input) -> str 的对象（Phase 3+ 用）
        checkpointer: SqliteSaver 实例，None 表示不用 checkpointer
    """
    g = StateGraph(AgentState)

    # 节点
    g.add_node("classify", classify_node)

    # 入口
    g.set_entry_point("classify")

    # 条件边：classify 后路由到 done（simple）或 planning（complex）
    # Phase 2 后续 task 实现 planning/executing/reflecting 节点
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": END,         # Phase 2 Task 2 实现 simple fallback
        "complex": "planning",  # Phase 2 Task 3 实现 planning 节点
    })

    # 编译
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/cognitive_graph.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): add LangGraph StateGraph skeleton with classify node"
```

---

### Task 2: 添加 done 节点 + simple fallback 路由

**Files:**
- Modify: `core/cognitive_graph.py`
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加测试**

```python
# tests/test_cognitive_graph.py 追加
def test_simple_input_completes_via_graph():
    """simple 输入应通过 graph 完成到 END。"""
    mock_planner = MagicMock()
    mock_executor = MagicMock()
    mock_reflector = MagicMock()
    g = build_cognitive_graph(
        planner=mock_planner,
        executor=mock_executor,
        reflector=mock_reflector,
    )
    result = g.invoke(_initial_state("hi"))
    assert result["verdict"] == "simple"
    # planner/executor 不应被调用
    mock_planner.invoke.assert_not_called()
    mock_executor.invoke.assert_not_called()


def test_done_node_builds_answer():
    """done 节点应构建最终答案。"""
    from core.cognitive_graph import done_node
    state = _initial_state("task")
    state["task_list"] = [
        {"id": 0, "desc": "t1", "status": "done", "result": "ok"},
    ]
    result = done_node(state)
    assert "ok" in result["final_answer"]
    assert "t1" in result["final_answer"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cognitive_graph.py::test_done_node_builds_answer -v`
Expected: FAIL with "cannot import name 'done_node'"

- [ ] **Step 3: 修改 cognitive_graph.py 添加 done 节点**

在 `core/cognitive_graph.py` 末尾追加：

```python
def done_node(state: AgentState) -> AgentState:
    """done 节点 - 汇总所有任务结果。"""
    results = []
    for task in state.get("task_list", []):
        status = task.get("status", "unknown")
        desc = task.get("desc", "")
        result = task.get("result", "")
        results.append(f"[{status}] {desc}: {result}")
    state["final_answer"] = "\n".join(results) if results else "(无任务执行)"
    return state
```

修改 `build_cognitive_graph` 添加 done 节点和 simple 路由：

```python
def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
    g = StateGraph(AgentState)

    # 节点
    g.add_node("classify", classify_node)
    g.add_node("done", done_node)

    # 入口
    g.set_entry_point("classify")

    # 条件边
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": "done",
        "complex": "planning",  # Phase 2 Task 3 实现
    })
    g.add_edge("done", END)

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（6 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/cognitive_graph.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): add done node with answer aggregation"
```

---

### Task 3: Planner 节点 + planning 节点

**Files:**
- Create: `core/planner.py`
- Modify: `core/cognitive_graph.py`
- Test: `tests/test_planner.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_planner.py
"""Planner 测试。"""
import json
from unittest.mock import patch, MagicMock
from core.planner import Planner


def test_planner_invoke_returns_list():
    """Planner.invoke 应返回任务列表。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None},
        {"id": 1, "desc": "step 2", "status": "pending", "retries": 0, "feedback": None},
    ])
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    tasks = planner.invoke("write a snake game")
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    assert tasks[0]["desc"] == "step 1"


def test_planner_invoke_with_feedback():
    """Planner.invoke 应能接受 feedback 参数。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"id": 0, "desc": "new step", "status": "pending", "retries": 0, "feedback": None}
    ])
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    tasks = planner.invoke("task", feedback=["previous failure"])
    assert len(tasks) == 1
    # LLM 应该被调用
    mock_llm.invoke.assert_called_once()


def test_planner_empty_response_fallback():
    """空响应应返回单任务兜底。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = ""
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    tasks = planner.invoke("task")
    assert len(tasks) == 1
    assert "task" in tasks[0]["desc"].lower() or tasks[0]["desc"]  # 不为空


def test_planner_invalid_json_fallback():
    """JSON 解析失败应返回单任务兜底。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "not a json"
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    tasks = planner.invoke("task")
    assert len(tasks) == 1


def test_planner_exception_fallback():
    """LLM 异常应返回单任务兜底，不抛异常。"""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API error")
    planner = Planner(mock_llm)
    tasks = planner.invoke("task")
    assert len(tasks) == 1
    assert "task" in tasks[0]["desc"].lower()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_planner.py -v`
Expected: FAIL with "No module named 'core.planner'"

- [ ] **Step 3: 实现 core/planner.py**

```python
# core/planner.py
"""Planner - 用 LLM 拆解任务，Phase 3 扩展 ToT。"""
import json
from typing import List, Dict, Optional, Any
from langchain_core.messages import HumanMessage, SystemMessage


class Planner:
    """Planner - 简单单次 LLM 调用生成任务列表。

    Phase 2: 简单 LLM 调用
    Phase 3: 扩展为 ToT（候选生成 → 评分 → 筛选）
    """

    def __init__(self, llm, tot_candidates: int = 3):
        self.llm = llm
        self.tot_candidates = tot_candidates  # Phase 3 用

    def invoke(self, user_input: str, feedback: Optional[List[str]] = None) -> List[Dict]:
        """生成任务列表。

        Args:
            user_input: 用户输入
            feedback: 失败反馈列表（L2 重规划时传入）
        """
        prompt = self._build_prompt(user_input, feedback)
        try:
            response = self.llm.invoke([
                SystemMessage(content="你是任务规划助手，把复杂任务拆解为子任务列表，输出 JSON 数组。"),
                HumanMessage(content=prompt),
            ])
            content = getattr(response, "content", "") or ""
            return self._parse_tasks(content, user_input)
        except Exception:
            return self._fallback_task(user_input)

    def _build_prompt(self, user_input: str, feedback: Optional[List[str]]) -> str:
        feedback_section = ""
        if feedback:
            feedback_str = "\n".join(f"- {f}" for f in feedback if f)
            feedback_section = f"\n\n之前的失败反馈：\n{feedback_str}\n请避免重复同样的错误。"
        return f"""把以下任务拆解为子任务列表：

用户任务: {user_input}{feedback_section}

输出 JSON 数组，每个元素格式：
{{"id": 0, "desc": "任务描述", "status": "pending", "retries": 0, "feedback": null}}

只输出 JSON，不要其他文字。"""

    def _parse_tasks(self, content: str, user_input: str) -> List[Dict]:
        """解析 LLM 输出为任务列表。"""
        # 提取 JSON 部分
        content = content.strip()
        # 去除 markdown 代码块
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(l for l in lines if not l.startswith("```"))
        try:
            tasks = json.loads(content)
            if not isinstance(tasks, list):
                return self._fallback_task(user_input)
            # 标准化
            for i, t in enumerate(tasks):
                t.setdefault("id", i)
                t.setdefault("status", "pending")
                t.setdefault("retries", 0)
                t.setdefault("feedback", None)
            return tasks
        except (json.JSONDecodeError, ValueError):
            return self._fallback_task(user_input)

    def _fallback_task(self, user_input: str) -> List[Dict]:
        """兜底：单个任务。"""
        return [{
            "id": 0,
            "desc": user_input,
            "status": "pending",
            "retries": 0,
            "feedback": None,
        }]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_planner.py -v`
Expected: PASS（5 个测试全过）

- [ ] **Step 5: 在 cognitive_graph.py 添加 planning 节点**

```python
# 在 cognitive_graph.py 添加
def make_planning_node(planner):
    """构造 planning 节点函数。"""
    def planning_node(state: AgentState) -> AgentState:
        feedback = state.get("last_feedback", [])
        tasks = planner.invoke(state["user_input"], feedback=feedback)
        state["task_list"] = tasks
        state["current_task_idx"] = 0
        return state
    return planning_node
```

修改 `build_cognitive_graph` 添加 planning 节点：

```python
def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
    g = StateGraph(AgentState)

    # 节点
    g.add_node("classify", classify_node)
    g.add_node("planning", make_planning_node(planner))
    g.add_node("done", done_node)

    # 入口
    g.set_entry_point("classify")

    # 条件边
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": "done",
        "complex": "planning",
    })
    g.add_edge("planning", "done")  # Phase 2 Task 4 改为 executing
    g.add_edge("done", END)

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 6: 跑全部 cognitive_graph 测试**

Run: `python -m pytest tests/test_cognitive_graph.py tests/test_planner.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add core/planner.py core/cognitive_graph.py tests/test_planner.py tests/test_cognitive_graph.py
git commit -m "feat(cognitive): add Planner with LLM task decomposition and planning node"
```

---

### Task 4: Executor 节点 + executing 节点

**Files:**
- Create: `core/executor.py`
- Modify: `core/cognitive_graph.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_executor.py
"""Executor 测试。"""
from unittest.mock import patch, MagicMock
from core.executor import Executor


def test_executor_invoke_returns_result():
    """Executor.invoke 应返回带 result 的 dict。"""
    mock_react_agent = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "task done successfully"
    mock_react_agent.invoke.return_value = {"messages": [mock_msg]}
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert "result" in result
    assert "status" in result
    assert result["status"] in ("done", "executed")


def test_executor_invoke_exception_returns_failed():
    """Executor 异常应返回 failed 状态。"""
    mock_react_agent = MagicMock()
    mock_react_agent.invoke.side_effect = Exception("API error")
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert result["status"] == "failed"
    assert "error" in result["result"].lower() or "API error" in result["result"]


def test_executor_invoke_preserves_task_fields():
    """Executor 应保留原 task 的 id 和 desc。"""
    mock_react_agent = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = "ok"
    mock_react_agent.invoke.return_value = {"messages": [mock_msg]}
    executor = Executor(react_agent=mock_react_agent)
    task = {"id": 5, "desc": "my task", "status": "pending", "retries": 0, "feedback": None}
    result = executor.invoke(task)
    assert result["id"] == 5
    assert result["desc"] == "my task"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_executor.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/executor.py**

```python
# core/executor.py
"""Executor - 包装 ReAct agent 执行单个任务。"""
from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage


class Executor:
    """Executor - 调用 ReAct agent 执行任务。

    Phase 2: 简单包装
    Phase 4: 扩展 Self-Ask 不确定性检测
    """

    def __init__(self, react_agent=None, llm=None, tools=None,
                 enable_uncertainty_check: bool = False):
        self.react_agent = react_agent
        self.llm = llm
        self.tools = tools or []
        self.enable_uncertainty_check = enable_uncertainty_check

    def invoke(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个任务。"""
        if self.react_agent is None:
            return {
                **task,
                "result": "Error: ReAct agent not configured",
                "status": "failed",
            }
        try:
            task_desc = task.get("desc", "")
            response = self.react_agent.invoke({
                "messages": [HumanMessage(content=task_desc)],
            })
            # 提取最后一条 AI 消息的内容
            messages = response.get("messages", [])
            content = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
                    content = msg.content
                    break
                elif hasattr(msg, "content") and msg.content:
                    content = msg.content
                    break
            return {
                **task,
                "result": content or "(无输出)",
                "status": "done",
            }
        except Exception as e:
            return {
                **task,
                "result": f"Error: {e}",
                "status": "failed",
            }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_executor.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 在 cognitive_graph.py 添加 executing 节点**

```python
# 在 cognitive_graph.py 添加
def make_executing_node(executor):
    """构造 executing 节点函数。"""
    def executing_node(state: AgentState) -> AgentState:
        task = state["task_list"][state["current_task_idx"]]
        task["status"] = "executing"
        result = executor.invoke(task)
        # 只更新 result 和 status，保留 retries 和 feedback
        task["result"] = result.get("result", "")
        task["status"] = result.get("status", "")
        return state
    return executing_node
```

修改 `build_cognitive_graph`：

```python
def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
    g = StateGraph(AgentState)

    # 节点
    g.add_node("classify", classify_node)
    g.add_node("planning", make_planning_node(planner))
    g.add_node("executing", make_executing_node(executor))
    g.add_node("done", done_node)

    # 入口
    g.set_entry_point("classify")

    # 条件边
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": "done",
        "complex": "planning",
    })
    g.add_edge("planning", "executing")
    g.add_edge("executing", "done")  # Phase 2 Task 5 改为 reflecting
    g.add_edge("done", END)

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 6: 跑全部测试**

Run: `python -m pytest tests/test_cognitive_graph.py tests/test_executor.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add core/executor.py core/cognitive_graph.py tests/test_executor.py
git commit -m "feat(cognitive): add Executor wrapping ReAct agent and executing node"
```

---

### Task 5: Reflector stub + reflecting 节点

**Files:**
- Create: `core/reflector.py`
- Modify: `core/cognitive_graph.py`
- Test: `tests/test_reflector.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_reflector.py
"""Reflector 测试。"""
from unittest.mock import MagicMock
from core.reflector import Reflector


def test_reflector_success_when_done():
    """status=done 应返回 success。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict == "success"


def test_reflector_fail_when_failed():
    """status=failed 应返回 fail:xxx。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "failed", "result": "Error: timeout", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")


def test_reflector_fail_with_error_in_result():
    """result 含 Error 应返回 fail。"""
    reflector = Reflector(llm=MagicMock())
    task = {"id": 0, "desc": "t1", "status": "done", "result": "Traceback: ...Error: something", "retries": 0, "feedback": None}
    verdict = reflector.invoke(task)
    assert verdict.startswith("fail")


def test_reflector_llm_not_called_in_stub():
    """Phase 2 stub 不应调 LLM。"""
    mock_llm = MagicMock()
    reflector = Reflector(llm=mock_llm)
    task = {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 0, "feedback": None}
    reflector.invoke(task)
    mock_llm.invoke.assert_not_called()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/reflector.py**

```python
# core/reflector.py
"""Reflector - 反思任务结果，Phase 2 stub。

Phase 2: 只看 status 和 result 关键词
Phase 3: 升级为 LLM 假成功检测
"""


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

        # 规则 3：Phase 2 stub，status=done 且无错误关键词即视为成功
        # Phase 3 升级为 LLM 评估
        return "success"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_reflector.py -v`
Expected: PASS（4 个测试全过）

- [ ] **Step 5: 在 cognitive_graph.py 添加 reflecting 节点**

```python
# 在 cognitive_graph.py 添加
def make_reflecting_node(reflector):
    """构造 reflecting 节点函数。

    Phase 2 stub: 只更新 verdict 为 success
    Phase 3: 实现 L1/L2/L3 分级降级
    """
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
            # Phase 3 实现 L1/L2/L3
            state["verdict"] = "fail_l3"  # stub 直接 L3
        return state
    return reflecting_node
```

修改 `build_cognitive_graph`：

```python
def build_cognitive_graph(planner, executor, reflector, classifier=None,
                          checkpointer=None):
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
    # Phase 2 stub: reflecting 后直接 done
    g.add_edge("reflecting", "done")
    g.add_edge("done", END)

    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 6: 跑全部测试**

Run: `python -m pytest tests/test_cognitive_graph.py tests/test_reflector.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add core/reflector.py core/cognitive_graph.py tests/test_reflector.py
git commit -m "feat(cognitive): add Reflector stub and reflecting node"
```

---

### Task 6: SelfAsker 占位

**Files:**
- Create: `core/self_asker.py`
- Test: `tests/test_self_asker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_self_asker.py
"""SelfAsker 测试。"""
from unittest.mock import MagicMock
from core.self_asker import SelfAsker


def test_selfasker_invoke_returns_confident():
    """Phase 4 之前的 SelfAsker 应返回 confident。"""
    asker = SelfAsker(llm=MagicMock(), tools=[])
    result = asker.invoke("some context")
    assert result == "confident"


def test_selfasker_ask_returns_empty():
    """Phase 4 之前的 ask 应返回空字符串。"""
    asker = SelfAsker(llm=MagicMock(), tools=[])
    result = asker.ask("question")
    assert result == ""


def test_selfasker_does_not_call_llm():
    """Phase 4 之前不应调 LLM。"""
    mock_llm = MagicMock()
    asker = SelfAsker(llm=mock_llm, tools=[])
    asker.invoke("ctx")
    mock_llm.invoke.assert_not_called()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_self_asker.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 core/self_asker.py**

```python
# core/self_asker.py
"""SelfAsker - 执行中遇不确定向用户提问。

Phase 2: 占位实现
Phase 4: LLM 不确定性检测 + ask_user 工具
"""


class SelfAsker:
    """SelfAsker - 不确定性检测。"""

    def __init__(self, llm=None, tools=None):
        self.llm = llm
        self.tools = tools or []

    def invoke(self, context: str) -> str:
        """检测不确定性。

        Returns:
            "confident" 或 "uncertain: <reason>"
        """
        # Phase 2 占位
        return "confident"

    def ask(self, question: str) -> str:
        """向用户提问。"""
        # Phase 4 实现
        return ""
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_self_asker.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add core/self_asker.py tests/test_self_asker.py
git commit -m "feat(cognitive): add SelfAsker placeholder"
```

---

### Task 7: 端到端集成测试（CLASSIFY → PLANNING → EXECUTING → REFLECTING → DONE）

**Files:**
- Modify: `tests/test_cognitive_graph.py`

- [ ] **Step 1: 添加端到端测试**

```python
# tests/test_cognitive_graph.py 追加
def test_full_flow_simple_input():
    """simple 输入完整流程：classify → done。"""
    mock_planner = MagicMock()
    mock_executor = MagicMock()
    mock_reflector = MagicMock()
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    result = g.invoke(_initial_state("hi"))
    assert result["verdict"] == "simple"
    assert "(无任务执行)" in result["final_answer"]
    mock_planner.invoke.assert_not_called()


def test_full_flow_complex_single_task():
    """complex 输入 + 单任务完整流程。"""
    mock_planner = MagicMock()
    mock_planner.invoke.return_value = [
        {"id": 0, "desc": "task1", "status": "pending", "retries": 0, "feedback": None}
    ]
    mock_executor = MagicMock()
    mock_executor.invoke.return_value = {
        "id": 0, "desc": "task1", "status": "done", "result": "ok", "retries": 0, "feedback": None
    }
    mock_reflector = MagicMock()
    mock_reflector.invoke.return_value = "success"
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    result = g.invoke(_initial_state("write a complex program"))
    assert "ok" in result["final_answer"]
    mock_planner.invoke.assert_called_once()
    mock_executor.invoke.assert_called_once()
    mock_reflector.invoke.assert_called_once()
```

- [ ] **Step 2: 跑测试确认通过**

Run: `python -m pytest tests/test_cognitive_graph.py -v`
Expected: PASS（8 个测试全过）

- [ ] **Step 3: 提交**

```bash
git add tests/test_cognitive_graph.py
git commit -m "test(cognitive): add end-to-end integration tests for full flow"
```

---

### Task 8: 集成到 LangChainAgent

**Files:**
- Modify: `core/agent.py`
- Modify: `tests/test_agent.py`

- [ ] **Step 1: 更新 test_agent.py 验证 cognitive 集成**

```python
# tests/test_agent.py 追加
def test_agent_cognitive_enabled_uses_graph():
    """cognitive 启用时应使用 cognitive_graph。"""
    mock_llm = MagicMock()
    agent = LangChainAgent(
        config={
            "llm": {"base_url": "http://t", "api_key": "sk", "model": "m"},
            "cognitive": {"enabled": True},
        },
        llm=mock_llm,
    )
    assert agent.cognitive_enabled is True
    assert agent._cognitive_graph is None  # 延迟构造
    # 访问 property 应触发构造
    g = agent.cognitive_graph
    assert g is not None


def test_agent_cognitive_chat_complex():
    """complex 输入应走 cognitive graph。"""
    mock_llm = MagicMock()
    with patch("core.cognitive_graph.build_cognitive_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "final_answer": "task completed",
            "verdict": "complex",
        }
        mock_build.return_value = mock_graph
        agent = LangChainAgent(
            config={
                "llm": {"base_url": "http://t", "api_key": "sk", "model": "m"},
                "cognitive": {"enabled": True},
            },
            llm=mock_llm,
        )
        chunks = list(agent.chat("write a complex program"))
        # 应该有内容
        assert any("task completed" in c for c in chunks)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_agent.py::test_agent_cognitive_enabled_uses_graph -v`
Expected: FAIL with "no attribute 'cognitive_graph'"

- [ ] **Step 3: 修改 core/agent.py 接入 cognitive_graph**

```python
# core/agent.py 替换 chat 方法和添加 cognitive_graph property

class LangChainAgent:
    def __init__(self, config: Dict[str, Any], llm: Optional[ChatOpenAI] = None):
        self.config = config
        self.llm = llm or create_llm(config)
        self.tools = list(ALL_TOOLS)
        self.memory = ConversationMemory(max_history=config.get("memory", {}).get("max_history", 50))
        self.cognitive_enabled = config.get("cognitive", {}).get("enabled", False)
        self._react_agent = None
        self._cognitive_graph = None

    @property
    def react_agent(self):
        if self._react_agent is None:
            self._react_agent = create_react_agent_langgraph(self.llm, self.tools)
        return self._react_agent

    @property
    def cognitive_graph(self):
        """延迟构造 cognitive graph。"""
        if self._cognitive_graph is None and self.cognitive_enabled:
            from core.cognitive_graph import build_cognitive_graph, _initial_state
            from core.planner import Planner
            from core.executor import Executor
            from core.reflector import Reflector
            from core.self_asker import SelfAsker

            cog_config = self.config.get("cognitive", {})
            planner = Planner(self.llm, tot_candidates=cog_config.get("tot_candidates", 3))
            executor = Executor(react_agent=self.react_agent, llm=self.llm, tools=self.tools)
            reflector = Reflector(self.llm)
            self_asker = SelfAsker(self.llm, self.tools)
            self._cognitive_graph = build_cognitive_graph(
                planner=planner,
                executor=executor,
                reflector=reflector,
            )
            self._cognitive_initial_state = _initial_state
        return self._cognitive_graph

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """主入口 - cognitive 启用走 LangGraph，否则走 ReAct。"""
        if self.cognitive_enabled:
            try:
                initial_state = self._cognitive_initial_state(
                    user_input,
                    max_task_retries=self.config.get("cognitive", {}).get("max_task_retries", 2),
                    max_replans=self.config.get("cognitive", {}).get("max_replans", 3),
                )
                result = self.cognitive_graph.invoke(initial_state)
                if result.get("verdict") == "simple":
                    # simple fallback 到 ReAct
                    yield from self._run_react(user_input)
                else:
                    yield result.get("final_answer", "")
                return
            except Exception as e:
                print_error(f"认知框架异常，回退到 ReAct: {e}")

        yield from self._run_react(user_input)

    # _run_react 方法保持不变
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_agent.py -v`
Expected: PASS（7 个测试全过）

- [ ] **Step 5: 跑全部测试确认无回归**

Run: `python -m pytest tests/ -v`
Expected: PASS（Phase 1 + Phase 2 全部 ~50 测试通过）

- [ ] **Step 6: 提交**

```bash
git add core/agent.py tests/test_agent.py
git commit -m "feat(agent): integrate cognitive graph with lazy initialization and fallback"
```

---

### Task 9: /cognitive 命令 + main.py 更新

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_cli.py`

- [ ] **Step 1: 添加 /cognitive 命令测试**

```python
# tests/test_main_cli.py 追加
def test_handle_cognitive_no_args():
    """/cognitive 无参数应返回当前状态。"""
    mock_agent = MagicMock()
    mock_agent.cognitive_enabled = True
    result = handle_command("/cognitive", agent=mock_agent)
    assert "启用" in result or "enabled" in result.lower() or "on" in result.lower()


def test_handle_cognitive_on():
    """/cognitive on 应启用认知框架。"""
    mock_agent = MagicMock()
    mock_agent.cognitive_enabled = False
    result = handle_command("/cognitive on", agent=mock_agent)
    mock_agent.__setattr__  # 验证调用
    assert "启用" in result or "enabled" in result.lower()
```

- [ ] **Step 2: 实现 /cognitive 命令**

在 `main.py` 的 `handle_command` 中添加：

```python
    if cmd == "/cognitive" and agent:
        return f"认知框架：{'启用' if agent.cognitive_enabled else '关闭'}"
    if cmd == "/cognitive on" and agent:
        agent.cognitive_enabled = True
        return "认知框架已启用"
    if cmd == "/cognitive off" and agent:
        agent.cognitive_enabled = False
        return "认知框架已关闭，回退到 ReAct"
```

- [ ] **Step 3: 跑测试确认通过**

Run: `python -m pytest tests/test_main_cli.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add main.py tests/test_main_cli.py
git commit -m "feat(main): add /cognitive on|off command"
```

---

## Phase 2 完成标准

- [ ] LangGraph StateGraph 5 节点全部实现（classify/planning/executing/reflecting/done）
- [ ] simple 输入直接走 done（预过滤生效）
- [ ] complex 输入完整流程：classify → planning → executing → reflecting → done
- [ ] Planner 能用 LLM 拆解任务
- [ ] Executor 能调用 ReAct agent 执行任务
- [ ] Reflector stub 能根据 status 判断 success/fail
- [ ] SelfAsker 占位不阻塞流程
- [ ] LangChainAgent 接入 cognitive_graph，启用时走状态机
- [ ] /cognitive on/off 命令工作
- [ ] 50+ 单元测试全部通过
