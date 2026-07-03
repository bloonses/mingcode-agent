"""TodoTool 单元测试。"""
from tools.todo import TodoTool


def test_schema():
    from core.todo import TodoList
    tool = TodoTool(TodoList())
    schema = tool.to_schema()
    assert schema["function"]["name"] == "todo"
    props = schema["function"]["parameters"]["properties"]
    assert "action" in props
    assert "content" in props
    assert "todo_id" in props
    assert "status" in props
    assert schema["function"]["parameters"]["required"] == ["action"]


def test_add_action_returns_id(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    tool = TodoTool(todo)
    result = tool.execute(action="add", content="写测试")
    assert result.startswith("Added todo ")
    # 提取 id（格式：Added todo <id>: <content>）
    rest = result[len("Added todo "):]
    new_id = rest.split(":")[0].strip()
    assert todo.get(new_id) is not None


def test_add_action_empty_content_returns_error(tmp_memory_file):
    from core.todo import TodoList
    tool = TodoTool(TodoList())
    result = tool.execute(action="add", content="")
    assert "Error" in result or "错误" in result


def test_list_action_empty(tmp_memory_file):
    from core.todo import TodoList
    tool = TodoTool(TodoList())
    result = tool.execute(action="list")
    assert "no todos" in result.lower()


def test_list_action_with_items(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    tid = todo.add("任务A")
    tool = TodoTool(todo)
    result = tool.execute(action="list")
    assert "任务A" in result
    assert tid in result


def test_list_action_filter_by_status(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    id1 = todo.add("pending")
    id2 = todo.add("done")
    todo.update_status(id2, "completed")
    tool = TodoTool(todo)
    result = tool.execute(action="list", status="completed")
    assert "done" in result
    assert "pending" not in result  # pending 任务不出现


def test_update_action_changes_status(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    tid = todo.add("task")
    tool = TodoTool(todo)
    result = tool.execute(action="update", todo_id=tid, status="in_progress")
    assert "Updated" in result or "更新" in result
    assert todo.get(tid)["status"] == "in_progress"


def test_update_action_invalid_status(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    tid = todo.add("task")
    tool = TodoTool(todo)
    result = tool.execute(action="update", todo_id=tid, status="bogus")
    assert "Error" in result or "无效" in result or "invalid" in result.lower()


def test_update_action_missing_id(tmp_memory_file):
    from core.todo import TodoList
    tool = TodoTool(TodoList())
    result = tool.execute(action="update", status="completed")
    assert "Error" in result or "错误" in result or "missing" in result.lower()


def test_delete_action(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    tid = todo.add("to remove")
    tool = TodoTool(todo)
    result = tool.execute(action="delete", todo_id=tid)
    assert "Deleted" in result or "删除" in result
    assert todo.get(tid) is None


def test_clear_action(tmp_memory_file):
    from core.todo import TodoList
    todo = TodoList()
    todo.add("keep")
    tid = todo.add("done")
    todo.update_status(tid, "completed")
    tool = TodoTool(todo)
    result = tool.execute(action="clear")
    assert "1" in result


def test_unknown_action(tmp_memory_file):
    from core.todo import TodoList
    tool = TodoTool(TodoList())
    result = tool.execute(action="bogus")
    assert "Error" in result or "未知" in result or "unknown" in result.lower()


def test_registered_in_main_agent():
    """主 agent 应注册 todo 工具。"""
    import config.config as cfg
    from core.agent import NeonAgent
    agent = NeonAgent(cfg.DEFAULT_CONFIG)
    try:
        assert "todo" in agent.registry.list_tools()
    finally:
        agent._executor.shutdown(wait=False)
