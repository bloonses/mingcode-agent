# CognitiveController Phase 3: Thinking (ToT) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Planner 内嵌 ToT（生成 N 候选 → 评估 → 筛选最优），提升规划质量；plan_tot 工具改为 Planner 薄包装（DRY）。

**Architecture:** Planner.execute 扩展为 3 步：`_generate_candidates`（调 LLM 生成 N 个候选计划）→ `_evaluate`（调 LLM 评分 + 理由）→ `_select_best`（选最高分）→ `_parse_to_tasks`（解析为任务列表）。重规划时 feedback 喂给候选生成 prompt。`tools/plan_tot.py` 改为调 `Planner.execute`，删除原有 ToT 逻辑。

**Tech Stack:** Python 3.8+ / pytest / requests

**Spec:** [docs/superpowers/specs/2026-07-04-cognitive-controller-design.md](file:///c:/Users/bloon/Downloads/neon_agent/docs/superpowers/specs/2026-07-04-cognitive-controller-design.md)

**Prerequisite:** Phase 1 + Phase 2 已完成（147 测试通过）

---

## 文件结构

| 文件 | 操作 | 责任 |
|------|------|------|
| `core/planner.py` | 修改 | 内嵌 ToT 3 步逻辑 |
| `tools/plan_tot.py` | 修改 | 改为 Planner 薄包装 |
| `tests/test_planner.py` | 修改 | 加 ToT 测试 |
| `tests/test_plan_tot.py` | 修改 | 更新薄包装测试（如已存在） |

---

## Task 1: TDD - 写 Planner ToT 测试

**Files:**
- Modify: `tests/test_planner.py`

- [ ] **Step 1: 在 test_planner.py 末尾追加 ToT 测试**

```python
class TestPlannerToT:
    """Phase 3: ToT 多候选 → 评估 → 筛选。"""

    def test_generate_candidates_returns_n(self):
        """_generate_candidates 应返回 tot_candidates 个候选。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=3)
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B\n=== Candidate 3 ===\nplan C"}
        with patch.object(planner.llm, 'chat', return_value=fake_response):
            candidates = planner._generate_candidates("input", None)
        assert len(candidates) == 3
        assert "plan A" in candidates[0]
        assert "plan B" in candidates[1]
        assert "plan C" in candidates[2]

    def test_generate_candidates_with_feedback(self):
        """_generate_candidates 应把 feedback 塞进 prompt。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B"}
        with patch.object(planner.llm, 'chat', return_value=fake_response) as mock_chat:
            planner._generate_candidates("input", ["上次失败：xxx"])
        # 验证 prompt 含 feedback
        call_args = mock_chat.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "上次失败" in prompt_text

    def test_evaluate_scores_each_candidate(self):
        """_evaluate 应为每个候选返回 dict 含 score。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        candidates = ["plan A", "plan B", "plan C"]
        fake_eval_response = {"content": "Candidate 1: score=7\nCandidate 2: score=9\nCandidate 3: score=5"}
        with patch.object(planner.llm, 'chat', return_value=fake_eval_response):
            scored = planner._evaluate(candidates, "input")
        assert len(scored) == 3
        for item in scored:
            assert "plan" in item
            assert "score" in item
            assert isinstance(item["score"], (int, float))
        # 验证评分正确解析
        assert scored[0]["score"] == 7
        assert scored[1]["score"] == 9
        assert scored[2]["score"] == 5

    def test_select_best_picks_highest_score(self):
        """_select_best 应选评分最高的候选。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        scored = [
            {"plan": "A", "score": 7},
            {"plan": "B", "score": 9},
            {"plan": "C", "score": 5},
        ]
        best = planner._select_best(scored)
        assert best == "B"

    def test_evaluate_llm_failure_returns_default_scores(self):
        """_evaluate LLM 失败时应兜底返回默认评分（全部 score=0）。"""
        from core.planner import Planner
        planner = Planner(MagicMock())
        candidates = ["plan A", "plan B"]
        with patch.object(planner.llm, 'chat', side_effect=Exception("network error")):
            scored = planner._evaluate(candidates, "input")
        assert len(scored) == 2
        for item in scored:
            assert item["score"] == 0  # 兜底默认分

    def test_execute_uses_tot_pipeline(self):
        """execute 应调用 _generate_candidates → _evaluate → _select_best。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        with patch.object(planner, '_generate_candidates', return_value=["plan A", "plan B"]) as mock_gen:
            with patch.object(planner, '_evaluate', return_value=[
                {"plan": "plan A", "score": 7},
                {"plan": "plan B", "score": 9},
            ]) as mock_eval:
                with patch.object(planner, '_select_best', return_value="plan B") as mock_select:
                    with patch.object(planner, '_parse_to_tasks', return_value=[{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]) as mock_parse:
                        planner.execute("input")
        mock_gen.assert_called_once()
        mock_eval.assert_called_once()
        mock_select.assert_called_once()
        mock_parse.assert_called_once_with("plan B")

    def test_fewer_candidates_than_requested(self):
        """LLM 生成少于 N 个候选时应正常处理（不报错）。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=3)
        # 只生成 2 个候选
        fake_response = {"content": "=== Candidate 1 ===\nplan A\n=== Candidate 2 ===\nplan B"}
        with patch.object(planner.llm, 'chat', return_value=fake_response):
            candidates = planner._generate_candidates("input", None)
        assert len(candidates) == 2  # 实际生成的数量

    def test_empty_candidates_falls_back_to_single_task(self):
        """所有候选都为空时应兜底返回单任务。"""
        from core.planner import Planner
        planner = Planner(MagicMock(), tot_candidates=2)
        # 候选生成返回空
        with patch.object(planner, '_generate_candidates', return_value=[]):
            tasks = planner.execute("做点什么")
        assert len(tasks) == 1
        assert tasks[0]["desc"] == "做点什么"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_planner.py::TestPlannerToT -v`
Expected: 8 FAIL（Phase 1 Planner 没有 _generate_candidates / _evaluate / _select_best 方法）

- [ ] **Step 3: Commit**

```bash
git add tests/test_planner.py
git commit -m "test: add failing Planner ToT tests (RED)"
```

---

## Task 2: 实现 Planner ToT（GREEN）

**Files:**
- Modify: `core/planner.py`

- [ ] **Step 1: 替换 core/planner.py 为 ToT 版本**

```python
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
```

- [ ] **Step 2: 跑 Planner 测试确认全 PASS**

Run: `python -m pytest tests/test_planner.py -v`
Expected: 12 PASSED（4 Phase 1 + 8 Phase 3）

- [ ] **Step 3: Commit**

```bash
git add core/planner.py
git commit -m "feat(planner): implement ToT pipeline (Phase 3)"
```

---

## Task 3: TDD - 写 plan_tot 工具薄包装测试

**Files:**
- Modify: `tests/test_plan_tot.py`（如不存在则创建）

- [ ] **Step 1: 检查现有 test_plan_tot.py 是否存在**

Run: `python -m pytest tests/test_plan_tot.py -v --collect-only`

如果文件不存在或测试为空，创建新文件：

```python
"""plan_tot 工具薄包装测试（Phase 3: 改为调 Planner）。"""
import pytest
from unittest.mock import MagicMock, patch


class TestPlanToTToolThinWrapper:
    def test_execute_calls_planner(self):
        """plan_tot.execute 应调 Planner.execute（薄包装）。"""
        from tools.plan_tot import PlanToTTool
        mock_planner = MagicMock()
        mock_planner.execute.return_value = [{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]
        tool = PlanToTTool(planner=mock_planner)
        result = tool.execute(input="写个贪吃蛇")
        mock_planner.execute.assert_called_once_with("写个贪吃蛇")
        assert "t1" in result

    def test_execute_no_planner_creates_default(self):
        """无 planner 参数时应内部构造默认 Planner。"""
        from tools.plan_tot import PlanToTTool
        tool = PlanToTTool(llm_client=MagicMock())
        assert tool._planner is not None

    def test_execute_returns_string(self):
        """execute 应返回字符串（工具协议）。"""
        from tools.plan_tot import PlanToTTool
        mock_planner = MagicMock()
        mock_planner.execute.return_value = [{"id": 0, "desc": "t1", "status": "pending", "retries": 0, "feedback": None}]
        tool = PlanToTTool(planner=mock_planner)
        result = tool.execute(input="test")
        assert isinstance(result, str)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_plan_tot.py -v`
Expected: FAIL（现有 PlanToTTool 没有 planner 参数）

- [ ] **Step 3: Commit**

```bash
git add tests/test_plan_tot.py
git commit -m "test: add failing plan_tot thin wrapper tests (RED)"
```

---

## Task 4: 实现 plan_tot 工具薄包装（GREEN）

**Files:**
- Modify: `tools/plan_tot.py`

- [ ] **Step 1: 读现有 tools/plan_tot.py**

Run: 用 Read 工具读 `c:\Users\bloon\Downloads\neon_agent\tools\plan_tot.py`

- [ ] **Step 2: 替换为薄包装版本**

```python
"""plan_tot 工具 - 调用 Planner 薄包装（Phase 3 DRY）。

Phase 1/2: 内含 ToT 逻辑
Phase 3: 改为调用 core.planner.Planner.execute，DRY
"""
from .base import BaseTool


class PlanToTTool(BaseTool):
    name = "plan_tot"
    description = (
        "使用思维树（ToT）生成任务计划。生成多个候选计划，评估后选最优。"
        "输入用户需求，返回任务列表。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "用户需求描述"
            }
        },
        "required": ["input"]
    }

    def __init__(self, planner=None, llm_client=None):
        """planner 可注入；不注入时用 llm_client 构造默认 Planner。"""
        self._planner = planner
        self._llm_client = llm_client

    def execute(self, **kwargs) -> str:
        input_text = kwargs.get("input", "")
        if not input_text:
            return "Error: input is required"

        planner = self._get_planner()
        tasks = planner.execute(input_text)
        return str(tasks)

    def _get_planner(self):
        """延迟构造 Planner（避免循环依赖）。"""
        if self._planner is None:
            from core.planner import Planner
            if self._llm_client is None:
                raise RuntimeError("planner or llm_client required")
            self._planner = Planner(self._llm_client)
        return self._planner
```

- [ ] **Step 3: 跑 plan_tot 测试确认 PASS**

Run: `python -m pytest tests/test_plan_tot.py -v`
Expected: 3 PASSED

- [ ] **Step 4: Commit**

```bash
git add tools/plan_tot.py
git commit -m "feat(plan_tot): refactor to thin wrapper around Planner (Phase 3 DRY)"
```

---

## Task 5: 集成测试 + 现有测试回归验证

- [ ] **Step 1: 跑全套测试**

Run: `python -m pytest tests/ -q --tb=short`
Expected: 158 passed（147 + 8 ToT + 3 plan_tot wrapper）

- [ ] **Step 2: 检查现有 test_plan_tot 老测试是否需要更新**

如果现有 test_plan_tot.py 有其他测试引用旧 API，更新或删除。

- [ ] **Step 3: 手动验证 ToT 提升**

启动 `python main.py`，输入复杂任务（如 "写一个 Web 爬虫"），观察：
- Planner 生成 3 个候选计划
- 评估后选最优
- 拆解为任务列表
- 逐个执行

- [ ] **Step 4: Commit（如有调整）**

```bash
git add -A
git commit -m "chore: Phase 3 integration verification"
```

---

## Phase 3 完成验收

- [ ] Planner 实现 ToT 3 步（候选 → 评估 → 筛选）
- [ ] _generate_candidates 生成 N 候选（N 可配）
- [ ] _evaluate LLM 评分 + 理由
- [ ] _select_best 选最高分
- [ ] 候选数少于 N 时正常处理
- [ ] 候选空时兜底单任务
- [ ] LLM 评估失败时兜底默认分
- [ ] plan_tot 工具改为薄包装（DRY）
- [ ] 重规划时 feedback 喂给候选生成 prompt
- [ ] 全部测试通过（158 个）
- [ ] 现有 147 个测试无回归
