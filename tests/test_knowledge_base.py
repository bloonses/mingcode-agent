"""测试 KnowledgeBase（RAG）：网络搜索结果归纳存储 + 关键词检索。

覆盖：
- store_search_result() 写入 vault（含 frontmatter）
- store_text() 手动写入
- search() 关键词匹配 + 评分
- get_note() 按 ID 读取
- list_notes() 列表
- stats() 统计
- delete_note() 删除
- 禁用模式 / auto_store=False 时不入库
- WebSearchTool 钩子触发入库
- WebFetchTool 钩子触发入库
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from core.knowledge_base import (
    KnowledgeBase,
    _tokenize,
    _filter_stopwords,
    _extract_keywords,
)


@pytest.fixture
def kb(tmp_path):
    """临时 vault 的 KnowledgeBase 实例。"""
    return KnowledgeBase(vault_path=tmp_path / "vault", llm_client=None, auto_store=True)


@pytest.fixture
def kb_with_llm(tmp_path):
    """带 mock LLM 的 KnowledgeBase。"""
    llm = MagicMock()
    llm.chat.return_value = {
        "role": "assistant",
        "content": "## 摘要\nLangGraph 是用于构建状态机的图库。\n\n## 关键发现\n- 支持条件边\n- 节点间共享状态",
        "tool_calls": None,
    }
    return KnowledgeBase(vault_path=tmp_path / "vault", llm_client=llm, auto_store=True)


# ---------- 内部工具函数 ----------

def test_tokenize_english():
    tokens = _tokenize("LangChain StateGraph workflow")
    assert "langchain" in tokens
    assert "stategraph" in tokens
    assert "workflow" in tokens


def test_tokenize_chinese_bigram():
    """中文按 2-gram 切分。"""
    tokens = _tokenize("知识库检索")
    # "知识", "识库", "库检", "检索", "索" 都应出现
    assert "知识" in tokens
    assert "识库" in tokens
    assert "检索" in tokens


def test_filter_stopwords_removes_common():
    """停用词应被过滤掉。"""
    filtered = _filter_stopwords(_tokenize("the quick brown fox jumps over the lazy dog"))
    assert "the" not in filtered
    assert "quick" in filtered


def test_extract_keywords_returns_top():
    """关键词按频次排序返回 Top-K。"""
    text = "python python python langchain langchain langchain graph graph node"
    kws = _extract_keywords(text, top_k=2)
    assert "python" in kws
    assert "langchain" in kws


# ---------- store_search_result ----------

def test_store_search_result_writes_markdown_file(kb_with_llm):
    """搜索结果应被写入 vault 为 .md 文件。"""
    result = kb_with_llm.store_search_result(
        query="how does langgraph work",
        raw_results="1. LangGraph title\n   URL: https://example.com/lg\n   摘要: LangGraph is a graph library",
        source="web_search",
        urls=["https://example.com/lg"],
    )
    assert result is not None
    assert result["id"].startswith("kb_")
    assert result["title"]
    assert result["tags"]
    note_path = Path(result["path"])
    assert note_path.exists()
    content = note_path.read_text(encoding="utf-8")
    # 应有 YAML frontmatter
    assert content.startswith("---")
    assert "id:" in content
    assert "title:" in content
    assert "tags:" in content
    # 应有正文
    assert "## 摘要" in content or "## 关键发现" in content


def test_store_search_result_includes_urls_in_frontmatter(kb_with_llm):
    """frontmatter 应包含 urls 列表。"""
    urls = ["https://a.com", "https://b.com"]
    result = kb_with_llm.store_search_result(
        query="test query",
        raw_results="some content",
        urls=urls,
    )
    content = Path(result["path"]).read_text(encoding="utf-8")
    for u in urls:
        assert u in content


def test_store_search_result_disabled_returns_none(tmp_path):
    """禁用时不应写入。"""
    kb = KnowledgeBase(vault_path=tmp_path / "v", enabled=False)
    result = kb.store_search_result("q", "raw")
    assert result is None
    assert not (tmp_path / "v").exists() or not list((tmp_path / "v").glob("*.md"))


def test_store_search_result_auto_store_off(tmp_path):
    """auto_store=False 时不应写入。"""
    kb = KnowledgeBase(vault_path=tmp_path / "v", auto_store=False)
    result = kb.store_search_result("q", "raw")
    assert result is None


def test_store_search_result_fallback_when_llm_raises(tmp_path):
    """LLM 抛异常时应走降级路径，仍能写入笔记。"""
    llm = MagicMock()
    llm.chat.side_effect = Exception("LLM unavailable")
    kb = KnowledgeBase(vault_path=tmp_path / "v", llm_client=llm, auto_store=True)
    result = kb.store_search_result("test query", "raw search results here")
    assert result is not None
    content = Path(result["path"]).read_text(encoding="utf-8")
    assert "test query" in content
    # 降级路径会包含原始结果
    assert "raw search results" in content


def test_store_search_result_truncates_long_content(tmp_path):
    """超过 max_note_length 的内容应被截断。"""
    kb = KnowledgeBase(vault_path=tmp_path / "v", llm_client=None, max_note_length=200)
    long_raw = "x" * 5000
    result = kb.store_search_result("q", long_raw)
    content = Path(result["path"]).read_text(encoding="utf-8")
    assert "截断" in content


# ---------- store_text ----------

def test_store_text_writes_manual_note(kb):
    """手动 store_text 应写入笔记，source=manual。"""
    result = kb.store_text("My Note", "这是笔记内容", tags=["custom"])
    assert result["title"] == "My Note"
    assert "custom" in result["tags"]
    # 验证文件内容
    content = Path(result["path"]).read_text(encoding="utf-8")
    assert "source: manual" in content
    assert "这是笔记内容" in content


def test_store_text_auto_generates_tags(kb):
    """未提供 tags 时应自动从内容生成。"""
    result = kb.store_text("Python 教程", "Python 是一种解释型编程语言，适合快速开发。")
    assert len(result["tags"]) > 0
    # "python" 应该在 tags 里
    assert any("python" in t.lower() or "解释" in t for t in result["tags"])


def test_store_text_disabled_returns_error(tmp_path):
    """禁用时 store_text 应返回 error。"""
    kb = KnowledgeBase(vault_path=tmp_path / "v", enabled=False)
    result = kb.store_text("t", "c")
    assert "error" in result


# ---------- search ----------

def test_search_finds_relevant_notes(kb):
    """search 应能找到包含查询关键词的笔记。"""
    kb.store_text("LangChain 教程", "LangChain 是一个 LLM 应用框架，支持 chain 链式调用和 agent 智能体。")
    kb.store_text("Python 基础", "Python 是一种解释型编程语言。")
    results = kb.search("langchain 框架")
    assert len(results) >= 1
    # 第一条应该是 langchain 教程
    assert "langchain" in results[0]["title"].lower() or "langchain" in results[0]["content"].lower()


def test_search_returns_empty_when_no_match(kb):
    """没有匹配时应返回空列表。"""
    kb.store_text("Python 教程", "Python 是一种编程语言。")
    results = kb.search("量子物理")
    assert results == []


def test_search_returns_preview(kb):
    """结果中应包含 preview 字段。"""
    kb.store_text("测试笔记", "这是一段关于测试的笔记内容，包含关键词 keyword。")
    results = kb.search("测试")
    assert results
    assert "preview" in results[0]
    assert results[0]["preview"]


def test_search_title_bonus(kb):
    """标题命中的笔记应优先于正文命中的。"""
    kb.store_text("LangChain 详解", "其他无关内容。")
    kb.store_text("其他主题", "LangChain 在这里被提及一次。")
    results = kb.search("langchain")
    assert results
    assert "langchain" in results[0]["title"].lower()


def test_search_top_k_limit(kb):
    """top_k 应限制返回数量。"""
    for i in range(10):
        kb.store_text(f"Python 教程 {i}", f"Python 内容 {i}")
    results = kb.search("python", top_k=3)
    assert len(results) <= 3


# ---------- get_note ----------

def test_get_note_by_id(kb):
    """按 ID 应能读取完整笔记。"""
    stored = kb.store_text("测试", "内容")
    note = kb.get_note(stored["id"])
    assert note is not None
    assert note["title"] == "测试"
    assert "内容" in note["content"]
    assert note["id"] == stored["id"]


def test_get_note_returns_none_for_unknown_id(kb):
    """未知 ID 应返回 None。"""
    note = kb.get_note("kb_nonexistent")
    assert note is None


# ---------- list_notes ----------

def test_list_notes_returns_recent(kb):
    """list_notes 应返回所有笔记，按时间倒序。"""
    kb.store_text("笔记 A", "内容 A")
    kb.store_text("笔记 B", "内容 B")
    notes = kb.list_notes()
    assert len(notes) == 2
    # 后写入的应该在前面
    assert notes[0]["title"] == "笔记 B"


def test_list_notes_respects_limit(kb):
    """limit 应限制返回数量。"""
    for i in range(5):
        kb.store_text(f"笔记 {i}", f"内容 {i}")
    notes = kb.list_notes(limit=2)
    assert len(notes) == 2


# ---------- stats ----------

def test_stats_returns_counts(kb):
    """stats 应返回笔记数和标签统计。"""
    kb.store_text("Python 教程", "Python 内容", tags=["python", "tutorial"])
    kb.store_text("LangChain 教程", "LangChain 内容", tags=["python", "langchain"])
    s = kb.stats()
    assert s["total_notes"] == 2
    assert s["enabled"] is True
    assert s["auto_store"] is True
    # python 标签出现 2 次
    tag_dict = dict(s["top_tags"])
    assert tag_dict.get("python") == 2


# ---------- delete_note ----------

def test_delete_note_removes_file(kb):
    """删除笔记后文件应不存在。"""
    stored = kb.store_text("待删除", "内容")
    note_path = Path(stored["path"])
    assert note_path.exists()
    assert kb.delete_note(stored["id"]) is True
    assert not note_path.exists()


def test_delete_note_unknown_returns_false(kb):
    """删除不存在的 ID 返回 False。"""
    assert kb.delete_note("kb_unknown") is False


# ---------- WebSearchTool 钩子 ----------

def test_web_search_tool_stores_to_kb_on_success():
    """WebSearchTool 成功搜索后应调用 kb.store_search_result。"""
    from tools.search import WebSearchTool
    tool = WebSearchTool()
    kb = MagicMock()
    kb.enabled = True
    kb.auto_store = True
    tool.knowledge_base = kb
    # mock DDGS
    with patch("tools.search.DDGS_AVAILABLE", True):
        fake_ddgs = MagicMock()
        fake_ddgs.__enter__.return_value.text.return_value = [
            {"title": "Test", "href": "http://x", "body": "Body"},
        ]
        with patch("tools.search.DDGS", return_value=fake_ddgs):
            result = tool.execute(query="test query", max_results=1)
    # KB 应被调用
    kb.store_search_result.assert_called_once()
    call_kwargs = kb.store_search_result.call_args
    assert call_kwargs[1]["query"] == "test query"
    assert call_kwargs[1]["source"] == "web_search"
    assert "http://x" in call_kwargs[1]["urls"]


def test_web_search_tool_no_kb_does_not_crash():
    """未注入 KB 时不应影响搜索主流程。"""
    from tools.search import WebSearchTool
    tool = WebSearchTool()
    tool.knowledge_base = None
    with patch("tools.search.DDGS_AVAILABLE", True):
        fake_ddgs = MagicMock()
        fake_ddgs.__enter__.return_value.text.return_value = [
            {"title": "T", "href": "http://x", "body": "B"},
        ]
        with patch("tools.search.DDGS", return_value=fake_ddgs):
            result = tool.execute(query="test")
    assert "T" in result


def test_web_search_tool_kb_storage_failure_does_not_break_search():
    """KB 存储抛异常时不应影响搜索结果的返回。"""
    from tools.search import WebSearchTool
    tool = WebSearchTool()
    kb = MagicMock()
    kb.enabled = True
    kb.auto_store = True
    kb.store_search_result.side_effect = Exception("KB write failed")
    tool.knowledge_base = kb
    with patch("tools.search.DDGS_AVAILABLE", True):
        fake_ddgs = MagicMock()
        fake_ddgs.__enter__.return_value.text.return_value = [
            {"title": "OK", "href": "http://x", "body": "B"},
        ]
        with patch("tools.search.DDGS", return_value=fake_ddgs):
            result = tool.execute(query="t")
    # 主结果正常返回
    assert "OK" in result


# ---------- WebFetchTool 钩子 ----------

def test_web_fetch_tool_stores_to_kb_on_success():
    """WebFetchTool 成功抓取后应调用 kb.store_search_result。"""
    from tools.search import WebFetchTool
    tool = WebFetchTool()
    kb = MagicMock()
    kb.enabled = True
    kb.auto_store = True
    tool.knowledge_base = kb
    fake_response = MagicMock()
    fake_response.text = "<html><body>Hello World</body></html>"
    fake_response.raise_for_status.return_value = None
    with patch("tools.search.requests.get", return_value=fake_response):
        result = tool.execute(url="http://example.com")
    kb.store_search_result.assert_called_once()
    call_kwargs = kb.store_search_result.call_args
    assert call_kwargs[1]["source"] == "web_fetch"
    assert call_kwargs[1]["urls"] == ["http://example.com"]


# ---------- KnowledgeBaseTool ----------

def test_kb_search_tool_returns_results(kb):
    """KnowledgeSearchTool.execute 应返回格式化结果。"""
    from tools.kb_tool import KnowledgeSearchTool
    kb.store_text("LangChain", "LangChain 是 LLM 框架。")
    tool = KnowledgeSearchTool(kb)
    output = tool.execute(query="langchain")
    assert "LangChain" in output
    assert "ID:" in output or "ID:" in output


def test_kb_search_tool_no_results():
    """无匹配时返回提示信息。"""
    from tools.kb_tool import KnowledgeSearchTool
    kb = MagicMock()
    kb.enabled = True
    kb.search.return_value = []
    tool = KnowledgeSearchTool(kb)
    output = tool.execute(query="xxx")
    assert "没有找到" in output or "未找到" in output


def test_kb_read_tool_returns_full_content(kb):
    """KnowledgeReadTool 应返回完整笔记内容。"""
    from tools.kb_tool import KnowledgeReadTool
    stored = kb.store_text("测试笔记", "完整内容在这里")
    tool = KnowledgeReadTool(kb)
    output = tool.execute(id=stored["id"])
    assert "测试笔记" in output
    assert "完整内容在这里" in output


def test_kb_read_tool_unknown_id(kb):
    """未知 ID 时返回错误信息。"""
    from tools.kb_tool import KnowledgeReadTool
    tool = KnowledgeReadTool(kb)
    output = tool.execute(id="kb_unknown")
    assert "未找到" in output or "not found" in output.lower()


def test_kb_store_tool_writes_note(kb):
    """KnowledgeStoreTool 应能写入笔记。"""
    from tools.kb_tool import KnowledgeStoreTool
    tool = KnowledgeStoreTool(kb)
    output = tool.execute(title="测试", content="内容", tags=["t1"])
    assert "已存入" in output
    assert "测试" in output
