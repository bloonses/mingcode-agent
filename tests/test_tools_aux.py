"""辅助工具测试（ask_user/time/math）。"""
from unittest.mock import patch
from tools.ask_user import ask_user
from tools.time_tool import time_now
from tools.math_tool import math_calc


def test_ask_user_returns_input():
    with patch("builtins.input", return_value="user answer"):
        result = ask_user.invoke({"question": "what is your name?"})
        assert "user answer" in result


def test_time_now_returns_iso():
    result = time_now.invoke({})
    assert "20" in result
    assert ":" in result


def test_math_calc_addition():
    result = math_calc.invoke({"expression": "0.1 + 0.2"})
    assert "0.3" in result


def test_math_calc_division():
    result = math_calc.invoke({"expression": "10 / 3"})
    assert "3.33" in result or "3.333" in result


def test_math_calc_error():
    result = math_calc.invoke({"expression": "1/0"})
    assert "error" in result.lower() or "Error" in result or "Division" in result or "division" in result
