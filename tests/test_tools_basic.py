"""基础工具测试（shell/files/code）。"""
import os
import tempfile
from tools.shell import shell
from tools.files import file_read, file_write
from tools.code import python_exec


def test_shell_echo():
    result = shell.invoke({"command": "echo hello"})
    assert "hello" in result


def test_shell_returns_string():
    result = shell.invoke({"command": "echo test"})
    assert isinstance(result, str)


def test_file_write_and_read():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        write_result = file_write.invoke({"path": path, "content": "hello world"})
        assert "成功" in write_result or "success" in write_result.lower()
        read_result = file_read.invoke({"path": path})
        assert "hello world" in read_result
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_file_read_nonexistent():
    result = file_read.invoke({"path": "nonexistent_file_12345.txt"})
    assert "error" in result.lower() or "不存在" in result or "not found" in result.lower()


def test_python_exec_simple():
    result = python_exec.invoke({"code": "print(1+1)"})
    assert "2" in result


def test_python_exec_error():
    result = python_exec.invoke({"code": "raise ValueError('test')"})
    assert "ValueError" in result or "test" in result
