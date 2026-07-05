"""工具注册表测试。"""
from tools import ALL_TOOLS, get_tool_by_name


def test_all_tools_has_15_plus():
    assert len(ALL_TOOLS) >= 12


def test_all_tools_have_names():
    for t in ALL_TOOLS:
        assert hasattr(t, "name"), f"Tool missing name: {t}"
        assert isinstance(t.name, str)


def test_get_tool_by_name_returns_tool():
    shell = get_tool_by_name("shell")
    assert shell is not None
    assert shell.name == "shell"


def test_get_tool_by_name_nonexistent():
    result = get_tool_by_name("nonexistent_tool")
    assert result is None
