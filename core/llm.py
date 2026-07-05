"""LLM 客户端工厂 - 用 ChatOpenAI 兼容多供应商。"""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI


def create_llm(config: Dict[str, Any]) -> ChatOpenAI:
    """根据 config 创建 ChatOpenAI 实例。"""
    llm_config = config.get("llm", config)
    base_url = llm_config["base_url"].rstrip("/")
    api_key = llm_config.get("api_key", "ollama")
    model = llm_config["model"]
    temperature = llm_config.get("temperature", 0.7)
    max_tokens = llm_config.get("max_tokens", 4096)

    raw_effort = llm_config.get("reasoning_effort")
    reasoning_effort = raw_effort if raw_effort in ("low", "medium", "high") else None

    kwargs = {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "streaming": True,
    }
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    return ChatOpenAI(**kwargs)


class LLMClientWrapper:
    """包装 ChatOpenAI 提供 NeonAgent 兼容的 chat 接口。"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List] = None,
             stream: bool = False) -> Dict[str, Any]:
        """同步调用 LLM，返回 dict 格式响应。"""
        kwargs = {}
        if tools:
            kwargs["tools"] = tools
        response = self.llm.invoke(messages, **kwargs)
        return {
            "content": getattr(response, "content", "") or "",
            "tool_calls": getattr(response, "tool_calls", None),
            "raw": response,
        }
