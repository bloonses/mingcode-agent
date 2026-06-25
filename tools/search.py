import re
import requests
from typing import Any
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
            for i, result in enumerate(results, 1):
                title = result.get("title", "无标题")
                href = result.get("href", "")
                body = result.get("body", "")
                output.append(f"{i}. {title}\n   URL: {href}\n   摘要: {body}\n")
            return "\n".join(output)
        except Exception as e:
            return f"搜索出错：{str(e)}"


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
            return html
        except requests.exceptions.Timeout:
            return f"错误：请求超时，无法获取 {url}"
        except requests.exceptions.ConnectionError:
            return f"错误：连接失败，无法访问 {url}"
        except Exception as e:
            return f"获取网页出错：{str(e)}"
