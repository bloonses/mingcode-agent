"""TodoList - 跨会话持久化的待办清单。

状态机：pending → in_progress → completed（允许任意方向跳转）。
存储位置：user_data_dir / "todos.json"
"""
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Literal

from config.config import get_user_data_dir


TodoStatus = Literal["pending", "in_progress", "completed"]
VALID_STATUSES = {"pending", "in_progress", "completed"}


class TodoList:
    def __init__(self):
        self._items: List[Dict] = []
        self._file = get_user_data_dir() / "todos.json"

    def add(self, content: str) -> str:
        """添加待办，返回新 id。content 不能为空。"""
        content = (content or "").strip()
        if not content:
            raise ValueError("content is required")
        now = datetime.now().isoformat()
        item = {
            "id": uuid.uuid4().hex[:8],
            "content": content,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }
        self._items.append(item)
        return item["id"]

    def get(self, todo_id: str) -> Optional[Dict]:
        for it in self._items:
            if it["id"] == todo_id:
                return it
        return None

    def list(self, status: Optional[str] = None) -> List[Dict]:
        if status:
            return [it for it in self._items if it["status"] == status]
        return list(self._items)

    def update_status(self, todo_id: str, status: str) -> bool:
        if status not in VALID_STATUSES:
            return False
        item = self.get(todo_id)
        if item is None:
            return False
        item["status"] = status
        item["updated_at"] = datetime.now().isoformat()
        return True

    def delete(self, todo_id: str) -> bool:
        before = len(self._items)
        self._items = [it for it in self._items if it["id"] != todo_id]
        return len(self._items) < before

    def clear_completed(self) -> int:
        before = len(self._items)
        self._items = [it for it in self._items if it["status"] != "completed"]
        return before - len(self._items)

    def save(self) -> None:
        data = {
            "saved_at": datetime.now().isoformat(),
            "items": self._items,
        }
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        if not self._file.exists():
            self._items = []
            return
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._items = data.get("items", [])
        except (OSError, json.JSONDecodeError):
            self._items = []
