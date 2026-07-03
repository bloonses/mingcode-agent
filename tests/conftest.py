import pytest
from unittest.mock import MagicMock
from core.llm import LLMClient


@pytest.fixture
def mock_llm():
    """Mock LLMClient，chat 方法可预设返回值。

    用法：
        mock_llm.set_responses([
            {"role": "assistant", "content": "Final Answer: done", "tool_calls": None},
        ])
    """
    llm = MagicMock(spec=LLMClient)
    responses = []

    def chat(messages, tools=None, stream=False):
        if not responses:
            resp = {"role": "assistant", "content": "Final Answer: no response", "tool_calls": None}
        else:
            resp = responses.pop(0)
        if stream:
            from core.llm import StreamResponse

            def _gen():
                content = resp.get("content") or ""
                if content:
                    yield content
                return resp

            return StreamResponse(_gen())
        return resp

    llm.set_responses = lambda r: responses.extend(r)
    llm.chat.side_effect = chat
    return llm


@pytest.fixture
def tmp_memory_file(tmp_path, monkeypatch):
    """让 LongTermMemory 和 TodoList 写到临时目录，避免污染真实数据。"""
    from core import long_term_memory as ltm_module
    from core import todo as todo_module
    fake_dir = tmp_path / "mingcode_test"
    fake_dir.mkdir()
    monkeypatch.setattr(ltm_module, "get_user_data_dir", lambda: fake_dir)
    monkeypatch.setattr(todo_module, "get_user_data_dir", lambda: fake_dir)
    return fake_dir
