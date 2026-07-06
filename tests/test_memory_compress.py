"""测试 ConversationMemory 的上下文压缩机制。

需求：取消每会话对话轮数硬限制（_trim_history），改为基于 token 阈值的上下文压缩——
当 token 估算超过 max_context_tokens 时，把早期对话用 LLM 摘要成一条 system 消息，
保留最近 keep_recent_turns 轮原始对话。
"""
from unittest.mock import MagicMock

from core.memory import ConversationMemory


def _make_long_messages(count: int, content_size: int = 200) -> list:
    """生成 count 条 user/assistant 交替的长消息。"""
    msgs = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"msg-{i}-" + "x" * content_size})
    return msgs


def test_no_trim_when_below_threshold(tmp_path, monkeypatch):
    """token 低于阈值时不应触发压缩，所有消息保留。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=10000, keep_recent_turns=4)
    for m in _make_long_messages(6):
        mem.add_message(m["role"], m["content"])
    # 6 条消息全部保留
    assert len(mem.messages) == 6
    # 不存在摘要消息
    assert not any(m.get("compressed_summary") for m in mem.messages)


def test_compress_triggers_when_exceeds_token_threshold(tmp_path, monkeypatch):
    """token 超过阈值时应触发压缩：生成一条摘要 system 消息，早期对话被替换。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)

    fake_llm = MagicMock()
    fake_llm.chat.return_value = {"role": "assistant", "content": "这是历史摘要", "tool_calls": None}

    mem = ConversationMemory(
        max_context_tokens=500,  # 很小，几条长消息就会超
        keep_recent_turns=2,    # 保留最近 2 轮 = 4 条消息
    )
    mem.set_llm_client(fake_llm)

    # 10 条消息 × 500 字符 = 5000 字符 ≈ 1250 tokens，远超 500
    for m in _make_long_messages(10, content_size=500):
        mem.add_message(m["role"], m["content"])

    # LLM 被调用过（用于生成摘要）
    assert fake_llm.chat.called
    # 应该有一条摘要消息（role=system，compressed_summary=True）
    summaries = [m for m in mem.messages if m.get("compressed_summary")]
    assert len(summaries) == 1
    assert "摘要" in summaries[0]["content"] or "历史" in summaries[0]["content"].lower()


def test_compress_preserves_recent_turns(tmp_path, monkeypatch):
    """压缩后最近 keep_recent_turns*2 条消息应原样保留。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)

    fake_llm = MagicMock()
    fake_llm.chat.return_value = {"role": "assistant", "content": "summary", "tool_calls": None}

    keep_turns = 3
    mem = ConversationMemory(max_context_tokens=300, keep_recent_turns=keep_turns)
    mem.set_llm_client(fake_llm)

    # 12 条 × 400 字符 ≈ 1200 tokens，远超 300
    msgs = _make_long_messages(12, content_size=400)
    for m in msgs:
        mem.add_message(m["role"], m["content"])

    # 末尾 keep_turns*2 条原始消息保留
    recent_expected = msgs[-(keep_turns * 2):]
    recent_actual = [m for m in mem.messages if not m.get("compressed_summary")][-len(recent_expected):]
    for expected, actual in zip(recent_expected, recent_actual):
        assert actual["role"] == expected["role"]
        assert actual["content"] == expected["content"]


def test_compress_falls_back_to_truncate_without_llm(tmp_path, monkeypatch):
    """没有注入 LLM 客户端时，超阈值应回退为截断标记，不抛异常，最近消息保留。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(
        max_context_tokens=300,
        keep_recent_turns=2,
    )
    # 不调 set_llm_client；10 条 × 400 字符 ≈ 1000 tokens，超 300
    msgs = _make_long_messages(10, content_size=400)
    for m in msgs:
        mem.add_message(m["role"], m["content"])

    # 有一条摘要占位消息（内容为截断标记）
    summaries = [m for m in mem.messages if m.get("compressed_summary")]
    assert len(summaries) == 1
    assert "截断" in summaries[0]["content"]
    # 最近 4 条（2 轮）保留
    recent = [m for m in mem.messages if not m.get("compressed_summary")][-4:]
    expected_recent = msgs[-4:]
    for e, a in zip(expected_recent, recent):
        assert a["content"] == e["content"]


def test_multiple_compress_cycles_merge_summaries(tmp_path, monkeypatch):
    """多次触发压缩时，新摘要应基于旧摘要 + 后续对话生成（合并摘要）。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)

    fake_llm = MagicMock()
    fake_llm.chat.return_value = {"role": "assistant", "content": "merged summary", "tool_calls": None}

    mem = ConversationMemory(max_context_tokens=400, keep_recent_turns=2)
    mem.set_llm_client(fake_llm)

    # 第一批：触发第一次压缩（8 条 × 400 字符 ≈ 800 tokens）
    for m in _make_long_messages(8, content_size=400):
        mem.add_message(m["role"], m["content"])
    first_summary_count = sum(1 for m in mem.messages if m.get("compressed_summary"))
    assert first_summary_count == 1

    # 第二批：再加消息触发第二次压缩
    for m in _make_long_messages(6, content_size=400):
        mem.add_message(m["role"], m["content"])

    # 仍然只有一条摘要（旧摘要被合并到新摘要）
    summaries = [m for m in mem.messages if m.get("compressed_summary")]
    assert len(summaries) == 1


def test_get_messages_includes_system_prompt_first(tmp_path, monkeypatch):
    """get_messages 应把 system_prompt 放最前，摘要消息放其后。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=10000, keep_recent_turns=4)
    mem.system_prompt = "YOU ARE MINGCODE."
    mem.add_message("user", "hi")
    msgs = mem.get_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "YOU ARE MINGCODE."


def test_max_history_field_backward_compat(tmp_path, monkeypatch):
    """max_history 字段保留向后兼容（已保存会话文件仍可加载），但不再用于硬截断。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    # 仍可用旧签名构造
    mem = ConversationMemory(max_history=50)
    assert mem.max_history == 50
    # 默认 max_context_tokens 应有合理值
    assert mem.max_context_tokens > 0
    assert mem.keep_recent_turns > 0


def test_load_legacy_session_without_compress_fields(tmp_path, monkeypatch):
    """加载不含压缩配置字段的旧会话文件应使用默认值，不报错。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    import json
    legacy_data = {
        "saved_at": "2026-01-01T00:00:00",
        "max_history": 30,
        "messages": [
            {"role": "user", "content": "old question"},
            {"role": "assistant", "content": "old answer"},
        ],
    }
    session_file = tmp_path / "conversations" / "legacy.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    mem = ConversationMemory()
    ok = mem.load("legacy")
    assert ok
    assert len(mem.messages) == 2
    assert mem.max_history == 30


def test_save_includes_compress_config(tmp_path, monkeypatch):
    """保存会话时应写入压缩配置字段，便于加载时恢复。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=2048, keep_recent_turns=5)
    mem.add_message("user", "hello")
    name = mem.save("test_session")

    import json
    data = json.loads((tmp_path / "conversations" / "test_session.json").read_text(encoding="utf-8"))
    assert data["max_context_tokens"] == 2048
    assert data["keep_recent_turns"] == 5


def test_auto_compress_at_two_thirds_threshold(tmp_path, monkeypatch):
    """自动压缩阈值 = max_context_tokens * 2/3，超过此值触发压缩。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    fake_llm = MagicMock()
    fake_llm.chat.return_value = {"role": "assistant", "content": "summary", "tool_calls": None}

    # max_context_tokens=3000 → 阈值 2000；超过 2000 才压缩
    mem = ConversationMemory(max_context_tokens=3000, keep_recent_turns=2)
    mem.set_llm_client(fake_llm)

    # 8 条 × 200 字符 ≈ 400 tokens，远低于 2000，不压缩
    for m in _make_long_messages(8, content_size=200):
        mem.add_message(m["role"], m["content"])
    assert not any(m.get("compressed_summary") for m in mem.messages)
    assert fake_llm.chat.call_count == 0

    # 再加 6 条 × 600 字符 ≈ 900 tokens，累计约 1300 tokens，仍低于 2000
    for m in _make_long_messages(6, content_size=600):
        mem.add_message(m["role"], m["content"])
    # 还没触发（1300 < 2000）
    assert fake_llm.chat.call_count == 0

    # 加一批超长消息触发压缩
    for m in _make_long_messages(4, content_size=1500):
        mem.add_message(m["role"], m["content"])
    # 应触发压缩
    assert fake_llm.chat.call_count >= 1
    summaries = [m for m in mem.messages if m.get("compressed_summary")]
    assert len(summaries) == 1


def test_get_compress_threshold_returns_two_thirds(tmp_path, monkeypatch):
    """get_compress_threshold() 应返回 max_context_tokens * 2/3。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=6000, keep_recent_turns=6)
    assert mem.get_compress_threshold() == 4000

    mem2 = ConversationMemory(max_context_tokens=3000, keep_recent_turns=4)
    assert mem2.get_compress_threshold() == 2000


def test_compression_status(tmp_path, monkeypatch):
    """compression_status() 返回当前 token 使用量和阈值。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=6000, keep_recent_turns=6)
    mem.add_message("user", "hello world")

    status = mem.compression_status()
    assert "current_tokens" in status
    assert "threshold" in status
    assert "max_context_tokens" in status
    assert "is_over_threshold" in status
    assert status["threshold"] == 4000
    assert status["max_context_tokens"] == 6000
    assert status["is_over_threshold"] is False
    assert status["current_tokens"] > 0


def test_compress_now_forces_compression_below_threshold(tmp_path, monkeypatch):
    """compress_now() 强制触发压缩，即使 token 未达阈值。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    fake_llm = MagicMock()
    fake_llm.chat.return_value = {"role": "assistant", "content": "manual summary", "tool_calls": None}

    mem = ConversationMemory(max_context_tokens=10000, keep_recent_turns=2)
    mem.set_llm_client(fake_llm)

    # 添加少量消息（远未达阈值）
    for m in _make_long_messages(6, content_size=100):
        mem.add_message(m["role"], m["content"])
    assert not any(m.get("compressed_summary") for m in mem.messages)

    # 手动强制压缩
    result = mem.compress_now()
    assert result is True
    summaries = [m for m in mem.messages if m.get("compressed_summary")]
    assert len(summaries) == 1
    assert "manual summary" in summaries[0]["content"]


def test_compress_now_returns_false_when_nothing_to_compress(tmp_path, monkeypatch):
    """消息数不足以压缩时 compress_now() 返回 False。"""
    monkeypatch.setattr("core.memory.get_user_data_dir", lambda: tmp_path)
    mem = ConversationMemory(max_context_tokens=10000, keep_recent_turns=4)
    mem.add_message("user", "hi")
    mem.add_message("assistant", "hello")

    # 仅 2 条消息，keep_recent_turns=4 → 不超过 keep_count*2，无法压缩
    result = mem.compress_now()
    assert result is False
