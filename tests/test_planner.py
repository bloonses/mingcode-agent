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
        # 验证 feedback 出现在 prompt 中（ToT 下第一次调用是 _generate_candidates，含 feedback）
        call_args = mock_chat.call_args_list[0]
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


class TestPlannerToT:
    """Phase 3: ToT 多候选 → 评估 → 筛选。"""

    def test_generate_candidates_returns_n(self):
        """_generate_candidates 应返回 tot_candidates 个候选。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=3)
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B\n=== Candidate 3 ===\nplan C"}
        with patch.object(planner.llm, 'chat', return_value=fake_response):
            candidates = planner._generate_candidates("input", None)
        assert len(candidates) == 3
        assert "plan A" in candidates[0]
        assert "plan B" in candidates[1]
        assert "plan C" in candidates[2]

    def test_generate_candidates_with_feedback(self):
        """_generate_candidates 应把 feedback 塞进 prompt。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B"}
        with patch.object(planner.llm, 'chat', return_value=fake_response) as mock_chat:
            planner._generate_candidates("input", ["上次失败：xxx"])
        # 验证 prompt 含 feedback
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "上次失败" in prompt_text

    def test_evaluate_scores_each_candidate(self):
        """_evaluate 应为每个候选返回 dict 含 score。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        candidates = ["plan A", "plan B", "plan C"]
        fake_eval_response = {"content": "Candidate 1: score=7\nCandidate 2: score=9\nCandidate 3: score=5"}
        with patch.object(planner.llm, 'chat', return_value=fake_eval_response):
            scored = planner._evaluate(candidates, "input")
        assert len(scored) == 3
        for item in scored:
            assert "plan" in item
            assert "score" in item
            assert isinstance(item["score"], (int, float))
        # 验证评分正确解析
        assert scored[0]["score"] == 7
        assert scored[1]["score"] == 9
        assert scored[2]["score"] == 5

    def test_select_best_picks_highest_score(self):
        """_select_best 应选评分最高的候选。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        scored = [
            {"plan": "A", "score": 7},
            {"plan": "B", "score": 9},
            {"plan": "C", "score": 5},
        ]
        best = planner._select_best(scored)
        assert best == "B"

    def test_evaluate_llm_failure_returns_default_scores(self):
        """_evaluate LLM 失败时应兜底返回默认评分（全部 score=0）。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        candidates = ["plan A", "plan B"]
        with patch.object(planner.llm, 'chat', side_effect=Exception("network error")):
            scored = planner._evaluate(candidates, "input")
        assert len(scored) == 2
        for item in scored:
            assert item["score"] == 0  # 兜底默认分

    def test_execute_uses_tot_pipeline(self):
        """execute 应调用 _generate_candidates → _evaluate → _select_best。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        with patch.object(planner, '_generate_candidates', return_value=["plan A", "plan B"]) as mock_gen:
            with patch.object(planner, '_evaluate', return_value=[
                {"plan": "plan A", "score": 7},
                {"plan": "plan B", "score": 9},
            ]) as mock_eval:
                with patch.object(planner, '_select_best', return_value="plan B") as mock_select:
                    with patch.object(planner, '_parse_to_tasks', return_value=[{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]) as mock_parse:
                        planner.execute("input")
        mock_gen.assert_called_once()
        mock_eval.assert_called_once()
        mock_select.assert_called_once()
        mock_parse.assert_called_once_with("plan B", "input")

    def test_fewer_candidates_than_requested(self):
        """LLM 生成少于 N 个候选时应正常处理（不报错）。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=3)
        # 只生成 2 个候选
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B"}
        with patch.object(planner.llm, 'chat', return_value=fake_response):
            candidates = planner._generate_candidates("input", None)
        assert len(candidates) == 2  # 实际生成的数量

    def test_empty_candidates_falls_back_to_single_task(self):
        """所有候选都为空时应兜底返回单任务。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        # 候选生成返回空
        with patch.object(planner, '_generate_candidates', return_value=[]):
            tasks = planner.execute("做点什么")
        assert len(tasks) == 1
        assert tasks[0]["desc"] == "做点什么"
