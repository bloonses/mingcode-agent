"""HttpTool - HTTP 请求调试工具。

action: get / post / put / delete
支持自定义 headers、body、timeout
"""
import json as _json
import requests
from typing import Optional, Dict, Any

from .base import BaseTool


class HttpTool(BaseTool):
    name = "http"
    description = (
        "发送 HTTP 请求调试 API。支持 action："
        "get / post / put / delete。"
        "可设置 headers（dict）、body（dict 或字符串）、timeout（秒，默认 30）。"
        "返回状态码、响应头、响应体（自动截断 4000 字符）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "post", "put", "delete"],
                "description": "HTTP 方法"
            },
            "url": {
                "type": "string",
                "description": "请求 URL"
            },
            "headers": {
                "type": "object",
                "description": "请求头键值对（可选）"
            },
            "body": {
                "description": "请求体。如果是 dict 会自动 JSON 序列化；如果是字符串则原样发送"
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30"
            }
        },
        "required": ["action", "url"]
    }

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()
        url = kwargs.get("url")
        if not url:
            return "Error: url is required"
        if not url.startswith(("http://", "https://")):
            return f"Error: url must start with http:// or https://, got: {url}"
        if action not in ("get", "post", "put", "delete"):
            return f"Error: invalid method '{action}'. Supported: get/post/put/delete"

        headers = kwargs.get("headers") or {}
        body = kwargs.get("body")
        timeout = int(kwargs.get("timeout") or 30)

        try:
            method = action.upper()
            req_headers = dict(headers)

            # body 处理
            req_body = None
            if body is not None:
                if isinstance(body, dict) or isinstance(body, list):
                    req_body = _json.dumps(body, ensure_ascii=False)
                    req_headers.setdefault("Content-Type", "application/json")
                else:
                    req_body = str(body)

            resp = requests.request(
                method=method,
                url=url,
                headers=req_headers,
                data=req_body,
                timeout=timeout,
            )

            # 响应处理
            text = resp.text
            if len(text) > 4000:
                text = text[:4000] + f"\n...[truncated, total {len(text)} chars]"

            # 关键响应头
            key_headers = {}
            for k in ("content-type", "content-length", "set-cookie", "location", "etag"):
                if k in resp.headers:
                    key_headers[k] = resp.headers[k]

            lines = [
                f"Status: {resp.status_code} {resp.reason}",
                f"Headers: {_json.dumps(key_headers, ensure_ascii=False)}",
                f"Body:",
                text,
            ]
            return "\n".join(lines)
        except requests.exceptions.Timeout:
            return f"Error: request timeout after {timeout}s"
        except requests.exceptions.ConnectionError as e:
            return f"Error: connection failed: {e}"
        except Exception as e:
            return f"Error: {e}"
