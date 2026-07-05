"""待办清单工具。"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from core.todo import _todo_list


class TodoAddInput(BaseModel):
    content: str = Field(description="Todo content to add")


class TodoMarkDoneInput(BaseModel):
    todo_id: int = Field(description="Todo ID to mark as done")


@tool(args_schema=TodoAddInput)
def todo_add(content: str) -> str:
    """Add a todo item."""
    return _todo_list.add(content)


@tool
def todo_list() -> str:
    """List all todos."""
    return _todo_list.list_all()


@tool(args_schema=TodoMarkDoneInput)
def todo_mark_done(todo_id: int) -> str:
    """Mark a todo as done."""
    return _todo_list.mark_done(todo_id)


@tool
def todo_clear() -> str:
    """Clear all todos."""
    return _todo_list.clear()
