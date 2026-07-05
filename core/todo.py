"""待办清单数据类 - 跨会话持久化。"""
import json
import os
from typing import List, Dict
from datetime import datetime


class TodoList:
    """待办清单，存到 JSON 文件。"""

    def __init__(self, todo_file: str = None):
        self._todo_file = todo_file or os.path.join(os.path.expanduser("~"), ".mingcode-lc", "todos.json")
        self._todos: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if not os.path.exists(self._todo_file):
            return []
        try:
            with open(self._todo_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def _save(self):
        os.makedirs(os.path.dirname(self._todo_file), exist_ok=True)
        with open(self._todo_file, "w", encoding="utf-8") as f:
            json.dump(self._todos, f, ensure_ascii=False, indent=2)

    def add(self, content: str) -> str:
        todo = {"id": len(self._todos) + 1, "content": content, "done": False, "created_at": datetime.now().isoformat()}
        self._todos.append(todo)
        self._save()
        return f"成功添加待办 #{todo['id']}: {content}"

    def list_all(self) -> str:
        if not self._todos:
            return "(待办清单为空)"
        return "\n".join(f"[{'x' if t['done'] else ' '}] #{t['id']}: {t['content']}" for t in self._todos)

    def clear(self) -> str:
        count = len(self._todos)
        self._todos = []
        self._save()
        return f"已清空 {count} 个待办"

    def mark_done(self, todo_id: int) -> str:
        for t in self._todos:
            if t["id"] == todo_id:
                t["done"] = True
                self._save()
                return f"已完成 #{todo_id}: {t['content']}"
        return f"Error: 找不到待办 #{todo_id}"


_todo_list = TodoList()
