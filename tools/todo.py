"""TodoTool - AI 通过工具调用管理待办清单。

action 路由：
- add: 创建待办（需 content）
- list: 列出待办（可选 status 过滤）
- update: 修改状态（需 todo_id + status）
- delete: 删除（需 todo_id）
- clear: 清除已完成
"""
from typing import Optional

from .base import BaseTool


_STATUS_ICON = {
    "pending": "[ ]",
    "in_progress": "[~]",
    "completed": "[x]",
}


class TodoTool(BaseTool):
    name = "todo"
    description = (
        "管理待办清单（跨会话持久化）。支持："
        "add（新增）/ list（列出，可选 status 过滤）/ "
        "update（改状态 pending|in_progress|completed）/ delete（删除）/ clear（清除已完成）。"
        "执行非平凡任务时主动维护清单：开始任务前 add+update 到 in_progress，"
        "完成后 update 到 completed。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "update", "delete", "clear"],
                "description": "要执行的操作"
            },
            "content": {
                "type": "string",
                "description": "action=add 时必填，待办内容"
            },
            "todo_id": {
                "type": "string",
                "description": "action=update/delete 时必填，目标待办 id"
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "action=update 时为状态值；action=list 时可选过滤条件"
            }
        },
        "required": ["action"]
    }

    def __init__(self, todo_list):
        # 依赖注入 TodoList 实例，与 /todo 命令共享同一实例
        self._todo = todo_list

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()

        if action == "add":
            return self._add(kwargs)
        if action == "list":
            return self._list(kwargs)
        if action == "update":
            return self._update(kwargs)
        if action == "delete":
            return self._delete(kwargs)
        if action == "clear":
            return self._clear()
        return f"Error: unknown action '{action}'. Supported: add/list/update/delete/clear"

    def _add(self, kwargs) -> str:
        content = (kwargs.get("content") or "").strip()
        if not content:
            return "Error: content is required for add action"
        try:
            new_id = self._todo.add(content)
            self._todo.save()
            return f"Added todo {new_id}: {content}"
        except Exception as e:
            return f"Error: {e}"

    def _list(self, kwargs) -> str:
        status = (kwargs.get("status") or "").strip().lower() or None
        if status and status not in ("pending", "in_progress", "completed"):
            return f"Error: invalid status filter '{status}'"
        items = self._todo.list(status=status)
        if not items:
            return "No todos." if not status else f"No {status} todos."
        lines = []
        for it in items:
            icon = _STATUS_ICON.get(it["status"], "[?]")
            lines.append(f"{icon} {it['id']}  {it['content']}  ({it['status']})")
        return "\n".join(lines)

    def _update(self, kwargs) -> str:
        todo_id = (kwargs.get("todo_id") or "").strip()
        status = (kwargs.get("status") or "").strip().lower()
        if not todo_id:
            return "Error: todo_id is required for update action"
        if not status:
            return "Error: status is required for update action"
        if not self._todo.update_status(todo_id, status):
            return f"Error: update failed (todo_id={todo_id}, status={status}). Check id and status validity."
        self._todo.save()
        return f"Updated todo {todo_id} -> {status}"

    def _delete(self, kwargs) -> str:
        todo_id = (kwargs.get("todo_id") or "").strip()
        if not todo_id:
            return "Error: todo_id is required for delete action"
        if not self._todo.delete(todo_id):
            return f"Error: todo not found: {todo_id}"
        self._todo.save()
        return f"Deleted todo {todo_id}"

    def _clear(self) -> str:
        removed = self._todo.clear_completed()
        self._todo.save()
        return f"Cleared {removed} completed todo(s)."
