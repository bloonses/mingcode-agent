import re
import requests
from typing import Any, Optional
from .base import BaseTool

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "使用DuckDuckGo搜索网络，返回相关结果摘要。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词"
            },
            "max_results": {
                "type": "integer",
                "description": "结果数量",
                "default": 5
            }
        },
        "required": ["query"]
    }

    def __init__(self):
        # 由 NeonAgent 注入：可选的知识库引用，搜索后自动归纳入库
        self.knowledge_base: Optional[Any] = None

    def execute(self, **kwargs) -> str:
        if not DDGS_AVAILABLE:
            return "错误：duckduckgo_search 库未安装，请运行 pip install duckduckgo-search"
        query = kwargs.get("query")
        max_results = kwargs.get("max_results", 5)
        if not query:
            return "错误：请提供搜索关键词 query"
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return f"未找到关于 '{query}' 的搜索结果。"
            output = []
            urls = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "无标题")
                href = result.get("href", "")
                body = result.get("body", "")
                if href:
                    urls.append(href)
                output.append(f"{i}. {title}\n   URL: {href}\n   摘要: {body}\n")
            result_text = "\n".join(output)
            # 自动归纳入库（不阻塞主流程，失败不影响搜索结果返回）
            self._maybe_store(query, result_text, urls)
            return result_text
        except Exception as e:
            return f"搜索出错：{str(e)}"

    def _maybe_store(self, query: str, result_text: str, urls: list) -> None:
        """把搜索结果归纳存入知识库（若有挂载且启用）。"""
        kb = self.knowledge_base
        if not kb or not getattr(kb, "enabled", False) or not getattr(kb, "auto_store", False):
            return
        try:
            kb.store_search_result(
                query=query,
                raw_results=result_text,
                source="web_search",
                urls=urls,
            )
        except Exception:
            # KB 存储失败不影响搜索工具的正常返回
            pass


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "获取网页URL的内容，提取可读文本。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要获取的网页URL"
            }
        },
        "required": ["url"]
    }

    def __init__(self):
        # 由 NeonAgent 注入：可选的知识库引用
        self.knowledge_base: Optional[Any] = None

    def execute(self, **kwargs) -> str:
        url = kwargs.get("url")
        if not url:
            return "错误：请提供要获取的网页 URL"
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html = response.text
            html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
            html = re.sub(r'<[^>]+>', ' ', html)
            html = re.sub(r'\s+', ' ', html).strip()
            if len(html) > 8000:
                html = html[:8000] + "...\n[内容已截断]"
            # 把抓取到的网页内容也存入知识库
            self._maybe_store(url, html)
            return html
        except requests.exceptions.Timeout:
            return f"错误：请求超时，无法获取 {url}"
        except requests.exceptions.ConnectionError:
            return f"错误：连接失败，无法访问 {url}"
        except Exception as e:
            return f"获取网页出错：{str(e)}"

    def _maybe_store(self, url: str, content: str) -> None:
        """把网页内容归纳存入知识库。"""
        kb = self.knowledge_base
        if not kb or not getattr(kb, "enabled", False) or not getattr(kb, "auto_store", False):
            return
        try:
            kb.store_search_result(
                query=url,
                raw_results=content,
                source="web_fetch",
                urls=[url],
            )
        except Exception:
            pass
