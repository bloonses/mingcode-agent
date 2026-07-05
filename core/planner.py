# core/planner.py 升级版
"""Planner - Phase 4 ToT 实现。

ToT 流程:
1. 生成 N 个候选方案（_generate_candidates）
2. 评估每个候选的分数（_evaluate_candidate）
3. 选分数最高的（_select_best）
"""
import json
import re
from typing import List, Dict, Optional, Any
from langchain_core.messages import HumanMessage, SystemMessage


class Planner:
    """Planner - ToT 任务规划。"""

    def __init__(self, llm, tot_candidates: int = 3):
        self.llm = llm
        self.tot_candidates = tot_candidates

    def invoke(self, user_input: str, feedback: Optional[List[str]] = None) -> List[Dict]:
        """生成任务列表 - ToT 流程。"""
        try:
            # 1. 生成候选
            candidates = self._generate_candidates(user_input, feedback)
            if len(candidates) <= 1:
                # 兜底：只生成一个，直接返回
                return candidates[0] if candidates else self._fallback_task(user_input)
            # 2. 评分
            scores = [self._evaluate_candidate(user_input, c) for c in candidates]
            # 3. 选最优
            return self._select_best(candidates, scores)
        except Exception:
            return self._fallback_task(user_input)

    def _generate_candidates(self, user_input: str, feedback: Optional[List[str]]) -> List[List[Dict]]:
        """生成 N 个候选方案。"""
        feedback_section = ""
        if feedback:
            feedback_str = "\n".join(f"- {f}" for f in feedback if f)
            feedback_section = f"\n\n之前失败反馈:\n{feedback_str}\n请避免重复错误。"
        prompt = f"""把以下任务拆解为子任务列表：

用户任务: {user_input}{feedback_section}

输出 JSON 数组，每个元素格式:
{{"id": 0, "desc": "任务描述", "status": "pending", "retries": 0, "feedback": null}}

只输出 JSON，不要其他文字。"""
        candidates = []
        for i in range(self.tot_candidates):
            try:
                response = self.llm.invoke([
                    SystemMessage(content=f"你是任务规划助手。生成方案 #{i+1}，尝试不同角度。"),
                    HumanMessage(content=prompt),
                ])
                content = getattr(response, "content", "") or ""
                tasks = self._parse_tasks(content, user_input)
                candidates.append(tasks)
            except Exception:
                continue
        return candidates

    def _evaluate_candidate(self, user_input: str, candidate: List[Dict]) -> float:
        """评估候选方案分数 0-1。"""
        try:
            candidate_str = json.dumps(candidate, ensure_ascii=False)
            prompt = f"""评估以下任务规划方案的质量：

用户任务: {user_input}
方案: {candidate_str}

评分标准（0-1）:
- 完整性：是否覆盖所有必需步骤
- 可执行性：步骤是否清晰可执行
- 合理性：顺序和依赖是否合理

只输出一个 0-1 的小数，不要其他文字。"""
            response = self.llm.invoke([
                SystemMessage(content="你是方案评估助手，输出 0-1 的分数。"),
                HumanMessage(content=prompt),
            ])
            content = getattr(response, "content", "") or ""
            content = content.strip()
            # 提取数字
            match = re.search(r"(\d+\.?\d*)", content)
            if match:
                score = float(match.group(1))
                return max(0.0, min(1.0, score))
            return 0.5
        except Exception:
            return 0.5

    def _select_best(self, candidates: List[List[Dict]], scores: List[float]) -> List[Dict]:
        """选分数最高的候选。"""
        if not candidates:
            return []
        best_idx = max(range(len(candidates)), key=lambda i: scores[i] if i < len(scores) else 0)
        return candidates[best_idx]

    def _parse_tasks(self, content: str, user_input: str) -> List[Dict]:
        """解析 LLM 输出为任务列表。"""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(l for l in lines if not l.startswith("```"))
        try:
            tasks = json.loads(content)
            if not isinstance(tasks, list):
                return self._fallback_task(user_input)
            for i, t in enumerate(tasks):
                t.setdefault("id", i)
                t.setdefault("status", "pending")
                t.setdefault("retries", 0)
                t.setdefault("feedback", None)
            return tasks
        except (json.JSONDecodeError, ValueError):
            return self._fallback_task(user_input)

    def _fallback_task(self, user_input: str) -> List[Dict]:
        """兜底：单个任务。"""
        return [{"id": 0, "desc": user_input, "status": "pending", "retries": 0, "feedback": None}]
