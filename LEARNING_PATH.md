# MINGCODE-LC 学习路线

> 一份从零到掌握 MINGCODE-LC（LangChain 版 MINGCODE）的循序渐进学习路径。
> 适合已熟悉 Python 基础但不了解 LangChain/LangGraph 的开发者。

---

## 路线总览

```
阶段 0: 前置基础        ──→  1-2 天
阶段 1: 项目骨架        ──→  1-2 天   (Phase 0 对应)
阶段 2: 工具系统        ──→  2-3 天   (Phase 1 对应)
阶段 3: 认知框架基础    ──→  3-4 天   (Phase 2 对应)
阶段 4: 反思与降级      ──→  2-3 天   (Phase 3 对应)
阶段 5: 高级认知        ──→  3-4 天   (Phase 4 对应)
阶段 6: IM 与打包       ──→  1-2 天   (Phase 4 后半)
阶段 7: 实战与扩展      ──→  持续
```

完成全部阶段后，你将能够独立设计并实现基于 LangGraph 的智能体框架。

---

## 阶段 0：前置基础

### 目标
掌握 MINGCODE-LC 用到的核心技术栈，避免边学项目边补基础。

### 学习内容

**1. LangChain 基础**
- ChatOpenAI 客户端：`langchain-openai` 包
- Messages：`HumanMessage` / `SystemMessage` / `AIMessage`
- 同步 vs 流式：`invoke()` vs `stream()`
- 推荐阅读：[LangChain 官方教程](https://python.langchain.com/docs/tutorials)

**2. LangGraph 基础**
- StateGraph 概念：节点（node）+ 边（edge）+ 状态（state）
- TypedDict 定义状态
- 条件边（conditional_edges）路由
- 入口点（entry_point）和终点（END）
- 推荐阅读：[LangGraph 官方教程](https://langchain-ai.github.io/langgraph/tutorials/intro/)

**3. 工具系统基础**
- `@tool` 装饰器
- Pydantic BaseModel 描述参数 schema
- `create_react_agent` 预构建 ReAct agent

**4. Rich 与 uv**
- Rich：`Theme` / `Live` / `Console` / `Text`
- uv：`uv venv` / `uv pip install` / `uv sync`

### 验收标准
- [ ] 能用 ChatOpenAI 写一个 hello world
- [ ] 能用 StateGraph 构建两节点图（A → B → END）
- [ ] 能用 @tool 装饰器定义一个简单工具

---

## 阶段 1：项目骨架

### 对应代码
- `pyproject.toml` — uv 项目配置
- `config/config.py` — 配置加载
- `ui/theme.py` + `ui/console.py` + `ui/callbacks.py` — Rich UI
- `core/llm.py` — ChatOpenAI 工厂
- `main.py` — CLI 入口

### 学习路径

1. **读 `pyproject.toml`**：理解依赖结构（langchain-core / langchain-openai / langgraph / rich / pydantic / pyyaml）
2. **读 `ui/theme.py`**：NEON_THEME 赛博极简风格定义
3. **读 `ui/console.py`**：`print_assistant_message` / `print_tool_call` / `print_tool_result` / `print_thinking_spinner`
4. **读 `ui/callbacks.py`**：`RichStreamHandler(BaseCallbackHandler)` 桥接 LangChain 流式 token 到 Rich Live
5. **读 `config/config.py`**：`DEFAULT_CONFIG` / `load_config` / `save_config` / `_deep_merge`
6. **读 `core/llm.py`**：`create_llm(config) -> ChatOpenAI` 工厂，重点看 `reasoning_effort` 顶层 kwarg 处理
7. **读 `main.py`**：`handle_command` 分发 `/help` / `/exit` / `/tools`

### 实践任务
- [ ] 修改 `NEON_THEME` 颜色为个人喜好
- [ ] 添加一个新命令 `/version` 输出版本号
- [ ] 阅读 `tests/test_config.py` / `tests/test_llm.py` / `tests/test_main_cli.py` / `tests/test_callbacks.py` 理解测试风格

### 验收标准
- [ ] 能运行 `python main.py`，看到欢迎界面并执行 `/help`
- [ ] 能解释 `RichStreamHandler.on_llm_new_token` 如何把 token 喂给 Rich Live 区域

---

## 阶段 2：工具系统

### 对应代码
- `tools/` 目录下所有 21 个工具
- `core/agent.py` 的 `_run_react` 方法
- `core/memory.py` — ConversationMemory

### 学习路径（按难度递增）

**简单工具（无依赖）**
1. `tools/time_tool.py` — `time_now`，最简单的 @tool 例子
2. `tools/math_tool.py` — `math_calc`，Decimal 精确计算
3. `tools/ask_user.py` — `ask_user`，input() 交互
4. `tools/shell.py` — `shell`，subprocess.run

**文件工具**
5. `tools/files.py` — `file_read` + `file_write`
6. `tools/code.py` — `python_exec`，tempfile + subprocess

**网络工具**
7. `tools/search.py` — `web_search`（DDGS）+ `web_fetch`（requests）
8. `tools/http_tool.py` — `http_request`，GET/POST/PUT/DELETE

**复合工具**
9. `tools/git_tool.py` — `git_status` + `git_command`（禁 push/force）
10. `tools/todo.py` — 4 个 todo 工具，看 `core/todo.py` 的 TodoList 持久化
11. `tools/plan_tot.py` — 调 Planner
12. `tools/subagent.py` — 派生独立 ReAct agent

**桌面控制**
13. `tools/computer_use.py` — `computer_screenshot` / `computer_click` / `computer_type`

**注册与发现**
14. `tools/__init__.py` — `ALL_TOOLS` 列表 + `get_tool_by_name`

**Agent 集成**
15. `core/agent.py`：
    - `LangChainAgent.__init__` — 构造 LLM + tools + memory
    - `react_agent` property — 延迟构造 `create_react_agent_langgraph`
    - `chat()` 方法 — cognitive 关闭时走 `_run_react`
    - `_run_react()` — 流式 stream + yield content

16. `core/memory.py` — ConversationMemory：max_history 截断 + JSON 持久化

### 实践任务
- [ ] 添加一个新工具 `tools/translate.py`，调用翻译 API
- [ ] 把它注册到 `ALL_TOOLS`
- [ ] 写对应测试 `tests/test_tools_translate.py`
- [ ] 用 `/tools` 命令验证注册成功

### 验收标准
- [ ] 能解释 @tool + Pydantic 如何替代 NeonAgent 的 BaseTool ABC
- [ ] 能解释 `create_react_agent_langgraph` 做了什么
- [ ] 49 个 Phase 1 测试全部通过

---

## 阶段 3：认知框架基础

### 对应代码
- `core/cognitive_graph.py` — LangGraph StateGraph
- `core/planner.py` — Planner（Phase 2 简化版）
- `core/executor.py` — Executor
- `core/reflector.py` — Reflector stub
- `core/self_asker.py` — SelfAsker 占位

### 学习路径

**状态与节点**
1. 读 `AgentState` TypedDict — 理解 10 个状态字段的含义
2. 读 `_initial_state()` — 初始状态构造
3. 读 `classify_node` — 本地预过滤（≤6 字符 → simple，问候词 → simple）
4. 读 `route_after_classify` — 路由函数返回 "simple" / "complex"
5. 读 `done_node` — 汇总 task_list 为 final_answer

**节点工厂**
6. 读 `make_planning_node(planner)` — 闭包工厂模式
7. 读 `make_executing_node(executor)`
8. 读 `make_reflecting_node(reflector)` — Phase 2 stub 版

**Planner**
9. 读 `core/planner.py`：
    - `invoke(user_input, feedback)` — 单次 LLM 调用
    - `_parse_tasks` — JSON 解析 + markdown 代码块剥离
    - `_fallback_task` — 兜底单任务

**Executor**
10. 读 `core/executor.py`：
    - `invoke(task)` — 包装 ReAct agent
    - 消息内容提取（注意 `not getattr(msg, "tool_calls", None)` 的判断）

**图构建**
11. 读 `build_cognitive_graph()`：
    - 节点注册：classify / planning / executing / reflecting / done
    - 入口：classify
    - 条件边：classify → (simple|complex)
    - Phase 2 版：reflecting → done 直连

**集成**
12. 读 `core/agent.py` 的 `cognitive_graph` property — 延迟构造 + 依赖注入
13. 读 `chat()` 方法：cognitive 启用走 graph，simple 回退 ReAct

### 实践任务
- [ ] 画一张 5 节点状态机图，标注每条边的路由条件
- [ ] 修改 `classify_node` 添加新的问候词
- [ ] 修改 `done_node` 改变汇总格式
- [ ] 阅读 `tests/test_cognitive_graph.py` 理解 LangGraph 测试模式

### 验收标准
- [ ] 能解释 TypedDict + StateGraph 如何替代 NeonAgent 的 while 循环
- [ ] 能解释节点工厂为什么用闭包（依赖注入 + 保持节点函数签名 `(state) -> state`）
- [ ] 能在纸上画出 simple / complex 两种输入的完整流程
- [ ] 78 个 Phase 1+2 测试全部通过

---

## 阶段 4：反思与降级

### 对应代码
- `core/reflector.py` 升级版 — LLM 假成功检测
- `core/cognitive_graph.py` 的 `route_after_reflect` + `make_reflecting_node` 升级版

### 学习路径

**Reflector 升级**
1. 读 `Reflector.invoke()` 三层规则：
    - status=failed → fail
    - result 含错误关键词 → fail
    - LLM 评估（异常兜底 success）
2. 读 `_llm_evaluate()` — 500 字符截断 + 解析 SUCCESS/FAIL
3. 理解为什么 LLM 异常要兜底 success（不阻塞流程）

**L1/L2/L3 降级**
4. 读 `make_reflecting_node()` 升级版：
    - success → 推进任务或 all_done
    - 失败 + `retries <= max_task_retries` → `retry_l1`
    - 失败 + `replan_count <= max_replans` → `replan_l2`（收集 feedback）
    - 否则 → `fail_l3`（task.status = failed）
5. 读 `route_after_reflect()` — 5 个分支路由

**条件边接入**
6. 读 `build_cognitive_graph()` 升级版：
    - `reflecting` 后用 `add_conditional_edges` 替代直连
    - 5 个 verdict 映射到 3 个目标节点

### 实践任务
- [ ] 修改 `max_task_retries` 和 `max_replans` 观察重试次数变化
- [ ] 添加一个新错误关键词到 Reflector
- [ ] 阅读 `tests/test_reflector.py` 的 LLM 评估测试，理解 mock 模式
- [ ] 阅读 `tests/test_cognitive_graph.py` 的 L1/L2/L3 集成测试

### 验收标准
- [ ] 能解释 L1/L2/L3 各自的触发条件
- [ ] 能解释为什么 L2 重规划要传 feedback
- [ ] 能解释 Reflector 兜底 success 而非 fail 的设计理由
- [ ] 98 个 Phase 1+2+3 测试全部通过

---

## 阶段 5：高级认知

### 对应代码
- `core/planner.py` 升级版 — ToT
- `core/self_asker.py` 升级版 — LLM 不确定性检测

### 学习路径

**ToT 思维树**
1. 读 `Planner.invoke()` 升级版：生成 → 评分 → 选最优
2. 读 `_generate_candidates()` — 循环 N 次调 LLM 生成不同方案
3. 读 `_evaluate_candidate()` — LLM 评分 + 正则提取数字 + 兜底 0.5
4. 读 `_select_best()` — `max(range(...), key=scores[i])`

**SelfAsker**
5. 读 `SelfAsker.invoke()` — LLM 判 CONFIDENT/UNCERTAIN
6. 读 `SelfAsker.ask()` — 查 ask_user 工具或走 input 兜底
7. 理解为什么 LLM 异常要兜底 confident（不阻塞流程）

### 实践任务
- [ ] 修改 `tot_candidates` 从 3 改为 5，观察效果
- [ ] 修改 `_evaluate_candidate` 的 prompt 改变评分标准
- [ ] 阅读 `tests/test_planner.py` 的 ToT 测试，理解 `patch.object` mock 私有方法
- [ ] 阅读 `tests/test_self_asker.py` 理解 `llm=None` 占位 vs LLM 检测两种场景

### 验收标准
- [ ] 能解释 ToT 三步骤（生成/评分/筛选）相比单次规划的优势
- [ ] 能解释为什么 SelfAsker 在 Executor 中是可选的
- [ ] 106 个 Phase 1-4 Task 1-2 测试全部通过

---

## 阶段 6：IM 与打包

### 对应代码
- `core/wechat_bot.py` / `qq_onebot.py` / `qq_official.py`
- `core/long_term_memory.py`
- `config/config.py` 的 `get_user_data_dir()`
- `mingcode-lc.spec` + `build.bat`
- `main.py` 的 `/wechat` / `/qq` 命令

### 学习路径

**配置基础**
1. 读 `get_app_dir()` — 应用目录（开发 vs 打包模式）
2. 读 `get_user_data_dir()` — 用户数据目录（APPDATA 或 ~/.mingcode-lc）

**IM 模块（复用 NeonAgent）**
3. 读 `core/long_term_memory.py` — LongTermMemory 类
4. 读 `core/wechat_bot.py` — WeChatBot 类（依赖 requests）
5. 读 `core/qq_onebot.py` — QQOneBot 类（依赖 websocket-client）
6. 读 `core/qq_official.py` — QQOfficialBot 类

**main.py 命令**
7. 读 `_handle_wechat()` — 子命令 status/login/start/stop/logout
8. 读 `_handle_qq()` — 协议 onebot|official + 子命令

**打包**
9. 读 `mingcode-lc.spec` — hiddenimports / datas / EXE 配置
10. 读 `build.bat` — uv sync → pyinstaller 流程

### 实践任务
- [ ] 执行 `build.bat` 实际打包一次
- [ ] 阅读 `tests/test_im_import.py` 理解导入测试模式

### 验收标准
- [ ] 能解释开发模式和打包模式下数据目录的差异
- [ ] 122 个全部测试通过

---

## 阶段 7：实战与扩展

### 实战任务

**1. 端到端 smoke test**
- 配置真实 LLM（DeepSeek/OpenAI/Ollama）
- 输入复杂任务（如"写一个贪吃蛇游戏"）观察完整流程
- 验证 ToT 生成多个候选 + L1 重试 + 最终汇总

**2. 添加新工具**
- 选一个真实需求（如天气查询、文件转换）
- 实现 @tool + Pydantic
- 注册到 ALL_TOOLS
- 写 TDD 测试

**3. 添加新节点**
- 在 `cognitive_graph.py` 加一个 "validation" 节点
- 在 executing 和 reflecting 之间插入
- 添加条件边路由

**4. 处理 LangGraph 弃用警告**
- 把 `from langgraph.prebuilt import create_react_agent` 改为 `from langchain.agents import create_agent`
- 跑全部测试确认无回归

**5. 深度集成 IM 到 Agent**
- 在 `LangChainAgent.__init__` 中初始化 wechat_bot 等属性
- 让 `/wechat status` 命令真实工作

### 进阶阅读

- LangGraph 官方文档：[Multi-Agent Systems](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/)
- LangChain Tools 高级用法：[Custom Tool Types](https://python.langchain.com/docs/how_to/custom_tools/)
- LangGraph Persistence：[SqliteSaver 完整用法](https://langchain-ai.github.io/langgraph/concepts/persistence/)

---

## 测试套件对照表

| 阶段 | 测试文件 | 数量 | 累计 |
|------|---------|------|------|
| Phase 0 | test_callbacks / test_config / test_llm / test_main_cli | 16 | 16 |
| Phase 1 | test_tools_* / test_memory / test_agent | 33 | 49 |
| Phase 2 | test_cognitive_graph / test_planner / test_executor / test_reflector / test_self_asker | 29 | 78 |
| Phase 3 | test_reflector 升级 / test_cognitive_graph 升级 | 20 | 98 |
| Phase 4 | test_planner ToT / test_self_asker 升级 / test_tools_advanced / test_im_import / test_main_cli 升级 / test_agent smoke | 24 | 122 |

每个阶段完成后跑对应测试验证理解：
```bash
.venv\Scripts\python.exe -m pytest tests/test_<module>.py -v
```

---

## 学习建议

1. **按阶段顺序学习**：每个阶段都建立在前一阶段之上，跳着学会导致理解断层
2. **先读测试再读实现**：测试是行为契约，先看测试理解"做什么"再看实现理解"怎么做"
3. **动手修改**：每阶段都有实践任务，不亲手改代码就无法真正理解
4. **画图辅助**：状态机图、调用关系图、数据流图，纸笔画一遍胜过读十遍
5. **对照 NeonAgent**：同一功能的两种实现对照看，能深刻理解架构差异

---

## 完成标志

完成全部 7 个阶段后，你应该能：

- [ ] 独立设计一个基于 LangGraph 的智能体状态机
- [ ] 用 @tool + Pydantic 设计可扩展的工具系统
- [ ] 实现 L1/L2/L3 分级降级策略
- [ ] 集成 ToT 多候选规划
- [ ] 集成 LLM 假成功检测
- [ ] 打包并分发 Python 应用
- [ ] 对比 NeonAgent 和 MINGCODE-LC 的架构差异并解释优劣

恭喜完成学习路线！
