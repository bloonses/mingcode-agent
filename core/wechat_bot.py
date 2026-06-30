"""
WeChat ClawBot (iLink Bot API) Client
基于腾讯官方 iLink 协议，实现微信个人账号 Bot 收发消息。
协议文档逆向自 @tencent-weixin/openclaw-weixin npm 包。
"""
import base64
import json
import logging
import os
import random
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List

import requests

from config.config import get_user_data_dir

logger = logging.getLogger(__name__)

ILINK_BASE = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "1.0.3"


class WeChatBot:
    """微信 iLink Bot 客户端"""

    def __init__(self, config_path: Optional[Path] = None):
        self.base = ILINK_BASE
        self.token: str = ""
        self.bot_id: str = ""
        self.user_id: str = ""
        self.context_tokens: Dict[str, str] = {}
        self._cursor: str = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handler: Optional[Callable[[str, str], str]] = None

        if config_path is None:
            self.config_path = get_user_data_dir() / "wechat_config.json"
        else:
            self.config_path = Path(config_path)

        self._load_config()

    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.token = cfg.get("token", "")
                self.bot_id = cfg.get("bot_id", "")
                self.user_id = cfg.get("user_id", "")
                self.context_tokens = cfg.get("context_tokens", {})
            except (json.JSONDecodeError, IOError):
                pass

    def _save_config(self) -> None:
        cfg = {
            "token": self.token,
            "bot_id": self.bot_id,
            "user_id": self.user_id,
            "context_tokens": self.context_tokens,
        }
        self.config_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @property
    def is_logged_in(self) -> bool:
        return bool(self.token)

    def _headers(self) -> Dict[str, str]:
        uin = base64.b64encode(
            str(random.randint(0, 0xFFFFFFFF)).encode()
        ).decode()
        return {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "Authorization": f"Bearer {self.token}",
            "X-WECHAT-UIN": uin,
        }

    def _post(self, endpoint: str, body: Dict[str, Any]) -> Dict[str, Any]:
        body["base_info"] = {"channel_version": CHANNEL_VERSION}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = self._headers()
        headers["Content-Length"] = str(len(raw))
        resp = requests.post(
            f"{self.base}/ilink/bot/{endpoint}",
            data=raw,
            headers=headers,
            timeout=35,
        )
        text = resp.text.strip()
        if text and text != "{}":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"ret": -1, "raw": text}
        return {"ret": 0}

    def login(self, print_qr: Optional[Callable[[str], None]] = None) -> bool:
        """扫码登录，返回是否成功"""
        try:
            resp = requests.get(
                f"{self.base}/ilink/bot/get_bot_qrcode?bot_type=3",
                timeout=15,
            )
            data = resp.json()
            qrcode_key = data.get("qrcode", "")
            qrcode_url = data.get("qrcode_img_content", "")

            if not qrcode_url:
                if print_qr:
                    print_qr("")
                return False

            if print_qr:
                print_qr(qrcode_url)

            while True:
                status_resp = requests.get(
                    f"{self.base}/ilink/bot/get_qrcode_status?qrcode={qrcode_key}",
                    headers={"iLink-App-ClientVersion": "1"},
                    timeout=40,
                )
                status = status_resp.json()
                status_val = status.get("status", "")

                if status_val == "scaned":
                    if print_qr:
                        print_qr("SCANED")
                elif status_val == "confirmed":
                    self.token = status.get("bot_token", "")
                    self.bot_id = status.get("ilink_bot_id", "")
                    self.user_id = status.get("ilink_user_id", "")
                    self._save_config()
                    return True
                elif status_val == "expired":
                    return False

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def get_updates(self) -> List[Dict[str, Any]]:
        """长轮询拉取新消息，自动更新 context_token"""
        result = self._post("getupdates", {"get_updates_buf": self._cursor})
        self._cursor = result.get("get_updates_buf", self._cursor)
        msgs = result.get("msgs", [])
        for msg in msgs:
            ct = msg.get("context_token", "")
            from_user = msg.get("from_user_id", "")
            if ct and from_user:
                self.context_tokens[from_user] = ct
                self._save_config()
        return msgs

    def send_message(
        self,
        text: str,
        to_user_id: Optional[str] = None,
        context_token: Optional[str] = None,
    ) -> bool:
        """发送文本消息"""
        target = to_user_id or self.user_id
        ct = context_token or self.context_tokens.get(target, "")
        if not ct:
            logger.warning("No context_token for target, message may not deliver")
            return False

        body = {
            "msg": {
                "from_user_id": "",
                "to_user_id": target,
                "client_id": f"mingcode-{uuid.uuid4().hex[:12]}",
                "message_type": 2,
                "message_state": 2,
                "context_token": ct,
                "item_list": [{"type": 1, "text_item": {"text": text}}],
            }
        }
        result = self._post("sendmessage", body)
        return result.get("ret", 0) == 0

    def send_typing(self, to_user_id: Optional[str] = None) -> None:
        """发送"正在输入"状态"""
        target = to_user_id or self.user_id
        ct = self.context_tokens.get(target, "")
        if not ct:
            return
        try:
            self._post("sendtyping", {
                "to_user_id": target,
                "context_token": ct,
            })
        except Exception:
            pass

    def _listen_loop(self) -> None:
        """后台监听循环"""
        while self._running:
            try:
                msgs = self.get_updates()
                for msg in msgs:
                    from_user = msg.get("from_user_id", "")
                    text = ""
                    for item in msg.get("item_list", []):
                        if item.get("type") == 1:
                            text = item.get("text_item", {}).get("text", "")
                    if text and from_user and self._handler:
                        self.send_typing(from_user)
                        reply = self._handler(text, from_user)
                        if reply:
                            self.send_message(reply, to_user_id=from_user)
            except Exception as e:
                logger.error(f"Listen error: {e}")
                time.sleep(5)

    def start_listening(self, handler: Callable[[str, str], str]) -> bool:
        """启动后台监听线程，handler 接收 (text, from_user) 返回回复文本"""
        if not self.is_logged_in:
            return False
        if self._running:
            return True
        self._handler = handler
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        return True

    def stop_listening(self) -> None:
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    @property
    def is_listening(self) -> bool:
        return self._running

    def logout(self) -> None:
        """登出，清除凭据"""
        self.stop_listening()
        self.token = ""
        self.bot_id = ""
        self.user_id = ""
        self.context_tokens = {}
        self._cursor = ""
        if self.config_path.exists():
            self.config_path.unlink()
