# MINGCODE <img src="https://img.shields.io/badge/version-1.4.0-neon?style=flat-square&color=%2300ff88" alt="version"> <img src="https://img.shields.io/badge/python-3.8+-blue?style=flat-square" alt="python"> <img src="https://img.shields.io/badge/tests-261-passing-neon?style=flat-square&color=%2300ff88" alt="tests"> <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="license">

> ⚡ 赛博朋克风格的终端 AI 编码助手，综合 4 种认知框架（Plan-and-Execute + Self-Reflection + Thinking/ToT + Self-Ask）+ LLM 上下文压缩 + RAG 知识库 + Token 可视化，支持多模型供应商、工具调用、会话持久化、多平台接入

**MINGCODE** 是一个轻量级、高颜值的命令行 AI 编码代理。它不再只是单一的 ReAct 循环，而是用状态机调度四种认知框架：复杂任务先规划再执行、执行后反思、失败自动重规划、不确定时主动向用户提问。当对话变长时自动 LLM 摘要压缩早期上下文（超 2/3 阈值触发，可手动 `/compress`），不再受硬轮数限制。每次联网搜索的结果会自动 LLM 归纳为 Obsidian 笔记存入本地知识库（RAG），下次相似问题先查 KB 避免重复联网。所有 LLM 调用的 token 消耗实时可视化（`/tokens` 详细面板）。同时兼容任何 OpenAI 格式 API，可通过微信 / QQ 远程接入，开箱即用。

---

## ✨ 特性

### 认知框架（v1.2.0 新增）
- 🧠 **综合认知框架** - 状态机调度 4 种认知框架，告别单一 ReAct 的"走一步看一步"
  - **Plan-and-Execute** - 复杂任务先拆解为子任务列表，再逐个执行
  - **Self-Reflection** - 每个任务执行后 LLM 反思，识别假成功（result 含 Error/Traceback）
  - **Thinking (ToT)** - 规划时生成 N 个候选方案 → LLM 评分 → 选最优
  - **Self-Ask** - 执行中遇不确定自动调 ask_user 工具向用户提问
- 🔄 **分级降级 L1/L2/L3** - 任务失败时局部重试 → 整体重规划（带 feedback）→ 报错给用户
- ⚡ **智能分类触发** - 简单任务（hi/你好）走 ReAct 快速响应，复杂任务走完整认知框架
- 🛡️ **延迟构造 + fallback** - CognitiveController 异常时自动回退到 ReAct，零感知升级

### 基础能力
- 🎨 **赛博极简 UI** - 霓虹青绿色调（#00ff88），锐利边框，打字机流式输出，代码语法高亮
- 🔌 **多供应商支持** - 兼容任何 OpenAI 格式 API：Ollama / OpenAI / DeepSeek / Qwen / Zhipu / Moonshot / 自定义
- 🛠️ **15+ 内置工具** - Shell、文件读写编辑、Python 执行、网络搜索、Git、HTTP、数学、时间、待办、子智能体、桌面控制（vision）
- 🧩 **子智能体（Subagent）** - 主 Agent 可自主派生子智能体处理独立子任务，支持有限递归
- 💬 **多平台接入** - 微信（ClawBot）、QQ（OneBot 11 + 官方 Bot），远程也能用
- 💾 **会话持久化** - 支持保存/加载/删除历史会话
- 📦 **上下文压缩（v1.3.0 新增）** - 取消硬轮数限制，token 超 `max_context_tokens * 2/3` 自动 LLM 摘要压缩早期对话，保留最近 K 轮原始消息；`/compress` 手动触发；`/config` 显示 token 进度条
- 📚 **RAG 知识库（v1.4.0 新增）** - 网络搜索结果自动 LLM 归纳为 Obsidian 兼容 Markdown 笔记存入本地 vault，支持关键词检索（TF 打分 + 标题/标签加权）；Agent 可调 `kb_search`/`kb_read`/`kb_store` 工具复用历史知识，避免重复联网
- 📊 **Token 消耗可视化（v1.4.0 新增）** - 每次回复后显示紧凑 token 行（prompt in → completion out），`/tokens` 查看详细面板（按模型分组、调用次数、平均 token、最近 5 次调用）；自动支持 API usage 和字符估算兜底
- 🧠 **自我进化记忆** - 四类长期记忆（偏好/项目/成功/教训），自动从错误中学习
- 🖥️ **桌面控制** - 截屏 + 鼠标键盘 + vision LLM 分析，对标 Codex computer use
- ⚙️ **交互式配置** - 内置 `/settings` 向导，无需手动编辑配置文件
- 📦 **一键安装** - 图形化安装程序，安装后输入 `mingcode` 即可使用
- 🧪 **TDD 工作流** - 内置专业编码代理提示词，遵循 RED-GREEN-REFACTOR 开发流程
- 🔬 **推理模型支持** - reasoning_effort 参数（None/low/medium/high）控制思考深度

---

## 🏗️ 认知框架架构

```
用户输入
  │
  ▼
CLASSIFY（LLM 分类 + 本地预过滤）
  │
  ├─ simple（短输入/问候）→ fallback ReAct（快速响应，零额外 LLM 调用）
  │
  └─ complex（写代码/分析/创建）
      │
      ▼
  PLANNING（ToT: N 候选 → LLM 评分 → 选最优 → 解析任务列表）
      │
      ▼
  EXECUTING（ReAct 串行循环 + Self-Ask 不确定性检测）
      │
      ▼
  REFLECTING（LLM 假成功检测 + L1/L2/L3 分级降级）
      │
      ├─ success → 下一个任务
      ├─ L1: 局部重试（retries ≤ max_task_retries）
      ├─ L2: 整体重规划（带 feedback，replan_count ≤ max_replans）
      └─ L3: 报错给用户
      │
      ▼
  DONE（汇总所有任务结果）
```

**关键设计**：
- **LLM 分类触发**：避免简单任务过度规划，"hi" 直接走 ReAct
- **本地预过滤**：输入 ≤ 6 字符或匹配问候词 → 零 LLM 调用直接 simple
- **ToT 内嵌 Planner**：不破坏对外接口，候选生成/评估/筛选作为内部方法
- **分级降级带 feedback**：L2 重规划时把失败原因喂给 Planner，避免重复失败
- **SelfAsker 失败不阻断**：LLM 异常、ask_user 异常都兜底返回，不阻塞主循环

---

## 🚀 快速开始

### 方式一：使用安装程序（推荐用户）

1. 前往 [Releases](https://github.com/yourname/mingcode/releases) 下载最新的 `MINGCODE-Setup-1.2.0.exe`
2. 双击运行安装向导，默认勾选"Add to PATH"
3. **打开一个新的终端窗口**，输入 `mingcode` 启动
4. 首次运行输入 `/settings` 配置你的 LLM 供应商

### 方式二：从源码运行（开发者）

```bash
# 克隆仓库
git clone https://github.com/yourname/mingcode.git
cd mingcode

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py

# 或者添加到PATH后直接运行
# 把当前目录加入系统PATH，之后任意终端输入 mingcode 即可
```

### 方式三：自己构建安装包

如果你想自己编译exe和安装程序：

1. 安装依赖：`pip install -r requirements.txt pyinstaller`
2. 下载安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)
3. 双击运行 `build.bat`
4. 构建产物在 `dist/` 目录下

### 快速验证

```bash
# 启动后输入 /doctor 全面健康检查
> /doctor

# 配置 LLM
> /settings

# 测试简单对话
> hi

# 测试复杂任务（触发认知框架）
> 请帮我写一个贪吃蛇游戏的 Python 代码

# 查看认知框架状态
> /cognitive
```

---

## 📖 使用指南

### 首次配置

启动后输入 `/settings` 进入交互式配置向导：

1. 选择 LLM 供应商（Ollama/OpenAI/DeepSeek/Qwen等）
2. 输入 API Key
3. 输入模型名称（例如 `deepseek-chat`、`gpt-4o`、`qwen2.5:7b`）
4. （可选）配置 reasoning_effort（推理模型才需设置）
5. 确认配置保存

### 常用命令

#### 基础命令
| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/settings` | 交互式配置 LLM 供应商 |
| `/config` | 查看当前配置 |
| `/model <name>` | 切换模型 |
| `/reasoning [low\|medium\|high\|off]` | 设置推理模型思考深度 |
| `/tools` | 列出可用工具 |
| `/debug` | 快速诊断（环境+配置+测试请求） |
| `/doctor` | 全面健康检查（依赖/网络/LLM） |
| `/clear` | 清空当前对话 |
| `/exit` | 退出（提示保存未保存会话） |

#### 认知框架（v1.2.0 新增）
| 命令 | 功能 |
|------|------|
| `/cognitive` | 查看当前认知框架状态 |
| `/cognitive on` | 启用认知框架（默认） |
| `/cognitive off` | 关闭认知框架，回退到纯 ReAct |

#### 上下文压缩（v1.3.0 新增）
| 命令 | 功能 |
|------|------|
| `/compress` | 手动强制触发 LLM 摘要压缩（无视阈值，压缩早期对话） |
| `/config` | 显示 token 使用进度条（含当前/阈值/上限） |

#### RAG 知识库（v1.4.0 新增）
| 命令 | 功能 |
|------|------|
| `/kb` | 列出最近 20 条知识笔记 |
| `/kb search <query>` | 关键词检索知识库（TF 打分 + 标题/标签加权） |
| `/kb read <id>` | 按 ID 读取完整笔记 |
| `/kb stats` | 知识库统计（笔记数、热门标签） |
| `/kb add <title> \| <body>` | 手动添加一条知识 |
| `/kb delete <id>` | 按 ID 删除笔记 |

#### Token 可视化（v1.4.0 新增）
| 命令 | 功能 |
|------|------|
| `/tokens` | 显示 Token 消耗面板（总计/按模型分组/最近 5 次调用） |
| （每次回复后） | 自动显示紧凑 token 行：`Tokens: 1,234 in → 567 out (total 1,801) | 3 calls` |

#### 会话管理
| 命令 | 功能 |
|------|------|
| `/new` | 开始新会话（清空历史） |
| `/save [name]` | 保存当前会话 |
| `/load <name>` | 加载已保存会话 |
| `/sessions` | 列出所有已保存会话 |
| `/delsession <name>` | 删除已保存会话 |

#### 长期记忆
| 命令 | 功能 |
|------|------|
| `/remember <text>` | 手动添加长期记忆 |
| `/memory [type]` | 查看长期记忆（preference/project/success/lesson） |
| `/forget <id>` | 删除指定长期记忆 |
| `/clearmemory` | 清空所有长期记忆 |

#### 子智能体
| 命令 | 功能 |
|------|------|
| `/sub <task>` | 启动一次性子智能体处理任务 |

#### 微信接入
| 命令 | 功能 |
|------|------|
| `/wechat login` | 微信 ClawBot 扫码登录 |
| `/wechat start` | 开始监听微信消息 |
| `/wechat stop` | 停止监听微信消息 |
| `/wechat status` | 查看微信 Bot 状态 |
| `/wechat logout` | 微信 Bot 登出 |

#### QQ 接入
| 命令 | 功能 |
|------|------|
| `/qq onebot <sub>` | OneBot 11 子命令（config/connect/stop/status/logout） |
| `/qq official <sub>` | QQ 官方 Bot 子命令（login/config/connect/stop/status/logout） |

### 核心工作流程

MINGCODE 内置了专业的编码代理工作流：

1. **头脑风暴** - 理解需求，提问澄清，生成产品文档
2. **计划阶段** - 拆解任务，制定精细实施计划
3. **执行阶段** - 使用工具逐步实现，严格遵循 TDD
4. **完成阶段** - 验证测试，清理工作树

### 认知框架使用场景

**默认行为**（推荐）：
- 简单输入（hi、你好、谢谢）→ 走 ReAct，秒回
- 复杂任务（写代码、分析、多步骤）→ 走完整认知框架，先规划再执行

**性能调优**：
```yaml
cognitive:
  enabled: true          # 总开关
  tot_candidates: 3      # ToT 候选数（生成 N 个方案对比）
  max_replans: 3         # 最大重规划次数（L2 降级上限）
  max_task_retries: 2    # 单任务最大重试次数（L1 降级上限）
  self_ask: false        # Self-Ask 不确定性检测（开启会每轮 ReAct 多一次 LLM 调用，按需开启）
```

**何时开启 self_ask**：
- 任务参数模糊（如"处理那个文件"）需要 AI 主动澄清时
- 用户希望 AI 在不确定时主动提问而非瞎猜时
- 注意：开启会让复杂任务每轮 ReAct 多一次 LLM 调用，速度变慢

### 子智能体（Subagent）

主 Agent 在 ReAct 循环中可自主调用 `task` 工具派生子智能体：

- **独立上下文** - 子智能体有独立的对话记忆，主 Agent 只收到最终答案
- **串行执行** - 同一轮的多个工具调用串行执行（避免顺序错乱）
- **有限递归** - 递归深度 2 层（主 → sub → sub，共 3 层调用链）
- **经验共享** - 子智能体学到的成功/教训写入共享的长期记忆池

也可通过 `/sub <task>` 手动启动一次性子智能体。

### 桌面控制（Computer Use）

内置 ComputerUseTool，对标 Codex computer use：

- **截屏 + vision 分析** - 截屏后调多模态 LLM 识别屏幕元素（带坐标）
- **鼠标键盘自动化** - click / type / key / drag / open_app
- **4 步工作流** - screenshot → click/type → screenshot 验证 → 循环
- **Windows 应用启动** - 支持 Chinese name（如"微信"），用 PowerShell Get-StartApps 反查 AppID
- **临时文件清理** - 截图文件分析完立即删除，不占磁盘

```bash
# 让 AI 帮你打开微信并发送消息
> 帮我打开微信，给张三发一条消息说"你好"
```

### RAG 知识库（v1.4.0 新增）

每次网络搜索/抓取的结果会自动 LLM 归纳为 Obsidian 兼容的 Markdown 笔记，存入本地 vault。下次相似问题先查 KB，避免重复联网。

- **自动归纳** - `WebSearchTool` / `WebFetchTool` 执行成功后钩入 `KnowledgeBase.store_search_result()`
- **非阻塞设计** - KB 存储失败不影响搜索结果返回；LLM 不可用时降级为截取原始结果入库
- **结构化笔记** - YAML frontmatter（id/title/source/query/urls/tags/created）+ Markdown 正文（摘要/关键发现/详细内容/来源）
- **关键词检索** - 中英文分词（英文按单词，中文按 2-gram）+ TF 打分 + 标题命中加权 ×3 + 标签命中加权 ×2
- **Obsidian 兼容** - 把 `vault_path` 配置为你的 Obsidian vault 目录，即可在 Obsidian 中直接浏览笔记（支持 frontmatter、标签、双链）
- **Agent 工具** - `kb_search`（关键词检索）/ `kb_read`（按 ID 读取）/ `kb_store`（主动写入）
- **子智能体共享** - SubAgent 的搜索结果也归入同一个 KB，主子 Agent 共享知识

```bash
> 搜索 LangChain StateGraph 的用法
# 自动归纳入库 → 下次问类似问题，AI 先调 kb_search 复用历史知识
> LangChain 怎么定义条件边？
> /kb search langgraph 条件边
```

### Token 消耗可视化（v1.4.0 新增）

所有 LLM 调用的 token 消耗实时跟踪，支持 API usage 和字符估算兜底两种模式。

- **每次回复后显示紧凑行** - `Tokens: 1,234 in → 567 out (total 1,801) | 3 calls`
- **`/tokens` 详细面板** - 会话总量、按模型分组、调用次数、平均 token、最近 5 次调用
- **流式 usage 提取** - 通过 `stream_options.include_usage: true` 请求流式响应的 token 用量
- **字符估算兜底** - API 未返回 usage 时按 4 字符 ≈ 1 token 估算
- **新会话重置** - `/clear` 或 `/new` 清空对话时 token 计数清零

### 微信 / QQ 接入

**微信 ClawBot**：`/wechat login` 扫码登录后，`/wechat start` 开始监听。微信消息会转发给 MINGCODE 处理并自动回复。

**QQ OneBot**：需先运行 NapCat / Lagrange 等协议端并登录个人 QQ。`/qq onebot config` 填写 WebSocket 地址，`/qq onebot connect` 连接。

**QQ 官方 Bot**：需在 [q.qq.com](https://q.qq.com) 注册机器人。`/qq official login` 扫码自动绑定（AES-GCM 解密获取 secret），或 `/qq official config` 手动填写 appid + secret，然后 `/qq official connect`。

---

## 🏗️ 项目结构

```
mingcode/
├── config/              # 配置管理
│   └── config.py
├── core/                 # 核心引擎
│   ├── agent.py          # NeonAgent 主入口（cognitive + ReAct fallback）
│   ├── cognitive.py      # CognitiveController 状态机（v1.2.0 新增）
│   ├── planner.py        # Planner + ToT 思维树（v1.2.0 新增）
│   ├── executor.py       # Executor ReAct + Self-Ask 触发（v1.2.0 新增）
│   ├── reflector.py      # Reflector 假成功检测 + 降级（v1.2.0 新增）
│   ├── self_asker.py     # SelfAsker 不确定性检测（v1.2.0 新增）
│   ├── subagent.py       # 子智能体（独立上下文 ReAct）
│   ├── llm.py            # LLM API 客户端（含 reasoning_effort + token usage 提取）
│   ├── memory.py         # 对话记忆与会话管理 + 上下文压缩（v1.3.0）
│   ├── token_tracker.py  # Token 消耗跟踪器（v1.4.0 新增）
│   ├── knowledge_base.py # RAG 知识库（Obsidian vault 归纳+检索）（v1.4.0 新增）
│   ├── long_term_memory.py    # 自我进化长期记忆
│   ├── todo.py           # 待办清单（跨会话持久化）
│   ├── wechat_bot.py     # 微信 ClawBot (iLink) 客户端
│   ├── qq_onebot.py      # QQ OneBot 11 客户端
│   └── qq_official.py    # QQ 官方开放平台 Bot 客户端
├── tools/                # 内置工具
│   ├── base.py           # 工具基类与注册表
│   ├── shell.py          # Shell 命令执行
│   ├── files.py          # 文件读写编辑
│   ├── code.py           # Python 代码执行
│   ├── search.py         # 网络搜索（含 KB 自动归纳入库钩子 v1.4.0）
│   ├── subagent.py       # 子智能体工具（task）
│   ├── ask_user.py       # 向用户提问（Self-Ask 调用）
│   ├── plan_tot.py       # ToT 规划薄包装（v1.2.0 改为调 Planner）
│   ├── todo.py           # 待办清单工具
│   ├── time_tool.py      # 时间日期
│   ├── math_tool.py      # 精确数学（decimal）
│   ├── http_tool.py      # HTTP 请求调试
│   ├── git_tool.py       # Git 版本控制
│   ├── computer_use.py   # 桌面控制（截屏+鼠标键盘+vision）
│   ├── office.py         # Office 文档读写（Word/PDF/Excel/PPT）
│   └── kb_tool.py        # 知识库工具（kb_search/kb_read/kb_store）（v1.4.0 新增）
├── ui/                   # 终端 UI
│   ├── console.py        # Rich 渲染组件
│   └── theme.py          # 赛博主题配色
├── tests/                # 单元测试（261 个，覆盖认知框架+压缩+KB+Token）
├── docs/superpowers/     # 设计文档与实现计划
│   ├── specs/            # 设计规格
│   └── plans/            # 实现计划（TDD 任务分解）
├── build.bat             # 一键构建脚本
├── main.py               # 程序入口
├── mingcode.bat          # 开发环境启动脚本
├── mingcode.spec         # PyInstaller 打包配置
├── setup.iss            # Inno Setup 安装程序脚本
├── requirements.txt      # 运行依赖
└── requirements-dev.txt  # 开发依赖（pytest）
```

---

## 🔧 配置说明

配置文件位置：
- **开发模式**：项目目录下 `config.yaml`
- **安装后**：`%APPDATA%\MINGCODE\config.yaml`

配置示例：

```yaml
llm:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  model: "deepseek-chat"
  temperature: 0.7
  max_tokens: 4096
  reasoning_effort: null  # null/low/medium/high（仅推理模型需设置）

ui:
  theme: "neon"
  animation: true
  show_thinking: true
  show_tools: true

tools:
  shell:
    enabled: true
    timeout: 30
  file:
    enabled: true
  python:
    enabled: true
    timeout: 10
  search:
    enabled: true
    max_results: 5

memory:
  max_history: 50              # 向后兼容字段，不再用于硬截断
  max_context_tokens: null     # 上下文 token 上限，null=继承 llm.max_tokens；自动压缩阈值 = 此值 * 2/3
  keep_recent_turns: 6         # 压缩时保留最近 K 轮原始对话（每轮 = user + assistant）

cognitive:
  enabled: true           # 总开关，关闭后回退到纯 ReAct
  tot_candidates: 3       # ToT 候选数
  max_replans: 3          # L2 最大重规划次数
  max_task_retries: 2     # L1 单任务最大重试次数
  self_ask: false         # Self-Ask 不确定性检测（开启会拖慢复杂任务）

knowledge_base:           # RAG 知识库（v1.4.0）
  enabled: true           # 总开关，关闭后搜索结果不入库
  vault_path: null        # Obsidian vault 路径，留空用用户数据目录/vault/
  auto_store: true        # 网络搜索/抓取后自动 LLM 归纳入库
  max_note_length: 4000   # 单条笔记最大字符数

wechat:
  enabled: false
  auto_start: false

qq:
  onebot:
    enabled: false
    ws_url: "ws://127.0.0.1:3001"
    access_token: ""
    auto_start: false
  official:
    enabled: false
    appid: ""
    secret: ""
    auto_start: false
```

---

## 🧪 测试

项目内置 174 个单元测试，覆盖认知框架全流程：

```bash
# 运行全部测试
python -m pytest tests/ -q --tb=short

# 运行认知框架测试
python -m pytest tests/test_cognitive_controller.py -v
python -m pytest tests/test_planner.py -v
python -m pytest tests/test_reflector.py -v
python -m pytest tests/test_self_asker.py -v
python -m pytest tests/test_executor.py -v
```

测试覆盖：
- **CognitiveController** - 状态机 + L1/L2/L3 降级 + 本地预过滤（12 个）
- **Planner** - ToT 候选生成/评估/筛选 + 解析（12 个）
- **Reflector** - LLM 假成功检测 + 失败兜底（7 个）
- **SelfAsker** - 不确定性检测 + ask_user 调用（11 个）
- **Executor** - ReAct 循环 + 不确定性触发（10 个）
- **Memory Compress** - 上下文压缩 + 阈值触发 + 多次合并 + 兜底（14 个，v1.3.0）
- **KnowledgeBase** - 归纳/存储/检索/分词/钩子/工具（34 个，v1.4.0）
- **TokenTracker** - record/estimate/summary/by_model/reset/format（13 个，v1.4.0）
- 其他工具、记忆、IM 接入等（148 个）

---

## 🎓 学习路线

如果你想从零开始学习复刻这个项目，请参考保姆级学习指南：[MINGCODE_LEARNING_ROADMAP.md](MINGCODE_LEARNING_ROADMAP.md)

学习路线涵盖 14 个阶段，从 Python 工程化基础到 v1.4.0 RAG 知识库 + Token 可视化综合实现，每个阶段都有：
- 核心知识点 + 练习任务
- 对应项目文件参考
- 验收标准 + 工程改进对比

---

## 🔄 版本历史

| 版本 | 主要特性 |
|------|---------|
| **v1.4.0** | **RAG 知识库 + Token 可视化**：网络搜索结果自动 LLM 归纳为 Obsidian 笔记存入 vault，`/kb` 命令族检索/读取/写入/删除；`/tokens` 详细面板 + 每次回复后紧凑 token 行；TF 打分 + 标题/标签加权检索；KB 钩子非阻塞设计 |
| **v1.3.0** | **上下文压缩**：取消硬轮数限制，token 超 `max_context_tokens * 2/3` 自动 LLM 摘要压缩早期对话；`/compress` 手动触发；`/config` 显示 token 进度条 |
| v1.2.0 | 综合认知框架（Plan-Execute + Self-Reflection + ToT + Self-Ask），状态机调度，L1/L2/L3 分级降级 |
| v1.1.1 | reasoning_effort 参数支持推理模型思考深度 |
| v1.1.0 | Computer Use 桌面控制（截屏 + vision + 鼠标键盘） |
| v1.0.x | 基础 ReAct Agent + 工具系统 + 微信/QQ 接入 + 会话持久化 |

---

## 📝 开源协议

MIT License - 详见 LICENSE 文件

---

## ⚠️ 注意事项

- 安装完成后**必须打开一个新的终端窗口**才能使用 `mingcode` 命令（Windows 环境变量刷新限制）
- 默认配置指向本地 Ollama (`http://localhost:11434/v1`)，首次使用请运行 `/settings` 配置
- Shell 工具可以执行系统命令，请确保你理解命令含义后再确认执行
- 微信 / QQ Bot 监听会与本地终端共享同一个 Agent 对话历史，多渠道消息会混在同一上下文
- QQ OneBot 方案使用第三方协议端，理论上存在被风控的可能；官方 Bot 方案无此风险但受 intents 限制
- v1.2.0 认知框架默认开启，如遇性能问题可用 `/cognitive off` 关闭回退到纯 ReAct
- `self_ask` 默认关闭以保持速度，需要 AI 主动提问澄清时再开启
- 推理模型（o-series / DeepSeek-R1 等）才支持 reasoning_effort，普通模型设置后会报 400
- v1.3.0 上下文压缩取消硬轮数限制：token 超 `max_context_tokens * 2/3` 自动触发 LLM 摘要，无 LLM 客户端时退化为截断标记
- 压缩失败（如 LLM 超时）不阻塞对话，会退化为截断标记保留最近 K 轮
- v1.4.0 RAG 知识库默认启用：网络搜索/抓取后自动入库（可通过 `knowledge_base.auto_store: false` 关闭）
- KB 存储失败不影响搜索/抓取主流程（非阻塞设计）；LLM 不可用时降级为截取原始结果入库
- 知识库 vault 目录默认在用户数据目录下，可配置为 Obsidian vault 路径直接在 Obsidian 中浏览
- Token 跟踪支持 API usage 和字符估算兜底两种模式；流式响应通过 `stream_options.include_usage` 请求 usage

---

## 🛣️ 路线图

- [ ] 思维树多轮迭代 - PlanToTTool 支持多轮自反思优化（当前是单次调用）
- [ ] ask_user 多渠道接入 - 微信/QQ 远程用户也能回答 AI 提问
- [ ] CognitiveController 手动模式 - `/plan` `/reflect` 等子命令细粒度控制
- [x] RAG 知识库 - 网络搜索结果自动归纳为 Obsidian 笔记，TF 打分检索（v1.4.0 已实现基础版）
- [ ] 向量语义检索 - 用 embedding 模型替代 TF 打分，提升知识库召回准确率
- [ ] 多会话切换 UI - 同时管理多个独立对话
- [ ] 主题切换 - 支持其他配色（除霓虹青绿外）
- [ ] 对话导出为 Markdown
- [ ] 多渠道上下文隔离 - 给每个 IM 用户/群维护独立 memory

---

## 💬 反馈与贡献

欢迎提 Issue 反馈 bug 或建议新特性。如需贡献代码：

1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交改动：`git commit -m "feat: add amazing feature"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

贡献时请确保：
- 新功能附带单元测试（遵循 TDD：RED → GREEN → REFACTOR）
- 全套测试通过：`python -m pytest tests/ -q`
- 遵循现有代码风格（赛博极简 UI、霓虹青绿色调、sharp borders、no shadows）
- 提交信息使用约定式提交（feat/fix/docs/chore/test/refactor）
