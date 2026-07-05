"""搜索工具测试。"""
from unittest.mock import patch, MagicMock
from tools.search import web_search, web_fetch


def test_web_search_returns_string():
    with patch("tools.search.DDGS") as mock_ddgs:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.text.return_value = [
            {"title": "Test", "body": "Test body", "href": "http://example.com"}
        ]
        mock_ddgs.return_value = mock_instance
        result = web_search.invoke({"query": "test query"})
        assert isinstance(result, str)
        assert "Test" in result


def test_web_search_empty_results():
    with patch("tools.search.DDGS") as mock_ddgs:
        mock_instance = MagicMock()
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.text.return_value = []
        mock_ddgs.return_value = mock_instance
        result = web_search.invoke({"query": "nonexistent"})
        assert "无结果" in result or "no" in result.lower() or "未找到" in result


def test_web_fetch_returns_content():
    with patch("tools.search.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Hello</body></html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        result = web_fetch.invoke({"url": "http://example.com"})
        assert "Hello" in result or "html" in result.lower()


def test_web_fetch_http_error():
    with patch("tools.search.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        result = web_fetch.invoke({"url": "http://example.com/nonexistent"})
        assert "404" in result or "error" in result.lower()
