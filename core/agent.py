"""LangChainAgent - NeonAgent 的 LangChain 等价实现。"""
from typing import Generator, Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent as create_react_agent_langgraph
from langchain_core.messages import HumanMessage

from core.llm import create_llm
from core.memory import ConversationMemory
from tools import ALL_TOOLS
from ui.console import print_assistant_message, print_tool_call, print_tool_result, print_error
from ui.callbacks import RichStreamHandler


class LangChainAgent:
    """LangChain 版 Agent - 对外 Generator[str] 接口与 NeonAgent 一致。"""

    def __init__(self, config: Dict[str, Any], llm: Optional[ChatOpenAI] = None):
        self.config = config
        self.llm = llm or create_llm(config)
        self.tools = list(ALL_TOOLS)
        self.memory = ConversationMemory(max_history=config.get("memory", {}).get("max_history", 50))
        self.cognitive_enabled = config.get("cognitive", {}).get("enabled", False)
        self._react_agent = None
        self._cognitive_graph = None

    @property
    def react_agent(self):
        """延迟构造 ReAct agent（LangGraph 版）。"""
        if self._react_agent is None:
            self._react_agent = create_react_agent_langgraph(self.llm, self.tools)
        return self._react_agent

    @property
    def cognitive_graph(self):
        """延迟构造 cognitive graph。"""
        if self._cognitive_graph is None and self.cognitive_enabled:
            from core.cognitive_graph import build_cognitive_graph, _initial_state
            from core.planner import Planner
            from core.executor import Executor
            from core.reflector import Reflector
            from core.self_asker import SelfAsker

            cog_config = self.config.get("cognitive", {})
            planner = Planner(self.llm, tot_candidates=cog_config.get("tot_candidates", 3))
            executor = Executor(react_agent=self.react_agent, llm=self.llm, tools=self.tools)
            reflector = Reflector(self.llm)
            # self_asker 当前不传给 build_cognitive_graph，但保留构造以备 Phase 4
            _ = SelfAsker(self.llm, self.tools)
            self._cognitive_graph = build_cognitive_graph(
                planner=planner,
                executor=executor,
                reflector=reflector,
            )
            self._cognitive_initial_state = _initial_state
        return self._cognitive_graph

    def chat(self, user_input: str) -> Generator[str, None, None]:
        """主入口 - cognitive 启用走 LangGraph，否则走 ReAct。"""
        if self.cognitive_enabled:
            try:
                # 访问 cognitive_graph 触发延迟构造（同时设置 _cognitive_initial_state）
                graph = self.cognitive_graph
                initial_state = self._cognitive_initial_state(
                    user_input,
                    max_task_retries=self.config.get("cognitive", {}).get("max_task_retries", 2),
                    max_replans=self.config.get("cognitive", {}).get("max_replans", 3),
                )
                result = graph.invoke(initial_state)
                if result.get("verdict") == "simple":
                    # simple fallback 到 ReAct
                    yield from self._run_react(user_input)
                else:
                    yield result.get("final_answer", "")
                return
            except Exception as e:
                print_error(f"认知框架异常，回退到 ReAct: {e}")

        yield from self._run_react(user_input)

    def _run_react(self, user_input: str) -> Generator[str, None, None]:
        """运行 ReAct agent，流式 yield 响应。"""
        try:
            for event in self.react_agent.stream(
                {"messages": [HumanMessage(content=user_input)]},
                stream_mode="values",
            ):
                if "messages" in event and event["messages"]:
                    last_msg = event["messages"][-1]
                    content = getattr(last_msg, "content", "")
                    if content and isinstance(content, str):
                        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                print_tool_call(tc.get("name", ""), tc.get("args", {}))
                        elif content.strip():
                            yield content
        except Exception as e:
            yield f"Error: {e}"

    def clear_memory(self):
        """清空对话历史。"""
        self.memory.clear()

    def save_session(self, name: str):
        """保存会话。"""
        self.memory.save(name)

    def load_session(self, name: str):
        """加载会话。"""
        self.memory.load(name)
