"""对话记忆 - 兼容 NeonAgent 接口。"""
import json
import os
from typing import List, Dict, Any, Optional


class ConversationMemory:
    """对话历史，带 max_history 截断和 JSON 持久化。"""

    def __init__(self, max_history: int = 50, save_file: Optional[str] = None):
        self.max_history = max_history
        self.save_file = save_file or os.path.join(os.path.expanduser("~"), ".mingcode-lc", "sessions.json")
        self.system_prompt: str = ""
        self._messages: List[Dict[str, Any]] = []

    def build_system_prompt(self, tool_schemas: List[Dict]):
        """根据工具 schema 构建 system prompt。"""
        tool_list = "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tool_schemas)
        self.system_prompt = f"""你是 MINGCODE-LC，一个赛博朋克风格的 AI 编码助手。

可用工具:
{tool_list}

工作原则:
1. 复杂任务先规划再执行
2. 严格遵循 TDD（RED-GREEN-REFACTOR）
3. 失败时反思并改进
4. 不确定时向用户提问
"""

    def add_message(self, role: str, content: str, **kwargs):
        """追加消息。"""
        msg = {"role": role, "content": content, **kwargs}
        self._messages.append(msg)
        non_system = [m for m in self._messages if m.get("role") != "system"]
        if len(non_system) > self.max_history:
            keep_ids = set(id(m) for m in non_system[-self.max_history:])
            self._messages = [m for m in self._messages if m.get("role") == "system" or id(m) in keep_ids]

    def get_messages(self) -> List[Dict[str, Any]]:
        """返回完整消息列表（含 system prompt）。"""
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self._messages)
        return msgs

    def clear(self):
        """清空对话（保留 system prompt）。"""
        self._messages = []

    def save(self, name: str):
        """保存会话到文件。"""
        os.makedirs(os.path.dirname(self.save_file), exist_ok=True)
        sessions = {}
        if os.path.exists(self.save_file):
            with open(self.save_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
        sessions[name] = self._messages
        with open(self.save_file, "w", encoding="utf-8") as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)

    def load(self, name: str):
        """加载会话。"""
        if not os.path.exists(self.save_file):
            return
        with open(self.save_file, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        if name in sessions:
            self._messages = sessions[name]

    def list_sessions(self) -> List[str]:
        """列出所有已保存会话。"""
        if not os.path.exists(self.save_file):
            return []
        with open(self.save_file, "r", encoding="utf-8") as f:
            return list(json.load(f).keys())

    def delete_session(self, name: str) -> bool:
        """删除会话。"""
        if not os.path.exists(self.save_file):
            return False
        with open(self.save_file, "r", encoding="utf-8") as f:
            sessions = json.load(f)
        if name in sessions:
            del sessions[name]
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            return True
        return False
