"""知识库（RAG）：把网络搜索结果归纳为 Obsidian 兼容的 Markdown 笔记并支持检索。

工作流：
1. WebSearchTool / WebFetchTool 执行成功后调用 store_search_result()
2. LLM 把原始搜索结果归纳为结构化知识笔记
3. 笔记以 Markdown + YAML frontmatter 形式存入 vault 目录
4. search() 用关键词匹配 + TF 简易打分返回 Top-N 相关笔记

笔记格式（Obsidian 兼容）：
    ---
    id: kb_20260706_143022_a1b2
    title: "LangChain StateGraph 工作流"
    source: web_search
    query: "how does langgraph work"
    urls:
      - https://example.com/...
    tags: [langchain, langgraph]
    created: 2026-07-06T14:30:22
    ---
    # Title
    ## 摘要
    ...
    ## 关键发现
    - ...
    ## 来源
    - [Title](url)
"""
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

from config.config import get_user_data_dir


# 关键词停用表（中英常见无意义词）
_STOPWORDS = {
    # 英文
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "could", "may", "might", "must", "shall", "can", "need", "dare",
    "of", "to", "in", "on", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after", "above",
    "below", "from", "up", "down", "out", "off", "over", "under", "again",
    "and", "or", "but", "if", "then", "than", "so", "no", "not", "only",
    "this", "that", "these", "those", "i", "you", "he", "she", "it", "we",
    "they", "what", "which", "who", "whom", "whose", "how", "where", "why",
    "when",
    # 中文
    "的", "了", "是", "在", "我", "你", "他", "她", "它", "我们", "你们", "他们",
    "这", "那", "之", "与", "和", "或", "但", "如", "因", "为", "所", "以",
    "可以", "能够", "应该", "必须", "需要", "可能", "或许", "也许",
    "一", "二", "三", "个", "些", "种", "样", "多", "少", "大", "小",
    "上", "下", "中", "里", "外", "前", "后", "左", "右",
    "把", "被", "让", "使", "给", "对", "向", "从", "到", "用", "按",
}


def _tokenize(text: str) -> List[str]:
    """简易分词：英文按空白与标点切分，中文按字符切分（Bigram 友好）。"""
    if not text:
        return []
    # 英文单词
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text.lower())
    # 中文单字（连续中文字符按 2-gram 切，提升匹配召回）
    chinese = re.findall(r"[\u4e00-\u9fa5]+", text)
    cn_tokens: List[str] = []
    for seg in chinese:
        if len(seg) == 1:
            cn_tokens.append(seg)
        else:
            for i in range(len(seg) - 1):
                cn_tokens.append(seg[i:i + 2])
            cn_tokens.append(seg[-1])  # 末字单独也算一次
    return words + cn_tokens


def _filter_stopwords(tokens: List[str]) -> List[str]:
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _extract_keywords(text: str, top_k: int = 8) -> List[str]:
    """从文本中提取 Top-K 关键词（词频排序）。"""
    tokens = _filter_stopwords(_tokenize(text))
    if not tokens:
        return []
    freq: Dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top_k]]


class KnowledgeBase:
    """管理 Obsidian 兼容的 Markdown 知识库。

    笔记存放在 vault 目录下，每条一个 .md 文件。
    支持自动归纳（LLM 摘要）与关键词检索。
    """

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        llm_client: Any = None,
        auto_store: bool = True,
        max_note_length: int = 4000,
        enabled: bool = True,
    ):
        self.enabled = enabled
        if vault_path:
            self.vault_path = Path(vault_path)
        else:
            self.vault_path = get_user_data_dir() / "vault"
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.llm = llm_client
        self.auto_store = auto_store
        self.max_note_length = max_note_length

    # ---------- 存储 ----------

    def store_search_result(
        self,
        query: str,
        raw_results: str,
        source: str = "web_search",
        urls: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """把搜索结果归纳为知识笔记并写入 vault。

        参数：
            query: 用户的搜索查询
            raw_results: 工具原始返回的字符串
            source: 来源标识（web_search / web_fetch）
            urls: 相关 URL 列表（可空）

        返回笔记元数据 dict；若禁用或 LLM 不可用则返回 None。
        """
        if not self.enabled or not self.auto_store:
            return None
        # 归纳内容（若 LLM 不可用则降级为截取前 N 字符）
        try:
            summary = self._summarize_with_llm(query, raw_results)
        except Exception:
            summary = self._fallback_summary(query, raw_results)
        if not summary:
            return None
        # 截断
        if len(summary) > self.max_note_length:
            summary = summary[:self.max_note_length] + "\n\n...(内容已截断)"
        # 提取 tags
        all_text = query + " " + summary
        tags = _extract_keywords(all_text, top_k=8)
        # 生成 ID 和文件名
        note_id = self._gen_id(query)
        title = self._gen_title(query, summary)
        safe_name = self._safe_filename(title)
        # YAML frontmatter + 正文
        front = {
            "id": note_id,
            "title": title,
            "source": source,
            "query": query,
            "urls": urls or [],
            "tags": tags,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        body = self._render_body(title, summary, urls or [], tags)
        md = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n" + body
        note_path = self.vault_path / f"{safe_name}.md"
        # 防止文件名冲突
        if note_path.exists():
            note_path = self.vault_path / f"{safe_name}_{note_id[-4:]}.md"
        note_path.write_text(md, encoding="utf-8")
        return {
            "id": note_id,
            "title": title,
            "path": str(note_path),
            "tags": tags,
            "query": query,
        }

    def store_text(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: str = "manual",
    ) -> Dict[str, Any]:
        """手动存一条文本到知识库（用户或 Agent 主动写入）。"""
        if not self.enabled:
            return {"error": "knowledge_base is disabled"}
        all_text = title + " " + content
        auto_tags = _extract_keywords(all_text, top_k=6)
        final_tags = list(dict.fromkeys((tags or []) + auto_tags))  # 去重保序
        note_id = self._gen_id(title)
        safe_name = self._safe_filename(title)
        front = {
            "id": note_id,
            "title": title,
            "source": source,
            "query": "",
            "urls": [],
            "tags": final_tags,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        body = f"# {title}\n\n{content}\n"
        md = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n" + body
        note_path = self.vault_path / f"{safe_name}.md"
        if note_path.exists():
            note_path = self.vault_path / f"{safe_name}_{note_id[-4:]}.md"
        note_path.write_text(md, encoding="utf-8")
        return {
            "id": note_id,
            "title": title,
            "path": str(note_path),
            "tags": final_tags,
        }

    # ---------- 检索 ----------

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """关键词检索：对 query 分词后在所有笔记的 title+tags+content 上做 TF 打分。

        返回 Top-N 笔记元数据 + 命中片段预览。
        """
        if not self.enabled:
            return []
        query_tokens = set(_filter_stopwords(_tokenize(query)))
        if not query_tokens:
            return []
        results: List[Dict[str, Any]] = []
        for note in self._iter_notes():
            text = note["search_text"]
            tokens = _filter_stopwords(_tokenize(text))
            if not tokens:
                continue
            token_set = set(tokens)
            # 命中数 = query 与文档共同 token 数
            hits = query_tokens & token_set
            if not hits:
                continue
            # 打分：命中 token 频次 + title 命中加权 + tag 命中加权
            freq: Dict[str, int] = {}
            for t in tokens:
                freq[t] = freq.get(t, 0) + 1
            score = sum(freq.get(t, 0) for t in hits)
            # 标题命中加权
            title_tokens = set(_filter_stopwords(_tokenize(note["title"])))
            title_bonus = len(query_tokens & title_tokens) * 3
            # tag 命中加权
            tag_tokens = set()
            for tag in note["tags"]:
                tag_tokens.update(_filter_stopwords(_tokenize(tag)))
            tag_bonus = len(query_tokens & tag_tokens) * 2
            score += title_bonus + tag_bonus
            preview = self._make_preview(note["content"], query_tokens)
            results.append({
                "id": note["id"],
                "title": note["title"],
                "path": note["path"],
                "tags": note["tags"],
                "query": note["query"],
                "created": note["created"],
                "score": score,
                "preview": preview,
            })
        results.sort(key=lambda r: -r["score"])
        return results[:top_k]

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 读取笔记完整内容。"""
        for note in self._iter_notes():
            if note["id"] == note_id:
                return {
                    "id": note["id"],
                    "title": note["title"],
                    "path": note["path"],
                    "tags": note["tags"],
                    "query": note["query"],
                    "urls": note["urls"],
                    "created": note["created"],
                    "content": note["content"],
                }
        return None

    def list_notes(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """列出最近的笔记（按文件 mtime 倒序，frontmatter created 作为次级键）。"""
        notes = list(self._iter_notes())
        # 主键：文件修改时间（更精确到秒以下，避免同秒写入顺序错乱）
        for n in notes:
            try:
                n["_mtime"] = Path(n["path"]).stat().st_mtime
            except Exception:
                n["_mtime"] = 0
        notes.sort(key=lambda n: (n["_mtime"], n.get("created", "")), reverse=True)
        for n in notes:
            n.pop("_mtime", None)
        return notes[offset:offset + limit]

    def stats(self) -> Dict[str, Any]:
        """知识库统计信息。"""
        notes = list(self._iter_notes())
        total = len(notes)
        all_tags: Dict[str, int] = {}
        for n in notes:
            for t in n["tags"]:
                all_tags[t] = all_tags.get(t, 0) + 1
        top_tags = sorted(all_tags.items(), key=lambda kv: -kv[1])[:10]
        return {
            "total_notes": total,
            "vault_path": str(self.vault_path),
            "top_tags": top_tags,
            "enabled": self.enabled,
            "auto_store": self.auto_store,
        }

    def delete_note(self, note_id: str) -> bool:
        """按 ID 删除笔记。"""
        for note in self._iter_notes():
            if note["id"] == note_id:
                try:
                    Path(note["path"]).unlink(missing_ok=True)
                    return True
                except Exception:
                    return False
        return False

    # ---------- 内部实现 ----------

    def _iter_notes(self) -> List[Dict[str, Any]]:
        """遍历 vault 读取所有 .md 笔记。"""
        notes: List[Dict[str, Any]] = []
        if not self.vault_path.exists():
            return notes
        for md_file in self.vault_path.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = self._parse_frontmatter(content)
            if not meta:
                continue
            notes.append({
                "id": meta.get("id", md_file.stem),
                "title": meta.get("title", md_file.stem),
                "path": str(md_file),
                "tags": meta.get("tags", []) or [],
                "query": meta.get("query", "") or "",
                "urls": meta.get("urls", []) or [],
                "created": meta.get("created", "") or "",
                "source": meta.get("source", "") or "",
                "content": meta.get("body", ""),
                "search_text": meta.get("title", "") + " " + " ".join(meta.get("tags", []) or []) + " " + meta.get("body", ""),
            })
        return notes

    @staticmethod
    def _parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
        """解析 Markdown frontmatter + body。"""
        if not content.startswith("---"):
            return None
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None
        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None
        meta["body"] = parts[2].lstrip("\n")
        return meta

    def _summarize_with_llm(self, query: str, raw: str) -> str:
        """用 LLM 把原始搜索结果归纳为结构化知识。"""
        if not self.llm:
            return self._fallback_summary(query, raw)
        # 截断原始内容防止 prompt 过长
        if len(raw) > 3000:
            raw = raw[:3000] + "\n\n...(原始内容已截断)"
        prompt = (
            "你是知识归纳助手。基于下面的搜索查询和搜索结果，提炼出一份结构化的知识笔记。\n"
            "要求：\n"
            "1. 用 Markdown 格式输出\n"
            "2. 用 `## 摘要` 开头写 2-3 句话概述\n"
            "3. 用 `## 关键发现` 列出 3-5 条要点\n"
            "4. 用 `## 详细内容` 写更深入的说明\n"
            "5. 不要包含来源链接（系统会自动添加）\n"
            "6. 只输出 Markdown 内容，不要任何前后缀\n\n"
            f"搜索查询：{query}\n\n"
            f"搜索结果：\n{raw}\n"
        )
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是一个擅长信息归纳和提炼的助手，输出简洁精确的 Markdown 知识笔记。"},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            content = resp.get("content") or ""
            content = content.strip()
            return content or self._fallback_summary(query, raw)
        except Exception:
            return self._fallback_summary(query, raw)

    @staticmethod
    def _fallback_summary(query: str, raw: str) -> str:
        """LLM 不可用时降级：截取原始结果前若干字符。"""
        snippet = raw[:1500].strip()
        return f"# {query}\n\n## 摘要\n\n以下为搜索 `{query}` 得到的原始结果（LLM 不可用，未做归纳）。\n\n## 原始结果\n\n{snippet}\n"

    @staticmethod
    def _gen_id(seed: str) -> str:
        """生成笔记 ID：kb_<时间>_<hash前4位>。"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        h = hashlib.md5(seed.encode("utf-8")).hexdigest()[:4]
        return f"kb_{ts}_{h}"

    @staticmethod
    def _gen_title(query: str, summary: str) -> str:
        """从 summary 的第一个标题或 query 生成笔记标题。"""
        # 尝试从 summary 第一个 # 标题取
        m = re.search(r"^#\s+(.+)$", summary, re.MULTILINE)
        if m:
            title = m.group(1).strip()
            # 移除可能的 markdown 强调符
            title = re.sub(r"[*_`]", "", title)
            if title and len(title) <= 80:
                return title
        # 降级使用 query
        title = query.strip()
        if len(title) > 80:
            title = title[:80]
        return title or "Untitled Note"

    @staticmethod
    def _safe_filename(name: str) -> str:
        """把标题转为安全的文件名（保留中文）。"""
        # 移除文件名非法字符
        safe = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", name)
        safe = safe.strip().strip(".")
        if not safe:
            safe = "untitled"
        if len(safe) > 60:
            safe = safe[:60]
        return safe

    @staticmethod
    def _render_body(title: str, summary: str, urls: List[str], tags: List[str]) -> str:
        """渲染笔记正文 Markdown。"""
        body = ""
        # 如果 summary 已经包含 title 行则不再重复加
        if not summary.lstrip().startswith("# "):
            body += f"# {title}\n\n"
        body += summary.rstrip() + "\n"
        # 来源链接
        if urls:
            body += "\n## 来源\n"
            for u in urls:
                body += f"- {u}\n"
        # 标签
        if tags:
            body += "\n## 标签\n"
            tag_str = " ".join(f"#{t}" for t in tags)
            body += tag_str + "\n"
        return body

    @staticmethod
    def _make_preview(content: str, query_tokens: set, max_chars: int = 300) -> str:
        """从笔记内容生成包含命中文本的预览片段。"""
        if not content:
            return ""
        # 找到第一个命中 token 所在位置，截取前后文
        lower = content.lower()
        pos = -1
        for tok in query_tokens:
            idx = lower.find(tok.lower())
            if idx >= 0 and (pos < 0 or idx < pos):
                pos = idx
        if pos < 0:
            return content[:max_chars].replace("\n", " ").strip() + ("..." if len(content) > max_chars else "")
        start = max(0, pos - 100)
        end = min(len(content), pos + 200)
        snippet = content[start:end].replace("\n", " ").strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        return f"{prefix}{snippet}{suffix}"
