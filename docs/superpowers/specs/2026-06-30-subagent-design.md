# Subagent 功能设计

- 日期：2026-06-30
- 项目：MINGCODE (neon_agent)
- 状态：待实现

## 1. 目标

为 MINGCODE 增加 subagent（子智能体）能力，使主 agent 能在 ReAct 循环中自主派生独立的子智能体处理子任务，同时支持用户在 CLI 手动启动一次性 subagent。

核心价值：
- 主 agent 上下文不被冗长子任务中间过程污染
- 多个独立子任务可并行执行，缩短总耗时
- 子智能体可递归派生（有限深度），处理分层复杂任务

## 2. 需求（已与用户确认）

| 需求项 | 决策 |
|--------|------|
| 触发方式 | 两种都做：主 agent 自主调用的 `task` 工具 + 用户手动 `/sub` 命令 |
| 工具范围 | 全工具（shell/files/code/search）+ 有限递归 |
| 递归深度 | depth 语义：剩余可递归次数。主 agent 调 task 时 SubAgent depth=2（可再递归 2 次），即调用链最多 3 层：主 → sub(depth=2) → sub(depth=1) → sub(depth=0 不注册 task，不可再起) |
| 返回内容 | 只返回最终答案字符串，中间过程留在 subagent 独立 memory |
| 并行执行 | 支持。主 ReAct 循环改为并行执行同一轮的多个 tool_calls |
| Long-term memory | 共享主 agent 的 LongTermMemory 池（subagent 学到的经验进同一池） |

## 3. 架构

采用**组合**关系，不继承 `NeonAgent`。

```
NeonAgent (主)
 ├─ ToolRegistry (全工具 + SubAgentTool)
 ├─ ConversationMemory (主对话)
 ├─ LongTermMemory (共享池)
 ├─ LLMClient (共享)
 └─ ThreadPoolExecutor (并行执行 tool_calls)

SubAgent (子, 由 SubAgentTool 实例化)
 ├─ ToolRegistry (全工具 + 当 depth>0 时再嵌 SubAgentTool)
 ├─ ConversationMemory (独立, 空)
 ├─ LongTermMemory (复用主的)
 ├─ LLMClient (复用主的)
 └─ depth (递归剩余层数)
```

### 3.1 隔离边界

- SubAgent 的 `ConversationMemory` 完全独立，主 agent 看不到 subagent 的中间思考/工具调用
- SubAgent 不复用主 agent 的会话历史，只用工具 schema + 通用任务指令构建 system prompt
- SubAgent 的 `LongTermMemory` 共享：subagent 自动学习到的 success/lesson 写入同一池，主 agent 下次推理能检索到
- 递归 depth 控制：SubAgent 构造时传 `depth`，到 0 不再注册 SubAgentTool，从机制上杜绝无限递归

### 3.2 数据流

```
用户输入 → NeonAgent.chat()
  ├─ LLM 决策调 task 工具 (可同时调多个)
  │   └─ [并行] SubAgentTool.execute(task, context)
  │       └─ SubAgent(depth=2).run(task)
  │           ├─ 独立 memory + 独立 ReAct 循环 (≤10 轮)
  │           ├─ 可再起 SubAgent(depth=1) (递归)
  │           └─ 返回 "最终答案" 字符串
  │       └─ 返回给主 agent 作为 tool_result
  └─ 主 agent 拿到多个 tool_result (并行完成) 继续推理
```

## 4. 组件设计

### 4.1 `core/subagent.py` — `SubAgent` 类

**职责**：在独立上下文中跑完一个任务，返回最终答案字符串。不与主 UI 交互。

**构造**：
```python
SubAgent(llm: LLMClient, long_term_memory: LongTermMemory,
         depth: int = 2, timeout: int = 180)
```
`depth` 含义：本 subagent 还能再派生几层 subagent。主 agent 调 task 工具时传入 `depth=2`；subagent 内部注册 SubAgentTool 时传 `depth-1`；`depth=0` 时不注册 SubAgentTool，递归终止。

**字段**：
- `self.llm` — 复用主 LLMClient
- `self.memory` — 新建空 `ConversationMemory(max_history=20)`
- `self.long_term_memory` — 复用主 LongTermMemory
- `self.depth` — 递归剩余层数
- `self.timeout` — 单次 run 硬超时秒数
- `self.registry` — 独立 ToolRegistry

**工具注册**：
- ShellTool, FileReadTool, FileWriteTool, FileEditTool, PythonExecTool, WebSearchTool, WebFetchTool（全工具）
- 当 `depth > 0`：额外注册 `SubAgentTool(depth-1)` 实现递归

**System prompt 构建**：
- 基础：工具 schema（同主 agent）
- 追加任务指令段：
  > "你是 MINGCODE 的子智能体。专注完成给定任务，不要闲聊，不要询问用户。使用工具完成任务后，用 `Final Answer: <结论>` 格式返回最终答案。结论应简洁、聚焦、可操作。若任务无法完成，返回 `Final Answer: [无法完成] <原因>`。"

**主方法**：
```python
def run(self, task: str, context: str = "") -> str
```
- 跑独立 ReAct 循环，最多 10 轮
- 不 yield、不调用主 UI 的 print_* 函数（仅 logging.debug）
- 解析每轮 assistant 响应，若含 `Final Answer:` 则提取后立即返回
- 硬超时：用 `threading.Timer` 兜底，超时返回 `"[subagent timeout]"`
- 异常：捕获后返回 `"[subagent error: <msg>]"`，并写入 long_term_memory

**Long-term memory 交互**：
- SubAgent 内工具执行失败时调 `long_term_memory.auto_learn_from_error(...)`（与主 agent 同机制）
- 工具执行从错误恢复时调 `auto_learn_success(...)`
- 不调 `format_for_prompt`（避免主 agent 上下文反向泄漏到 subagent）

### 4.2 `tools/subagent.py` — `SubAgentTool`

**Schema**：
```json
{
  "name": "task",
  "description": "派一个子智能体处理独立的子任务。子智能体有独立上下文，只返回最终答案。适合：并行调研多个主题、独立子问题、需要长时间工具链的任务。不要用于简单查询或单步工具调用。",
  "parameters": {
    "type": "object",
    "properties": {
      "task": {"type": "string", "description": "给子智能体的任务描述，要具体完整"},
      "context": {"type": "string", "description": "可选的背景信息"}
    },
    "required": ["task"]
  }
}
```

**execute**：
```python
def execute(self, task: str, context: str = "") -> str:
    sub = SubAgent(self._llm, self._ltm, depth=self._depth)
    return sub.run(task, context)
```

**依赖注入**：SubAgentTool 在构造时接收 `llm` 和 `long_term_memory` 引用（不通过全局），depth 由构造参数决定。

### 4.3 `NeonAgent` 主循环并行改造

**现状**（`core/agent.py` 第 97-145 行）：
```python
for tool_call in tool_calls:
    # 串行 execute + add_message
```

**改造后**：
```python
# 1. 收集所有 tool_calls
# 2. 用 ThreadPoolExecutor(max_workers=4) 并行 safe_execute
# 3. 等待全部完成，按 call_id 对齐结果
# 4. 按原顺序 add_message("tool", result, tool_call_id=...)
```

**约束**：
- `max_workers=4`（仅用于并行 tool_calls，不含主 agent 自身推理；防止一次性起太多 subagent 拖垮系统）
- 单个工具异常不影响其他工具，各自返回 result/error
- `print_tool_call` 在派发前按顺序打印，`print_tool_result` 在收集后按原顺序打印
- 主循环迭代次数 `max_iterations=10` 保持不变（subagent 内部独立计数）

**线程安全**：
- `LLMClient` 已用 `@property headers` 无状态生成，多线程安全
- `LongTermMemory` 的写操作需加锁（`threading.Lock`），避免并发写文件损坏
- `ToolRegistry.execute_tool` 无共享可变状态，安全

### 4.4 `main.py` 的 `/sub` 命令

**用法**：`/sub <task description>`

**行为**：
- 直接实例化 `SubAgent(llm=agent.llm, long_term_memory=agent.long_term_memory, depth=2)`（depth 与主 agent 调 task 工具时一致，保证用户手动起也能递归 2 层）
- 调 `run(task)`，结果用 `print_assistant_message` 打印，前缀 "[子智能体]"
- 不进入主对话历史（一次性）
- `/help` 增加 `/sub` 说明

## 5. 错误处理

| 场景 | 处理 |
|------|------|
| SubAgent 内 LLM 连接失败 | 返回 `"[subagent error: connection]"`，主 agent 可见，可重试 |
| SubAgent 工具异常 | 内部捕获，写 long_term_memory，继续循环 |
| SubAgent 超时（>180s） | Timer 强制返回 `"[subagent timeout]"` |
| SubAgent 达到 10 轮未出 Final Answer | 返回最后一轮 content 或 `"[subagent: max iterations]"` |
| 主循环并行某工具异常 | 不影响其他工具，该工具返回 error 字符串 |
| 递归深度耗尽仍调 task | SubAgentTool 未注册，LLM 调用会得到 "Tool 'task' not found" |

## 6. 测试策略

- **SubAgent 单元测试**：mock LLMClient，验证 ReAct 循环、Final Answer 解析、超时、异常返回格式
- **SubAgentTool 测试**：mock SubAgent.run，验证工具返回值正确传入主循环
- **并行执行测试**：构造 2 个慢工具（sleep 2s），验证并行总耗时 ≈ 2s 而非 4s
- **递归测试**：depth=0 时不注册 SubAgentTool，验证工具列表无 "task"
- **集成测试**：主 agent 收到 "并行调研 A 和 B" 类任务，验证能并行起 2 个 subagent

## 7. 范围外（YAGNI）

明确不做：
- subagent 进度条/流式输出（只返回最终答案）
- subagent 历史持久化（独立 memory 用完即弃）
- subagent 权限隔离（全工具，信任内部代码）
- subagent 计费/ token 统计
- 预设角色 subagent（用户未要求）
- /sub 后台运行（用户未要求，并行已通过主循环实现）

## 8. 实现顺序

1. `core/subagent.py` — SubAgent 类 + 单元测试
2. `tools/subagent.py` — SubAgentTool
3. `NeonAgent` 注册 SubAgentTool + 主循环并行改造
4. `main.py` 添加 `/sub` 命令 + `/help` 更新
5. `LongTermMemory` 加写锁
6. 集成测试 + 语法验证
