"""Executor 测试（Phase 1: ReAct + 串行工具执行）。"""
import pytest
from unittest.mock import MagicMock, patch


def _make_executor(self_asker=None, enable_uncertainty_check=False, max_iterations=25):
    """构造 Executor。Phase 1 默认关闭不确定性检测。"""
    from core.executor import Executor
    return Executor(
        llm_client=MagicMock(),
        memory=MagicMock(),
        tool_registry=MagicMock(),
        max_iterations=max_iterations,
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

    def test_uncertainty_check_disabled(self):
        """enable_uncertainty_check=False 时不应调 self_asker。"""
        executor = _make_executor(enable_uncertainty_check=False)
        with patch.object(executor, '_parse_stream', return_value=("", [], "done")):
            with patch.object(executor.self_asker, 'check_uncertainty') as mock_check:
                task = {"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}
                executor.execute(task)
        mock_check.assert_not_called()


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
