"""TodoList 核心类单元测试。"""
import json

from core.todo import TodoList


def test_add_returns_id_and_defaults_pending(tmp_memory_file):
    todo = TodoList()
    todo_id = todo.add("写测试")
    assert todo_id  # 非空字符串
    item = todo.get(todo_id)
    assert item["content"] == "写测试"
    assert item["status"] == "pending"
    assert "created_at" in item


def test_list_all_and_filter_by_status(tmp_memory_file):
    todo = TodoList()
    id1 = todo.add("task A")
    id2 = todo.add("task B")
    todo.update_status(id2, "completed")

    all_items = todo.list()
    assert len(all_items) == 2

    pending = todo.list(status="pending")
    assert len(pending) == 1
    assert pending[0]["id"] == id1

    completed = todo.list(status="completed")
    assert len(completed) == 1
    assert completed[0]["id"] == id2


def test_update_status_transitions(tmp_memory_file):
    todo = TodoList()
    tid = todo.add("做某事")
    assert todo.update_status(tid, "in_progress") is True
    assert todo.get(tid)["status"] == "in_progress"
    assert todo.update_status(tid, "completed") is True
    assert todo.get(tid)["status"] == "completed"
    # updated_at 被刷新
    assert todo.get(tid)["updated_at"] >= todo.get(tid)["created_at"]


def test_update_status_rejects_invalid_status(tmp_memory_file):
    todo = TodoList()
    tid = todo.add("x")
    assert todo.update_status(tid, "invalid") is False
    assert todo.get(tid)["status"] == "pending"


def test_update_status_unknown_id_returns_false(tmp_memory_file):
    todo = TodoList()
    assert todo.update_status("nonexistent", "completed") is False


def test_delete_removes_item(tmp_memory_file):
    todo = TodoList()
    tid = todo.add("to delete")
    assert todo.delete(tid) is True
    assert todo.get(tid) is None
    assert todo.delete(tid) is False  # 再删返回 False


def test_clear_completed_only_removes_completed(tmp_memory_file):
    todo = TodoList()
    id1 = todo.add("pending task")
    id2 = todo.add("done task")
    todo.update_status(id2, "completed")
    removed = todo.clear_completed()
    assert removed == 1
    assert todo.get(id1) is not None
    assert todo.get(id2) is None


def test_persistence_save_and_load(tmp_memory_file):
    todo = TodoList()
    tid = todo.add("persistent task")
    todo.update_status(tid, "in_progress")
    todo.save()

    # 新实例加载
    todo2 = TodoList()
    todo2.load()
    item = todo2.get(tid)
    assert item is not None
    assert item["content"] == "persistent task"
    assert item["status"] == "in_progress"


def test_load_handles_missing_file(tmp_memory_file):
    # 文件不存在时也不报错
    todo = TodoList()
    todo.load()
    assert todo.list() == []


def test_get_unknown_id_returns_none(tmp_memory_file):
    todo = TodoList()
    assert todo.get("nope") is None
