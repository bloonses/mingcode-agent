"""LangChain StreamingCallback 桥接 Rich 测试。"""
from ui.callbacks import RichStreamHandler


def test_handler_collects_tokens():
    handler = RichStreamHandler()
    handler.on_llm_new_token("Hello")
    handler.on_llm_new_token(" ")
    handler.on_llm_new_token("World")
    assert handler.collected_text == "Hello World"


def test_handler_starts_and_ends():
    handler = RichStreamHandler()
    handler.on_llm_start(serialized={}, messages=[{"content": "hi"}])
    handler.on_llm_end(response={"generations": []})
    assert handler.collected_text == ""


def test_handler_handles_error():
    handler = RichStreamHandler()
    handler.on_llm_error(error=Exception("test"))
