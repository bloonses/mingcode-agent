# CognitiveController（四框架综合认知框架）设计文档

**日期**：2026-07-04
**版本**：v1.2.0（计划）
**作者**：MINGCODE

---

## 1. 背景与目标

### 1.1 现状

MINGCODE v1.1.1 使用单一 ReAct 循环（[core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) 第 89-110 行），线性执行 Thought → Action → Observation，max_iterations=25。已有 `plan_tot` 工具（思维树单次调用）和 `ask_user` 工具，但都是 LLM 自主调用的零散工具，未集成到统一认知框架。

### 1.2 目标

实现 **CognitiveController** 状态机，综合 4 种认知框架：

1. **Plan-and-Execute**：先拆任务再逐个执行
2. **Self-Reflection**：执行后反思，失败可重规划
3. **Thinking (ToT)**：规划时生成多候选并选最优
4. **Self-Ask**：执行中遇不确定自动向用户提问

### 1.3 非目标（YAGNI）

- 不实现 checkpoint / 状态持久化（留接口，v1.0.0 不做）
- 不实现 ToT 并行候选生成（串行即可）
- 不实现 Reflector 用 ToT（评估是单次判断）
- 不实现任务间依赖图（线性任务列表足够）
- 不实现 human-in-the-loop 中断（Ctrl+C 即可）
- 不更新学习路线（新阶段后续单独更新）
- 不 bump 版本号（Phase 1-4 全部完成后再 bump 到 v1.2.0）

---

## 2. 架构决策

### 2.1 5 个核心决策（brainstorming 阶段确定）

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 融合深度 | C 完整重写（状态机驱动） | 四框架都真正集成，可扩展 |
| 任务分解 | 按框架逐个加（4 阶段） | 每阶段可用、风险最低、可独立验证 |
| Plan 触发 | LLM 判断 simple/complex | 成本可忽略、准确率高、可在 config 加 always_plan |
| Reflect 失败 | 局部重试 + 分级降级 L1/L2/L3 | 保留进度、cost 受控、不死锁 |
| Self-Ask 触发 | Execute 内嵌不确定性检测 | 真正的 Self-Ask 框架、~100 token 成本极低 |
| ToT 集成 | Planner 内嵌 ToT 逻辑 | ToT 本质是 Planner 该做的事、参数可配置、DRY |

### 2.2 状态机

```
User Input
    ↓
[CLASSIFY] ← LLM 轻量分类 (~200 token)
    ├── simple → 现有 ReAct 直走
    └── complex ↓
[PLANNING] ← ToT: 3 候选 → 评估 → 筛选 → 任务列表
    ↓ plan: [T1, T2, T3]
[EXECUTING] ← for each task: ReAct loop + 不确定性检测
    ↓ 每轮 ReAct 后
[UNCERTAINTY CHECK] ← ~100 token 判断 CONFIDENT / UNCERTAIN
    ├── confident → 继续 ReAct
    └── uncertain → [SELF-ASK] → ask_user 工具
    ↓ 任务完成
[REFLECTING] ← 评估任务结果：SUCCESS / FAIL
    ├── SUCCESS → 下一个任务 / 全部完成 → [DONE]
    └── FAIL → 分级降级
        ├── L1: 局部重试 (≤2次) → 回 EXECUTING
        ├── L2: 整体重规划 (≤3次) → 回 PLANNING（带反馈）
        └── L3: 报错给用户 → [DONE]
```

---

## 3. 文件结构

```
core/
├── cognitive.py          # CognitiveController + 状态机 (~400 行)
├── planner.py            # Planner + ToT 逻辑 (~300 行)
├── executor.py           # Executor + ReAct + 不确定性检测 (~400 行)
├── reflector.py          # Reflector + 分级降级 (~250 行)
├── self_asker.py         # SelfAsker (~200 行)
├── agent.py              # NeonAgent 改：simple 走现有 ReAct，complex 委托 CognitiveController
└── ...（llm.py / memory.py / long_term_memory.py / subagent.py 不动）

config/
└── config.py             # DEFAULT_CONFIG 加 cognitive 节

main.py                   # 加 /cognitive on|off 命令

tools/
└── plan_tot.py           # 改为 Planner 薄包装（DRY）

tests/
├── test_cognitive_controller.py   # 状态机测试 (~8 个)
├── test_planner.py                 # ToT 测试 (~6 个)
├── test_executor.py                # ReAct + 不确定性检测测试 (~6 个)
├── test_reflector.py               # 评估 + 降级测试 (~6 个)
└── test_self_asker.py              # Self-Ask 触发测试 (~6 个)
```

---

## 4. 核心类设计

### 4.1 CognitiveController（core/cognitive.py）

```python
from enum import Enum
from typing import Optional, List, Dict, Any

class State(Enum):
    CLASSIFY = "classify"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    DONE = "done"

class CognitiveController:
    def __init__(self, llm_client, memory, tool_registry,
                 planner=None, executor=None, reflector=None, self_asker=None,
                 max_replans: int = 3, max_task_retries: int = 2):
        self.llm = llm_client
        self.memory = memory
        self.registry = tool_registry
        self.planner = planner or Planner(llm_client)
        self.executor = executor or Executor(llm_client, memory, tool_registry)
        self.reflector = reflector or Reflector(llm_client)
        self.self_asker = self_asker or SelfAsker(llm_client, tool_registry)
        self.max_replans = max_replans
        self.max_task_retries = max_task_retries
        self.state = State.CLASSIFY
        self.task_list: List[Dict] = []
        self.current_task_idx = 0
        self.replan_count = 0

    def chat(self, user_input: str) -> str:
        if self._classify(user_input) == "simple":
            return self._fallback_to_react(user_input)
        
        self.state = State.PLANNING
        self.task_list = self.planner.execute(user_input)
        
        while self.state != State.DONE:
            if self.state == State.EXECUTING:
                self._step_execute()
            elif self.state == State.REFLECTING:
                self._step_reflect()
            elif self.state == State.PLANNING:
                self._step_replan()
        
        return self._build_answer()

    def _classify(self, input: str) -> str: ...
    def _step_execute(self): ...
    def _step_reflect(self): ...
    def _step_replan(self): ...
    def _build_answer(self) -> str: ...
    def _fallback_to_react(self, input: str) -> str: ...
```

**关键设计**：依赖注入所有子模块；状态机驱动；中间状态可序列化（task_list + current_task_idx + replan_count）。

### 4.2 Planner（core/planner.py）

```python
class Planner:
    def __init__(self, llm_client, tot_candidates: int = 3):
        self.llm = llm_client
        self.tot_candidates = tot_candidates

    def execute(self, user_input: str, feedback: Optional[List[str]] = None) -> List[Dict]:
        candidates = self._generate_candidates(user_input, feedback)
        scored = self._evaluate(candidates, user_input)
        best = self._select_best(scored)
        return self._parse_to_tasks(best)

    def _generate_candidates(self, input, feedback) -> List[str]: ...
    def _evaluate(self, candidates, input) -> List[Dict]: ...
    def _select_best(self, scored) -> str: ...
    def _parse_to_tasks(self, plan) -> List[Dict]: ...
```

**关键设计**：ToT 内嵌（候选数可配）；重规划时 feedback 喂给评估 prompt；plan_tot 工具改为薄包装。

任务结构：`{id, desc, status, retries, feedback}`，status 有 `pending/executing/done/failed` 四态。

### 4.3 Executor（core/executor.py）

```python
class Executor:
    def __init__(self, llm_client, memory, tool_registry,
                 max_iterations: int = 25,
                 self_asker=None,
                 enable_uncertainty_check: bool = True):
        ...

    def execute(self, task: Dict) -> Dict:
        # 1. 任务描述塞进 memory
        # 2. for iteration: ReAct loop（复用现有 _parse_stream 逻辑）
        # 3. 串行执行 tool_calls（v1.1.0 串行循环）
        # 4. 每轮后不确定性检测（可关）
        # 5. uncertain → 触发 SelfAsker.ask
        # 6. final_answer 且无 tool_calls → done
        # 7. max_iterations → failed
```

**关键设计**：复用现有 ReAct 逻辑；任务通过 memory 边界标记；重试带 feedback；不确定性检测可关；SelfAsker 延迟注入避免循环依赖。

### 4.4 Reflector（core/reflector.py）

```python
class Reflector:
    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(self, task: Dict) -> str:
        # status=done → _llm_evaluate 假成功检测
        # status=failed → "fail: <reason>"
        # 返回 "success" 或 "fail: <reason>"

    def _llm_evaluate(self, task: Dict) -> str:
        # ~150 token 检测 result 是否含 Error/Traceback
```

**关键设计**：假成功检测（避免 LLM 说完成但 result 含 Error）；轻量 ~150 token；反馈格式 `fail: <reason>` 带回 Controller。

### 4.5 SelfAsker（core/self_asker.py）

```python
class SelfAsker:
    def __init__(self, llm_client, tool_registry):
        self.llm = llm_client
        self.registry = tool_registry

    def check_uncertainty(self, last_observation: str, task: Dict) -> str:
        # ~100 token 返回 "confident" 或 "uncertain: <reason>"

    def ask(self, task_desc: str, uncertainty_reason: str) -> str:
        # 调 registry.execute_tool("ask_user", prompt=...)
```

**关键设计**：轻量 ~100 token；复用现有 ask_user 工具；提问前缀 `[Self-Ask]` 标识；可关闭。

---

## 5. 与 NeonAgent 集成

### 5.1 core/agent.py 改动

```python
class NeonAgent:
    def __init__(self, config):
        # ... 现有初始化不变 ...
        self._cognitive_controller = None
        self._cognitive_enabled = config.get("cognitive", {}).get("enabled", True)

    @property
    def cognitive_controller(self):
        # 延迟构造，按需启用
        # 注入 Planner / Executor / Reflector / SelfAsker
        ...

    def chat(self, user_input: str):
        if self._cognitive_enabled:
            try:
                return self.cognitive_controller.chat(user_input)
            except Exception:
                # 兜底：异常时 fallback 走现有 ReAct
                yield from self._react_loop(user_input)
        else:
            yield from self._react_loop(user_input)
```

### 5.2 config/config.py 新增

```python
"cognitive": {
    "enabled": True,              # 总开关
    "tot_candidates": 3,          # ToT 候选数
    "max_replans": 3,             # 整体重规划上限
    "max_task_retries": 2,        # 单任务重试上限
    "self_ask": True,             # 不确定性检测开关
},
```

### 5.3 main.py 新增 /cognitive 命令

```python
elif cmd == '/cognitive':
    if not arg:
        # 显示当前状态
        ...
    val = arg.strip().lower()
    if val in ("on", "off"):
        config['cognitive']['enabled'] = (val == "on")
        save_config(config)
        agent._cognitive_enabled = (val == "on")
        agent._cognitive_controller = None  # 重置实例
        # 打印切换结果
    return True
```

### 5.4 tools/plan_tot.py 改为薄包装

```python
class PlanToTTool(BaseTool):
    name = "plan_tot"
    description = "..."
    parameters = {...}
    
    def execute(self, **kwargs) -> str:
        # 改为调用 Planner（DRY）
        from core.planner import Planner
        planner = Planner(self._llm_client)  # _llm_client 通过构造注入
        tasks = planner.execute(kwargs.get("input"))
        return str(tasks)
```

---

## 6. 错误处理与边界

| 场景 | 处理 |
|------|------|
| Classify LLM 失败 | 兜底走 simple ReAct |
| Planner 生成 0 候选 | 兜底单任务退化为直接执行 |
| ToT 评估失败 | 选第一个候选（best-effort） |
| Executor 达 max_iterations | task failed，进 REFLECTING |
| SelfAsker check 失败 | 兜底 confident（继续） |
| ask_user 被取消 | 空字符串塞 memory，LLM 自行判断 |
| Reflector 评估失败 | 兜底信任 task status |
| 重规划 3 次仍失败 | DONE，返回累积错误 |
| Controller 任意异常 | NeonAgent chat 捕获，fallback ReAct |
| Memory 滑动窗口超限 | 现有裁剪逻辑不动 |
| LLM 返回空 choices | 现有空 choices 保护不动 |

**核心原则**：所有外部 LLM 调用都有兜底，永不阻断主流程，最坏退化为现有 ReAct。

---

## 7. 测试策略

- **5 个测试文件**：每模块独立测试，模块间用 MagicMock 隔离
- **mock_llm fixture 复用**：沿用 tests/conftest.py 现有 fixture
- **状态机全覆盖**：CLASSIFY → PLANNING → EXECUTING → REFLECTING → DONE + L1/L2/L3 降级
- **不破坏现有 124 测试**：NeonAgent simple 输入仍走现有 ReAct，行为不变
- **TDD 顺序**：每 Phase 先写测试再实现

预计新增 ~26 个测试（Phase 1: 8 / Phase 2: 6 / Phase 3: 6 / Phase 4: 6），总计 124+26=150 个。

---

## 8. 验收标准

- [ ] 全部测试通过（124 现有 + ~26 新增 = ~150 个）
- [ ] 现有 124 个测试无回归
- [ ] CognitiveController 5 个状态全覆盖
- [ ] simple 输入走现有 ReAct，行为不变
- [ ] complex 输入走 Plan → Execute → Reflect → Done
- [ ] Planner ToT 生成 N 候选并选最优
- [ ] Executor 每轮 ReAct 后触发不确定性检测（可关）
- [ ] SelfAsker uncertain 时调 ask_user 工具
- [ ] Reflector 假成功检测有效
- [ ] 单任务失败 → 局部重试 ≤ 2 → 整体重规划 ≤ 3 → 报错给用户
- [ ] `/cognitive on|off` 可运行时切换
- [ ] config 全可配
- [ ] plan_tot 工具改为 Planner 薄包装，现有测试无回归
- [ ] NeonAgent.chat 异常时 fallback 走现有 ReAct

---

## 9. 4 阶段实现路线

| Phase | 框架 | 行数 | 测试数 | 验收 |
|-------|------|------|--------|------|
| 1 | Plan-and-Execute | ~400 | ~8 | 端到端可用：拆任务 + ReAct 执行 |
| 2 | Self-Reflection | ~250 | ~6 | 失败可重规划 + 分级降级 |
| 3 | Thinking (ToT) | ~300 | ~6 | 规划质量提升 + plan_tot 改薄包装 |
| 4 | Self-Ask | ~200 | ~6 | 遇不确定自动提问 |
| 合计 | 四框架综合 | ~1150 | ~26 | 完整 CognitiveController |

每个 Phase 独立提交，TDD 顺序：RED → GREEN → REFACTOR。全部完成后 bump 到 v1.2.0。
