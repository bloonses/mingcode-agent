import json
from concurrent.futures import ThreadPoolExecutor
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
        self.memory = ConversationMemory(
            max_history=config['memory']['max_history']
        )
        self.long_term_memory = LongTermMemory()
        self.todo_list = TodoList()
        self.todo_list.load()
        self.registry = ToolRegistry()
        self._register_tools()
        self.memory.build_system_prompt(self.registry.get_all_schemas())
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _register_tools(self):
        self.registry.register(ShellTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(FileEditTool())
        self.registry.register(PythonExecTool())
        self.registry.register(WebSearchTool())
        self.registry.register(WebFetchTool())
        # 主 agent 的 subagent 工具，depth=2（可再递归 2 层）
        self.registry.register(SubAgentTool(self.llm, self.long_term_memory, depth=2))
        # 行动前向用户提问以明确意图
        self.registry.register(AskUserTool())
        # 思维树规划：思考 → 评估 → 筛选循环后再行动
        self.registry.register(PlanToTTool(self.llm))
        # 待办清单：跨会话持久化，AI 与 /todo 命令共享同一实例
        self.registry.register(TodoTool(self.todo_list))

    def _build_system_prompt_with_memory(self, user_input: str) -> str:
        base_prompt = self.memory.system_prompt or ""
        memory_section = self.long_term_memory.format_for_prompt(user_input)
        return base_prompt + memory_section

    def chat(self, user_input: str) -> Generator[str, None, None]:
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

                    # 并行执行工具
                    def _exec_one(pc):
                        cid = pc["call_id"]
                        tn = pc["tool_name"]
                        ag = pc["arguments"]
                        try:
                            res = self.registry.execute_tool(tn, **ag)
                            return cid, tn, ag, res, None
                        except Exception as e:
                            return cid, tn, ag, None, str(e)

                    futures = [self._executor.submit(_exec_one, pc) for pc in parsed_calls]
                    results = [f.result() for f in futures]

                    # 按原顺序处理结果
                    for call_id, tool_name, arguments, result, error in results:
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
