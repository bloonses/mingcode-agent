"""新增工具的单元测试（schema + 参数校验，不执行实际有副作用的操作）。"""
import os
import sys
from unittest.mock import patch, MagicMock

# 让 conftest 的 tmp_memory_file 不影响这里
import config.config as cfg


def _git_repo(tmp_path, monkeypatch):
    """创建一个临时 git 仓库用于测试。"""
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    return tmp_path


# ============== TimeTool ==============

def test_time_tool_schema():
    from tools.time_tool import TimeTool
    schema = TimeTool().to_schema()
    assert schema["function"]["name"] == "time"
    assert "action" in schema["function"]["parameters"]["properties"]


def test_time_now_returns_iso():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="now")
    assert "T" in result  # ISO 格式


def test_time_format():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="format", fmt="%Y-%m-%d")
    assert len(result) == 10
    assert result[4] == "-"


def test_time_diff():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="diff", start="2026-01-01T00:00:00", end="2026-01-02T00:00:00")
    assert "1d" in result
    assert "86400" in result


def test_time_timestamp():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="timestamp", ts=1700000000)
    assert "UTC" in result
    assert "Local" in result


def test_time_unknown_action():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="bogus")
    assert "Error" in result


def test_time_invalid_timezone():
    from tools.time_tool import TimeTool
    result = TimeTool().execute(action="now", timezone="Invalid/Zone")
    assert "Error" in result


# ============== MathTool ==============

def test_math_schema():
    from tools.math_tool import MathTool
    schema = MathTool().to_schema()
    assert schema["function"]["name"] == "math"


def test_math_calc_exact_decimal():
    """0.1 + 0.2 应该等于 0.3 而不是 0.30000000000000004"""
    from tools.math_tool import MathTool
    result = MathTool().execute(action="calc", expression="0.1 + 0.2")
    assert "0.3" in result
    assert "00000000000004" not in result


def test_math_calc_with_parens():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="calc", expression="(3 * 4) / 2")
    assert "6" in result


def test_math_calc_rejects_dangerous_chars():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="calc", expression="__import__('os')")
    assert "Error" in result or "disallowed" in result.lower()


def test_math_sqrt():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="sqrt", number=2, precision=20)
    assert "1.414" in result


def test_math_pow():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="pow", number=2, exponent=10)
    assert "1024" in result


def test_math_gcd():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="gcd", numbers=[12, 18, 24])
    assert "6" in result


def test_math_lcm():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="lcm", numbers=[4, 6, 8])
    assert "24" in result


def test_math_unknown_action():
    from tools.math_tool import MathTool
    result = MathTool().execute(action="bogus")
    assert "Error" in result


# ============== HttpTool ==============

def test_http_schema():
    from tools.http_tool import HttpTool
    schema = HttpTool().to_schema()
    assert schema["function"]["name"] == "http"
    assert "url" in schema["function"]["parameters"]["properties"]


def test_http_rejects_missing_url():
    from tools.http_tool import HttpTool
    result = HttpTool().execute(action="get")
    assert "Error" in result


def test_http_rejects_bad_protocol():
    from tools.http_tool import HttpTool
    result = HttpTool().execute(action="get", url="ftp://example.com")
    assert "Error" in result


def test_http_rejects_bad_method():
    from tools.http_tool import HttpTool
    result = HttpTool().execute(action="patch", url="http://example.com")
    assert "Error" in result


def test_http_get_success():
    """用 mock 测试 requests.request 调用。"""
    from tools.http_tool import HttpTool
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.reason = "OK"
    mock_resp.text = "hello world"
    mock_resp.headers = {"content-type": "text/plain"}
    with patch("tools.http_tool.requests.request", return_value=mock_resp):
        result = HttpTool().execute(action="get", url="http://example.com")
    assert "200" in result
    assert "hello world" in result


def test_http_post_with_json_body():
    from tools.http_tool import HttpTool
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.reason = "Created"
    mock_resp.text = '{"id":1}'
    mock_resp.headers = {"content-type": "application/json"}
    with patch("tools.http_tool.requests.request", return_value=mock_resp) as m:
        result = HttpTool().execute(action="post", url="http://api.example.com", body={"key": "val"})
    assert "201" in result
    # 验证 body 被序列化
    call_kwargs = m.call_args.kwargs
    assert "key" in call_kwargs["data"]


# ============== GitTool ==============

def test_git_schema():
    from tools.git_tool import GitTool
    schema = GitTool().to_schema()
    assert schema["function"]["name"] == "git"


def test_git_status_in_repo(tmp_path, monkeypatch):
    _git_repo(tmp_path, monkeypatch)
    f = tmp_path / "test.txt"
    f.write_text("hello")
    from tools.git_tool import GitTool
    # status 不需要确认
    result = GitTool().execute(action="status")
    assert "test.txt" in result


def test_git_log_in_repo(tmp_path, monkeypatch):
    _git_repo(tmp_path, monkeypatch)
    f = tmp_path / "a.txt"
    f.write_text("a")
    import subprocess
    subprocess.run(["git", "add", "a.txt"], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first commit"], check=True, capture_output=True)
    from tools.git_tool import GitTool
    result = GitTool().execute(action="log")
    assert "first commit" in result


def test_git_add_requires_confirmation(tmp_path, monkeypatch):
    _git_repo(tmp_path, monkeypatch)
    f = tmp_path / "x.txt"
    f.write_text("x")
    from tools.git_tool import GitTool
    tool = GitTool()
    # 拒绝确认
    with patch.object(tool, "_confirm", return_value=False):
        result = tool.execute(action="add", file="x.txt")
    assert "Cancelled" in result


def test_git_add_confirmed(tmp_path, monkeypatch):
    _git_repo(tmp_path, monkeypatch)
    f = tmp_path / "y.txt"
    f.write_text("y")
    from tools.git_tool import GitTool
    tool = GitTool()
    with patch.object(tool, "_confirm", return_value=True):
        result = tool.execute(action="add", file="y.txt")
    assert "Error" not in result


def test_git_diff(tmp_path, monkeypatch):
    _git_repo(tmp_path, monkeypatch)
    f = tmp_path / "d.txt"
    f.write_text("diff content")
    import subprocess
    subprocess.run(["git", "add", "d.txt"], check=True, capture_output=True)
    from tools.git_tool import GitTool
    result = GitTool().execute(action="diff", staged=True)
    # staged diff 应包含内容
    assert "diff content" in result or "no output" in result.lower() or "diff --git" in result


def test_git_unknown_action():
    from tools.git_tool import GitTool
    result = GitTool().execute(action="push")
    assert "Error" in result or "unsupported" in result.lower()


def test_git_commit_missing_message():
    from tools.git_tool import GitTool
    tool = GitTool()
    with patch.object(tool, "_confirm", return_value=True):
        result = tool.execute(action="commit")
    assert "Error" in result or "missing" in result.lower()


# ============== ComputerUseTool ==============

def test_computer_schema():
    from tools.computer_use import ComputerUseTool
    schema = ComputerUseTool().to_schema()
    assert schema["function"]["name"] == "computer"


def test_computer_unknown_action():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="bogus")
    assert "Error" in result


def test_computer_click_missing_coords():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="click")
    assert "Error" in result


def test_computer_key_disallowed():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="key", keys="ctrl+pause")
    assert "Error" in result or "disallowed" in result.lower()


def test_computer_key_safe():
    """测试按键校验逻辑。pyautogui 可能未安装，用 create=True 让 patch 自动创建属性。"""
    import tools.computer_use as cu_mod
    tool = cu_mod.ComputerUseTool()
    with patch.object(tool, "_confirm", return_value=True):
        with patch.object(cu_mod, "pyautogui_available", True):
            with patch.object(cu_mod, "pyautogui", MagicMock(), create=True):
                result = tool.execute(action="key", keys="enter")
    assert "Pressed" in result


def test_computer_type_missing_text():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="type")
    assert "Error" in result


def test_computer_open_app_missing_name():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="open_app")
    assert "Error" in result


def test_computer_focus_missing_title():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="focus")
    assert "Error" in result


def test_computer_drag_missing_coords():
    from tools.computer_use import ComputerUseTool
    result = ComputerUseTool().execute(action="drag")
    assert "Error" in result


# ============== 注册到 NeonAgent ==============

def test_all_new_tools_registered_in_main_agent():
    """主 agent 应注册全部 5 个新工具。"""
    agent = __import__("core.agent", fromlist=["NeonAgent"]).NeonAgent(cfg.DEFAULT_CONFIG)
    tools = agent.registry.list_tools()
    assert "time" in tools
    assert "math" in tools
    assert "http" in tools
    assert "git" in tools
    assert "computer" in tools


def test_execute_tool_with_name_kwarg_no_conflict():
    """回归测试：工具参数名 'name' 不能与 execute_tool 的第一位置参数冲突。

    Bug: execute_tool(self, name, **kwargs) 在 AI 调用 computer(action='open_app', name='微信')
    时会把位置参数 name='computer' 与关键字 name='微信' 视为重复赋值。
    修复: 第一参数重命名为 tool_name。
    """
    from tools.base import ToolRegistry, BaseTool

    class DummyTool(BaseTool):
        name = "dummy"
        description = "test"
        parameters = {"type": "object", "properties": {
            "action": {"type": "string"},
            "name": {"type": "string"},
        }, "required": ["action"]}
        def execute(self, **kwargs):
            return f"action={kwargs.get('action')}, name={kwargs.get('name')}"

    reg = ToolRegistry()
    reg.register(DummyTool())
    # 这个调用在 bug 版本会报 "got multiple values for argument 'name'"
    result = reg.execute_tool("dummy", action="open_app", name="微信")
    assert "action=open_app" in result
    assert "name=微信" in result
