"""ConversationMemory 测试。"""
import tempfile
import os
from core.memory import ConversationMemory


def test_memory_starts_empty():
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    msgs = m.get_messages()
    assert len(msgs) >= 1


def test_add_message():
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    msgs = m.get_messages()
    assert any(m.get("content") == "hello" and m.get("role") == "user" for m in msgs)


def test_max_history_truncation():
    m = ConversationMemory(max_history=3)
    m.build_system_prompt([])
    for i in range(10):
        m.add_message("user", f"msg {i}")
    user_msgs = [m for m in m.get_messages() if m.get("role") == "user"]
    assert len(user_msgs) <= 3


def test_save_and_load(tmp_path):
    save_file = str(tmp_path / "session.json")
    m = ConversationMemory(max_history=10, save_file=save_file)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    m.add_message("assistant", "hi back")
    m.save("test_session")

    m2 = ConversationMemory(max_history=10, save_file=save_file)
    m2.load("test_session")
    msgs = m2.get_messages()
    assert any(m.get("content") == "hello" for m in msgs)
    assert any(m.get("content") == "hi back" for m in msgs)


def test_clear():
    m = ConversationMemory(max_history=10)
    m.build_system_prompt([])
    m.add_message("user", "hello")
    m.clear()
    user_msgs = [m for m in m.get_messages() if m.get("role") == "user"]
    assert len(user_msgs) == 0
