import json
from typing import Generator, Dict, Any, Optional

from core.llm import LLMClient
from core.memory import ConversationMemory
from tools.base import ToolRegistry
from tools.shell import ShellTool
from tools.files import FileReadTool, FileWriteTool, FileEditTool
from tools.code import PythonExecTool
from tools.search import WebSearchTool, WebFetchTool
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
        self.registry = ToolRegistry()
        self._register_tools()
        self.memory.build_system_prompt(self.registry.get_all_schemas())

    def _register_tools(self):
        self.registry.register(ShellTool())
        self.registry.register(FileReadTool())
        self.registry.register(FileWriteTool())
        self.registry.register(FileEditTool())
        self.registry.register(PythonExecTool())
        self.registry.register(WebSearchTool())
        self.registry.register(WebFetchTool())

    def chat(self, user_input: str) -> Generator[str, None, None]:
        self.memory.add_message("user", user_input)
        max_iterations = 10

        for _ in range(max_iterations):
            try:
                with print_thinking_spinner():
                    stream_response = self.llm.chat(
                        messages=self.memory.get_messages(),
                        tools=self.registry.get_all_schemas(),
                        stream=True
                    )

                for chunk in stream_response:
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

                for tool_call in tool_calls:
                    call_id = tool_call["id"]
                    func = tool_call["function"]
                    tool_name = func["name"]
                    arguments = func["arguments"]

                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError as e:
                            print_error(f"工具参数解析失败: {str(e)}")
                            arguments = {"_raw": arguments}

                    print_tool_call(tool_name, arguments)

                    try:
                        result = self.registry.execute_tool(tool_name, **arguments)
                    except Exception as e:
                        result = f"工具执行错误: {str(e)}"

                    print_tool_result(result)
                    self.memory.add_message("tool", result, tool_call_id=call_id)

            except Exception as e:
                print_error(f"发生错误: {str(e)}")
                break
        else:
            print_error("达到最大迭代次数，已终止")

    def _parse_tool_calls(self, response: Dict[str, Any]) -> Optional[list]:
        return response.get("tool_calls")

    def clear_memory(self):
        self.memory.clear()
        self.memory.build_system_prompt(self.registry.get_all_schemas())
