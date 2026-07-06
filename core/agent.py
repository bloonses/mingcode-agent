import json
from typing import Generator, Dict, Any, Optional, List

from core.llm import LLMClient
from core.memory import ConversationMemory
from core.long_term_memory import LongTermMemory
from tools.base import ToolRegistry
from tools.shell import ShellTool
from tools.files import FileReadTool, FileWriteTool, FileEditTool
from tools.code import PythonExecTool
from tools.search import WebSearchTool, WebFetchTool
from tools.subagent import SubAgentTool
from tools.ask_user import AskUserTool
from tools.plan_tot import PlanToTTool
from tools.todo import TodoTool
from tools.time_tool import TimeTool
from tools.math_tool import MathTool
from tools.http_tool import HttpTool
from tools.git_tool import GitTool
from tools.computer_use import ComputerUseTool
from tools.office import WordTool, PdfTool, ExcelTool, PptTool
from tools.kb_tool import KnowledgeSearchTool, KnowledgeReadTool, KnowledgeStoreTool
from core.knowledge_base import KnowledgeBase
from core.todo import TodoList
from ui.console import (
    print_thinking_spinner,
    print_tool_call,
    print_tool_result,
    print_error,
    print_assistant_message
)
from config.config import load_config


class NeonAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = LLMClient(config)
        # Token 消耗跟踪器：LLMClient 每次调用后自动记录 usage
        from core.token_tracker import TokenTracker
        self.token_tracker = TokenTracker()
        self.llm.token_tracker = self.token_tracker
        mem_config = config.get('memory', {})
        # 自动压缩阈值基于 LLM max_tokens * 2/3（若 memory 未显式配置 max_context_tokens）
        llm_max_tokens = config.get('llm', {}).get('max_tokens', 4096)
        max_ctx = mem_config.get('max_context_tokens') or llm_max_tokens
        self.memory = ConversationMemory(
            max_history=mem_config.get('max_history', 50),
            max_context_tokens=max_ctx,
            keep_recent_turns=mem_config.get('keep_recent_turns', 6),
        )
        # 注入 LLM 客户端用于上下文压缩（超阈值时生成摘要）
        self.memory.set_llm_client(self.llm)
        # 初始化知识库（RAG）：网络搜索结果自动归纳存入 Obsidian vault
        kb_config = config.get('knowledge_base', {})
        kb_vault = kb_config.get('vault_path')
        self.knowledge_base = KnowledgeBase(
            vault_path=kb_vault if kb_vault else None,
            llm_client=self.llm,
            auto_store=kb_config.get('auto_store', True),
            max_note_length=kb_config.get('max_note_length', 4000),
            enabled=kb_config.get('enabled', True),
        )
        self.long_term_memory = LongTermMemory()
        self.todo_list = TodoList()
        self.todo_list.load()
        self.registry = ToolRegistry()
        self._register_tools()
        self.memory.build_system_prompt(self.registry.get_all_schemas())
        self._cognitive_controller = None
        self._cognitive_enabled = config.get("cognitive", {}).get("enabled", True)

    @property
    def cognitive_controller(self):
        """延迟构造 CognitiveController。"""
        if self._cognitive_controller is None and self._cognitive_enabled:
            from core.cognitive import CognitiveController
            from core.planner import Planner
            from core.executor import Executor
            from core.reflector import Reflector
            from core.self_asker import SelfAsker

            cog_config = self.config.get("cognitive", {})
            self_asker = SelfAsker(self.llm, self.registry)
            executor = Executor(
                self.llm, self.memory, self.registry,
                self_asker=self_asker,
                enable_uncertainty_check=cog_config.get("self_ask", True),
            )
            self._cognitive_controller = CognitiveController(
                llm_client=self.llm,
                memory=self.memory,
                tool_registry=self.registry,
                planner=Planner(self.llm, tot_candidates=cog_config.get("tot_candidates", 3)),
                executor=executor,
                reflector=Reflector(self.llm),
                self_asker=self_asker,
                max_replans=cog_config.get("max_replans", 3),
                max_task_retries=cog_config.get("max_task_retries", 2),
            )
        return self._cognitive_controller

    def _register_tools(self):
        self.registry.register(ShellTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(FileEditTool())
        self.registry.register(PythonExecTool())
        web_search = WebSearchTool()
        web_fetch = WebFetchTool()
        # 注入知识库引用：搜索/抓取成功后自动归纳入库
        web_search.knowledge_base = self.knowledge_base
        web_fetch.knowledge_base = self.knowledge_base
        self.registry.register(web_search)
        self.registry.register(web_fetch)
        # 主 agent 的 subagent 工具，depth=2（可再递归 2 层）
        self.registry.register(SubAgentTool(self.llm, self.long_term_memory, depth=2,
                                            knowledge_base=self.knowledge_base))
        # 行动前向用户提问以明确意图
        self.registry.register(AskUserTool())
        # 思维树规划：思考 → 评估 → 筛选循环后再行动
        self.registry.register(PlanToTTool(llm_client=self.llm))
        # 待办清单：跨会话持久化，AI 与 /todo 命令共享同一实例
        self.registry.register(TodoTool(self.todo_list))
        # 时间日期：获取当前时间/时区/格式化/时间差
        self.registry.register(TimeTool())
        # 精确数学：避免浮点误差，使用 decimal
        self.registry.register(MathTool())
        # HTTP 请求调试：GET/POST/PUT/DELETE
        self.registry.register(HttpTool())
        # Git 版本控制：status/diff/log/add/commit/branch（不含 push/force）
        self.registry.register(GitTool())
        # 桌面控制（模仿 Codex computer use）：截屏 + 鼠标键盘 + vision 分析
        self.registry.register(ComputerUseTool(llm_client=self.llm))
        # Office 文档读写：Word/PDF/Excel/PPT
        self.registry.register(WordTool())
        self.registry.register(PdfTool())
        self.registry.register(ExcelTool())
        self.registry.register(PptTool())
        # 知识库（RAG）：检索/读取/写入归纳后的网络搜索知识
        self.registry.register(KnowledgeSearchTool(self.knowledge_base))
        self.registry.register(KnowledgeReadTool(self.knowledge_base))
        self.registry.register(KnowledgeStoreTool(self.knowledge_base))

    def _build_system_prompt_with_memory(self, user_input: str) -> str:
        base_prompt = self.memory.system_prompt or ""
        memory_section = self.long_term_memory.format_for_prompt(user_input)
        return base_prompt + memory_section

    def chat(self, user_input: str) -> Generator[str, None, None]:
        # Cognitive 分支：若启用则优先走 CognitiveController
        # simple 任务返回 "[React fallback] " 前缀，落到下面流式 ReAct
        # complex 任务返回最终结果，直接 yield
        # 任何异常 fallback 走现有 ReAct
        if self._cognitive_enabled:
            try:
                result = self.cognitive_controller.chat(user_input)
                if not result.startswith("[React fallback] "):
                    yield result
                    return
            except Exception:
                pass  # 兜底：异常时 fallback 走现有 ReAct

        self.memory.add_message("user", user_input)
        
        original_system_prompt = self.memory.system_prompt
        self.memory.system_prompt = self._build_system_prompt_with_memory(user_input)
        
        max_iterations = 25
        last_error: Optional[str] = None
        last_error_tool: Optional[str] = None

        try:
            for iteration in range(max_iterations):
                try:
                    with print_thinking_spinner():
                        stream_response = self.llm.chat(
                            messages=self.memory.get_messages(),
                            tools=self.registry.get_all_schemas(),
                            stream=True
                        )

                    full_response = ""
                    for chunk in stream_response:
                        full_response += chunk
                        yield chunk

                    final_message = stream_response.final_message
                    tool_calls = self._parse_tool_calls(final_message)

                    if not tool_calls:
                        self.memory.add_message("assistant", final_message.get("content") or "")
                        break

                    assistant_kwargs = {}
                    if tool_calls:
                        assistant_kwargs["tool_calls"] = [
                            {
                                "id": tc["id"],
                                "type": tc["type"],
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": json.dumps(tc["function"]["arguments"], ensure_ascii=False)
                                    if isinstance(tc["function"]["arguments"], dict)
                                    else tc["function"]["arguments"]
                                }
                            }
                            for tc in tool_calls
                        ]
                    self.memory.add_message("assistant", final_message.get("content") or "", **assistant_kwargs)

                    # 解析参数 + 打印 tool_call（顺序执行，快）
                    parsed_calls: List[Dict[str, Any]] = []
                    for tool_call in tool_calls:
                        call_id = tool_call["id"]
                        func = tool_call["function"]
                        tool_name = func["name"]
                        arguments = func["arguments"]

                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError as e:
                                error_msg = f"工具参数解析失败: {str(e)}"
                                print_error(error_msg)
                                self.long_term_memory.auto_learn_from_error(
                                    f"JSON解析错误 for {tool_name}",
                                    "确保arguments是合法JSON，不要有多余注释或尾逗号"
                                )
                                arguments = {"_raw": arguments}

                        print_tool_call(tool_name, arguments)
                        parsed_calls.append({
                            "call_id": call_id,
                            "tool_name": tool_name,
                            "arguments": arguments,
                        })

                    # 串行执行并处理（思考一步执行一步：每个工具执行完立即输出结果）
                    def _exec_one(pc):
                        cid = pc["call_id"]
                        tn = pc["tool_name"]
                        ag = pc["arguments"]
                        try:
                            res = self.registry.execute_tool(tn, **ag)
                            return cid, tn, ag, res, None
                        except Exception as e:
                            return cid, tn, ag, None, str(e)

                    for pc in parsed_calls:
                        call_id, tool_name, arguments, result, error = _exec_one(pc)
                        if error is not None:
                            result = f"工具执行错误: {error}"
                            last_error = error
                            last_error_tool = tool_name
                            err_str = error
                            if "chcp" in err_str or "编码" in err_str or "乱码" in err_str or "gbk" in err_str.lower() or "codec" in err_str.lower():
                                self.long_term_memory.auto_learn_from_error(
                                    "Windows cmd编码问题/中文乱码",
                                    "执行命令前先运行chcp 65001切换到UTF-8编码，或者只输出ASCII字符"
                                )
                            elif "Permission denied" in err_str or "权限" in err_str:
                                self.long_term_memory.auto_learn_from_error(
                                    "权限错误",
                                    "系统目录(如Program Files)写入需要管理员权限，优先写入用户目录或%APPDATA%"
                                )
                            elif "not found" in err_str.lower() or "无法识别" in err_str or "不是内部" in err_str:
                                pass
                        else:
                            if last_error_tool == tool_name and last_error:
                                self.long_term_memory.auto_learn_success(
                                    f"解决 {last_error[:50]}",
                                    f"使用 {tool_name} 成功，参数: {str(arguments)[:100]}"
                                )
                                last_error = None
                                last_error_tool = None

                        print_tool_result(result)
                        self.memory.add_message("tool", result, tool_call_id=call_id)

                except Exception as e:
                    err_str = str(e)
                    print_error(f"发生错误: {err_str}")
                    if "Connection refused" in err_str or "无法连接" in err_str or "ConnectionError" in err_str:
                        self.long_term_memory.auto_learn_from_error(
                            "LLM连接失败",
                            "检查LLM服务是否启动，base_url是否正确；默认配置指向localhost:11434(Ollama)，需要运行/settings配置云服务商或启动Ollama"
                        )
                    break
            else:
                print_error("达到最大迭代次数，已终止")
        finally:
            self.memory.system_prompt = original_system_prompt

    def remember(self, content: str, memory_type: str = "preference") -> str:
        return self.long_term_memory.add(content, memory_type=memory_type)

    def _parse_tool_calls(self, response: Dict[str, Any]) -> Optional[list]:
        return response.get("tool_calls")

    def clear_memory(self):
        self.memory.clear()
        self.memory.build_system_prompt(self.registry.get_all_schemas())
        # 重置 token 跟踪器（新会话从零开始计数）
        self.token_tracker.reset()
