"""网络搜索工具。"""
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Max results to return")


class WebFetchInput(BaseModel):
    url: str = Field(description="URL to fetch")


@tool(args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results."""
    if DDGS is None:
        return "Error: duckduckgo-search not installed. Run: pip install duckduckgo-search"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"未找到关于 '{query}' 的结果"
        output = []
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r.get('title', 'No title')}\n   {r.get('body', '')[:200]}\n   {r.get('href', '')}")
        return "\n\n".join(output)
    except Exception as e:
        return f"Error: {e}"


@tool(args_schema=WebFetchInput)
def web_fetch(url: str) -> str:
    """Fetch URL content as text."""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "MINGCODE-LC/0.1"})
        if response.status_code != 200:
            return f"Error: HTTP {response.status_code}"
        return response.text[:5000]
    except Exception as e:
        return f"Error: {e}"
