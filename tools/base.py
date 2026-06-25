from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str
    description: str
    parameters: dict

    @abstractmethod
    def execute(self, **kwargs) -> str:
        pass

    def safe_execute(self, **kwargs) -> str:
        try:
            return self.execute(**kwargs)
        except Exception as e:
            return f"Error: {str(e)}"

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_schemas(self) -> list[dict]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute_tool(self, name: str, **kwargs) -> str:
        tool = self.get(name)
        if tool is None:
            return f"Error: Tool '{name}' not found"
        return tool.safe_execute(**kwargs)
