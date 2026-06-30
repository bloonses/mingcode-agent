"""
QQ OneBot 11 Client (正向 WebSocket)
对接本地运行的协议端：NapCat / Lagrange.OneBot / go-cqhttp 等。
MINGCODE 作为 WebSocket 客户端连接协议端，持续接收事件，
通过 HTTP POST 发送消息。
"""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Dict, Any

import requests

from config.config import get_user_data_dir

logger = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT = 15


class QQOneBot:
    """OneBot 11 正向 WS 客户端"""

    def __init__(self, config_path: Optional[Path] = None):
        self.ws_url: str = ""        # e.g. ws://127.0.0.1:3001
        self.access_token: str = ""
        self.self_id: str = ""       # 登录的 QQ 号
        self.http_base: str = ""     # HTTP API base，默认从 ws_url 推导
        self._ws: Any = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._connected: bool = False
        self._handler: Optional[Callable[[str, str, Optional[str]], str]] = None

        if config_path is None:
            self.config_path = get_user_data_dir() / "qq_onebot_config.json"
        else:
            self.config_path = Path(config_path)

        self._load_config()

    # ---------- 配置持久化 ----------
    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.ws_url = cfg.get("ws_url", "")
                self.access_token = cfg.get("access_token", "")
                self.self_id = cfg.get("self_id", "")
                self.http_base = cfg.get("http_base", "")
            except (json.JSONDecodeError, IOError):
                pass

    def _save_config(self) -> None:
        cfg = {
            "ws_url": self.ws_url,
            "access_token": self.access_token,
            "self_id": self.self_id,
            "http_base": self.http_base,
        }
        self.config_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 状态 ----------
    @property
    def is_configured(self) -> bool:
        return bool(self.ws_url)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_listening(self) -> bool:
        return self._running

    def _http_base(self) -> str:
        if self.http_base:
            return self.http_base.rstrip("/")
        # 从 ws_url 推导: ws://host:port -> http://host:port
        url = self.ws_url
        if url.startswith("wss://"):
            return "https://" + url[len("wss://"):].split("/", 1)[0]
        if url.startswith("ws://"):
            return "http://" + url[len("ws://"):].split("/", 1)[0]
        return ""

    def _http_headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    # ---------- HTTP API ----------
    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        base = self._http_base()
        if not base:
            return {"retcode": -1, "msg": "no http_base"}
        url = f"{base}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(
                url, json=payload, headers=self._http_headers(),
                timeout=DEFAULT_HTTP_TIMEOUT,
            )
            return resp.json() if resp.text else {}
        except Exception as e:
            logger.error(f"OneBot HTTP {endpoint} error: {e}")
            return {"retcode": -1, "msg": str(e)}

    def send_private(self, user_id: int, text: str) -> bool:
        r = self._post("send_private_msg", {
            "user_id": user_id, "message": text, "auto_escape": False
        })
        return r.get("retcode", -1) == 0

    def send_group(self, group_id: int, text: str) -> bool:
        r = self._post("send_group_msg", {
            "group_id": group_id, "message": text, "auto_escape": False
        })
        return r.get("retcode", -1) == 0

    # ---------- WebSocket 监听 ----------
    def _on_ws_open(self, ws):
        self._connected = True
        logger.info("OneBot WS connected")

    def _on_ws_close(self, ws, *args):
        self._connected = False
        logger.info("OneBot WS closed")

    def _on_ws_error(self, ws, error):
        self._connected = False
        logger.error(f"OneBot WS error: {error}")

    def _on_ws_message(self, ws, message: str):
        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            return
        if event.get("post_type") != "message":
            # 忽略元事件 (heartbeat/lifecycle)，但提取 self_id
            if event.get("post_type") == "meta_event":
                sid = event.get("self_id")
                if sid and not self.self_id:
                    self.self_id = str(sid)
                    self._save_config()
            return
        text = event.get("raw_message") or event.get("message", "")
        if isinstance(text, list):
            text = "".join(seg.get("data", {}).get("text", "") for seg in text if seg.get("type") == "text")
        user_id = event.get("user_id", 0)
        group_id = event.get("group_id")
        msg_type = event.get("message_type")
        if not text or not self._handler:
            return
        try:
            reply = self._handler(text, str(user_id), str(group_id) if group_id else None)
        except Exception as e:
            reply = f"[处理失败: {e}]"
        if not reply:
            return
        if msg_type == "group" and group_id:
            self.send_group(int(group_id), reply)
        elif msg_type == "private":
            self.send_private(int(user_id), reply)

    def _listen_loop(self) -> None:
        try:
            from websocket import WebSocketApp
        except ImportError:
            logger.error("websocket-client not installed")
            self._running = False
            return
        header = [f"Authorization: Bearer {self.access_token}"] if self.access_token else []
        while self._running:
            try:
                self._ws = WebSocketApp(
                    self.ws_url,
                    header=header,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"OneBot WS loop error: {e}")
            self._connected = False
            if self._running:
                time.sleep(3)  # 断线重连

    def start_listening(self, handler: Callable[[str, str, Optional[str]], str]) -> bool:
        """handler(text, user_id, group_id_or_None) -> reply_text"""
        if not self.is_configured:
            return False
        if self._running:
            return True
        self._handler = handler
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        return True

    def stop_listening(self) -> None:
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        self._connected = False

    def configure(self, ws_url: str, access_token: str = "", http_base: str = "") -> None:
        self.ws_url = ws_url.strip()
        self.access_token = access_token.strip()
        if http_base.strip():
            self.http_base = http_base.strip()
        else:
            self.http_base = ""
        self._save_config()

    def logout(self) -> None:
        self.stop_listening()
        self.ws_url = ""
        self.access_token = ""
        self.self_id = ""
        self.http_base = ""
        if self.config_path.exists():
            self.config_path.unlink()
