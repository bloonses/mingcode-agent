"""LangChainAgent 测试。"""
import json
from unittest.mock import patch, MagicMock, ANY
from core.agent import LangChainAgent


def _make_agent():
    """构造带 mock LLM 的 Agent。"""
    mock_llm = MagicMock()
    mock_config = {
        "llm": {"base_url": "http://test", "api_key": "sk-test", "model": "test-model"},
        "cognitive": {"enabled": False},
    }
    return LangChainAgent(config=mock_config, llm=mock_llm)


def test_agent_constructs():
    agent = _make_agent()
    assert agent is not None


def test_agent_chat_returns_generator():
    agent = _make_agent()
    result = agent.chat("hi")
    assert hasattr(result, "__iter__") or hasattr(result, "__next__")


def test_agent_has_tools():
    agent = _make_agent()
    assert len(agent.tools) > 0


def test_agent_cognitive_disabled_by_default():
    agent = _make_agent()
    assert agent.cognitive_enabled is False


def test_agent_simple_input_yields_response():
    """简单输入应 yield 响应字符串。"""
    mock_llm = MagicMock()
    last_msg = MagicMock()
    last_msg.content = "hello back"
    last_msg.tool_calls = None  # 避免触发 tool_call 分支
    mock_response = {"messages": [last_msg]}
    with patch("core.agent.create_react_agent_langgraph") as mock_create:
        mock_react = MagicMock()
        mock_react.stream.return_value = iter([mock_response])
        mock_create.return_value = mock_react
        agent = LangChainAgent(
            config={"llm": {"base_url": "http://test", "api_key": "sk-test", "model": "m"}, "cognitive": {"enabled": False}},
            llm=mock_llm,
        )
        chunks = list(agent.chat("hi"))
        assert len(chunks) >= 1


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


def test_agent_cognitive_chat_simple_fallback():
    """cognitive 启用时 simple 输入应回退到 ReAct。"""
    mock_llm = MagicMock()
    last_msg = MagicMock()
    last_msg.content = "hello response"
    last_msg.tool_calls = None  # 避免触发 tool_call 分支
    with patch("core.agent.create_react_agent_langgraph") as mock_create:
        mock_react = MagicMock()
        # ReAct 返回流式 chunks
        mock_react.stream.return_value = iter([{"messages": [last_msg]}])
        mock_create.return_value = mock_react
        agent = LangChainAgent(
            config={
                "llm": {"base_url": "http://t", "api_key": "sk", "model": "m"},
                "cognitive": {"enabled": True},
            },
            llm=mock_llm,
        )
        chunks = list(agent.chat("hi"))
        # 应该有内容（从 ReAct 流式回退）
        assert len(chunks) >= 1


def test_agent_cognitive_chat_complex():
    """cognitive 启用时 complex 输入应走 cognitive graph。"""
    mock_llm = MagicMock()
    with patch("core.cognitive_graph.build_cognitive_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "final_answer": "task completed",
            "verdict": "all_done",
            "task_list": [{"id": 0, "desc": "t", "status": "done", "result": "task completed"}],
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


def test_agent_cognitive_full_flow_with_tot():
    """完整流程：complex → ToT → execute → reflect → done。"""
    mock_llm = MagicMock()
    mock_planner_response = MagicMock()
    mock_planner_response.content = json.dumps([
        {"id": 0, "desc": "step 1", "status": "pending", "retries": 0, "feedback": None}
    ])
    mock_llm.invoke.return_value = mock_planner_response

    with patch("core.cognitive_graph.build_cognitive_graph") as mock_build:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "final_answer": "task completed",
            "verdict": "all_done",
            "task_list": [{"id": 0, "desc": "step 1", "status": "done", "result": "ok", "retries": 0, "feedback": None}],
        }
        mock_build.return_value = mock_graph
        agent = LangChainAgent(
            config={
                "llm": {"base_url": "http://t", "api_key": "sk", "model": "m"},
                "cognitive": {"enabled": True, "tot_candidates": 3},
            },
            llm=mock_llm,
        )
        chunks = list(agent.chat("complex task"))
        assert any("task completed" in c for c in chunks)


def test_agent_cognitive_fallback_on_exception():
    """cognitive 异常应 fallback 到 ReAct。"""
    mock_llm = MagicMock()
    with patch("core.cognitive_graph.build_cognitive_graph", side_effect=Exception("graph error")):
        with patch("core.agent.create_react_agent_langgraph") as mock_create:
            mock_react = MagicMock()
            mock_msg = MagicMock()
            mock_msg.content = "react fallback response"
            mock_msg.tool_calls = None
            mock_react.stream.return_value = iter([{"messages": [mock_msg]}])
            mock_create.return_value = mock_react
            agent = LangChainAgent(
                config={
                    "llm": {"base_url": "http://t", "api_key": "sk", "model": "m"},
                    "cognitive": {"enabled": True},
                },
                llm=mock_llm,
            )
            chunks = list(agent.chat("test"))
            # 应该有 fallback 响应（不抛异常）
            assert len(chunks) >= 1
