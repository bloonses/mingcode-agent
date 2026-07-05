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
    # ToT 升级后 invoke 会被多次调用（候选生成 + 评分），只验证被调用过
    mock_llm.invoke.assert_called()


def test_planner_empty_response_fallback():
    """空响应应返回单任务兜底。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = ""
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    tasks = planner.invoke("task")
    assert len(tasks) == 1
    assert tasks[0]["desc"]  # 不为空


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


def test_planner_tot_generates_multiple_candidates():
    """ToT 应生成多个候选。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps([
        {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    ])
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm, tot_candidates=3)
    # mock _generate_candidates
    with patch.object(planner, '_generate_candidates', return_value=[
        [{"id": 0, "desc": "candidate A", "status": "pending", "retries": 0, "feedback": None}],
        [{"id": 0, "desc": "candidate B", "status": "pending", "retries": 0, "feedback": None}],
        [{"id": 0, "desc": "candidate C", "status": "pending", "retries": 0, "feedback": None}],
    ]) as mock_gen:
        with patch.object(planner, '_evaluate_candidate', side_effect=[0.5, 0.9, 0.3]):
            tasks = planner.invoke("complex task")
            # 应选 score 最高的 candidate B
            assert len(tasks) == 1
            assert tasks[0]["desc"] == "candidate B"
            mock_gen.assert_called_once()


def test_planner_tot_evaluate_returns_score():
    """_evaluate_candidate 应返回 0-1 的 score。"""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "0.85"
    mock_llm.invoke.return_value = mock_response
    planner = Planner(mock_llm)
    candidate = [{"id": 0, "desc": "test", "status": "pending", "retries": 0, "feedback": None}]
    score = planner._evaluate_candidate("task", candidate)
    assert 0 <= score <= 1


def test_planner_tot_selects_best():
    """_select_best 应选 score 最高的。"""
    mock_llm = MagicMock()
    planner = Planner(mock_llm)
    candidates = [
        [{"id": 0, "desc": "A", "status": "pending", "retries": 0, "feedback": None}],
        [{"id": 0, "desc": "B", "status": "pending", "retries": 0, "feedback": None}],
    ]
    scores = [0.4, 0.8]
    best = planner._select_best(candidates, scores)
    assert best[0]["desc"] == "B"


def test_planner_tot_fallback_on_evaluation_error():
    """评分异常应兜底选第一个。"""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = Exception("API error")
    planner = Planner(mock_llm)
    candidate = [{"id": 0, "desc": "test", "status": "pending", "retries": 0, "feedback": None}]
    score = planner._evaluate_candidate("task", candidate)
    assert score == 0.5  # 兜底分数
