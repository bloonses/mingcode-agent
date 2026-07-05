"""LangChain StreamingCallback 桥接 Rich Live 区域。"""
from typing import Optional
from rich.live import Live
from rich.text import Text
from langchain_core.callbacks import BaseCallbackHandler


class RichStreamHandler(BaseCallbackHandler):
    """收集 LLM 流式 token，可桥接到 Rich Live 区域。"""

    def __init__(self, live: Optional[Live] = None):
        self.live = live
        self.collected_text = ""
        self._text = Text()

    def on_llm_start(self, serialized, messages, **kwargs):
        self.collected_text = ""
        self._text = Text()

    def on_llm_new_token(self, token, **kwargs):
        self.collected_text += token
        self._text.append(token)
        if self.live is not None:
            self.live.update(self._text)

    def on_llm_end(self, response, **kwargs):
        pass

    def on_llm_error(self, error, **kwargs):
        pass
