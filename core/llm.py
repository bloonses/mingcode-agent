import json
import requests
from typing import Generator, Dict, List, Optional, Any


class LLMError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"LLM API Error {status_code}: {message}")


class StreamResponse:
    def __init__(self, generator):
        self._generator = generator
        self.final_message = None
    
    def __iter__(self):
        self.final_message = yield from self._generator


class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        llm_config = config.get("llm", config)
        self.base_url = llm_config["base_url"].rstrip("/")
        self.api_key = llm_config["api_key"]
        self.model = llm_config["model"]
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4096)
        self.timeout = 60
    
    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _build_payload(self, messages: List[Dict[str, Any]], tools: Optional[List] = None, stream: bool = False) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def _parse_tool_calls(self, raw_tool_calls: List[Dict]) -> List[Dict]:
        parsed = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            arguments_str = func.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {"_raw": arguments_str}
            parsed.append({
                "id": tc.get("id"),
                "type": tc.get("type", "function"),
                "function": {
                    "name": func.get("name", ""),
                    "arguments": arguments
                }
            })
        return parsed

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List] = None, stream: bool = False) -> Any:
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(messages, tools, stream)
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=self.timeout, stream=stream)
        except requests.exceptions.ConnectionError as e:
            if "10061" in str(e) or "Connection refused" in str(e) or "actively refused" in str(e):
                raise LLMError(0, f"无法连接到 LLM 服务: {self.base_url}\n\n"
                                   f"可能的原因：\n"
                                   f"  1. 本地 Ollama 未启动（默认配置指向 localhost:11434）\n"
                                   f"  2. API 地址配置错误\n"
                                   f"  3. 网络连接问题\n\n"
                                   f"解决方法：\n"
                                   f"  • 输入 /settings 配置云服务商（DeepSeek/OpenAI/Qwen等）\n"
                                   f"  • 或启动本地 Ollama 服务: ollama serve")
            raise LLMError(0, f"网络连接错误: {str(e)}\n\n请输入 /settings 检查你的 LLM 配置")
        except requests.exceptions.Timeout:
            raise LLMError(0, f"请求超时：连接 {self.base_url} 超时，请检查网络或稍后重试")
        except requests.exceptions.RequestException as e:
            raise LLMError(0, f"网络错误: {str(e)}")
        
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", response.text)
            except:
                error_msg = response.text
            raise LLMError(response.status_code, error_msg)
        
        if not stream:
            return self._handle_non_stream(response)
        else:
            return StreamResponse(self._handle_stream(response))

    def _handle_non_stream(self, response: requests.Response) -> Dict[str, Any]:
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        result = {
            "role": message.get("role", "assistant"),
            "content": message.get("content"),
            "tool_calls": None
        }
        if message.get("tool_calls"):
            result["tool_calls"] = self._parse_tool_calls(message["tool_calls"])
        return result

    def _handle_stream(self, response: requests.Response) -> Generator[str, None, Dict[str, Any]]:
        full_content = ""
        full_tool_calls = {}
        tool_call_indices = set()
        
        for line in response.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    
                    if delta.get("content"):
                        content_piece = delta["content"]
                        full_content += content_piece
                        yield content_piece
                    
                    if delta.get("tool_calls"):
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            tool_call_indices.add(idx)
                            if idx not in full_tool_calls:
                                full_tool_calls[idx] = {
                                    "id": None,
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }
                            if tc_delta.get("id"):
                                full_tool_calls[idx]["id"] = tc_delta["id"]
                            if tc_delta.get("type"):
                                full_tool_calls[idx]["type"] = tc_delta["type"]
                            if tc_delta.get("function"):
                                func_delta = tc_delta["function"]
                                if func_delta.get("name"):
                                    full_tool_calls[idx]["function"]["name"] += func_delta["name"]
                                if func_delta.get("arguments"):
                                    full_tool_calls[idx]["function"]["arguments"] += func_delta["arguments"]
                except json.JSONDecodeError:
                    continue
        
        result = {
            "role": "assistant",
            "content": full_content if full_content else None,
            "tool_calls": None
        }
        if tool_call_indices:
            raw_tool_calls = [full_tool_calls[i] for i in sorted(tool_call_indices)]
            result["tool_calls"] = self._parse_tool_calls(raw_tool_calls)
        return result
