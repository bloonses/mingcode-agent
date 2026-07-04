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


class TestCognitiveClassifyPreFilter:
    """_classify 本地规则预过滤：短输入和问候词应零 LLM 调用直接 simple。"""

    def test_short_input_skips_llm(self):
        """短输入（<= 12 字符）应直接返回 simple，不调 LLM。"""
        controller = _make_controller()
        with patch.object(controller.llm, 'chat') as mock_chat:
            assert controller._classify("hi") == "simple"
            assert controller._classify("你好") == "simple"
            assert controller._classify("写贪吃蛇") == "simple"  # 4 字符
        mock_chat.assert_not_called()

    def test_greeting_keyword_skips_llm(self):
        """问候词（即使 > 12 字符）应直接返回 simple。"""
        controller = _make_controller()
        with patch.object(controller.llm, 'chat') as mock_chat:
            assert controller._classify("thank you very much") == "simple"
        mock_chat.assert_not_called()

    def test_long_input_calls_llm(self):
        """长输入（> 12 字符且非问候词）应调 LLM 分类。"""
        controller = _make_controller()
        with patch.object(controller.llm, 'chat', return_value={"content": "COMPLEX"}) as mock_chat:
            assert controller._classify("请帮我写一个贪吃蛇游戏") == "complex"
        mock_chat.assert_called_once()



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
        # 验证 retries 递增（L1 触发：失败后 retries 应至少为 1）
        assert controller.task_list[0]["retries"] >= 1
        assert controller.task_list[0]["feedback"] == "fail: test failure"

    def test_local_retry_exhausted_triggers_replan_l2(self):
        """局部重试耗尽（retries > max_task_retries）应升级为整体重规划（L2）。"""
        controller = _make_controller(max_task_retries=2, max_replans=3)
        fake_tasks = [{"id": 0, "desc": "t1", "status": "pending", "retries": 3, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute', return_value={"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 3, "feedback": None}):
                    with patch.object(controller.reflector, 'evaluate', return_value="fail: persistent failure"):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        # 验证 replan_count 递增（L2 触发：局部重试耗尽后应触发重规划）
        assert controller.replan_count >= 1

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
        new_tasks = [{"id": 0, "desc": "new task", "status": "pending", "retries": 0, "feedback": None}]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute') as mock_plan:
                # 第一次规划返回 fake_tasks，第二次重规划返回 new_tasks，之后兜底返回 new_tasks
                mock_plan.side_effect = [fake_tasks, new_tasks, new_tasks, new_tasks, new_tasks]
                # executor 第一次返回 failed（触发 L2），之后返回 done
                with patch.object(controller.executor, 'execute', side_effect=[
                    {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None},
                    {"id": 0, "desc": "new task", "status": "done", "result": "ok", "retries": 0, "feedback": None},
                ]):
                    # reflector 第一次返回 fail，第二次返回 success
                    with patch.object(controller.reflector, 'evaluate', side_effect=["fail: test failure", "success"]):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        # 验证第二次调用 Planner.execute 时传了 feedback
        assert mock_plan.call_count >= 2, "应触发重规划（至少 2 次 planner.execute 调用）"
        second_call = mock_plan.call_args_list[1]
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
        exec_results = [
            {"id": 0, "desc": "t1", "status": "failed", "result": "error", "retries": 0, "feedback": None},
            {"id": 0, "desc": "t1", "status": "done", "result": "ok", "retries": 1, "feedback": None},
            {"id": 1, "desc": "t2", "status": "done", "result": "ok", "retries": 0, "feedback": None},
        ]
        with patch.object(controller, '_classify', return_value="complex"):
            with patch.object(controller.planner, 'execute', return_value=fake_tasks):
                with patch.object(controller.executor, 'execute', side_effect=exec_results):
                    reflect_results = ["fail: error", "success", "success"]
                    with patch.object(controller.reflector, 'evaluate', side_effect=reflect_results):
                        with patch.object(controller, '_build_answer', return_value="done"):
                            controller.chat("task")
        from core.cognitive import State
        assert controller.state == State.DONE
        assert controller.current_task_idx == 2
