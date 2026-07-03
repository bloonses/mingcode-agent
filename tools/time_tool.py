"""TimeTool - 时间日期工具。

action 路由：
- now: 当前时间（可选 timezone 参数）
- format: 自定义 strftime 格式化
- diff: 计算两个时间差
- timestamp: Unix 时间戳转可读
"""
from datetime import datetime, timezone
from typing import Optional

from .base import BaseTool


class TimeTool(BaseTool):
    name = "time"
    description = (
        "获取当前时间或计算时间差。支持 action："
        "now（当前时间，可选 timezone 参数如 'Asia/Shanghai'）/ "
        "format（自定义 strftime 格式）/ "
        "diff（计算两个 ISO 时间差）/ "
        "timestamp（Unix 时间戳转可读时间）。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["now", "format", "diff", "timestamp"],
                "description": "操作类型"
            },
            "timezone": {
                "type": "string",
                "description": "action=now 时可选，IANA 时区名如 'Asia/Shanghai'、'UTC'、'America/New_York'"
            },
            "fmt": {
                "type": "string",
                "description": "action=format 时必填，strftime 格式如 '%Y-%m-%d %H:%M:%S'"
            },
            "start": {
                "type": "string",
                "description": "action=diff 时必填，开始时间 ISO 格式"
            },
            "end": {
                "type": "string",
                "description": "action=diff 时必填，结束时间 ISO 格式"
            },
            "ts": {
                "type": "number",
                "description": "action=timestamp 时必填，Unix 时间戳"
            }
        },
        "required": ["action"]
    }

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()

        if action == "now":
            return self._now(kwargs.get("timezone"))
        if action == "format":
            return self._format(kwargs.get("fmt"))
        if action == "diff":
            return self._diff(kwargs.get("start"), kwargs.get("end"))
        if action == "timestamp":
            return self._timestamp(kwargs.get("ts"))
        return f"Error: unknown action '{action}'. Supported: now/format/diff/timestamp"

    def _now(self, tz_name: Optional[str]) -> str:
        if not tz_name:
            return datetime.now().isoformat()
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
            return datetime.now(tz).isoformat()
        except ImportError:
            return f"Error: zoneinfo not available (Python 3.9+ required). Now (local): {datetime.now().isoformat()}"
        except Exception as e:
            return f"Error: invalid timezone '{tz_name}': {e}"

    def _format(self, fmt: Optional[str]) -> str:
        if not fmt:
            return "Error: fmt is required for format action"
        try:
            return datetime.now().strftime(fmt)
        except Exception as e:
            return f"Error: invalid format: {e}"

    def _diff(self, start: Optional[str], end: Optional[str]) -> str:
        if not start or not end:
            return "Error: start and end are required for diff action"
        try:
            s = datetime.fromisoformat(start.replace("Z", "+00:00"))
            e = datetime.fromisoformat(end.replace("Z", "+00:00"))
            delta = e - s
            days = delta.days
            seconds = delta.seconds
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{days}d {hours}h {minutes}m {seconds}s (total {delta.total_seconds()} seconds)"
        except Exception as e:
            return f"Error: parse failed: {e}"

    def _timestamp(self, ts) -> str:
        if ts is None:
            return "Error: ts is required for timestamp action"
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            return f"UTC: {dt.isoformat()}\nLocal: {dt.astimezone().isoformat()}"
        except Exception as e:
            return f"Error: invalid timestamp: {e}"
