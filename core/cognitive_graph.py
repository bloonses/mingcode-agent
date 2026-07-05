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
    """分类节点 - 本地预过滤 + LLM 分类。

    复用 NeonAgent 优化经验：
    - 输入 <= 6 字符 → simple（hi/hello/你好/在吗 等）
    - 包含常见问候/闲聊词 → simple
    - 否则 → complex（Phase 2 简化版不调 LLM）
    """
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


def route_after_reflect(state: AgentState) -> str:
    """reflecting 后的路由函数。"""
    return state.get("verdict", "fail_l3")


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


def make_planning_node(planner):
    """构造 planning 节点函数。"""
    def planning_node(state: AgentState) -> AgentState:
        feedback = state.get("last_feedback", [])
        tasks = planner.invoke(state["user_input"], feedback=feedback)
        state["task_list"] = tasks
        state["current_task_idx"] = 0
        return state
    return planning_node


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
