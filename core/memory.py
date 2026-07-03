import os
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.config import get_user_data_dir


class ConversationMemory:
    def __init__(self, max_history: int = 50, system_prompt: Optional[str] = None):
        self.max_history = max_history
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, Any]] = []
        self.conversations_dir = get_user_data_dir() / "conversations"
        self.conversations_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_name: Optional[str] = None

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        if role not in ("user", "assistant", "system", "tool"):
            raise ValueError(f"Unsupported role: {role}")
        
        message: Dict[str, Any] = {"role": role, "content": content}
        
        if role == "tool":
            if "tool_call_id" not in kwargs:
                raise ValueError("tool message requires tool_call_id parameter")
            message["tool_call_id"] = kwargs["tool_call_id"]
        
        if role == "assistant" and "tool_calls" in kwargs:
            message["tool_calls"] = kwargs["tool_calls"]
        
        self.messages.append(message)
        self._trim_history()

    def get_messages(self) -> List[Dict[str, Any]]:
        result = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        result.extend(self.messages)
        return result

    def clear(self) -> None:
        self.messages = []
        self.current_session_name = None

    def _trim_history(self) -> None:
        non_system = [m for m in self.messages if m["role"] != "system"]
        max_messages = self.max_history * 2
        if len(non_system) > max_messages:
            remove_count = len(non_system) - max_messages
            removed = 0
            new_messages = []
            for msg in self.messages:
                if msg["role"] != "system" and removed < remove_count:
                    removed += 1
                else:
                    new_messages.append(msg)
            self.messages = new_messages

    def estimate_tokens(self) -> int:
        total = 0
        for msg in self.get_messages():
            content = msg.get("content", "") or ""
            total += len(content) // 4
            if "tool_calls" in msg and msg["tool_calls"]:
                total += len(json.dumps(msg["tool_calls"])) // 4
        return total

    def _generate_session_name(self) -> str:
        for msg in self.messages:
            if msg["role"] == "user":
                content = msg["content"][:30].strip()
                content = "".join(c for c in content if c.isalnum() or c in (' ', '-', '_')).strip()
                if content:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    return f"{timestamp}_{content.replace(' ', '_')}"
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def save(self, name: Optional[str] = None) -> str:
        if name:
            safe_name = "".join(c for c in name if c.isalnum() or c in ('-', '_')).strip()
            filename = f"{safe_name}.json"
        else:
            if self.current_session_name:
                filename = f"{self.current_session_name}.json"
            else:
                filename = f"{self._generate_session_name()}.json"
                self.current_session_name = filename[:-5]
        
        save_data = {
            "saved_at": datetime.now().isoformat(),
            "max_history": self.max_history,
            "messages": self.messages
        }
        
        filepath = self.conversations_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        self.current_session_name = filename[:-5]
        return filename[:-5]

    def load(self, name: str) -> bool:
        filename = f"{name}.json" if not name.endswith(".json") else name
        filepath = self.conversations_dir / filename
        
        if not filepath.exists():
            return False
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.messages = data.get("messages", [])
        self.max_history = data.get("max_history", self.max_history)
        self.current_session_name = filename[:-5]
        return True

    def list_sessions(self) -> List[Dict[str, str]]:
        sessions = []
        for f in self.conversations_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                saved_at = data.get("saved_at", "")
                msg_count = len([m for m in data.get("messages", []) if m["role"] in ("user", "assistant")])
                first_user_msg = ""
                for m in data.get("messages", []):
                    if m["role"] == "user":
                        first_user_msg = m["content"][:50]
                        break
                sessions.append({
                    "name": f.stem,
                    "saved_at": saved_at,
                    "message_count": str(msg_count),
                    "preview": first_user_msg
                })
            except Exception:
                continue
        sessions.sort(key=lambda x: x["saved_at"], reverse=True)
        return sessions

    def delete_session(self, name: str) -> bool:
        filename = f"{name}.json" if not name.endswith(".json") else name
        filepath = self.conversations_dir / filename
        if filepath.exists():
            filepath.unlink()
            if self.current_session_name == name:
                self.current_session_name = None
            return True
        return False

    def build_system_prompt(self, tools_list: Optional[List[Dict[str, Any]]] = None) -> str:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        working_dir = os.getcwd()
        
        prompt = f"""你是 MINGCODE，一个专业的AI编码代理。永远使用中文回复。

从你启动编码代理的那一刻起，你就开始遵循以下工作流程：

【核心原则】
- TDD（测试驱动开发）：严格遵循 RED-GREEN-REFACTOR 循环——先写一个会失败的测试，观察它失败，写最小量的代码让它通过，重构，然后重复。删除测试前编写的任何代码。
- YAGNI（你不需要它）：只实现用户明确要求的功能，不做预测性扩展。
- DRY（不要重复自己）：每段知识/逻辑必须有一个单一、明确、权威的表示。
- 提交粒度：每个小任务完成后立即提交，提交信息清晰。

【工作流程阶段】

1. 头脑风暴阶段（默认启动状态）
   - 当用户说要构建某样东西时，不要直接写代码。退一步，先问用户到底想做什么。
   - 通过提问完善粗略想法，探索替代方案，澄清模糊需求。
   - 一次只问一个问题，不要一次抛出多个问题 overwhelm 用户。
   - 当从对话中提取出明确需求后，生成产品需求文档（spec），以足够短的片段形式分段展示给用户阅读和消化。
   - spec 内容包括：概述、目标、非目标、功能需求、验收标准。
   - 保存设计文档到 .trae/specs/ 目录。

2. 计划阶段（设计批准后激活）
   - 用户确认设计后，制定一份实施计划。
   - 思维树规划（强制）：制定计划时必须调用 plan_tot 工具，完成"思考（生成 3 个候选方案）→ 评估（对比优缺点）→ 筛选（选定最优）"的循环后，再基于最优方案输出 tasks.md。
   - 把工作分解成极小的任务（每个 2-5 分钟），让一个品味差、没有评判、没有项目背景且不喜欢测试的热情初级工程师都能理解。
   - 每个任务必须包含：精确的文件路径、完整的代码改动说明、验证步骤。
   - 保存 tasks.md 到 .trae/specs/ 目录。

3. 执行阶段（用户说"开始"后激活）
   - 行动前 Planning：动手写代码或调用工具前，若任务范围、目标或实现方式存在任何模糊，必须先用 ask_user 工具向用户提问，明确意图后再继续。
   - 待办清单追踪（强制）：执行多步骤任务时，必须用 todo 工具维护清单——开始任务前 add 并 update 到 in_progress，每完成一步 update 到 completed。让用户能通过 /todo 命令实时看到进度。简单单步任务可跳过。
   - 启动子代理驱动开发流程：每个任务派遣独立子代理执行。
   - 执行前：让子代理做两阶段审查——先检查是否符合规范，再检查代码质量。
   - 执行中：严格遵循 TDD 红-绿-重构。
   - 任务间：在进入下一个任务前，与计划进行审查，按严重程度报告问题。关键问题阻碍进展。
   - 你经常能独立工作几个小时，而不偏离用户制定的计划。

4. 完成阶段
   - 所有任务完成后，验证所有测试通过。
   - 提供选项给用户：合并到主分支/创建PR/保留分支/丢弃更改。
   - 清理工作树。

【工具使用】
- 你有工具可以执行shell命令、读写编辑文件、执行Python代码、搜索网络。
- 需要执行任务时，大胆使用工具。
- 执行shell命令前，评估命令的安全性，破坏性命令（如 rm -rf、format）需要向用户确认。
- ask_user 工具：行动前向用户提问以明确意图。任何非平凡任务（新建功能/修改逻辑/重构）开始前，必须先用 ask_user 提一个澄清问题，确认目标、范围或实现选择后再动手。一次只问一个问题，聚焦单一决策点；简单事实性回答或用户已明确指定的任务无需再问。
- plan_tot 工具：思维树规划。计划阶段必须调用此工具，让 LLM 生成 3 个候选方案、对比评估优缺点、筛选最优方案后输出可执行计划。完成"思考 → 评估 → 筛选"循环后再进入执行阶段，禁止跳过规划直接动手。
- todo 工具：跨会话持久化的待办清单。多步骤任务执行时必须主动维护：开始任务前 add 并 update 到 in_progress，完成后 update 到 completed。用户可通过 /todo 命令同步查看与操作，AI 与用户共享同一份清单。

当前时间: {current_time}
工作目录: {working_dir}

记住：你是一个严谨的工程师，不是一个草率的代码生成器。先想清楚，再写代码。"""

        if tools_list:
            prompt += "\n\n可用工具:\n"
            for tool in tools_list:
                func = tool.get("function", {})
                name = func.get("name", "unknown")
                desc = func.get("description", "No description")
                prompt += f"- {name}: {desc}\n"

        self.system_prompt = prompt
        return prompt
