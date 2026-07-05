"""其他工具测试（http/git/todo）。"""
import os
import tempfile
from unittest.mock import patch, MagicMock
from tools.http_tool import http_request
from tools.git_tool import git_status
from tools.todo import todo_add, todo_list, todo_clear
from core.todo import _todo_list


def test_http_get():
    with patch("tools.http_tool.requests.request") as mock_req:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_req.return_value = mock_response
        result = http_request.invoke({"method": "GET", "url": "http://example.com"})
        assert "200" in result
        assert "ok" in result


def test_git_status_in_temp_repo():
    with tempfile.TemporaryDirectory() as tmp:
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, capture_output=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=tmp, capture_output=True)
        with open(os.path.join(tmp, "test.txt"), "w") as f:
            f.write("test")
        with patch("os.getcwd", return_value=tmp):
            result = git_status.invoke({})
            assert isinstance(result, str)


def test_todo_add_and_list():
    with tempfile.TemporaryDirectory() as tmp:
        todo_path = os.path.join(tmp, "todos.json")
        with patch.object(_todo_list, "_todo_file", todo_path):
            _todo_list._todos = []  # 重置状态，保证测试隔离
            add_result = todo_add.invoke({"content": "test task"})
            assert "成功" in add_result or "added" in add_result.lower()
            list_result = todo_list.invoke({})
            assert "test task" in list_result


def test_todo_clear():
    with tempfile.TemporaryDirectory() as tmp:
        todo_path = os.path.join(tmp, "todos.json")
        with patch.object(_todo_list, "_todo_file", todo_path):
            _todo_list._todos = []  # 重置状态，保证测试隔离
            todo_add.invoke({"content": "task1"})
            clear_result = todo_clear.invoke({})
            list_result = todo_list.invoke({})
            assert "task1" not in list_result
