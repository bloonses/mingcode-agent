"""Planner - 任务规划器（含 ToT 思维树）。

Phase 3: ToT 多候选 → 评估 → 筛选最优 → 解析任务列表。
"""
import re
from typing import List, Dict, Optional


class Planner:
    def __init__(self, llm_client, tot_candidates: int = 3):
        self.llm = llm_client
        self.tot_candidates = tot_candidates

    def execute(self, user_input: str, feedback: Optional[List[str]] = None) -> List[Dict]:
        """生成任务列表（ToT 三步：候选 → 评估 → 筛选）。"""
        try:
            candidates = self._generate_candidates(user_input, feedback)
            if not candidates:
                # 兜底：返回单任务
                return [self._make_task(0, user_input)]

            scored = self._evaluate(candidates, user_input)
            best = self._select_best(scored)
            tasks = self._parse_to_tasks(best, user_input)

            if not tasks:
                # 解析失败兜底
                return [self._make_task(0, user_input)]
            return tasks
        except Exception:
            # 任何异常兜底返回单任务
            return [self._make_task(0, user_input)]

    def _generate_candidates(self, user_input: str, feedback: Optional[List[str]]) -> List[str]:
        """调 LLM 生成 N 个候选计划。"""
        feedback_section = ""
        if feedback:
            feedback_section = "\n\n上次执行失败的反馈：\n"
            for i, fb in enumerate(feedback, 1):
                feedback_section += f"{i}. {fb}\n"
            feedback_section += "请基于反馈重新规划，避免重复失败。\n"

        prompt = (
            f"用户需求: {user_input}{feedback_section}\n\n"
            f"请生成 {self.tot_candidates} 个不同的执行计划候选。\n"
            f"每个候选用 === Candidate N === 分隔，格式：\n"
            f"=== Candidate 1 ===\n1. 步骤一\n2. 步骤二\n"
            f"=== Candidate 2 ===\n1. 步骤一\n2. 步骤二\n"
            f"...\n\n"
            f"要求：\n"
            f"- 每个候选思路不同（激进/保守/折中）\n"
            f"- 每个候选 1-5 个步骤\n"
            f"- 每个步骤可由 ReAct Agent 独立完成"
        )
        response = self.llm.chat([
            {"role": "user", "content": prompt}
        ], stream=False)
        content = response.get("content", "")
        return self._split_candidates(content)

    def _split_candidates(self, content: str) -> List[str]:
        """把 LLM 输出按 === Candidate N === 分隔为候选列表。"""
        if not content or not content.strip():
            return []
        # 用 === Candidate 分隔
        parts = re.split(r"===\s*Candidate\s*\d+\s*===\s*", content)
        # 第一项通常是空字符串（=== 前没内容）
        candidates = [p.strip() for p in parts if p.strip()]
        return candidates

    def _evaluate(self, candidates: List[str], user_input: str) -> List[Dict]:
        """调 LLM 评估每个候选（评分 + 理由）。"""
        if not candidates:
            return []
        try:
            candidates_text = ""
            for i, c in enumerate(candidates, 1):
                candidates_text += f"Candidate {i}:\n{c}\n\n"

            prompt = (
                f"用户需求: {user_input}\n\n"
                f"候选计划:\n{candidates_text}\n"
                f"评估每个候选的质量（1-10 分），考虑：\n"
                f"- 任务拆分合理性\n"
                f"- 步骤可执行性\n"
                f"- 风险与复杂度\n\n"
                f"按以下格式输出：\n"
                f"Candidate 1: score=N\n"
                f"Candidate 2: score=N\n"
                f"..."
            )
            response = self.llm.chat([
                {"role": "user", "content": prompt}
            ], stream=False)
            content = response.get("content", "")
            return self._parse_evaluations(content, candidates)
        except Exception:
            # LLM 失败兜底：全部给默认分 0
            return [{"plan": c, "score": 0} for c in candidates]

    def _parse_evaluations(self, content: str, candidates: List[str]) -> List[Dict]:
        """解析 LLM 评估输出为 [{plan, score}]。"""
        scored = []
        for i, plan in enumerate(candidates, 1):
            # 找 "Candidate N: score=M" 模式
            pattern = rf"Candidate\s*{i}\s*:\s*score\s*=\s*(\d+)"
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                score = int(match.group(1))
            else:
                score = 0  # 解析失败默认 0
            scored.append({"plan": plan, "score": score})
        return scored

    def _select_best(self, scored: List[Dict]) -> str:
        """选评分最高的候选。平分时选第一个。"""
        if not scored:
            return ""
        return max(scored, key=lambda x: x["score"])["plan"]

    def _parse_to_tasks(self, plan: str, original_input: str) -> List[Dict]:
        """把计划文本解析为任务列表。"""
        if not plan or not plan.strip():
            return []
        tasks = []
        lines = plan.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 解析 "1. 任务描述" 或 "- 任务描述" 或 "* 任务描述"
            desc = line
            for prefix in ["1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.", "- ", "* "]:
                if line.startswith(prefix + " "):
                    desc = line[len(prefix):].strip()
                    break
            if desc:
                tasks.append(self._make_task(len(tasks), desc))
        return tasks

    def _make_task(self, task_id: int, desc: str) -> Dict:
        """构造任务 dict。"""
        return {
            "id": task_id,
            "desc": desc,
            "status": "pending",
            "retries": 0,
            "feedback": None,
        }
