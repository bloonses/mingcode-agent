"""
QQ 官方开放平台 Bot Client
通过 appid + secret 获取 AccessToken，WebSocket 接收事件，HTTP 发送消息。
支持扫码配置（scan-to-configure）：手机 QQ 扫码自动获取 AppID + Secret。
协议参考：Hermes Agent v0.11.0 gateway/platforms/qqbot/
文档: https://bot.q.qq.com/wiki/
"""
import base64
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List

import requests

from config.config import get_user_data_dir

logger = logging.getLogger(__name__)

OPENAPI_BASE = "https://api.sgroup.qq.com"
TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
PORTAL_HOST = "https://q.qq.com"
DEFAULT_INTENTS = (1 << 1) | (1 << 12) | (1 << 25)  # GROUP_AT_MESSAGE + DIRECT_MESSAGE + C2C_GROUP_AT_MESSAGES
HTTP_TIMEOUT = 15


class QQOfficialBot:
    """QQ 官方开放平台 Bot 客户端"""

    def __init__(self, config_path: Optional[Path] = None):
        self.appid: str = ""
        self.secret: str = ""
        self.token: str = ""          # 可选，Bot token 备用鉴权
        self.intents: int = DEFAULT_INTENTS
        self.sandbox: bool = False

        self._access_token: str = ""
        self._token_expires: float = 0.0
        self._ws_url: str = ""
        self._ws: Any = None
        self._thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._connected: bool = False
        self._seq: Optional[int] = None
        self._session_id: str = ""
        self._handler: Optional[Callable[[str, str, str, str], str]] = None

        if config_path is None:
            self.config_path = get_user_data_dir() / "qq_official_config.json"
        else:
            self.config_path = Path(config_path)

        self._load_config()

    # ---------- 配置持久化 ----------
    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                cfg = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.appid = cfg.get("appid", "")
                self.secret = cfg.get("secret", "")
                self.token = cfg.get("token", "")
                self.intents = cfg.get("intents", DEFAULT_INTENTS)
                self.sandbox = cfg.get("sandbox", False)
            except (json.JSONDecodeError, IOError):
                pass

    def _save_config(self) -> None:
        cfg = {
            "appid": self.appid,
            "secret": self.secret,
            "token": self.token,
            "intents": self.intents,
            "sandbox": self.sandbox,
        }
        self.config_path.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 状态 ----------
    @property
    def is_configured(self) -> bool:
        return bool(self.appid and self.secret)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_listening(self) -> bool:
        return self._running

    # ---------- AccessToken ----------
    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token
        try:
            resp = requests.post(TOKEN_URL, json={
                "appId": self.appid,
                "clientSecret": self.secret,
            }, timeout=HTTP_TIMEOUT)
            data = resp.json()
            self._access_token = data.get("access_token", "")
            expires_in = int(data.get("expires_in", 7200))
            self._token_expires = time.time() + expires_in
            return self._access_token
        except Exception as e:
            logger.error(f"getAppAccessToken error: {e}")
            return ""

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"QQBot {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    # ---------- HTTP API ----------
    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{OPENAPI_BASE}/{endpoint.lstrip('/')}"
        try:
            resp = requests.post(
                url, json=payload, headers=self._auth_headers(),
                timeout=HTTP_TIMEOUT,
            )
            text = resp.text.strip()
            if not text:
                return {"ok": resp.status_code == 200}
            return json.loads(text)
        except Exception as e:
            logger.error(f"Official HTTP {endpoint} error: {e}")
            return {"error": str(e)}

    def send_channel_message(self, channel_id: str, content: str, msg_id: str = "") -> bool:
        payload = {"content": content}
        if msg_id:
            payload["msg_id"] = msg_id
        r = self._post(f"/channels/{channel_id}/messages", payload)
        return "id" in r or "ok" in r

    def send_group_message(self, group_openid: str, content: str, msg_id: str = "") -> bool:
        payload = {"content": content, "msg_type": 0}
        if msg_id:
            payload["msg_id"] = msg_id
        r = self._post(f"/v2/groups/{group_openid}/messages", payload)
        return "ok" in r

    def send_c2c_message(self, openid: str, content: str, msg_id: str = "") -> bool:
        payload = {"content": content, "msg_type": 0}
        if msg_id:
            payload["msg_id"] = msg_id
        r = self._post(f"/v2/users/{openid}/messages", payload)
        return "ok" in r

    # ---------- WebSocket ----------
    def _get_ws_url(self) -> str:
        url = f"{OPENAPI_BASE}/gateway/bot"
        if self.sandbox:
            url = f"https://sandbox.api.sgroup.qq.com/gateway/bot"
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=HTTP_TIMEOUT)
            data = resp.json()
            return data.get("url", "")
        except Exception as e:
            logger.error(f"get gateway error: {e}")
            return ""

    def _send_ws(self, payload: Dict[str, Any]) -> None:
        try:
            self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"ws send error: {e}")

    def _identify(self) -> None:
        self._send_ws({
            "op": 2,
            "d": {
                "token": f"QQBot {self._get_access_token()}",
                "intents": self.intents,
                "shard": [0, 1],
            },
        })

    def _resume(self) -> None:
        if not self._session_id or self._seq is None:
            self._identify()
            return
        self._send_ws({
            "op": 6,
            "d": {
                "token": f"QQBot {self._get_access_token()}",
                "session_id": self._session_id,
                "seq": self._seq,
            },
        })

    def _heartbeat_loop(self) -> None:
        while self._running and self._connected:
            time.sleep(5)
            if not self._connected:
                break
            payload = {"op": 1}
            if self._seq is not None:
                payload["d"] = self._seq
            else:
                payload["d"] = None
            self._send_ws(payload)

    def _on_ws_open(self, ws):
        self._connected = True
        logger.info("Official WS connected")
        self._resume()

    def _on_ws_close(self, ws, *args):
        self._connected = False
        logger.info("Official WS closed")

    def _on_ws_error(self, ws, error):
        self._connected = False
        logger.error(f"Official WS error: {error}")

    def _on_ws_message(self, ws, message: str):
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return
        op = payload.get("op")
        d = payload.get("d", {})
        s = payload.get("s")
        if s is not None:
            self._seq = s

        if op == 10:  # Hello
            self._identify()
        elif op == 11:  # Heartbeat ACK
            pass
        elif op == 0:  # Dispatch
            t = payload.get("t")
            if t == "READY":
                self._session_id = d.get("session_id", "")
                logger.info("Official bot ready")
            elif t in ("MESSAGE_CREATE", "AT_MESSAGE_CREATE", "DIRECT_MESSAGE_CREATE",
                       "GROUP_AT_MESSAGE_CREATE", "C2C_MESSAGE_CREATE"):
                self._handle_message(t, d)

    def _handle_message(self, event_type: str, data: Dict[str, Any]) -> None:
        if not self._handler:
            return
        text = data.get("content", "").strip()
        if not text:
            return
        msg_id = data.get("id", "")
        if event_type in ("MESSAGE_CREATE", "AT_MESSAGE_CREATE"):
            channel_id = data.get("channel_id", "")
            user_id = data.get("author", {}).get("id", "")
            scope = "channel"
            target_id = channel_id
        elif event_type == "DIRECT_MESSAGE_CREATE":
            guild_id = data.get("guild_id", "")
            user_id = data.get("author", {}).get("id", "")
            # 私信需要先创建私信会话，简化处理：通过 channel_id 回复
            scope = "direct"
            target_id = data.get("channel_id", "") or guild_id
        elif event_type == "GROUP_AT_MESSAGE_CREATE":
            target_id = data.get("group_openid", "")
            user_id = data.get("author", {}).get("member_openid", "")
            scope = "group"
        else:  # C2C_MESSAGE_CREATE
            target_id = data.get("author", {}).get("user_openid", "")
            user_id = target_id
            scope = "c2c"

        # 去掉 @ 机器人 的前缀
        if text.startswith("<@") and ">" in text:
            text = text.split(">", 1)[1].strip()

        try:
            reply = self._handler(text, user_id, target_id, scope)
        except Exception as e:
            reply = f"[处理失败: {e}]"
        if not reply:
            return

        if scope == "channel":
            self.send_channel_message(target_id, reply, msg_id)
        elif scope == "direct":
            self.send_channel_message(target_id, reply, msg_id)
        elif scope == "group":
            self.send_group_message(target_id, reply, msg_id)
        elif scope == "c2c":
            self.send_c2c_message(target_id, reply, msg_id)

    def _listen_loop(self) -> None:
        try:
            from websocket import WebSocketApp
        except ImportError:
            logger.error("websocket-client not installed")
            self._running = False
            return
        while self._running:
            if not self._ws_url:
                self._ws_url = self._get_ws_url()
            if not self._ws_url:
                time.sleep(5)
                continue
            try:
                self._ws = WebSocketApp(
                    self._ws_url,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                self._heartbeat_thread = threading.Thread(
                    target=self._heartbeat_loop, daemon=True
                )
                self._heartbeat_thread.start()
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                logger.error(f"Official WS loop error: {e}")
            self._connected = False
            # 会话失效时清除以触发重新 IDENTIFY
            if self._running:
                time.sleep(3)

    def start_listening(self, handler: Callable[[str, str, str, str], str]) -> bool:
        """handler(text, user_id, target_id, scope) -> reply_text
        scope: channel / direct / group / c2c"""
        if not self.is_configured:
            return False
        if self._running:
            return True
        self._handler = handler
        self._running = True
        self._seq = None
        self._session_id = ""
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        return True

    def stop_listening(self) -> None:
        self._running = False
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
            self._heartbeat_thread = None

    def configure(self, appid: str, secret: str, token: str = "",
                  intents: Optional[int] = None, sandbox: bool = False) -> None:
        self.appid = appid.strip()
        self.secret = secret.strip()
        self.token = token.strip()
        if intents is not None:
            self.intents = intents
        self.sandbox = sandbox
        self._access_token = ""
        self._token_expires = 0.0
        self._ws_url = ""
        self._save_config()

    # ---------- 扫码配置（scan-to-configure） ----------
    def qr_login(self, print_qr: Optional[Callable[[str], None]] = None,
                 poll_timeout: int = 120) -> bool:
        """手机 QQ 扫码自动获取 AppID + Secret。
        print_qr 回调接收二维码 URL 字符串；登录成功后自动 configure 并保存。
        协议：q.qq.com/lite/create_bind_task + poll_bind_result，AES-256-GCM 解密。"""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            logger.error("cryptography not installed, cannot decrypt bind secret")
            return False

        # Step 1: 生成 AES-256 密钥
        aes_key_raw = os.urandom(32)
        aes_key_b64 = base64.b64encode(aes_key_raw).decode()

        # Step 2: 创建绑定任务
        try:
            resp = requests.post(
                f"{PORTAL_HOST}/lite/create_bind_task",
                json={"key": aes_key_b64},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=HTTP_TIMEOUT,
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"create_bind_task error: {e}")
            return False
        if data.get("retcode") != 0:
            logger.error(f"create_bind_task failed: {data}")
            return False
        task_id = data.get("data", {}).get("task_id", "")
        if not task_id:
            return False

        # Step 3: 生成二维码 URL 并显示
        qr_url = (
            f"{PORTAL_HOST}/qqbot/openclaw/connect.html"
            f"?task_id={task_id}&_wv=2&source=mingcode"
        )
        if print_qr:
            print_qr(qr_url)

        # Step 4: 轮询扫码结果
        deadline = time.time() + poll_timeout
        while time.time() < deadline:
            try:
                resp = requests.post(
                    f"{PORTAL_HOST}/lite/poll_bind_result",
                    json={"task_id": task_id},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                    timeout=HTTP_TIMEOUT,
                )
                rdata = resp.json()
            except Exception as e:
                logger.error(f"poll_bind_result error: {e}")
                time.sleep(2)
                continue
            if rdata.get("retcode") != 0:
                logger.error(f"poll_bind_result failed: {rdata}")
                return False
            d = rdata.get("data", {})
            status = d.get("status", 0)
            # status: 0=NONE, 1=PENDING, 2=COMPLETED, 3=EXPIRED
            if status == 2:
                bot_appid = d.get("bot_appid", "")
                encrypt_secret_b64 = d.get("bot_encrypt_secret", "")
                if not bot_appid or not encrypt_secret_b64:
                    return False
                # Step 5: AES-256-GCM 解密 client_secret
                try:
                    raw = base64.b64decode(encrypt_secret_b64)
                    iv, ct_tag = raw[:12], raw[12:]
                    client_secret = AESGCM(aes_key_raw).decrypt(iv, ct_tag, None).decode("utf-8")
                except Exception as e:
                    logger.error(f"AES decrypt error: {e}")
                    return False
                self.configure(bot_appid, client_secret)
                return True
            elif status == 3:
                return False
            time.sleep(2)
        return False

    def logout(self) -> None:
        self.stop_listening()
        self.appid = ""
        self.secret = ""
        self.token = ""
        self._access_token = ""
        self._token_expires = 0.0
        self._ws_url = ""
        self._session_id = ""
        self._seq = None
        if self.config_path.exists():
            self.config_path.unlink()
