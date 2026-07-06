"""测试 TokenTracker：累计 LLM 调用的 token 消耗。

覆盖：
- record() 累加 prompt/completion/total
- estimate_tokens() 字符数估算
- record_estimated() 估算兜底
- summary() 汇总
- by_model() 按模型分组
- reset() 清空
- format_compact() 紧凑显示
"""
from core.token_tracker import TokenTracker


def test_empty_tracker_summary():
    """新建的 tracker 应该是零计数。"""
    t = TokenTracker()
    s = t.summary()
    assert s["call_count"] == 0
    assert s["total_prompt"] == 0
    assert s["total_completion"] == 0
    assert s["total_tokens"] == 0
    assert s["avg_per_call"] == 0


def test_empty_format_compact_returns_empty():
    """没有调用时 format_compact 应返回空串。"""
    t = TokenTracker()
    assert t.format_compact() == ""


def test_record_single_call():
    """单次调用：累加数值正确。"""
    t = TokenTracker()
    entry = t.record(prompt_tokens=100, completion_tokens=50, total_tokens=150, model="gpt-test")
    assert entry["prompt_tokens"] == 100
    assert entry["completion_tokens"] == 50
    assert entry["total_tokens"] == 150
    assert entry["model"] == "gpt-test"
    assert "timestamp" in entry
    s = t.summary()
    assert s["call_count"] == 1
    assert s["total_prompt"] == 100
    assert s["total_completion"] == 50
    assert s["total_tokens"] == 150
    assert s["avg_per_call"] == 150


def test_record_total_default_to_sum():
    """不传 total_tokens 时应等于 prompt + completion。"""
    t = TokenTracker()
    entry = t.record(prompt_tokens=30, completion_tokens=20, model="m")
    assert entry["total_tokens"] == 50
    assert t.total_tokens == 50


def test_record_multiple_calls_accumulate():
    """多次调用：所有计数累加。"""
    t = TokenTracker()
    t.record(prompt_tokens=100, completion_tokens=50, total_tokens=150, model="a")
    t.record(prompt_tokens=200, completion_tokens=80, total_tokens=280, model="b")
    s = t.summary()
    assert s["call_count"] == 2
    assert s["total_prompt"] == 300
    assert s["total_completion"] == 130
    assert s["total_tokens"] == 430
    assert s["avg_per_call"] == 215


def test_estimate_tokens():
    """估算：4 字符 ≈ 1 token。"""
    assert TokenTracker.estimate_tokens("") == 0
    assert TokenTracker.estimate_tokens(None) == 0
    assert TokenTracker.estimate_tokens("abcd") == 1
    assert TokenTracker.estimate_tokens("abcdefgh") == 2
    # 中文每个字符也算 1 字符，所以 8 个中文字符 = 2 tokens
    assert TokenTracker.estimate_tokens("你好世界测试一下") == 2


def test_record_estimated():
    """估算兜底：用字符数推算 token。"""
    t = TokenTracker()
    prompt_text = "x" * 40   # 40 chars → 10 tokens
    completion_text = "y" * 20  # 20 chars → 5 tokens
    entry = t.record_estimated(prompt_text, completion_text, model="est")
    assert entry["prompt_tokens"] == 10
    assert entry["completion_tokens"] == 5
    assert entry["total_tokens"] == 15
    assert entry["model"] == "est"
    assert t.total_tokens == 15


def test_by_model_single():
    """单一模型：分组只有一个 entry。"""
    t = TokenTracker()
    t.record(prompt_tokens=10, completion_tokens=5, total_tokens=15, model="m1")
    t.record(prompt_tokens=20, completion_tokens=10, total_tokens=30, model="m1")
    grouped = t.by_model()
    assert len(grouped) == 1
    assert grouped["m1"]["prompt"] == 30
    assert grouped["m1"]["completion"] == 15
    assert grouped["m1"]["total"] == 45
    assert grouped["m1"]["calls"] == 2


def test_by_model_multiple():
    """多个模型：按模型名分组各自统计。"""
    t = TokenTracker()
    t.record(prompt_tokens=10, completion_tokens=5, total_tokens=15, model="m1")
    t.record(prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m2")
    t.record(prompt_tokens=20, completion_tokens=10, total_tokens=30, model="m1")
    grouped = t.by_model()
    assert len(grouped) == 2
    assert grouped["m1"] == {"prompt": 30, "completion": 15, "total": 45, "calls": 2}
    assert grouped["m2"] == {"prompt": 100, "completion": 50, "total": 150, "calls": 1}


def test_by_model_empty_model_name():
    """空 model 名应归入 'unknown'。"""
    t = TokenTracker()
    t.record(prompt_tokens=10, completion_tokens=5, total_tokens=15, model="")
    grouped = t.by_model()
    assert "unknown" in grouped
    assert grouped["unknown"]["calls"] == 1


def test_reset_clears_all():
    """reset() 应清空所有记录和累计计数。"""
    t = TokenTracker()
    t.record(prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m")
    t.record(prompt_tokens=200, completion_tokens=80, total_tokens=280, model="m")
    assert len(t.calls) == 2
    t.reset()
    assert len(t.calls) == 0
    assert t.total_prompt == 0
    assert t.total_completion == 0
    assert t.total_tokens == 0
    s = t.summary()
    assert s["call_count"] == 0
    assert t.format_compact() == ""


def test_format_compact_after_calls():
    """有调用时 format_compact 返回非空格式化串。"""
    t = TokenTracker()
    t.record(prompt_tokens=1000, completion_tokens=500, total_tokens=1500, model="m")
    line = t.format_compact()
    assert "1,000" in line
    assert "500" in line
    assert "1,500" in line
    assert "1 calls" in line


def test_format_compact_format_pattern():
    """验证 format_compact 的字符串结构。"""
    t = TokenTracker()
    t.record(prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m")
    line = t.format_compact()
    # 格式：Tokens: 100 in → 50 out (total 150) | 1 calls
    assert line.startswith("Tokens:")
    assert "in" in line
    assert "out" in line
    assert "total" in line
    assert "calls" in line
