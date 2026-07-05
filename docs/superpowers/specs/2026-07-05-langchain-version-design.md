# MINGCODE-LC（LangChain 版本）设计规格

**版本**：lc-v0.1.0（混合版本号，独立演进）
**位置**：`c:\Users\bloon\Downloads\mingcode-langchain`
**技术栈**：LangGraph + langchain-openai + Rich UI（复用）+ uv 包管理
**目标**：1:1 等价复刻 NeonAgent v1.2.0 的所有功能，用 LangChain 生态重写核心认知框架

---

## 1. 背景与目标

### 1.1 背景
NeonAgent v1.2.0 已实现综合认知框架（Plan-and-Execute + Self-Reflection + ToT + Self-Ask），全部用手撸代码（requests + 自定义状态机 + 自定义工具基类）。这产生了几个痛点：
- 工具调用、消息历史、流式输出等基础设施全部手撸，维护成本高
- 状态机用 `while/if` 循环实现，调试时无法可视化、无法断点续接
- 没有 checkpoint 机制，会话保存/加载是手动的 JSON 序列化
- LLM 客户端只支持 OpenAI 格式，扩展到 Anthropic/Bedrock 需要重写

### 1.2 目标
用 LangChain 生态重写核心认知框架，保持功能等价，对比两种实现方案的优劣：
- **核心**：用 LangGraph StateGraph 重写 CognitiveController 状态机
- **工具**：用 `@tool` 装饰器 + Pydantic 替换 BaseTool ABC
- **LLM**：用 `langchain-openai.ChatOpenAI`（兼容 OpenAI 格式 API）
- **记忆**：用 `SqliteSaver` checkpointer 自动持久化
- **IM/桌面控制**：直接 copy NeonAgent 文件（独立协议层）

### 1.3 非目标
- 不复刻 NeonAgent 的所有 174 个测试（用 LangChain 测试体系重新组织）
- 不追求性能极致（LangChain 有序列化开销，但足够用）
- 不替换所有第三方协议（微信 iLink / QQ OneBot / QQ 官方 Bot 保持原样）

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                   mingcode-langchain/                            │
│                                                                   │
│  main.py ──► CLI入口 (/settings /cognitive /model 等命令)        │
│       │                                                           │
│       ▼                                                           │
│  core/agent.py ──► LangChainAgent                                │
│       │  (NeonAgent 等价物，对外 Generator[str] 接口)              │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  CognitiveController (LangGraph StateGraph)             │     │
│  │                                                          │     │
│  │  CLASSIFY ──► PLANNING ──► EXECUTING ──► REFLECTING    │     │
│  │       │           │            │             │          │     │
│  │       │           ▼            ▼             ▼          │     │
│  │   simple      Planner      Executor      Reflector      │     │
│  │   fallback    (ToT)         (ReAct +      (LLM 评估     │     │
│  │   (直接        候选生成      Self-Ask)     + L1/L2/L3)  │     │
│  │   ReAct)      评分筛选                                   │     │
│  │                                                          │     │
│  │  状态保存在 SqliteSaver checkpointer                     │     │
│  └─────────────────────────────────────────────────────────┘     │
│       │                                                           │
│       ▼                                                           │
│  tools/ (15+ @tool decorator)                                    │
│  llm.py (ChatOpenAI 兼容 Ollama/OpenAI/DeepSeek/Qwen)            │
│  ui/ (Rich 复用 + LangChain StreamingCallback 桥接)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 模块映射（NeonAgent → LangChainAgent）

| NeonAgent 模块 | LangChain 等价实现 | 备注 |
|---------------|-------------------|------|
| `core/llm.py` (requests 手撸) | `langchain-openai.ChatOpenAI` | 兼容 OpenAI 格式 API，原生支持 streaming/tools/reasoning |
| `core/memory.py` (手动 list) | `langgraph.checkpoint.sqlite.SqliteSaver` | 进程间共享、断点续接 |
| `core/long_term_memory.py` | 自定义 `LongTermMemory`（保留）+ 可选向量检索 | 简单 JSON 即可，后期升级 |
| `core/agent.py` (NeonAgent) | `core/agent.py` (LangChainAgent) | 对外 Generator[str] 接口一致 |
| `core/cognitive.py` (状态机) | `langgraph.StateGraph` | 节点=状态处理函数，边=状态转换 |
| `core/planner.py` | `core/planner.py` (用 LLM + Pydantic 解析) | ToT 用 `@chain` 装饰器 |
| `core/executor.py` (ReAct) | `create_react_agent` 或自写 LCEL | 串行执行 + Self-Ask 钩子 |
| `core/reflector.py` | `core/reflector.py` (LLM 评估 + Pydantic) | 输出 verdict: success/fail:xxx |
| `core/self_asker.py` | `core/self_asker.py` (调 ask_user tool) | 不确定时 yield 暂停给用户 |
| `tools/base.py` (BaseTool ABC) | `langchain_core.tools.@tool` / `StructuredTool` | 用 Pydantic 描述参数 |
| `tools/shell.py` 等 15 个 | `@tool` 装饰器重写 | 逻辑可复用，只是包装层换 |
| `ui/console.py` + `theme.py` | 直接 copy 整个目录 | Rich 渲染不变 |
| `main.py` CLI | 改造（保留所有 / 命令） | 多 `/cognitive on/off` |
| `wechat_bot.py / qq_*.py` | 直接 copy（独立 IM 协议层） | 不依赖 LangChain |

---

## 4. LangGraph 状态机设计

### 4.1 状态定义

```python
# core/cognitive_graph.py
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    user_input: str
    messages: List[Dict[str, Any]]          # LangGraph 消息历史
    task_list: List[Dict]                    # Planner 生成的任务
    current_task_idx: int
    replan_count: int
    last_feedback: List[str]                 # Reflector 的失败反馈
    final_answer: str
    verdict: str                              # success / fail: xxx
    max_task_retries: int
    max_replans: int
```

### 4.2 节点函数（纯函数式）

```python
def classify_node(state: AgentState) -> AgentState:
    """分类 simple/complex，带本地预过滤。"""
    user_input = state["user_input"]
    # 本地预过滤（复制 NeonAgent 经验）
    if len(user_input.strip()) <= 6:
        state["verdict"] = "simple"
        return state
    greeting_patterns = ("你好", "您好", "嗨", "哈喽", "在吗", "thanks", "thank you", "谢谢", "辛苦", "再见", "bye")
    lower = user_input.lower()
    if any(p in lower for p in greeting_patterns):
        state["verdict"] = "simple"
        return state
    # LLM 分类
    result = classifier.invoke(user_input)
    state["verdict"] = result
    return state

def planning_node(state: AgentState) -> AgentState:
    """Planner + ToT。"""
    feedback = state.get("last_feedback", [])
    tasks = planner.invoke(state["user_input"], feedback=feedback)
    state["task_list"] = tasks
    state["current_task_idx"] = 0
    return state

def executing_node(state: AgentState) -> AgentState:
    """Executor ReAct + Self-Ask。"""
    task = state["task_list"][state["current_task_idx"]]
    result = executor.invoke(task)
    task["result"] = result
    task["status"] = "executed"
    return state

def reflecting_node(state: AgentState) -> AgentState:
    """Reflector + L1/L2/L3 降级。"""
    task = state["task_list"][state["current_task_idx"]]
    verdict = reflector.invoke(task)
    if verdict == "success":
        task["status"] = "done"
        state["current_task_idx"] += 1
        state["verdict"] = "success_next" if state["current_task_idx"] < len(state["task_list"]) else "all_done"
    else:
        task["retries"] = task.get("retries", 0) + 1
        task["feedback"] = verdict
        if task["retries"] <= state["max_task_retries"]:
            state["verdict"] = "retry_l1"
        else:
            state["replan_count"] += 1
            if state["replan_count"] <= state["max_replans"]:
                state["last_feedback"] = [t.get("feedback") for t in state["task_list"] if t.get("feedback")]
                state["verdict"] = "replan_l2"
            else:
                task["status"] = "failed"
                state["verdict"] = "fail_l3"
    return state

def done_node(state: AgentState) -> AgentState:
    """汇总答案。"""
    state["final_answer"] = _build_answer(state["task_list"])
    return state
```

### 4.3 条件边（路由函数）

```python
def route_after_classify(state: AgentState) -> str:
    return "simple" if state.get("verdict") == "simple" else "complex"

def route_after_reflect(state: AgentState) -> str:
    return state.get("verdict", "fail_l3")

def build_cognitive_graph(planner, executor, reflector, classifier):
    g = StateGraph(AgentState)
    g.add_node("classify", classify_node)
    g.add_node("planning", planning_node)
    g.add_node("executing", executing_node)
    g.add_node("reflecting", reflecting_node)
    g.add_node("done", done_node)

    g.set_entry_point("classify")
    g.add_conditional_edges("classify", route_after_classify, {
        "simple": "done",
        "complex": "planning",
    })
    g.add_edge("planning", "executing")
    g.add_edge("executing", "reflecting")
    g.add_conditional_edges("reflecting", route_after_reflect, {
        "success_next": "executing",
        "retry_l1": "executing",
        "replan_l2": "planning",
        "fail_l3": "done",
        "all_done": "done",
    })
    g.add_edge("done", END)
    return g.compile(checkpointer=SqliteSaver("checkpoints.db"))
```

### 4.4 关键设计点
- **状态保存在 `AgentState` TypedDict**，节点是纯函数 `(state) -> state`
- **条件边用 `route_after_*` 函数实现 L1/L2/L3 分级降级**
- **`SqliteSaver` 自动持久化**，重启可断点续接
- **复用 NeonAgent 的预过滤逻辑**（短输入直接 simple，零 LLM 调用）
- **fallback 机制**：CognitiveController compile 时套 try/except，异常 fallback 到 `create_react_agent`

---

## 5. 工具系统（@tool 装饰器）

### 5.1 包装方式

```python
# tools/shell.py
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class ShellInput(BaseModel):
    command: str = Field(description="Shell command to execute")

@tool(args_schema=ShellInput)
def shell(command: str) -> str:
    """Execute shell command and return stdout."""
    # 复用 NeonAgent ShellTool.execute 逻辑
    ...
    return result
```

### 5.2 工具清单（15+）

| 工具 | 包装方式 | 复用 NeonAgent 业务逻辑 |
|------|---------|----------------------|
| shell | @tool + ShellInput | subprocess + chcp 65001 |
| file_read / file_write / file_edit | @tool | 直接复用 |
| python_exec | @tool | subprocess + timeout |
| web_search / web_fetch | @tool | duckduckgo-search + requests |
| subagent | @tool | 复用 SubAgentTool |
| ask_user | @tool | input() 暂停 |
| plan_tot | @tool | 调 Planner |
| todo / time / math / http / git | @tool | 直接复用 |
| computer_use | @tool | pyautogui + vision LLM |

### 5.3 工具注册

```python
# tools/__init__.py
from langchain_core.tools import StructuredTool
from .shell import shell
from .files import file_read, file_write, file_edit
# ... 其他工具

ALL_TOOLS = [
    shell, file_read, file_write, file_edit,
    python_exec, web_search, web_fetch,
    subagent, ask_user, plan_tot, todo,
    time_tool, math_tool, http_tool, git_tool,
    computer_use,
]

def get_tool_registry():
    """返回 LangChain Tool 列表，供 ToolNode 使用。"""
    return ALL_TOOLS
```

---

## 6. 文件结构

```
mingcode-langchain/
├── pyproject.toml              # uv 管理，name=mingcode-lc, version=lc-v0.1.0
├── uv.lock
├── README.md
├── main.py                      # CLI 入口
├── config/
│   ├── __init__.py
│   └── config.py                # 复用 NeonAgent 配置结构
├── core/
│   ├── __init__.py
│   ├── agent.py                 # LangChainAgent（对外 Generator[str]）
│   ├── cognitive_graph.py       # LangGraph StateGraph（替代 cognitive.py）
│   ├── planner.py               # Planner + ToT（用 LCEL）
│   ├── executor.py              # ReAct 包装（create_react_agent 或自写）
│   ├── reflector.py             # Reflector（LLM 评估 + Pydantic）
│   ├── self_asker.py            # SelfAsker（调 ask_user tool）
│   ├── llm.py                   # LLM 客户端工厂（ChatOpenAI 多供应商）
│   ├── memory.py                # SqliteSaver checkpointer 封装
│   ├── long_term_memory.py      # 复用 NeonAgent（独立 JSON 持久化）
│   ├── todo.py                  # 复用 NeonAgent TodoList
│   ├── wechat_bot.py            # 直接 copy（独立 IM 层）
│   ├── qq_onebot.py             # 直接 copy
│   └── qq_official.py           # 直接 copy
├── tools/
│   ├── __init__.py              # @tool 装饰器注册
│   ├── shell.py files.py code.py search.py
│   ├── subagent.py ask_user.py plan_tot.py todo.py
│   ├── time_tool.py math_tool.py http_tool.py git_tool.py
│   └── computer_use.py          # 复用 NeonAgent 逻辑（vision 调用）
├── ui/
│   ├── __init__.py
│   ├── console.py theme.py     # 直接 copy neon_agent/ui/
│   └── callbacks.py            # LangChain StreamingCallback 桥接 Rich
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cognitive_graph.py
│   ├── test_planner.py test_executor.py test_reflector.py test_self_asker.py
│   ├── test_tools.py
│   └── test_agent.py
├── docs/superpowers/
│   ├── specs/2026-07-05-langchain-version-design.md
│   └── plans/2026-07-05-langchain-version-phase*.md
└── checkpoints.db               # SqliteSaver 持久化（gitignore）
```

---

## 7. 实施阶段划分（5 个 Phase）

| Phase | 目标 | 测试数 | Task 数 |
|-------|------|--------|-----------|
| **Phase 0** | 项目初始化 + UI 复用 + 配置 + LLM 客户端 | 8 | 6 |
| **Phase 1** | 工具系统（@tool + Pydantic）+ 简单 ReAct Agent | 12 | 8 |
| **Phase 2** | LangGraph 认知框架（Plan-Execute + Reflector stub） | 15 | 10 |
| **Phase 3** | Reflector 真实评估 + L1/L2/L3 分级降级 | 10 | 6 |
| **Phase 4** | Planner ToT + SelfAsker + 完整 IM 接入 + 打包 | 20 | 12 |

**总计**：~65 测试，~42 Task

### 7.1 Phase 0：项目初始化
- 创建 pyproject.toml（uv 管理）
- 复用 ui/ 目录
- 创建 config/config.py（兼容 NeonAgent 结构）
- 实现 core/llm.py（ChatOpenAI 工厂）
- 实现 ui/callbacks.py（LangChain StreamingCallback）
- 写 README.md 初版

### 7.2 Phase 1：工具系统 + ReAct
- 用 @tool 重写 15 个工具（复用 NeonAgent 业务逻辑）
- 实现 tools/__init__.py 注册
- 实现 core/agent.py 的 LangChainAgent（简单 ReAct 分支）
- 实现 main.py 基础 CLI（/help /config /settings /model）
- 测试：每个工具 invoke + 简单 ReAct 循环

### 7.3 Phase 2：LangGraph 认知框架基础
- 实现 core/cognitive_graph.py（StateGraph + 5 节点）
- 实现 core/planner.py（简单单次 LLM 调用）
- 实现 core/executor.py（用 create_react_agent 包装）
- 实现 core/reflector.py（stub，只看 status）
- 实现 core/self_asker.py（占位）
- 集成到 LangChainAgent
- 测试：5 节点状态转换 + 简单流程

### 7.4 Phase 3：Reflector + 分级降级
- 升级 reflector.py：LLM 假成功检测 + Pydantic 输出
- 实现条件边路由（L1/L2/L3）
- 实现 last_feedback 传递
- 测试：L1 局部重试 / L2 重规划 / L3 报错

### 7.5 Phase 4：ToT + SelfAsk + IM + 打包
- 升级 planner.py：ToT 候选生成 + 评分 + 筛选
- 升级 self_asker.py：LLM 不确定性检测
- copy wechat_bot.py / qq_*.py
- 实现 /wechat /qq 命令
- PyInstaller 打包脚本
- 完整测试套件
- README 终版 + 与 NeonAgent 对比文档

---

## 8. 关键技术决策

### 8.1 LLM 抽象
用 `langchain-openai.ChatOpenAI`（兼容 Ollama/OpenAI/DeepSeek），原生支持：
- streaming（`stream=True`）
- tool_calls（OpenAI function calling 格式）
- reasoning_effort（通过 `model_kwargs={"reasoning_effort": "high"}` 透传）

```python
# core/llm.py
from langchain_openai import ChatOpenAI

def create_llm(config):
    llm_config = config.get("llm", config)
    return ChatOpenAI(
        base_url=llm_config["base_url"],
        api_key=llm_config["api_key"],
        model=llm_config["model"],
        temperature=llm_config.get("temperature", 0.7),
        max_tokens=llm_config.get("max_tokens", 4096),
        streaming=True,
        model_kwargs={"reasoning_effort": llm_config.get("reasoning_effort")} if llm_config.get("reasoning_effort") in ("low", "medium", "high") else {},
    )
```

### 8.2 状态持久化
`SqliteSaver` 自动管理 checkpointer：
- 重启自动恢复（按 `thread_id`）
- 会话保存/加载用 `thread_id` 切换（替代 NeonAgent 的手动 JSON）
- `/sessions` 命令列出所有 thread_id

### 8.3 工具调用
LangGraph 的 `ToolNode` 默认并行调度，但 NeonAgent 经验说串行更稳（避免顺序错乱）：
- 设置 `parallel_tool_calls=False`（OpenAI 参数）
- 或用 `create_react_agent` 自带的串行循环

### 8.4 流式输出
用 LangChain `BaseCallbackHandler` 把 token 流桥接到 Rich `Live` 渲染：

```python
# ui/callbacks.py
from langchain_core.callbacks import BaseCallbackHandler
from rich.live import Live
from rich.text import Text

class RichStreamHandler(BaseCallbackHandler):
    def __init__(self):
        self.live = Live()
        self.text = Text()

    def on_llm_new_token(self, token, **kwargs):
        self.text.append(token)
        self.live.update(self.text)
```

### 8.5 IM 层复用
微信/QQ 直接 copy 文件，它们用 `requests` + `websocket`，跟 LangChain 无关。只需在 main.py 中桥接消息回调到 LangChainAgent.chat()。

### 8.6 fallback 机制
CognitiveController compile 时套 try/except：
```python
try:
    result = cognitive_graph.invoke(initial_state, config={"configurable": {"thread_id": session_id}})
    return result["final_answer"]
except Exception:
    # fallback 到 create_react_agent
    return react_agent.invoke({"messages": [...]})
```

### 8.7 本地预过滤
复制 NeonAgent 的 ≤6 字符 + 问候词规则（性能优化经验，避免简单输入调 LLM）。

### 8.8 配置兼容
config.yaml 结构与 NeonAgent 一致，方便用户迁移：
```yaml
llm:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-..."
  model: "deepseek-chat"
  reasoning_effort: null
cognitive:
  enabled: true
  tot_candidates: 3
  max_replans: 3
  max_task_retries: 2
  self_ask: false
```

---

## 9. 测试策略

### 9.1 TDD RED-GREEN-REFACTOR
每个 Task 先写失败测试 → 实现最小代码让测试通过 → 重构。

### 9.2 Mock LLM
- 用 `langchain_core.language_models.FakeLLM` 或 `unittest.mock.MagicMock`
- mock `ChatOpenAI.invoke` 返回预定义响应

### 9.3 LangGraph 测试
用 `g.invoke({...})` 直接断言状态转换：
```python
def test_classify_simple_returns_done():
    g = build_cognitive_graph(planner=mock_plan, executor=mock_exec, ...)
    result = g.invoke({"user_input": "hi", ...})
    assert result["verdict"] == "simple"
    assert result["final_answer"] is not None
```

### 9.4 工具测试
`@tool` 装饰后的函数可直接调用：
```python
def test_shell_echo():
    result = shell.invoke({"command": "echo hi"})
    assert "hi" in result
```

### 9.5 集成测试
mock LLM 返回 tool_calls，验证完整 ReAct 循环。

---

## 10. 与 NeonAgent 的对比维度

最终交付时附对比文档：
- **代码行数**：LangChain 版本预期更短（声明式 vs 手撸循环）
- **依赖大小**：langchain 生态 vs requests + 手撸（LangChain 会大很多）
- **性能**：LangGraph 的 checkpointer 有序列化开销，但 streaming 原生支持
- **可维护性**：LangGraph 节点函数式 vs NeonAgent 类方法
- **扩展性**：LangChain 生态工具直接可用 vs NeonAgent 自定义
- **调试体验**：LangGraph 可视化（langgraph dev）vs NeonAgent 手撸日志
- **学习曲线**：LangChain 概念多 vs NeonAgent 简单直接

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LangChain 依赖膨胀（500MB+） | 用 `langchain-core` + `langchain-openai` + `langgraph` 精选子包 |
| LangGraph API 变动（库还较新） | 锁版本号在 pyproject.toml |
| SqliteSaver 并发写入 | 用单 thread_id，IM 多渠道时加锁 |
| FakeLLM 测试覆盖不全 | 关键流程用真实 LLM 跑 smoke test |
| IM 协议层与 LangChain 集成 | 用独立线程跑 IM，消息回调转发到主 Agent |

---

## 12. 验收标准

- [ ] 65+ 单元测试全部通过
- [ ] `python main.py` 可启动，`/settings` 可配置
- [ ] 简单输入（hi/你好）秒回（预过滤生效）
- [ ] 复杂任务（写贪吃蛇）走完整认知框架：classify → plan → execute → reflect → done
- [ ] L1/L2/L3 分级降级正常工作
- [ ] Self-Ask 在 self_ask=true 时触发 ask_user 工具
- [ ] ToT 生成多候选并选最优
- [ ] 微信/QQ 接入可登录、收发消息
- [ ] 桌面控制可截屏 + 鼠标键盘
- [ ] PyInstaller 打包成 exe
- [ ] README + 学习路线完整

---

## 13. 后续演进

- v0.2.0：向量语义检索记忆（embedding 模型）
- v0.3.0：多会话切换 UI
- v0.4.0：LangSmith 集成（trace 调试）
- v0.5.0：流式 LangGraph（节点边输出）
