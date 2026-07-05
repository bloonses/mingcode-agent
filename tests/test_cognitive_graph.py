# tests/test_cognitive_graph.py
"""CognitiveGraph (LangGraph StateGraph) 测试。"""
from unittest.mock import patch, MagicMock
from core.cognitive_graph import AgentState, build_cognitive_graph, classify_node, _initial_state


def test_agent_state_typed_dict_fields():
    """AgentState 应包含所有必需字段。"""
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
    state = _initial_state("hi")
    result = classify_node(state)
    assert result["verdict"] == "simple"


def test_classify_node_greeting():
    """问候词应判定 simple。"""
    state = _initial_state("你好世界")
    result = classify_node(state)
    assert result["verdict"] == "simple"


def test_build_graph_returns_compiled():
    """build_cognitive_graph 应返回编译后的图。"""
    mock_planner = MagicMock()
    mock_executor = MagicMock()
    mock_reflector = MagicMock()
    g = build_cognitive_graph(
        planner=mock_planner,
        executor=mock_executor,
        reflector=mock_reflector,
    )
    assert g is not None
    assert hasattr(g, "invoke")


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
    assert any("persistent error" in (fb or "") for fb in result["last_feedback"])


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
    state = _initial_state("complex task here", max_task_retries=2, max_replans=3)
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
        {"id": 0, "desc": "t1", "status": "failed", "result": "error2", "retries": 1, "feedback": None},
        {"id": 0, "desc": "new task", "status": "done", "result": "ok", "retries": 0, "feedback": None},
    ]
    mock_reflector = MagicMock()
    mock_reflector.invoke.side_effect = ["fail: test", "fail: test2", "success"]
    g = build_cognitive_graph(planner=mock_planner, executor=mock_executor, reflector=mock_reflector)
    state = _initial_state("complex task here", max_task_retries=1, max_replans=3)
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
    state = _initial_state("complex task here", max_task_retries=1, max_replans=1)
    result = g.invoke(state)
    assert "failed" in result["final_answer"]
    assert result["task_list"][0]["status"] == "failed"


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
    state = _initial_state("complex task here", max_task_retries=2, max_replans=3)
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
    state = _initial_state("complex task here", max_task_retries=2, max_replans=3)
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
