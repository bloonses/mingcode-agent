"""知识库工具：供 Agent 在执行任务时检索历史归纳的知识。

工具：
- KnowledgeSearchTool: 关键词检索知识库
- KnowledgeReadTool: 按 ID 读取完整笔记
- KnowledgeStoreTool: 主动写入一条知识
"""
from typing import Any
from .base import BaseTool


class KnowledgeSearchTool(BaseTool):
    name = "kb_search"
    description = (
        "在本地知识库（Obsidian vault）中检索之前归纳的网络搜索结果。"
        "适合回答那些之前已经搜索过、可复用的问题，避免重复联网。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索关键词或问题",
            },
            "top_k": {
                "type": "integer",
                "description": "返回结果数量（默认 5）",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self, knowledge_base: Any):
        self.kb = knowledge_base

    def execute(self, **kwargs) -> str:
        if not getattr(self.kb, "enabled", False):
            return "知识库未启用"
        query = kwargs.get("query")
        if not query:
            return "错误：请提供检索关键词 query"
        top_k = kwargs.get("top_k", 5)
        results = self.kb.search(query, top_k=top_k)
        if not results:
            return f"知识库中没有找到关于 '{query}' 的笔记。"
        output = [f"找到 {len(results)} 条相关知识笔记：\n"]
        for i, r in enumerate(results, 1):
            output.append(f"--- 笔记 {i} ---")
            output.append(f"标题: {r['title']}")
            output.append(f"ID: {r['id']}")
            output.append(f"标签: {', '.join(r['tags']) if r['tags'] else '无'}")
            output.append(f"分数: {r['score']}")
            if r.get("query"):
                output.append(f"原查询: {r['query']}")
            output.append(f"预览: {r['preview']}")
            output.append("")
        output.append("提示：调用 kb_read 并传 id 可查看完整笔记内容。")
        return "\n".join(output)


class KnowledgeReadTool(BaseTool):
    name = "kb_read"
    description = "按 ID 读取知识库笔记的完整内容。先调用 kb_search 获取笔记 ID。"
    parameters = {
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "笔记 ID（如 kb_20260706_143022_a1b2）",
            },
        },
        "required": ["id"],
    }

    def __init__(self, knowledge_base: Any):
        self.kb = knowledge_base

    def execute(self, **kwargs) -> str:
        if not getattr(self.kb, "enabled", False):
            return "知识库未启用"
        note_id = kwargs.get("id")
        if not note_id:
            return "错误：请提供笔记 ID"
        note = self.kb.get_note(note_id)
        if not note:
            return f"未找到笔记: {note_id}"
        parts = [
            f"# {note['title']}",
            f"ID: {note['id']}",
            f"标签: {', '.join(note['tags']) if note['tags'] else '无'}",
            f"创建时间: {note['created']}",
        ]
        if note.get("query"):
            parts.append(f"原查询: {note['query']}")
        if note.get("urls"):
            parts.append("来源链接:")
            for u in note["urls"]:
                parts.append(f"  - {u}")
        parts.append("")
        parts.append(note["content"])
        return "\n".join(parts)


class KnowledgeStoreTool(BaseTool):
    name = "kb_store"
    description = (
        "主动把一段重要信息存入知识库，作为未来检索的来源。"
        "适合保存从对话中得到的结论、用户偏好、技术发现等。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "笔记标题",
            },
            "content": {
                "type": "string",
                "description": "笔记内容（Markdown）",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选的标签列表",
            },
        },
        "required": ["title", "content"],
    }

    def __init__(self, knowledge_base: Any):
        self.kb = knowledge_base

    def execute(self, **kwargs) -> str:
        if not getattr(self.kb, "enabled", False):
            return "知识库未启用"
        title = kwargs.get("title")
        content = kwargs.get("content")
        if not title or not content:
            return "错误：title 和 content 都是必填"
        tags = kwargs.get("tags") or []
        result = self.kb.store_text(title, content, tags=tags, source="agent")
        if result.get("error"):
            return result["error"]
        return f"已存入知识库：{result['title']} (id={result['id']}, tags={result['tags']})"
