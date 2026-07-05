"""HTTP 请求工具。"""
import json as json_module
import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class HttpRequestInput(BaseModel):
    method: str = Field(description="HTTP method (GET/POST/PUT/DELETE)")
    url: str = Field(description="URL to request")
    headers: dict = Field(default=None, description="Request headers")
    body: str = Field(default=None, description="Request body (JSON string)")


@tool(args_schema=HttpRequestInput)
def http_request(method: str, url: str, headers: dict = None, body: str = None) -> str:
    """Send an HTTP request and return status/headers/body."""
    try:
        kwargs = {"headers": headers or {}}
        if body and method.upper() in ("POST", "PUT", "PATCH"):
            kwargs["data"] = body
        response = requests.request(method, url, timeout=30, **kwargs)
        result = f"Status: {response.status_code}\nHeaders: {dict(response.headers)}\nBody: {response.text[:2000]}"
        return result
    except Exception as e:
        return f"Error: {e}"
