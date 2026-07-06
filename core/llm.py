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
        # 推理模型思考深度（None / "low" / "medium" / "high"）
        raw_effort = llm_config.get("reasoning_effort")
        self.reasoning_effort = raw_effort if raw_effort in ("low", "medium", "high") else None
        # Token 消耗跟踪器（由 NeonAgent 注入）
        self.token_tracker = None

    def _record_usage(self, usage: Optional[Dict[str, Any]], prompt_text: str = "", completion_text: str = "") -> None:
        """把 API 返回的 usage 记录到 tracker；缺失时用估算兜底。"""
        if self.token_tracker is None:
            return
        if usage and isinstance(usage, dict) and usage.get("total_tokens") is not None:
            self.token_tracker.record(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens"),
                model=self.model,
            )
        else:
            # API 未返回 usage，用字符数估算兜底
            self.token_tracker.record_estimated(prompt_text, completion_text, self.model)
    
    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _extract_error_message(self, response: requests.Response) -> str:
        """健壮解析各种供应商的 4xx/5xx 错误响应体，返回可读字符串"""
        raw_text = response.text or ""
        try:
            data = response.json()
        except Exception:
            return raw_text[:500] or f"(empty body, status {response.status_code})"
        # 常见格式按优先级尝试
        if not isinstance(data, dict):
            return str(data)[:500]
        # 1. OpenAI 标准: {"error": {"message": "...", "type": "...", "code": "..."}}
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or ""
            etype = err.get("type") or ""
            code = err.get("code") or ""
            parts = []
            if msg: parts.append(msg)
            if etype: parts.append(f"type={etype}")
            if code: parts.append(f"code={code}")
            return " | ".join(parts) if parts else str(err)[:500]
        # 2. {"message": "..."}
        if data.get("message"):
            return str(data["message"])[:500]
        # 3. {"detail": "..."}
        if data.get("detail"):
            detail = data["detail"]
            return str(detail if isinstance(detail, str) else detail)[:500]
        # 4. {"msg": "..."}
        if data.get("msg"):
            return str(data["msg"])[:500]
        # 5. {"error": "string"} (非 dict)
        if isinstance(err, str) and err:
            return err[:500]
        # 6. Ollama: {"error": "..."} 有时在顶层
        # 7. fallback 到原始文本
        return raw_text[:500] or f"(empty body, status {response.status_code})"

    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """规范化 messages，修复各供应商（智谱 GLM code=1214 等）的格式要求。

        规则：
        - content 缺失或 None → ''（智谱不接受 null）
        - tool 角色空 content → 填充默认值（智谱不接受空 tool 结果）
        - assistant 带 tool_calls 时空 content → 保留 ''（合规）
        - list 形式的 content（多模态 image_url）→ 原样保留，不规范化
        """
        sanitized = []
        for msg in messages:
            new_msg = dict(msg)
            # 多模态 content 是 list，直接保留不规范化，避免破坏 image_url 结构
            if isinstance(new_msg.get("content"), list):
                sanitized.append(new_msg)
                continue
            if "content" not in new_msg or new_msg["content"] is None:
                new_msg["content"] = ""
            if new_msg["role"] == "tool" and not new_msg["content"]:
                new_msg["content"] = "(no output)"
            sanitized.append(new_msg)
        return sanitized

    def _build_payload(self, messages: List[Dict[str, Any]], tools: Optional[List] = None, stream: bool = False) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": self._sanitize_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream
        }
        if stream:
            # 请求流式响应中包含 usage（OpenAI 标准，部分供应商支持）
            payload["stream_options"] = {"include_usage": True}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.reasoning_effort:  # None 或空字符串都不传
            payload["reasoning_effort"] = self.reasoning_effort
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

    def chat_with_image(self, prompt: str, image_path: str, system: str = None) -> str:
        """多模态调用：发送图片+提示词，返回文本描述。

        不走 stream（vision 通常不需要流式）。LLMError 向上抛出，由调用方捕获降级。
        """
        import base64
        from pathlib import Path

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        })

        result = self.chat(messages, stream=False)
        return result.get("content") or ""

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
            error_msg = self._extract_error_message(response)
            raise LLMError(response.status_code, error_msg)
        
        if not stream:
            return self._handle_non_stream(response)
        else:
            return StreamResponse(self._handle_stream(response, messages))

    def _handle_non_stream(self, response: requests.Response) -> Dict[str, Any]:
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(response.status_code, f"LLM 返回空 choices（响应体: {str(data)[:300]}）")
        choice = choices[0]
        message = choice["message"]
        result = {
            "role": message.get("role", "assistant"),
            "content": message.get("content"),
            "tool_calls": None
        }
        if message.get("tool_calls"):
            result["tool_calls"] = self._parse_tool_calls(message["tool_calls"])
        # 提取 usage 并记录 token 消耗
        usage = data.get("usage")
        self._record_usage(usage, completion_text=result.get("content") or "")
        return result

    def _handle_stream(self, response: requests.Response, messages: List[Dict[str, Any]] = None) -> Generator[str, None, Dict[str, Any]]:
        full_content = ""
        full_tool_calls = {}
        tool_call_indices = set()
        stream_usage = None

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
                    # 流式 usage 通常在最后一个 chunk（choices 为空但 usage 存在）
                    if data.get("usage"):
                        stream_usage = data["usage"]
                    choice = (data.get("choices") or [{}])[0]
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
        # 记录流式调用的 token 消耗（messages 用于 usage 缺失时的 prompt 估算）
        prompt_text = ""
        if messages:
            prompt_text = " ".join(
                str(m.get("content") or "")
                for m in messages
                if isinstance(m.get("content"), str)
            )
        self._record_usage(stream_usage, prompt_text=prompt_text, completion_text=full_content)
        return result
