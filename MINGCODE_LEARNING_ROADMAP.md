# 🚀 MINGCODE 保姆级复刻学习路线 v1.0.6

**总周期：10-12周 | 每日投入：1-2小时 | 目标：1:1完整复刻**

---

## 📋 学前准备
- [ ] 安装 Python 3.8+（推荐3.10/3.11）
- [ ] 安装 VS Code + Python 插件
- [ ] 注册一个 LLM API 账号（DeepSeek 最便宜，或者本地装 Ollama）
- [ ] 下载安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)（打包用，免费）
- [ ] （可选）准备一个微信账号和一部手机（用于阶段十扫码）
- [ ] （可选）在 [q.qq.com](https://q.qq.com) 注册 QQ 官方机器人（用于阶段十官方 Bot）

---

## 🔧 项目所用技术框架详解

### 核心依赖库
| 库 | 版本 | 用途 | 重要程度 |
|----|------|------|---------|
| **requests** | >=2.28.0 | HTTP 客户端，调用 LLM API、网络搜索、网页抓取、微信/QQ Bot 接口 | ⭐⭐⭐⭐⭐ |
| **rich** | >=13.0.0 | 终端 UI 框架，负责所有界面渲染、彩色输出、面板、动画 | ⭐⭐⭐⭐⭐ |
| **pyyaml** | >=6.0 | YAML 配置文件读写 | ⭐⭐⭐⭐ |
| **pygments** | >=2.15.0 | 代码语法高亮，Rich 内部使用 | ⭐⭐⭐⭐ |
| **duckduckgo-search** | >=3.9.0 | DuckDuckGo 网络搜索 API | ⭐⭐⭐ |
| **qrcode** | >=7.3.1 | 终端绘制 ASCII 二维码（微信/QQ 扫码登录用） | ⭐⭐⭐⭐ |
| **websocket-client** | >=1.6.0 | WebSocket 客户端，连接 QQ OneBot / 官方 Bot | ⭐⭐⭐⭐ |
| **cryptography** | >=41.0.0 | AES-GCM 解密 QQ 官方 Bot 扫码绑定返回的 secret | ⭐⭐⭐ |

### 开发依赖
| 库 | 用途 |
|----|------|
| **pytest** | 单元测试框架，配合 mock_llm fixture 测试 Agent 行为 |

### 构建与打包工具
| 工具 | 用途 |
|------|------|
| **PyInstaller** | 将 Python 脚本打包成单个独立 exe 文件，包含 Python 运行时和所有依赖 |
| **Inno Setup 6** | 制作专业图形化 Windows 安装程序，支持开始菜单、桌面快捷方式、PATH 配置、卸载 |

### 架构模式
| 模式 | 应用位置 |
|------|---------|
| **ReAct Agent** | 核心推理循环：Thought(思考) → Action(工具调用) → Observation(观察结果) → Answer(回答) |
| **注册表模式 (Registry)** | 工具系统：ToolRegistry 统一注册、管理、调度所有工具 |
| **策略模式** | 多 LLM 供应商支持：通过 base_url 切换，统一 OpenAI 兼容接口 |
| **生成器模式 (Generator)** | 流式输出：用 yield 逐块返回 LLM 响应，实现打字机效果 |
| **关键词检索 + 评分** | 长期记忆：基于标签重叠、子串匹配、使用频率、最近使用时间综合排序 |
| **组合模式 (Composition)** | SubAgent 独立类组合复用主 LLM 和 LongTermMemory，不继承 NeonAgent |
| **递归 + 深度控制** | SubAgent 通过 depth 参数限制递归层数，到 0 不再注册 task 工具 |
| **线程池并行** | ThreadPoolExecutor(max_workers=4) 并行执行同一轮多个 tool_calls |
| **后台守护线程** | 微信/QQ Bot 用 daemon thread + 长轮询/WS 监听消息，主线程不被阻塞 |
| **Mock 测试** | pytest + MagicMock 构造 mock_llm fixture，预编排 LLM 响应序列 |
| **依赖注入** | AskUserTool 通过构造参数注入 prompt_func（默认 input），便于测试和未来接 IM 渠道 |
| **思维树（ToT）单次调用** | PlanToTTool 用结构化 prompt 让 LLM 一次完成"3 候选→评估→筛选→最终计划"，避免多轮对话 |
| **共享实例协同** | AI 工具（TodoTool）与用户命令（/todo）注入同一 TodoList 实例，操作完全同步 |
| **多模态消息格式** | chat_with_image 用 OpenAI vision 标准：content 为 list，含 text + image_url（base64 data URI） |
| **ANSI 半块字符渲染** | print_screenshot_thumbnail 用 ▀ 字符 + truecolor 一次显示两行像素，codex 风格终端缩略图 |
| **三路独立降级** | screenshot 内截屏/vision/缩略图三者异常互不影响，分别降级为 Error/placeholder/跳过 |
| **串行 ReAct 循环** | 同一轮多个 tool_calls 改为 for 循环串行执行（替代 ThreadPoolExecutor），思考一步执行一步，每个工具结果出来后立即输出 |
| **参数名冲突坑** | execute_tool(self, name, **kwargs) 的位置参数 name 会与工具参数 name="微信" 冲突，必须重命名为 tool_name |
| **模块级 import 检测坑** | _check_optional("pyautogui") 只检测不导入，模块级名字未绑定会报 NameError，必须 if available: import xxx |

### 项目架构总览
```
┌─────────────────────────────────────────────────────────────────┐
│                            main.py                              │
│  入口、斜杠命令（/help /settings /sub /wechat /qq ...）、向导   │
└──────────────┬──────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────┐
│                       core/agent.py                             │
│  NeonAgent 主类：ReAct 循环、并行工具调度、长期记忆集成        │
│  ThreadPoolExecutor(max_workers=4)                              │
└──────┬─────────────┬──────────────┬──────────────┬─────────────┘
       │             │              │              │
┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐ ┌────▼────────────┐
│ core/llm.py │ │memory.py │ │long_term_   │ │ core/subagent.py│
│ LLM 客户端  │ │对话记忆  │ │memory.py    │ │ 子智能体        │
│ 流式/非流式 │ │滑动窗口  │ │ 持久记忆    │ │ 独立 ReAct      │
│ @property   │ │会话存取  │ │ 线程锁      │ │ depth 递归      │
└─────────────┘ └──────────┘ └─────────────┘ └─────────────────┘
       │                                                  │
       │   ┌──────────────────────────────────────────────┘
       │   │ (SubAgent 复用主 LLM 和 LongTermMemory)
       │   ▼
┌──────▼──────────────────────────────────────────────────────────┐
│                       tools/base.py                             │
│          BaseTool 抽象基类 + ToolRegistry 注册表               │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬──────────────────┘
   │      │      │      │      │      │      │
┌──▼──┐┌──▼─┐ ┌──▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼─────────┐
│shell││files│ │code │ │sear│ │sub │ │ask │ │ plan_tot   │
│.py  ││.py  │ │.py  │ │ch  │ │agent│ │user│ │ 思维树规划 │
└─────┘└─────┘ └─────┘ └────┘ └────┘ └────┘ └────────────┘
                                              ┌─▼──────────┐
                                              │ todo.py    │
                                              │ 待办清单工具│
                                              └────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  即时通讯接入层（core/）                        │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ wechat_bot   │  │ qq_onebot    │  │ qq_official        │    │
│  │ iLink Bot    │  │ OneBot 11    │  │ 官方开放平台       │    │
│  │ 长轮询收消息 │  │ WebSocket    │  │ WebSocket + 心跳   │    │
│  │ 幽灵字段     │  │ 断线重连     │  │ AccessToken 刷新   │    │
│  │ context_token│  │              │  │ 扫码绑定(AES-GCM)  │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
│         └─────── daemon thread + handler 回调 ──────┘           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              AI 主动规划层（core/ + tools/）                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ core/todo.py │  │ ask_user.py  │  │ plan_tot.py         │    │
│  │ 跨会话持久化 │  │ 依赖注入     │  │ 单次 LLM 调用       │    │
│  │ todos.json   │  │ prompt_func  │  │ 3 候选→评估→筛选    │    │
│  │ 三状态机     │  │ 默认 input  │  │ 结构化 prompt 模板  │    │
│  └──────────────┘  └──────────────┘  └────────────────────┘    │
│         └──── AI 与 /todo 命令共享 TodoList 实例 ──────┘        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                              ui/                                │
│  console.py - Rich 组件渲染、面板、动画、打字机效果            │
│  theme.py   - 赛博主题配色定义                                 │
└─────────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│                   config/config.py                              │
│  配置加载/保存、用户数据目录定位、默认配置（含 wechat/qq 节）  │
└─────────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│                          tests/                                 │
│  conftest.py - mock_llm + tmp_memory_file fixtures              │
│  test_subagent.py / test_subagent_tool.py                       │
│  test_parallel_execution.py / test_long_term_memory_lock.py     │
│  test_ask_user.py / test_plan_tot.py / test_todo*.py            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🟢 阶段一：Python 项目工程化基础（3-5天）
**目标：掌握现代Python项目结构和开发规范**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 模块化与包管理 | ⭐⭐⭐⭐⭐ | `__init__.py`、相对导入、绝对导入、避免循环依赖（延迟导入） |
| 类型提示（Type Hints） | ⭐⭐⭐⭐⭐ | `typing` 模块、`List/Dict/Optional/Generator` |
| 虚拟环境 | ⭐⭐⭐⭐ | `venv`、依赖隔离 |
| 路径处理 | ⭐⭐⭐⭐ | `pathlib.Path` 替代 `os.path` |
| 面向对象进阶 | ⭐⭐⭐⭐ | 抽象基类（ABC）、@property 装饰器、组合优于继承 |
| 异常处理 | ⭐⭐⭐ | 自定义异常、try-except-finally 最佳实践 |
| JSON 序列化 | ⭐⭐⭐⭐ | json 模块读写结构化数据 |

### 🎯 练习任务
1. 创建标准项目目录结构：
   ```
   my_agent/
   ├── config/        # 配置模块
   ├── core/          # 核心逻辑
   ├── tools/         # 工具模块
   ├── ui/            # UI模块
   ├── tests/         # 单元测试
   └── main.py        # 入口
   ```
2. 每个目录创建 `__init__.py`，练习跨模块导入
3. 用 `pathlib.Path` 写一个读取当前目录文件列表的脚本
4. 写一个抽象基类 `BaseClass`，定义抽象方法，然后实现子类
5. 练习用 json 模块读写一个列表到文件
6. **循环依赖练习**：A 模块 import B，B 又需要 A，用函数内延迟 import 打破循环（参考 tools/subagent.py）

### 📂 对应项目文件参考
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py#L1-L15) - 项目路径处理
- [tools/base.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/base.py#L1-L20) - 抽象基类示例
- [tools/subagent.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/subagent.py) - 延迟 import 打破循环依赖
- [config/config.py](file:///c:/Users/bloon/Downloads/neon_agent/config/config.py) - 配置文件读写示例

### ✅ 验收标准
- [ ] 能熟练在不同模块间互相导入
- [ ] 知道如何用延迟 import 解决循环依赖
- [ ] 所有函数参数和返回值都有类型提示
- [ ] 会用 `pathlib` 处理路径，不硬编码分隔符
- [ ] 能正确读写 JSON 文件

---

## 🟢 阶段二：终端 UI 开发 - Rich 库深度掌握（5-7天）
**目标：做出 MINGCODE 那样炫酷的赛博风格终端界面**

> 💡 Rich 是这个项目的 UI 灵魂，务必多花时间练习！

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| Console 对象 | ⭐⭐⭐⭐⭐ | 控制台输出基础 |
| Text 样式 | ⭐⭐⭐⭐⭐ | 颜色、加粗、斜体、样式组合、自定义颜色（#00ff88） |
| Panel 面板 | ⭐⭐⭐⭐⭐ | 带边框的面板，box.SQUARE 直角边框（赛博风格不用圆角） |
| Table 表格 | ⭐⭐⭐⭐⭐ | 数据表格展示（会话列表、记忆列表、Bot 状态） |
| Syntax 代码高亮 | ⭐⭐⭐⭐ | Markdown 代码块语法高亮（Pygments 后端） |
| Live 动态更新 | ⭐⭐⭐⭐ | 打字机流式输出效果 |
| Progress + Spinner | ⭐⭐⭐⭐ | Thinking... 加载动画 |
| Prompt 交互式输入 | ⭐⭐⭐⭐ | 密码输入、确认框、选项选择 |
| Group 组合渲染 | ⭐⭐⭐ | 多个组件组合在一起 |

### 🎯 练习任务（按顺序做）
1. **Task 1**：用 Rich 打印彩色 "Hello World"，尝试红/绿/蓝/霓虹青（#00ff88）
2. **Task 2**：打印 MINGCODE 的大 ASCII Logo（参考 [console.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/console.py#L32-L39)）
3. **Task 3**：创建两个 Panel：蓝色边框 "YOU"、青绿色边框 "MINGCODE"，用 box.SQUARE 直角边框
4. **Task 4**：用 Table 做一个简单的数据列表，带标题、彩色列
5. **Task 5**：实现 Markdown 代码块渲染 - 把 ```python ... ``` 渲染成 Syntax 高亮
6. **Task 6**：用 Live 实现打字机效果 - 一个字一个字输出面板内容
7. **Task 7**：做一个 spinner 加载动画，显示 "Thinking..."，3秒后消失
8. **Task 8**：用 Prompt.ask()/Confirm.ask() 做一个交互式问答（名字、年龄、密码输入、确认）

### 📂 对应项目文件参考
- [ui/theme.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/theme.py) - 颜色和样式定义
- [ui/console.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/console.py) - 所有 UI 渲染函数
  - `print_logo()` - 打印 Logo
  - `print_user_message()` - 用户消息面板（蓝色）
  - `print_assistant_message()` - AI回复（青绿色，含打字机效果）
  - `print_thinking_spinner()` - 思考动画
  - `print_tool_call()` - 工具调用面板（紫色）
  - `print_tool_result()` - 工具结果面板（灰色）
  - `print_error()` - 错误提示（红色）

### ✅ 验收标准
- [ ] 能复刻 MINGCODE 的启动界面（大 Logo + 欢迎文字 + 版本号）
- [ ] 用户/AI/工具/结果四种面板样式都能实现，全部直角边框
- [ ] Markdown 代码块能正确高亮
- [ ] 打字机流式输出流畅不卡顿
- [ ] 能用 Table 渲染会话列表、记忆列表、Bot 状态

---

## 🟡 阶段三：LLM API 对接（4-6天）
**目标：实现与大模型的对话，支持流式输出**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| REST API 基础 | ⭐⭐⭐⭐⭐ | POST 请求、headers、JSON |
| requests 库 | ⭐⭐⭐⭐⭐ | HTTP 请求、stream=True 流式响应 |
| OpenAI Chat Completions API 格式 | ⭐⭐⭐⭐⭐ | /v1/chat/completions 接口、消息格式（role/content） |
| SSE 流式响应 | ⭐⭐⭐⭐⭐ | Server-Sent Events、逐行解析、data: 前缀、[DONE] 结束标记 |
| 生成器（Generator/yield） | ⭐⭐⭐⭐⭐ | yield 逐块返回内容，实现流式迭代 |
| @property 装饰器 | ⭐⭐⭐⭐ | 动态 headers，api_key 修改后立即生效 |
| 多供应商兼容 | ⭐⭐⭐⭐ | base_url 切换支持不同厂商（OpenAI/DeepSeek/Ollama/Qwen等） |
| 非流式响应 | ⭐⭐⭐⭐ | stream=False 模式，SubAgent 用它跑独立 ReAct |

### 🎯 练习任务
1. **Task 1**：用 requests 写一个最简单的非流式调用，向 DeepSeek/OpenAI 发请求，获取回复
2. **Task 2**：改成流式调用（stream=True），用 for 循环逐块打印返回内容
3. **Task 3**：封装成 `LLMClient` 类，包含 `__init__`（设置 base_url/api_key/model/temperature/max_tokens）和 `chat()` 方法
4. **Task 4**：chat() 方法改造成生成器，用 yield 返回每个 token，而不是一次性返回
5. **Task 5**：把 headers 改成 @property，确保 api_key 修改后请求头立即更新
6. **Task 6**：chat() 方法增加 `stream` 参数，True 走生成器，False 返回完整 dict（后续 SubAgent 要用）
7. **Task 7**：测试不同的 base_url：
   - Ollama: `http://localhost:11434/v1`
   - DeepSeek: `https://api.deepseek.com/v1`
   - 确保换个 URL 就能用，不用改其他代码

### 📂 对应项目文件参考
- [core/llm.py](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py) - LLM 客户端实现
  - `@property headers` - 动态请求头技巧
  - 流式响应解析逻辑
  - `StreamResponse` 类包装流式结果

### 💡 关键提示
```python
# 流式响应解析的核心代码模式
response = requests.post(url, headers=self.headers, json=data, stream=True, timeout=120)
response.raise_for_status()
for line in response.iter_lines():
    if not line:
        continue
    line = line.decode('utf-8').strip()
    if line.startswith('data: '):
        data = line[6:]
        if data == '[DONE]':
            break
        try:
            chunk = json.loads(data)
            delta = chunk['choices'][0]['delta']
            if 'content' in delta and delta['content']:
                yield delta['content']
        except json.JSONDecodeError:
            continue
```

### ✅ 验收标准
- [ ] 能成功调用至少一个 LLM API 得到回复
- [ ] 流式输出正常，一个字一个字蹦出来
- [ ] 非流式模式（stream=False）能返回完整 dict
- [ ] 切换 base_url 就能换供应商，代码不用改
- [ ] 修改 api_key 后不需要重启程序

---

## 🟡 阶段四：对话记忆与会话管理（3-4天）
**目标：实现多轮对话、记住上下文、会话持久化**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 消息列表管理 | ⭐⭐⭐⭐⭐ | system/user/assistant/tool 四种角色 |
| 滑动窗口 | ⭐⭐⭐⭐ | 保留最近 N 轮对话（*2条消息/轮），避免 token 超限 |
| 系统提示词（System Prompt） | ⭐⭐⭐⭐⭐ | Agent 的"人设"、工作流程指令、工具描述 |
| 会话序列化 | ⭐⭐⭐⭐ | JSON 保存/加载完整对话历史 |
| 自动命名 | ⭐⭐⭐ | 从第一条用户消息自动生成会话名 |
| 消息预览 | ⭐⭐⭐ | 列表显示时截断长消息 |

### 🎯 练习任务
1. **Task 1**：实现 `ConversationMemory` 类基础功能
   - `add_message(role, content)` 添加消息
   - `get_messages()` 获取所有消息（包含system prompt）
   - `clear()` 清空历史
2. **Task 2**：添加滑动窗口功能 - 只保留最近 N 轮对话（默认20轮）
3. **Task 3**：实现系统提示词构建 `build_system_prompt(tools_list)`，包含TDD/YAGNI/DRY工作流、工具使用说明
4. **Task 4**：实现会话保存功能 `save(name=None)` - 将messages序列化到JSON文件，name为空时自动从首条消息命名
5. **Task 5**：实现会话加载功能 `load(name)` - 从JSON文件恢复对话历史
6. **Task 6**：实现 `list_sessions()` - 列出所有保存的会话，带保存时间、消息数、内容预览
7. **Task 7**：实现 `delete_session(name)` - 删除指定会话

### 📂 对应项目文件参考
- [core/memory.py](file:///c:/Users/bloon/Downloads/neon_agent/core/memory.py) - 对话记忆、系统提示词、会话持久化

### ✅ 验收标准
- [ ] 可以多轮对话，LLM 能记住之前说的话
- [ ] 输入 `/new`/`/clear` 能清空对话历史
- [ ] `/save`/`/load`/`/sessions`/`/delsession` 命令工作正常
- [ ] 超过20轮自动截断最早的消息
- [ ] 会话列表显示正确的预览

---

## 🟠 阶段五：工具系统 - ReAct Agent 核心（7-10天）
**目标：这是最核心的部分！实现 Agent 思考→调用工具→观察→回答的完整循环**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| ReAct 推理模式 | ⭐⭐⭐⭐⭐ | Thought(思考) → Action(工具调用) → Observation(结果) → Answer循环 |
| 抽象基类 + 注册表模式 | ⭐⭐⭐⭐⭐ | BaseTool定义接口，ToolRegistry统一注册/发现/执行工具 |
| Function Calling | ⭐⭐⭐⭐⭐ | OpenAI 工具调用格式：tools参数、tool_calls响应 |
| JSON 格式解析 | ⭐⭐⭐⭐ | 解析工具调用参数，处理异常情况 |
| subprocess 模块 | ⭐⭐⭐⭐ | 执行 Shell 命令，捕获stdout/stderr，超时控制 |
| 文件读写 | ⭐⭐⭐⭐ | 安全的文件操作，编码处理 |
| 上下文管理器 | ⭐⭐⭐⭐ | spinner 动画的上下文管理 `with print_thinking_spinner():` |
| 迭代上限 | ⭐⭐⭐ | 防止Agent无限循环，最多10次工具调用 |
| Windows编码处理 | ⭐⭐⭐⭐ | chcp 65001 解决中文乱码 |
| **ThreadPoolExecutor 并行** | ⭐⭐⭐⭐⭐ | 同一轮多个 tool_calls 并行执行，max_workers=4 |
| **threading.Lock 并发安全** | ⭐⭐⭐⭐ | LongTermMemory 多线程写入加锁 |

### 🎯 练习任务（逐个实现工具）
1. **Task 1**：先搭基础框架
   - 写 `BaseTool` 抽象基类，定义 `name/description/parameters/execute()` 抽象方法
   - 写 `ToolRegistry` 注册表：`register()`, `get_tool()`, `execute_tool()`, `get_all_schemas()`, `list_tools()`
2. **Task 2**：实现 Shell 工具 - 执行终端命令并返回输出，先chcp 65001解决编码问题，带超时
3. **Task 3**：实现文件工具 - FileRead/FileWrite/FileEdit，注意编码utf-8
4. **Task 4**：实现网络搜索工具 - duckduckgo-search 库，返回标题/链接/摘要
5. **Task 5**：实现网页获取工具 - requests抓取网页，简单HTML标签清理
6. **Task 6**：实现 Python 代码执行工具（可选，注意安全，用subprocess执行）
7. **Task 7**：**核心！实现 Agent chat() 循环（串行版）**
   - 用户消息加入memory
   - 循环（最多max_iterations次）：
     - 显示spinner，调用LLM（带tools参数）
     - 流式输出回复内容
     - 检查是否有tool_calls
     - 没有tool_calls → 结束循环，返回给用户
     - 有tool_calls → 依次执行每个工具：显示TOOL面板 → 执行 → 显示RESULT面板 → 结果加入memory作为tool消息
   - 异常处理：工具执行错误加入memory让LLM自我修正
8. **Task 8**：**改造成并行执行**
   - 在 `__init__` 创建 `self._executor = ThreadPoolExecutor(max_workers=4)`
   - 把 `for tool_call in tool_calls:` 串行循环拆成两阶段：
     - 阶段一：顺序解析参数 + print_tool_call（快，UI 不乱序）
     - 阶段二：`self._executor.submit(_exec_one, pc)` 并行执行，`f.result()` 收集
     - 阶段三：按原顺序处理结果，保留错误学习逻辑（auto_learn_from_error / auto_learn_success）
9. **Task 9**：**LongTermMemory 加锁**
   - `__init__` 中 `self._lock = threading.Lock()`
   - `_save()` 用 `with self._lock:` 包裹文件写入
   - 写并发写测试：8 线程 × 20 条 add，文件应保持合法 JSON 且条目数正确

### 📂 对应项目文件参考
- [tools/base.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/base.py) - 工具基类和注册表
- [tools/shell.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/shell.py) - Shell命令执行（注意编码处理）
- [tools/files.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/files.py) - 文件操作
- [tools/search.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/search.py) - 网页搜索和抓取
- [tools/code.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/code.py) - Python代码执行
- [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) - Agent 循环 + 并行执行（重点看 chat 方法）
- [core/long_term_memory.py](file:///c:/Users/bloon/Downloads/neon_agent/core/long_term_memory.py) - 加锁后的并发安全实现

### 💡 关键提示
工具定义使用OpenAI Function Calling标准格式，LLM会自动返回JSON格式的工具调用，不需要正则解析。

并行执行的拆分思路：
```python
# 阶段一：顺序解析参数（快，避免 UI 乱序）
parsed_calls = []
for tool_call in tool_calls:
    arguments = json.loads(tool_call["function"]["arguments"])
    print_tool_call(tool_name, arguments)
    parsed_calls.append({...})

# 阶段二：并行执行
def _exec_one(pc):
    try:
        return pc["call_id"], pc["tool_name"], self.registry.execute_tool(...)
    except Exception as e:
        return pc["call_id"], pc["tool_name"], None, str(e)

futures = [self._executor.submit(_exec_one, pc) for pc in parsed_calls]
results = [f.result() for f in futures]

# 阶段三：按原顺序处理结果（保留错误学习）
for call_id, tool_name, result, error in results:
    if error: ...
    print_tool_result(result)
    self.memory.add_message("tool", result, tool_call_id=call_id)
```

### ✅ 验收标准
- [ ] Agent 能根据用户问题自动决定是否调用工具
- [ ] 每个工具都能正常工作
- [ ] 工具调用结果能正确返回给 LLM 继续推理
- [ ] 工具调用时有紫色 TOOL 面板，结果有灰色 RESULT 面板
- [ ] 遇到错误能自动修正（比如命令输错了会自己调整）
- [ ] 达到最大迭代次数会自动停止，不会死循环
- [ ] **并行执行验证**：两个慢工具（各 sleep 2s）并行总耗时约 2s 而非 4s
- [ ] **并发安全验证**：多线程并发写 LongTermMemory 不损坏文件

---

## 🟠 阶段六：配置系统与交互体验（3-4天）
**目标：实现 YAML 配置、交互式设置向导、斜杠命令**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| YAML 配置 | ⭐⭐⭐⭐⭐ | pyyaml 库读写 yaml 文件 |
| 用户数据目录 | ⭐⭐⭐⭐ | 开发环境用项目目录，安装后用%APPDATA%，避免权限问题 |
| 默认值处理 | ⭐⭐⭐⭐ | 配置不存在时用默认值，首次启动自动生成配置文件 |
| 斜杠命令解析 | ⭐⭐⭐⭐ | split(maxsplit=1)分割命令和参数，分发表格模式 |
| 交互式向导 | ⭐⭐⭐⭐ | Rich Prompt/Confirm/Table 做配置界面 |
| 敏感信息掩码 | ⭐⭐⭐ | 显示配置时API Key只显示后4位 |
| 配置节扩展 | ⭐⭐⭐⭐ | 新增 wechat/qq 配置节，DEFAULT_CONFIG 字典嵌套 |

### 🎯 练习任务
1. **Task 1**：定义 DEFAULT_CONFIG 字典，包含 llm配置、ui配置、tools配置、memory配置，以及 wechat 配置节（enabled/auto_start）
2. **Task 2**：实现 `get_app_dir()` 和 `get_user_data_dir()` - 打包后用%APPDATA%，开发环境用项目目录
3. **Task 3**：实现 `load_config()` 和 `save_config()` 读写 config.yaml，合并加载的配置和默认配置
4. **Task 4**：实现斜杠命令解析 `handle_slash_command(cmd, arg, agent, config, ...)` - 检测用户输入是否以 `/` 开头，分发到对应处理函数
5. **Task 5**：实现 `/settings` 交互式配置向导
   - 列出7个供应商选项（Ollama/OpenAI/DeepSeek/Qwen/Zhipu/Moonshot/Custom）
   - 让用户选，然后输入API Key、模型名、temperature、max_tokens
   - 显示配置摘要，确认后保存
   - 保存后更新agent.llm的属性，清空对话历史
6. **Task 6**：实现核心斜杠命令：`/help` `/model` `/config` `/tools` `/new` `/save` `/load` `/sessions` `/delsession` `/exit`
7. **Task 7**：退出时检测是否有未保存的会话，提示用户保存
8. **Task 8**：扩展 DEFAULT_CONFIG 加入 `qq.onebot` 和 `qq.official` 两个嵌套配置节

### 📂 对应项目文件参考
- [config/config.py](file:///c:/Users/bloon/Downloads/neon_agent/config/config.py) - 配置加载保存、路径定位、wechat/qq 默认配置
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py) - 斜杠命令和设置向导

### ✅ 验收标准
- [ ] 首次启动自动生成默认config.yaml
- [ ] /settings 向导工作正常
- [ ] 修改配置后立即生效，不需要重启程序
- [ ] 所有核心 / 命令都能正常使用
- [ ] /config显示时API Key正确打码
- [ ] 退出时提示保存未保存会话
- [ ] config.yaml 包含 wechat 和 qq 配置节

---

## 🟣 阶段七：自我进化持久记忆系统（3-4天）
**目标：让AI跨会话记住经验，从错误中学习，越用越好用**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 持久化存储 | ⭐⭐⭐⭐⭐ | JSON文件存储长期记忆，跨会话保留 |
| 信息检索（IR）基础 | ⭐⭐⭐⭐ | 关键词提取、停用词过滤、标签匹配 |
| 评分排序 | ⭐⭐⭐⭐ | 多维度评分：关键词重叠*2 + 子串匹配 + 使用频率 + 最近使用时间 |
| 自动知识提取 | ⭐⭐⭐⭐ | 从错误/成功事件中自动提取经验教训 |
| 上下文注入 | ⭐⭐⭐⭐⭐ | 每次提问前检索相关记忆，动态注入系统提示词 |
| 记忆分类 | ⭐⭐⭐ | 四类记忆：preference/project/success/lesson |
| 使用计数与衰减 | ⭐⭐⭐ | 越常用的记忆优先级越高，长期不用的记忆优先级降低 |
| 线程锁 | ⭐⭐⭐⭐ | SubAgent 并发写共享 LongTermMemory 时必须加锁 |

### 🎯 练习任务
1. **Task 1**：实现 `LongTermMemory` 类
   - `_load()`/_save() 读写 long_term_memory.json
   - `add(content, memory_type, tags)` 添加记忆，自动生成uuid，提取标签
   - `_extract_tags(content)` 中英文分词，过滤停用词
2. **Task 2**：实现 `retrieve(query, top_k=5)` 检索功能
   - 提取query关键词
   - 对每条记忆计算得分：标签重叠*2 + 子串匹配 + 使用频率bonus + 最近使用bonus
   - 按得分排序返回top_k，更新last_used和use_count
3. **Task 3**：实现 `format_for_prompt(query)` - 将检索到的记忆格式化为文本，注入系统提示词
4. **Task 4**：实现自动学习方法
   - `auto_learn_from_error(error_msg, fix)` 错误→教训
   - `auto_learn_success(problem, solution)` 成功→经验
   - `auto_learn_preference(context, preference)` 用户偏好
5. **Task 5**：集成到Agent
   - `_build_system_prompt_with_memory(user_input)` 每次提问动态构建带记忆的system prompt
   - 工具执行错误时自动学习（编码错误、权限错误、连接错误等）
   - 失败后重试成功自动记录成功经验
6. **Task 6**：实现记忆管理命令
   - `/remember [type:] <content>` 手动添加记忆
   - `/memory [type]` 表格列出所有记忆
   - `/forget <id>` 删除指定记忆
   - `/clearmemory` 清空所有记忆（需确认）
7. **Task 7**：**加 threading.Lock 保证并发安全**（为阶段九 SubAgent 共享 LongTermMemory 做准备）

### 📂 对应项目文件参考
- [core/long_term_memory.py](file:///c:/Users/bloon/Downloads/neon_agent/core/long_term_memory.py) - 长期记忆核心模块（含线程锁）
- [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) - 记忆集成与自动学习
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py) - 记忆管理命令

### ✅ 验收标准
- [ ] 用 `/remember` 添加的记忆，下次提问相关问题时能被AI参考
- [ ] 遇到一次编码错误后，下次不会再犯同样的错
- [ ] 记忆跨会话保留，重启程序不丢失
- [ ] `/memory` 能正确显示记忆表格，带类型标签和使用次数
- [ ] `/forget` 能删除指定记忆
- [ ] **8 线程并发写 long_term_memory.json 文件不损坏**

---

## 🟦 阶段八：测试基础设施与子智能体系统（5-7天）
**目标：建立 TDD 工作流，实现可递归的 Subagent，主 Agent 能自主派生子智能体并行处理子任务**

> 💡 这一阶段开始进入"高级 Agent 工程"，TDD 是关键，否则并行+递归很难调试

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| pytest 基础 | ⭐⭐⭐⭐⭐ | fixture、断言、运行测试、测试发现规则 |
| unittest.mock.MagicMock | ⭐⭐⭐⭐⭐ | Mock LLMClient，预编排响应序列，避免真实 API 调用 |
| conftest.py 共享 fixture | ⭐⭐⭐⭐ | mock_llm / tmp_memory_file 跨测试文件复用 |
| monkeypatch | ⭐⭐⭐⭐ | 临时替换函数/方法（如 get_user_data_dir 重定向到 tmp_path） |
| TDD 红绿循环 | ⭐⭐⭐⭐⭐ | RED（写失败测试）→ GREEN（最小实现）→ REFACTOR → COMMIT |
| 组合模式 | ⭐⭐⭐⭐⭐ | SubAgent 独立类组合复用主 LLM 和 LongTermMemory，不继承 NeonAgent |
| 递归 + 深度控制 | ⭐⭐⭐⭐⭐ | depth 参数限制递归层数，到 0 不再注册 SubAgentTool |
| threading.Timer 超时 | ⭐⭐⭐⭐ | SubAgent 单次 run 硬超时 180s，daemon 线程兜底 |
| Final Answer 解析 | ⭐⭐⭐⭐ | SubAgent 用 `Final Answer: <结论>` 标记结束，提取结论返回 |
| 工具即子智能体 | ⭐⭐⭐⭐⭐ | SubAgentTool 包装 SubAgent 作为主 Agent 可调用的 `task` 工具 |

### 🎯 练习任务
1. **Task 1**：搭建测试基础设施
   - 创建 `requirements-dev.txt`（pytest>=7.0.0）
   - 创建 `tests/__init__.py` 和 `tests/conftest.py`
   - 在 conftest.py 实现 `mock_llm` fixture：用 MagicMock(spec=LLMClient)，支持 `set_responses([...])` 预编排响应序列，stream=True/False 都支持
   - 实现 `tmp_memory_file` fixture：用 monkeypatch 把 get_user_data_dir 重定向到 tmp_path，避免污染真实数据
   - 写一个 smoke test 验证 pytest 能发现测试
2. **Task 2**：写 LongTermMemory 并发写测试（先红后绿）
   - 测试：8 线程 × 20 条 add，文件应保持合法 JSON 且条目数正确
   - 如果阶段七还没加锁，现在加 threading.Lock 让测试通过
3. **Task 3**：TDD 实现 SubAgent 核心类
   - **RED**：写测试 `test_run_returns_final_answer`，验证 LLM 返回 `"Final Answer: done"` 时 SubAgent.run 返回 `"done"`
   - **GREEN**：创建 `core/subagent.py`，实现：
     - `__init__(llm, long_term_memory, depth=2, timeout=180)` 构造，注册全工具（shell/files/code/search），创建独立 ConversationMemory，追加 SubAgent 专属系统 prompt
     - `run(task, context="")` 跑独立 ReAct 循环（最多 10 轮），用 daemon thread + join(timeout) 实现超时
     - `_parse_final_answer(content)` 提取 Final Answer 后的文本
   - 逐步追加测试：ReAct 多轮（先调工具再 Final Answer）、LLM 异常、超时、max iterations
4. **Task 4**：TDD 实现递归深度控制 + SubAgentTool
   - **RED**：写测试 `test_depth_zero_does_not_register_task_tool` / `test_depth_positive_registers_task_tool`
   - **GREEN**：创建 `tools/subagent.py` 的 SubAgentTool（name="task"，execute 延迟导入 SubAgent 避免循环依赖）
   - 在 SubAgent._register_tools 末尾：`if self.depth > 0: registry.register(SubAgentTool(llm, ltm, depth-1))`
5. **Task 5**：写 SubAgentTool 单元测试（schema + execute 返回结果）
6. **Task 6**：TDD 改造 NeonAgent 主循环为并行（阶段五已做过的话跳过）
   - **RED**：写 SlowTool（sleep 2s），两个并行调用总耗时 < 3.5s（串行会是 4s）
   - **GREEN**：ThreadPoolExecutor(max_workers=4) 并行执行 tool_calls
7. **Task 7**：在 NeonAgent 注册 SubAgentTool（depth=2）
   - 测试：`assert "task" in agent.registry.list_tools()`
8. **Task 8**：在 main.py 添加 `/sub <task>` 命令
   - 实例化 SubAgent，run() 后用 print_assistant_message 打印结果（带 `[子智能体]` 前缀）
   - 结果不进入主对话历史
   - 在 /help 添加 Subagent 板块
9. **Task 9**：集成验证
   - 全部测试通过（pytest tests/ -v）
   - py_compile 所有核心文件
   - 导入冒烟测试
   - 验证 SubAgent 源码不含 print_* 等 UI 副作用（UI 隔离）

### 📂 对应项目文件参考
- [tests/conftest.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/conftest.py) - mock_llm 和 tmp_memory_file fixtures
- [tests/test_subagent.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_subagent.py) - SubAgent 单元测试（6 个）
- [tests/test_subagent_tool.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_subagent_tool.py) - SubAgentTool 测试（3 个）
- [tests/test_parallel_execution.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_parallel_execution.py) - 并行执行 + 主 agent 注册 task 工具
- [tests/test_long_term_memory_lock.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_long_term_memory_lock.py) - 并发写测试
- [core/subagent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/subagent.py) - SubAgent 类
- [tools/subagent.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/subagent.py) - SubAgentTool

### 💡 关键提示
mock_llm fixture 设计要点：
```python
@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMClient)
    responses = []
    def chat(messages, tools=None, stream=False):
        if not responses:
            return {"role": "assistant", "content": "Final Answer: no response", "tool_calls": None}
        return responses.pop(0)
    llm.set_responses = lambda r: responses.extend(r)
    llm.chat.side_effect = chat
    return llm
```

SubAgent 超时实现要点：
```python
worker = threading.Thread(target=_run_internal, daemon=True)
worker.start()
worker.join(timeout=self.timeout)
if worker.is_alive():
    return "[subagent timeout]"  # daemon 线程随进程退出
return result_holder["value"]
```

### ✅ 验收标准
- [ ] 全部测试通过（15+ 个）
- [ ] SubAgent 能解析 Final Answer 返回结论
- [ ] SubAgent 多轮 ReAct 能正确执行工具再返回
- [ ] LLM 异常返回 `[subagent error: ...]`
- [ ] 超时返回 `[subagent timeout]`
- [ ] depth=0 不注册 task 工具，depth>0 注册
- [ ] 主 Agent 工具列表包含 task
- [ ] `/sub <task>` 命令工作正常
- [ ] 主循环并行执行验证通过（两个慢工具总耗时约等于单个）
- [ ] SubAgent 源码不含 UI 副作用（UI 隔离）

---

## 🟥 阶段九：即时通讯平台接入（7-10天）
**目标：让 MINGCODE 接入微信和 QQ，用户可以通过 IM 远程对话**

> ⚠️ 这是项目里最有挑战的部分，涉及协议逆向、长轮询、WebSocket、扫码登录、加密

### 9.1 微信 ClawBot（iLink Bot API） - 3-4天

#### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 协议逆向 | ⭐⭐⭐⭐⭐ | 从 npm 包 TypeScript 源码逆向出 HTTP 接口和"幽灵字段" |
| 长轮询（Long Polling） | ⭐⭐⭐⭐⭐ | POST /getupdates，timeout=35s，服务端 hold 住连接等新消息 |
| 扫码登录流程 | ⭐⭐⭐⭐⭐ | get_bot_qrcode → 终端显示 ASCII 二维码 → 轮询 get_qrcode_status → 拿 token |
| 幽灵字段 | ⭐⭐⭐⭐⭐ | client_id/message_type=2/message_state=2/base_info.channel_version="1.0.3"，缺一消息就被静默丢弃 |
| context_token 机制 | ⭐⭐⭐⭐⭐ | 从 getUpdates 获取，可复用，持久化保存，发送消息必须携带 |
| qrcode 库 | ⭐⭐⭐⭐ | 终端打印 ASCII 二维码（qr.print_ascii(invert=True)） |
| 后台守护线程 | ⭐⭐⭐⭐ | daemon thread 跑长轮询循环，handler 回调处理消息 |
| 凭据持久化 | ⭐⭐⭐⭐ | token/bot_id/user_id/context_tokens 写 wechat_config.json |

#### 🎯 练习任务
1. **Task 1**：研究 iLink Bot 协议（读 [OpenClaw npm 包源码](https://unpkg.com/@tencent-weixin/openclaw-weixin@1.0.3/) 或参考项目里的逆向文档）
2. **Task 2**：实现扫码登录
   - GET /ilink/bot/get_bot_qrcode?bot_type=3 获取二维码
   - 用 qrcode 库在终端打印 ASCII 二维码
   - 轮询 GET /ilink/bot/get_qrcode_status?qrcode=xxx，status=confirmed 时拿到 bot_token/ilink_bot_id/ilink_user_id
3. **Task 3**：实现 HTTP 客户端基础
   - `_headers()` 生成通用请求头（AuthorizationType / Authorization / X-WECHAT-UIN 随机 base64 / Content-Length 精确）
   - `_post(endpoint, body)` 给 body 加 `base_info: {channel_version: "1.0.3"}`，json.dumps(ensure_ascii=False).encode("utf-8")
4. **Task 4**：实现长轮询收消息 `get_updates()`
   - POST /ilink/bot/getupdates，body 含 get_updates_buf（游标）
   - 解析返回的 msgs，自动更新 context_tokens[from_user]
   - 更新游标 get_updates_buf
5. **Task 5**：实现发消息 `send_message(text, to_user_id, context_token)`
   - **关键**：必须包含全部幽灵字段：from_user_id="" / client_id=uuid / message_type=2 / message_state=2 / context_token / base_info.channel_version
   - 缺任何一个，API 返回 200 但消息不投递
6. **Task 6**：实现 send_typing（"正在输入"状态）
7. **Task 7**：实现后台监听 `start_listening(handler)`
   - handler 签名：`(text, from_user) -> str(回复)`
   - daemon thread 跑 _listen_loop：get_updates → 收到消息调 handler → send_message 回复
   - 异常自动重试，间隔 5s
8. **Task 8**：在 main.py 添加 `/wechat login|start|stop|status|logout` 命令
   - handler 把微信消息转发给 agent.chat()，聚合流式输出为完整字符串再发回微信

#### 📂 对应项目文件参考
- [core/wechat_bot.py](file:///c:/Users/bloon/Downloads/neon_agent/core/wechat_bot.py) - 完整 iLink Bot 客户端
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py) - /wechat 命令和 handler 集成

### 9.2 QQ OneBot 11 接入 - 2-3天

#### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| OneBot 11 协议 | ⭐⭐⭐⭐⭐ | 开放机器人标准，正向 WebSocket 接收事件，HTTP 发送动作 |
| NapCat / Lagrange | ⭐⭐⭐⭐ | 第三方 QQ 协议端，登录个人 QQ 号当 Bot |
| WebSocket 客户端 | ⭐⭐⭐⭐⭐ | websocket-client 库，ws.run_forever 阻塞监听 |
| 断线重连 | ⭐⭐⭐⭐ | on_close / on_error 触发重连，间隔 3s |
| 事件分发 | ⭐⭐⭐⭐ | post_type/message_type/message_type 区分私聊/群消息 |
| 消息段（CQ码） | ⭐⭐⭐ | OneBot 消息格式，[{type:"text",data:{text:"..."}}] |

#### 🎯 练习任务
1. **Task 1**：装好 NapCat 并登录个人 QQ（参考 [NapCat 文档](https://napneko.github.io/)）
2. **Task 2**：实现 QQOneBot 类
   - WebSocket 连接 ws://127.0.0.1:3001，带 access_token 鉴权
   - on_message 回调解析事件，提取 text 段
   - send_private_msg / send_group_msg HTTP 接口
3. **Task 3**：实现断线自动重连（间隔 3s）
4. **Task 4**：在 main.py 添加 `/qq onebot config|connect|stop|status|logout` 命令

#### 📂 对应项目文件参考
- [core/qq_onebot.py](file:///c:/Users/bloon/Downloads/neon_agent/core/qq_onebot.py) - OneBot 11 客户端

### 9.3 QQ 官方开放平台 Bot - 2-3天

#### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| QQ 官方 Bot API | ⭐⭐⭐⭐⭐ | q.qq.com 注册，appid + secret 鉴权，WebSocket 事件 + HTTP 动作 |
| AccessToken 鉴权 | ⭐⭐⭐⭐⭐ | POST /app/getAppAccessToken，过期前 60s 自动刷新 |
| WebSocket + 心跳 | ⭐⭐⭐⭐⭐ | 连接后发 IDENTIFY，定期发 HEARTBEAT（5s），断线 RESUME |
| intents 订阅 | ⭐⭐⭐⭐ | 位运算订阅事件类型（GROUP_AT_MESSAGE / DIRECT_MESSAGE 等） |
| 扫码绑定协议 | ⭐⭐⭐⭐ | create_bind_task → 二维码 → poll_bind_result → AES-GCM 解密 secret |
| AES-256-GCM 解密 | ⭐⭐⭐⭐ | cryptography 库，密文 = IV(12B) ‖ ciphertext ‖ tag(16B)，整体 base64 |

#### 🎯 练习任务
1. **Task 1**：在 [q.qq.com](https://q.qq.com) 注册一个机器人，拿到 appid
2. **Task 2**：实现 QQOfficial 类基础
   - `get_access_token()` POST /app/getAppAccessToken，缓存 token，过期前 60s 刷新
   - `connect()` WebSocket 连接，发 IDENTIFY（含 intents、token、shards）
   - 定期发 HEARTBEAT（5s），收 HEARTBEAT_ACK
   - 断线 RESUME 续传
3. **Task 3**：实现事件处理
   - GROUP_AT_MESSAGE（群@消息）：去掉 @ 前缀，调 handler，发 send_group_msg 回复
   - DIRECT_MESSAGE（私信）：调 handler，发 send_direct_msg 回复
4. **Task 4**：实现扫码绑定 `qr_login(print_qr)`（可选，协议在 Hermes Agent v0.11.0 后被移除，但端点仍可用）
   - 生成 32 字节随机 AES 密钥，base64
   - POST https://q.qq.com/lite/create_bind_task，body 含 key
   - 拿 task_id 生成二维码 URL：`https://q.qq.com/qqbot/openclaw/connect.html?task_id=...`
   - 轮询 POST https://q.qq.com/lite/poll_bind_result，status=2 时拿到 bot_encrypt_secret
   - AES-256-GCM 解密：密文 = IV(12B) ‖ ciphertext ‖ tag(16B)，得到 client_secret
   - 自动 configure(appid, secret) 保存
5. **Task 5**：在 main.py 添加 `/qq official login|config|connect|stop|status|logout` 命令

#### 📂 对应项目文件参考
- [core/qq_official.py](file:///c:/Users/bloon/Downloads/neon_agent/core/qq_official.py) - 官方 Bot 客户端（含扫码绑定）

### ✅ 验收标准
- [ ] `/wechat login` 终端显示二维码，手机扫码后状态显示已登录
- [ ] `/wechat start` 后，微信发消息能收到回复
- [ ] `/wechat logout` 清除凭据
- [ ] `/qq onebot connect` 能连上本地 NapCat
- [ ] `/qq official login` 扫码绑定成功（或 `/qq official config` 手动填 appid+secret）
- [ ] `/qq official connect` 后，群里 @ 机器人能收到回复
- [ ] 三个 Bot 共享同一个 NeonAgent 实例
- [ ] 主线程退出时所有监听线程优雅停止

---

## 🔴 阶段十：打包分发与一键安装（3-4天）
**目标：打包成单个exe，制作专业图形化安装程序，用户双击就能装**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| PyInstaller | ⭐⭐⭐⭐⭐ | Python脚本打包成独立exe，--onefile单文件模式 |
| spec 文件配置 | ⭐⭐⭐⭐⭐ | PyInstaller打包配置，指定入口、hiddenimports |
| hiddenimports | ⭐⭐⭐⭐⭐ | qrcode/websocket/cryptography 等动态导入的库必须手动声明，否则打包后 ImportError |
| Inno Setup 脚本 | ⭐⭐⭐⭐ | .iss 文件语法，[Setup]/[Files]/[Icons]/[Tasks]/[Registry]/[Code] 段 |
| 环境变量 PATH | ⭐⭐⭐⭐ | 写入用户注册表HKCU\Environment\PATH，避免管理员权限 |
| 安装/卸载逻辑 | ⭐⭐⭐⭐ | 安装时添加PATH，卸载时清理PATH |
| 安装完成页面 | ⭐⭐⭐ | 提示用户打开新终端运行mingcode |
| 构建自动化 | ⭐⭐⭐ | build.bat 一键完成清理→PyInstaller→Inno Setup全流程 |

### 🎯 练习任务
1. **Task 1**：写 `requirements.txt`，列出所有依赖包和版本要求（含 qrcode/websocket-client/cryptography）
2. **Task 2**：创建 `mingcode.spec` PyInstaller配置文件
   - 指定入口文件main.py
   - 配置console=True（控制台程序）
   - **hiddenimports 必须包含**：duckduckgo_search / pygments / rich / yaml / requests / qrcode / websocket / cryptography
   - 确保所有子模块被正确收集
3. **Task 3**：测试PyInstaller打包：`pyinstaller mingcode.spec --clean --noconfirm`
   - 验证dist/mingcode.exe能独立运行（不需要装Python）
   - 验证微信/QQ 相关 import 不报错
4. **Task 4**：开发环境创建 `mingcode.bat` 启动脚本，添加项目目录到PATH方便开发
5. **Task 5**：编写 `setup.iss` Inno Setup脚本
   - 配置AppId/AppName/AppVersion/默认安装目录（用户目录，不需要管理员权限）
   - [Files]段：打包mingcode.exe
   - [Icons]段：开始菜单快捷方式、桌面快捷方式（可选）
   - [Tasks]段：可选"添加到PATH"（默认勾选）、"创建桌面图标"
   - [Code]段：
     - 安装时检查PATH是否已包含安装目录，防止重复添加
     - 写入用户PATH注册表
     - 卸载时从PATH移除安装目录
     - 安装完成页面显示启动指引（打开新终端，输入mingcode）
   - ChangesEnvironment=yes 广播环境变量变更
6. **Task 6**：创建 `build.bat` 一键构建脚本
   - 检查PyInstaller是否安装，没装自动pip install
   - 清理旧的build/和dist/
   - 运行PyInstaller打包
   - 检测Inno Setup是否安装，找到ISCC.exe
   - 运行ISCC编译安装程序
   - 显示最终产物路径（版本号从 setup.iss 的 #define 同步）
7. **Task 7**：在另一台Windows机器测试完整安装流程
   - 双击MINGCODE-Setup-x.x.x.exe
   - 安装完成后打开新终端
   - 输入mingcode能启动
   - 控制面板能正常卸载

### 📂 对应项目文件参考
- [mingcode.spec](file:///c:/Users/bloon/Downloads/neon_agent/mingcode.spec) - PyInstaller打包配置（含全部 hiddenimports）
- [setup.iss](file:///c:/Users/bloon/Downloads/neon_agent/setup.iss) - Inno Setup安装程序脚本
- [build.bat](file:///c:/Users/bloon/Downloads/neon_agent/build.bat) - 一键构建脚本
- [mingcode.bat](file:///c:/Users/bloon/Downloads/neon_agent/mingcode.bat) - 开发环境启动脚本
- [requirements.txt](file:///c:/Users/bloon/Downloads/neon_agent/requirements.txt) - Python依赖清单
- [requirements-dev.txt](file:///c:/Users/bloon/Downloads/neon_agent/requirements-dev.txt) - 开发依赖（pytest）

### ✅ 验收标准
- [ ] build.bat双击运行能自动完成全流程构建
- [ ] 生成的MINGCODE-Setup-x.x.x.exe是独立安装包
- [ ] 普通用户不需要管理员权限就能安装（安装到用户目录）
- [ ] 安装后打开新终端输入mingcode能启动
- [ ] 启动后微信/QQ 相关命令可用（不报 ImportError）
- [ ] 开始菜单有快捷方式
- [ ] 能从控制面板正常卸载，卸载后PATH被清理

---

## 🟪 阶段十一：AI 主动规划能力（4-6天）
**目标：让 AI 在行动前能提问澄清、用思维树做规划、维护待办清单追踪进度**

> 💡 这是把 Agent 从"被动执行者"升级为"主动规划者"的关键阶段，三个能力互补：ask_user 解决"意图模糊"、plan_tot 解决"方案选择"、todo 解决"进度追踪"

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 依赖注入（DI） | ⭐⭐⭐⭐⭐ | AskUserTool 构造参数注入 prompt_func，解耦 UI 层与工具层，便于测试 mock |
| 思维树（Tree of Thoughts） | ⭐⭐⭐⭐⭐ | PlanToTTool 强制 LLM 走"3 候选 → 评估 → 筛选 → 最终计划"完整循环 |
| 结构化 prompt 工程 | ⭐⭐⭐⭐ | 用固定 Markdown 段落（候选方案/评估/最优方案/最终计划）约束 LLM 输出格式 |
| 单次调用 vs 多轮对话 | ⭐⭐⭐⭐ | ToT 用单次非流式 LLM 调用一次性输出完整规划，比多轮 ReAct 更稳定可控 |
| 跨会话持久化 | ⭐⭐⭐⭐⭐ | TodoList 写到 user_data_dir/todos.json，重启后 load() 恢复 |
| 状态机设计 | ⭐⭐⭐⭐ | 待办三状态 pending → in_progress → completed，允许任意方向跳转 |
| 共享实例协同 | ⭐⭐⭐⭐⭐ | AI 工具（TodoTool）和用户命令（/todo）注入同一 TodoList 实例，操作完全同步 |
| UUID 短 id | ⭐⭐⭐ | uuid.uuid4().hex[:8] 生成 8 字符 id，足够唯一且便于人类阅读 |
| monkeypatch 测试 | ⭐⭐⭐⭐ | conftest.py 用 monkeypatch 把 TodoList 的 get_user_data_dir 重定向到 tmp_path |
| system prompt 强化 | ⭐⭐⭐⭐⭐ | 在执行阶段 prompt 中加入"强制 ask_user / plan_tot / todo"指令，让 AI 主动调用 |

### 🎯 练习任务
1. **Task 1**：TDD 实现 AskUserTool
   - **RED**：写测试 `test_schema` / `test_execute_returns_user_answer` / `test_execute_empty_input_returns_marker` / `test_default_prompt_func_is_input_builtin`
   - **GREEN**：创建 `tools/ask_user.py`，AskUserTool 通过构造参数注入 prompt_func（默认为内置 input），execute 内部调用 prompt_func(question) 获取用户回答
   - 注册到 NeonAgent（不注册到 SubAgent，避免后台任务阻塞）
   - 在 system prompt 工具使用部分加入 ask_user 规则
2. **Task 2**：TDD 实现 PlanToTTool（思维树规划）
   - **RED**：写测试 `test_schema` / `test_execute_returns_llm_content` / `test_prompt_contains_tot_structure_keywords`（断言 prompt 含"候选方案/评估/最优方案/最终计划"）
   - **GREEN**：创建 `tools/plan_tot.py`，构造参数注入 llm，execute 内部用单次非流式 LLM 调用
   - prompt 模板用 Markdown 固定段落约束 LLM 走完整 ToT 循环
   - 在 system prompt 计划阶段加入"思维树规划（强制）"指令
3. **Task 3**：TDD 实现 TodoList 核心类
   - **RED**：写 10 个测试覆盖 add/get/list/update_status/delete/clear_completed/save/load
   - **GREEN**：创建 `core/todo.py`，TodoList 类持久化到 `user_data_dir/todos.json`
   - 三状态机：pending / in_progress / completed
   - 测试 `update_status` 拒绝非法状态、`load` 容错处理文件不存在
4. **Task 4**：TDD 实现 TodoTool
   - **RED**：写测试 `test_schema` / 5 个 action 测试（add/list/update/delete/clear）/ 错误处理测试 / 主 agent 注册测试
   - **GREEN**：创建 `tools/todo.py`，TodoTool 通过 action 参数路由，依赖注入 TodoList 实例
   - 每次写操作后调用 todo.save() 持久化
5. **Task 5**：集成到 NeonAgent + conftest 更新
   - NeonAgent.__init__ 创建 todo_list 并 load() 历史数据
   - 注册 TodoTool(self.todo_list)，AI 与用户共享同一实例
   - conftest.py 的 tmp_memory_file fixture 加 monkeypatch core.todo.get_user_data_dir
6. **Task 6**：实现 /todo 命令族
   - 在 main.py 写 `handle_todo_command(arg, agent)` 函数
   - 子命令：list / add / start / done / pending / delete / clear
   - 在 /help 中加入 Todo List 板块
   - 在 handle_slash_command 中分发 `/todo` 到 handle_todo_command
7. **Task 7**：强化 system prompt
   - 执行阶段加入"待办清单追踪（强制）"指令
   - 工具使用部分加入 todo 工具使用规则
8. **Task 8**：集成验证
   - 全部测试通过（pytest tests/ -v，应 52+ 个）
   - py_compile 所有新增文件
   - 手动验证：AI 主动调用 ask_user 提问、调用 plan_tot 输出规划、调用 todo 维护清单
   - 手动验证：用户 /todo add 后 AI 工具能 list 到同一项

### 📂 对应项目文件参考
- [tools/ask_user.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/ask_user.py) - AskUserTool（依赖注入 prompt_func）
- [tools/plan_tot.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/plan_tot.py) - PlanToTTool（思维树规划，单次 LLM 调用）
- [core/todo.py](file:///c:/Users/bloon/Downloads/neon_agent/core/todo.py) - TodoList 核心类（持久化 + 状态机）
- [tools/todo.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/todo.py) - TodoTool（5 个 action）
- [tests/test_ask_user.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_ask_user.py) - AskUserTool 测试（6 个）
- [tests/test_plan_tot.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_plan_tot.py) - PlanToTTool 测试（8 个）
- [tests/test_todo.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_todo.py) - TodoList 测试（10 个）
- [tests/test_todo_tool.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_todo_tool.py) - TodoTool 测试（13 个）
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py#L92-L159) - handle_todo_command 函数

### 💡 关键提示
依赖注入让工具可测试且可扩展：
```python
class AskUserTool(BaseTool):
    def __init__(self, prompt_func=None):
        # 默认用内置 input；测试时可注入 mock，未来可接 IM 渠道
        self._prompt_func = prompt_func if prompt_func is not None else input

    def execute(self, **kwargs):
        question = kwargs.get("question", "").strip()
        # 始终把原始 question 传给 prompt_func
        answer = self._prompt_func(question)
        return answer.strip() if answer else "(no input)"
```

思维树 prompt 模板要点（强制 LLM 走完整循环）：
```python
_TOT_PROMPT_TEMPLATE = """对以下任务进行思维树规划。
任务: {task}

## 候选方案
### 方案 1: <名称>
- 思路: ...
- 优点: ...
- 缺点: ...
### 方案 2 / 3: 同上结构

## 评估
<横向对比 3 个方案>

## 最优方案
<选中方案> —— <选择理由>

## 最终计划
<基于最优方案的可执行步骤>
"""
```

共享实例协同是核心设计：
```python
# NeonAgent 中创建一次 TodoList 实例
self.todo_list = TodoList()
self.todo_list.load()
# AI 工具注入同一实例
self.registry.register(TodoTool(self.todo_list))
# /todo 命令也用同一实例
# → 用户 /todo add 后 AI 工具能立即 list 到，反之亦然
```

### ✅ 验收标准
- [ ] 全部测试通过（52+ 个）
- [ ] AskUserTool 默认 prompt_func 是内置 input
- [ ] AskUserTool 注入 mock 后能正确返回用户输入
- [ ] PlanToTTool prompt 包含"候选方案/评估/最优方案/最终计划"四段
- [ ] PlanToTTool 用单次非流式 LLM 调用（stream=False）
- [ ] TodoList 三状态机正确转换（pending → in_progress → completed）
- [ ] TodoList update_status 拒绝非法状态
- [ ] TodoList save/load 跨会话持久化
- [ ] TodoList load 容错处理文件不存在
- [ ] TodoTool 5 个 action（add/list/update/delete/clear）全部工作
- [ ] AI 工具与 /todo 命令共享同一 TodoList 实例（操作同步）
- [ ] /todo 命令族 7 个子命令全部工作
- [ ] system prompt 包含 ask_user / plan_tot / todo 三条强制指令

---

## 🟦 阶段十二：Computer Vision 与终端缩略图特效（5-7天）
**目标：让 AI 真正"看见"屏幕——截屏后自动调多模态 LLM 分析画面，并在终端用半块字符渲染缩略图，对标 Codex computer use**

> 💡 这是把 Agent 从"只能读文本"升级为"能看屏幕"的关键阶段。核心能力互补：chat_with_image 解决"画面理解"，print_screenshot_thumbnail 解决"视觉反馈"，区域截屏解决"token 节省"

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 多模态 LLM 消息格式 | ⭐⭐⭐⭐⭐ | OpenAI vision 标准：content 为 list，含 text + image_url 两个 item，base64 编码图片为 data URI |
| ANSI truecolor 半块字符 | ⭐⭐⭐⭐⭐ | ▀（U+2580）一次显示两行像素：上像素做前景色，下像素做背景色，2 像素合并为 1 字符 |
| base64 图片编码 | ⭐⭐⭐⭐ | base64.b64encode 编码 PNG 文件为 ASCII 字符串，拼成 `data:image/png;base64,...` |
| sanitize list 保护 | ⭐⭐⭐⭐⭐ | _sanitize_messages 遇到 list 形式 content（多模态）直接保留不规范化，避免破坏 image_url 结构 |
| 依赖注入扩展 | ⭐⭐⭐⭐ | ComputerUseTool 构造接受 `llm_client=None`，向后兼容无参构造 |
| 三路独立降级 | ⭐⭐⭐⭐⭐ | 截屏失败→return Error；vision 失败→placeholder 字符串；缩略图失败→打印提示，三者互不影响 |
| 区域截屏 bbox 语义 | ⭐⭐⭐⭐ | `PIL.ImageGrab.grab(bbox=(x,y,x+w,y+h))`，部分参数缺失降级为全屏 |
| mock PIL.ImageGrab | ⭐⭐⭐⭐ | 测试中 monkeypatch ImageGrab.grab 返回 MagicMock img，避免真截屏 |
| patch create=True | ⭐⭐⭐ | pyautogui 未安装时模块无该属性，patch.object 用 `create=True` 允许创建 |
| Rich markup=False | ⭐⭐⭐ | Rich 会把 `[text]` 当样式标签吞掉，打印含方括号的提示行需 `markup=False` |
| 串行 ReAct 循环 | ⭐⭐⭐⭐⭐ | 同一轮多个 tool_calls 用 for 循环串行执行（替代 ThreadPoolExecutor），思考一步执行一步 |
| 可选依赖模块级 import | ⭐⭐⭐⭐⭐ | _check_optional 只检测不导入，必须 `if available: import xxx` 在模块级绑定名字，否则 NameError |
| 参数名冲突规避 | ⭐⭐⭐⭐ | execute_tool 第一参数不能叫 name（会与工具参数 name 冲突），必须重命名为 tool_name |
| PowerShell Get-StartApps | ⭐⭐⭐⭐ | Windows start 命令不解析应用名（如"微信"），必须用 PowerShell Get-StartApps 反查 AppID 启动 |
| 高精度 vision prompt | ⭐⭐⭐⭐ | prompt 明确要求检测小元素（桌面图标 32x32、托盘图标 20x20），坐标带 w/h 尺寸 |
| 截图用完即删 | ⭐⭐⭐⭐ | vision 分析完成后 os.remove 删除截图文件，避免磁盘累积临时文件 |
| codex 自主执行 | ⭐⭐⭐ | _confirm 直接返回 True，移除所有写操作的用户确认提示，AI 自主操作 |

### 🎯 练习任务
1. **Task 1**：TDD 实现 LLMClient.chat_with_image
   - **RED**：写 4 个测试 `test_chat_with_image_returns_content` / `test_chat_with_image_builds_image_url_payload` / `test_chat_with_image_propagates_llm_error` / `test_sanitize_messages_preserves_list_content`
   - **GREEN**：在 `core/llm.py` 新增 `chat_with_image(prompt, image_path, system=None)` 方法，base64 编码图片→构造 OpenAI 多模态 messages（content 为 list 含 text + image_url）→调 `self.chat(stream=False)`→返回 content 字符串
   - 在 `_sanitize_messages` 加 list 保护分支：`isinstance(content, list)` 时直接保留不规范化
2. **Task 2**：TDD 实现 print_screenshot_thumbnail
   - **RED**：写 4 个测试 `test_thumbnail_renders_half_block_chars`（断言输出含 `\x1b[38;2;` 和 ▀）/ `test_thumbnail_respects_max_width` / `test_thumbnail_pillow_missing_prints_placeholder` / `test_thumbnail_image_error_prints_error_message`
   - **GREEN**：在 `ui/console.py` 顶部加 `pil_available` 检测；末尾加 `print_screenshot_thumbnail(image_path, max_width=80)` 函数
   - 算法：PIL.Image.open→等比缩放（高除 2 因半块）→resize→双重循环取像素→拼 ANSI truecolor 前景+背景色码 + ▀
   - 用内置 `print` 而非 `console.print`（Rich 会把 ANSI 转义码当文本显示）
3. **Task 3**：TDD 实现 ComputerUseTool 构造注入
   - **RED**：写 2 个测试 `test_no_arg_construction_still_works` / `test_llm_client_injection`
   - **GREEN**：在 `tools/computer_use.py` 的 ComputerUseTool 类顶部加 `__init__(self, llm_client=None)`，存 `self.llm_client`
   - 向后兼容：`ComputerUseTool()` 无参构造仍工作（现有测试零改动）
4. **Task 4**：TDD 实现 _screenshot 区域截屏
   - **RED**：写 3 个测试 `test_screenshot_fullscreen_saves_and_returns_path` / `test_screenshot_region_uses_bbox` / `test_screenshot_region_partial_params_falls_back_to_fullscreen`
   - **GREEN**：schema 加 w/h 参数；`_screenshot(x=None,y=None,w=None,h=None)` 四参数全有走 bbox，部分缺失降级全屏
   - 返回值格式：`Screenshot saved: {path}\nSize: {w}x{h}\nRegion: {desc}`
   - 调用 print_screenshot_thumbnail，失败不影响主流程
5. **Task 5**：TDD 实现 _screenshot vision LLM 集成
   - **RED**：写 4 个测试 `test_screenshot_with_llm_client_calls_vision` / `test_screenshot_without_llm_client_returns_placeholder` / `test_screenshot_vision_error_degrades_gracefully` / `test_screenshot_calls_thumbnail_renderer`
   - **GREEN**：在 _screenshot 缩略图块之后、return 之前加 vision 调用块
   - 降级链：llm_client=None→"(llm_client not configured)"；LLMError→"(vision unavailable: {e})"；其他异常→"(vision error: {e})"
6. **Task 6**：NeonAgent 注册注入
   - 在 `core/agent.py` 把 `ComputerUseTool()` 改为 `ComputerUseTool(llm_client=self.llm)`
   - 运行全套测试验证无回归

### 📂 对应项目文件参考
- [core/llm.py](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py#L132-L155) - chat_with_image 方法（多模态调用）
- [core/llm.py](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py#L90-L92) - sanitize list 保护分支
- [ui/console.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/console.py#L188-L216) - print_screenshot_thumbnail（ANSI 半块渲染）
- [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py) - ComputerUseTool（构造注入 + screenshot 增强）
- [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py#L73) - 注册时注入 llm_client
- [tests/test_computer_vision.py](file:///c:/Users/bloon/Downloads/neon_agent/tests/test_computer_vision.py) - 17 个测试（4+4+2+3+4）

### 💡 关键提示
多模态消息格式是 OpenAI vision 标准：
```python
messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    ],
}]
```

半块字符渲染算法（2 像素合并为 1 字符）：
```python
for y in range(0, resized.height, 2):
    line = ""
    for x in range(new_w):
        upper = resized.getpixel((x, y))           # 上像素→前景色
        lower = resized.getpixel((x, y+1))          # 下像素→背景色
        line += f"\x1b[38;2;{upper[0]};{upper[1]};{upper[2]}m"  # 前景色
        line += f"\x1b[48;2;{lower[0]};{lower[1]};{lower[2]}m"  # 背景色
        line += "▀"                                # 半块字符
    line += "\x1b[0m"                               # 行末重置
    print(line)  # 用内置 print，不用 Rich（Rich 会吞 ANSI）
```

三路独立降级是核心设计（任一环节失败不影响其他）：
```python
try:
    img = ImageGrab.grab(bbox=bbox)  # 截屏失败 → return Error（不到后续）
    img.save(filepath)
    try:
        print_screenshot_thumbnail(filepath)  # 缩略图失败 → 打印提示，不抛
    except: pass
    if self.llm_client:
        try:
            desc = self.llm_client.chat_with_image(...)  # vision 失败 → placeholder
        except LLMError as e:
            desc = f"(vision unavailable: {e})"
    # 全部成功 → 返回组合字符串
except Exception as e:
    return f"Error: {e}"
```

Rich markup 吞方括号的坑：
```python
# 错误：Rich 把 [text] 当样式标签，输出空行
console.print("[thumbnail unavailable: Pillow not installed]")
# 正确：markup=False 让 Rich 按字面文本渲染
console.print("[thumbnail unavailable: Pillow not installed]", markup=False)
```

### 🛠️ 工程改进（v1.1.0）
本阶段在初版完成后做了若干工程改进，建议学习者按顺序对照实现，每改完一步跑测试验证无回归：

| 改进点 | 原问题 | 改进方案 | 涉及文件 |
|--------|--------|----------|----------|
| 串行 ReAct 循环 | ThreadPoolExecutor 并行执行导致工具结果顺序错乱、用户难以"思考一步看一步" | 改为 for 循环串行执行，每个工具结果出来后立即输出 | [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) |
| 模块级 import 检测 | `_check_optional("pyautogui")` 只检测不导入，模块级名字未绑定，运行时报 `NameError: name 'pyautogui' is not defined` | 检测后立即 `if available: import xxx` 在模块级绑定名字 | [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py#L37-L41) |
| 参数名冲突规避 | `execute_tool(self, name, **kwargs)` 第一参数 `name` 与工具参数 `name="微信"` 冲突，报 `got multiple values for argument 'name'` | 第一参数重命名为 `tool_name`，并加回归测试 `test_execute_tool_with_name_kwarg_no_conflict` | [tools/base.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/base.py) |
| PowerShell Get-StartApps | Windows `start "微信"` 不解析应用名，报"系统找不到文件 微信" | 区分路径/exe 和应用名，应用名走 `Get-StartApps` 反查 AppID 启动 | [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py#L316-L360) |
| 高精度 vision prompt | 默认 prompt 漏检桌面图标、托盘图标等小元素 | prompt 明确要求检测 32x32/48x48 小元素，坐标带 w/h 尺寸，给出示例 | [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py#L182-L200) |
| 截图用完即删 | 截图文件累积在 user_data_dir/screenshots 占磁盘 | vision 分析完成后 `os.remove` 删除临时文件，并加 `test_screenshot_file_removed_after_use` | [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py#L213-L218) |
| codex 自主执行 | 每个写操作都弹 `Confirm: ... [y/N]` 阻塞 AI 自主循环 | `_confirm` 直接返回 True，移除所有用户确认提示 | [tools/computer_use.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/computer_use.py#L230-L232) |
| 空 choices 保护 | LLM 返回 `{"choices": []}` 时 `data.get("choices", [{}])[0]` 报 `list index out of range` | 改为 `(data.get("choices") or [{}])[0]`，非流式显式 `if not choices: raise LLMError` | [core/llm.py](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py) |

**串行 ReAct 循环核心代码**：
```python
# 改进前（并行，结果顺序错乱）
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = [ex.submit(_exec_one, pc) for pc in parsed_calls]
    for fut in futures:
        call_id, tool_name, arguments, result, error = fut.result()
        # ... 收集所有结果后一次性输出 ...

# 改进后（串行，思考一步执行一步）
for pc in parsed_calls:
    call_id, tool_name, arguments, result, error = _exec_one(pc)
    # ... 立即处理并输出此工具结果 ...
    self.memory.add_message("tool", result, tool_call_id=call_id)
```

**模块级 import 检测的正确写法**：
```python
# 错误：_check_optional 只检测不导入，模块级名字未绑定
pyautogui_available, _ = _check_optional("pyautogui", ...)
def click(...):
    pyautogui.click(x, y)  # NameError: name 'pyautogui' is not defined

# 正确：检测后立即在模块级 import
pyautogui_available, _ = _check_optional("pyautogui", ...)
if pyautogui_available:
    import pyautogui  # noqa: E402  模块级绑定名字
```

**PowerShell Get-StartApps 反查 AppID**：
```python
# Windows start 命令不解析应用名（如"微信"），直接 start "微信" 会报错
# 必须用 PowerShell Get-StartApps 反查 AppID
ps_cmd = (
    f"Get-StartApps | "
    f"Where-Object {{$_.Name -like '*{ps_name}*'}} | "
    f"Select-Object -First 1 -ExpandProperty AppID"
)
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command", ps_cmd],
    capture_output=True, text=True, timeout=10,
)
app_id = result.stdout.strip()
if app_id:
    subprocess.Popen(f'start "" "shell:AppsFolder\\{app_id}"', shell=True)
```

### ✅ 验收标准
- [ ] 全部测试通过（118+ 个）
- [ ] chat_with_image 返回 LLM 响应的 content 字符串
- [ ] chat_with_image 构造的 user content 是 list 形式含 text + image_url
- [ ] chat_with_image 遇 LLMError 向上抛出（由调用方降级）
- [ ] _sanitize_messages 遇 list content 直接保留不规范化
- [ ] print_screenshot_thumbnail 输出含 `\x1b[38;2;` 和 ▀ 字符
- [ ] print_screenshot_thumbnail 遵守 max_width 限制
- [ ] Pillow 未安装时打印 placeholder 不抛异常
- [ ] ComputerUseTool() 无参构造仍工作（向后兼容）
- [ ] ComputerUseTool(llm_client=mock) 注入成功
- [ ] screenshot 全屏返回 "Region: fullscreen"
- [ ] screenshot 区域传 bbox=(x,y,x+w,y+h) 给 ImageGrab.grab
- [ ] screenshot 部分参数缺失降级全屏带 "fell back" 提示
- [ ] vision LLM 调用使用 chat_with_image(prompt, image_path=str(filepath))
- [ ] vision LLMError 降级为 "(vision unavailable: {error})"
- [ ] llm_client=None 返回 "(llm_client not configured)"
- [ ] NeonAgent 注册时注入 llm_client=self.llm

---

## 🎓 进阶扩展（可选，学完上面再做）
- [ ] 支持 Linux/macOS（写 .sh 启动脚本，对应打包工具）
- [ ] 技能(Skills)插件系统 - 动态加载第三方工具包
- [ ] 向量语义检索记忆 - 用embedding模型提升记忆召回准确率（需要ollama）
- [ ] Token 计数与用量统计
- [x] 更多工具：Git 操作、HTTP请求调试（已实现 GitTool / HttpTool / TimeTool / MathTool / ComputerUseTool）
- [ ] 多会话切换UI
- [ ] 主题切换（除了霓虹青绿，支持其他配色）
- [ ] 对话导出为Markdown
- [ ] 多渠道上下文隔离 - 给每个 IM 用户/群维护独立 memory
- [ ] Subagent 工具结果流式回传（当前是聚合后一次性返回）
- [ ] Subagent 并发度限制和优先级队列
- [ ] 思维树多轮迭代 - PlanToTTool 支持多轮自反思优化（当前是单次调用）
- [ ] 待办优先级和截止时间 - TodoList 加 priority / due_date 字段
- [ ] AI 主动汇报进度 - 长任务执行中定期用 todo list 输出当前进度
- [ ] ask_user 多渠道接入 - 微信/QQ 远程用户也能回答 AI 提问（当前只支持本地终端）

---

## 📚 推荐学习资源
| 资源 | 用途 |
|------|------|
| [Rich 官方文档](https://rich.readthedocs.io/) | UI 开发必看，有很多交互式示例 |
| [OpenAI API 文档 - Function Calling](https://platform.openai.com/docs/guides/function-calling) | 工具调用格式标准 |
| [PyInstaller 官方文档](https://pyinstaller.org/) | 打包问题排查 |
| [Inno Setup 文档](https://jrsoftware.org/ishelp.php) | 安装程序脚本参考 |
| Python 官方文档 - typing 模块 | 类型提示参考 |
| Python 官方文档 - concurrent.futures | ThreadPoolExecutor 并行执行参考 |
| Python 官方文档 - threading | 线程、Lock、Timer 参考 |
| [ReAct 论文](https://arxiv.org/abs/2210.03629) | 理解Agent推理原理（可选） |
| Python requests 文档 | HTTP客户端使用 |
| [pytest 文档](https://docs.pytest.org/) | 测试框架、fixture、monkeypatch |
| [OneBot 11 协议规范](https://github.com/botuniverse/onebot-11) | QQ OneBot 标准 |
| [QQ 开放平台文档](https://bot.q.qq.com/wiki/) | 官方 Bot API |
| [cryptography 库文档](https://cryptography.io/) | AES-GCM 解密 |
| [websocket-client 文档](https://websocket-client.readthedocs.io/) | WebSocket 客户端 |
| [Tree of Thoughts 论文](https://arxiv.org/abs/2305.10601) | 思维树规划原理（阶段十一参考） |
| [OpenAI Vision API 文档](https://platform.openai.com/docs/guides/vision) | 多模态图片理解参考（阶段十二） |
| [Pillow (PIL) 文档](https://pillow.readthedocs.io/) | ImageGrab 截屏与 Image.open 图片处理（阶段十二） |
| [ANSI 转义码参考](https://en.wikipedia.org/wiki/ANSI_escape_code) | truecolor 24-bit 颜色码格式（阶段十二缩略图渲染） |
| Python 官方文档 - uuid 模块 | TodoList 短 id 生成参考 |
| [Dependency Injection in Python](https://python-dependency-injector.ets.liniotech.com/) | 依赖注入模式深入（可选） |
| [pyautogui 文档](https://pyautogui.readthedocs.io/) | 鼠标键盘自动化、屏幕定位（阶段十二 computer use） |
| [PowerShell Get-StartApps](https://learn.microsoft.com/powershell/module/microsoft.powershell.management/) | Windows 开始菜单应用 AppID 反查（阶段十二 open_app） |
| [OpenAI Computer Use Guide](https://platform.openai.com/docs/guides/computer-use) | Codex computer use 设计理念与最佳实践（阶段十二对标参考） |
| [PyInstaller Hidden Imports](https://pyinstaller.org/en/stable/usage.html) | frozen 模式下可选依赖打包配置（阶段十二跨环境运行） |

---

## 💡 学习建议
1. **不要抄代码，要理解后自己写** - 先看参考文件理解思路，然后关掉自己写
2. **每完成一个小任务就运行测试** - 不要攒一大堆代码再调试
3. **遇到 bug 先自己排查** - print 调试、看错误信息，实在解决不了再对照源码
4. **重点阶段**：阶段二（Rich UI）、阶段五（ReAct Agent）、阶段八（Subagent + TDD）、阶段九（IM 接入）是核心，多花时间
5. **建议用 Git 提交** - 每个阶段完成后 commit 一次，方便回滚
6. **每完成一个阶段就可以跑一下程序** - 看到实际效果能保持动力
7. **先跑通最小流程**：先实现最简单的对话，再一步步加功能，不要一开始就想做全
8. **阶段八开始必须用 TDD** - Subagent 的递归和并行很难纯手测，没有测试会陷入调试地狱
9. **阶段九 IM 接入建议分开做** - 微信 / QQ OneBot / QQ 官方 Bot 三个子模块独立做，每做完一个先 commit
10. **协议逆向能力是加分项** - 微信 iLink 协议没有官方文档，能逆向出来是核心能力
11. **阶段十一是 Agent 升级关键** - ask_user / plan_tot / todo 三个能力让 AI 从"被动执行"变为"主动规划"，建议按顺序做（先 ask_user 解决意图，再 plan_tot 解决方案选择，最后 todo 解决进度追踪）
12. **共享实例设计要理解透** - TodoList 在 NeonAgent 创建一次，AI 工具和 /todo 命令注入同一实例，这是"AI 与用户协同"的核心模式，理解后可应用到其他共享状态场景
13. **阶段十二是多模态能力关键** - chat_with_image 让 AI 从"只读文本"升级为"能看见屏幕"，是对标 Codex computer use 的核心能力。建议先用一个支持 vision 的 model 测试（如 glm-4v / qwen-vl-plus / gpt-4o），理解多模态消息格式后再做缩略图渲染
14. **三路独立降级是工程关键** - 截屏/vision/缩略图三者异常互不影响，这种"局部失败不拖全局"的设计在多步骤工具中非常重要，理解后可应用到其他涉及多个外部依赖的工具
15. **工程改进是迭代必修课** - 阶段十二的 v1.1.0 工程改进都是真实使用中暴露的问题：串行 vs 并行、模块级 import 检测、参数名冲突、Windows start 命令解析等。建议按"工程改进"表格逐项对照实现，每改完一步跑 `python -m pytest tests/ -q --tb=short` 确认无回归。这些坑都很典型，遇到报错时先看错误信息（`NameError` / `got multiple values for argument` / `list index out of range`）就能定位到对应改进点
16. **GUI 自动化优先用"截屏+点击"而非 shell** - ComputerUseTool 默认走 `screenshot → click/type → screenshot 验证 → 循环` 的工作流，而不是用大量 shell 命令。原因：(1) shell 启动应用难定位窗口位置；(2) 点击坐标可跨应用复用；(3) vision LLM 返回结构化坐标清单可直接喂给下一步。理解这个工作流后，可应用到 RPA、自动化测试、远程协助等场景
17. **codex 自主执行的边界** - `_confirm` 直接返回 True 让 AI 自主循环不卡顿，但这也意味着 AI 可能误删文件、误点按钮。生产环境建议加白名单（仅允许 click/type，禁止 drag/key 系统组合键）+ 关键操作二次确认（如删除文件、发送消息）。本项目的安全键白名单 `_SAFE_KEYS` 是基础防护，可在此基础上扩展

---

## 📊 学习进度追踪
| 阶段 | 预计天数 | 状态 | 完成日期 |
|------|---------|------|---------|
| 阶段一：Python 工程化基础 | 3-5天 | ⬜ 待开始 | |
| 阶段二：Rich 终端 UI | 5-7天 | ⬜ 待开始 | |
| 阶段三：LLM API 对接 | 4-6天 | ⬜ 待开始 | |
| 阶段四：对话记忆与会话管理 | 3-4天 | ⬜ 待开始 | |
| 阶段五：工具系统与 ReAct Agent | 7-10天 | ⬜ 待开始 | |
| 阶段六：配置系统与交互 | 3-4天 | ⬜ 待开始 | |
| 阶段七：自我进化持久记忆 | 3-4天 | ⬜ 待开始 | |
| 阶段八：测试基础设施与子智能体 | 5-7天 | ⬜ 待开始 | |
| 阶段九：即时通讯平台接入 | 7-10天 | ⬜ 待开始 | |
| 阶段十：打包分发与图形安装 | 3-4天 | ⬜ 待开始 | |
| 阶段十一：AI 主动规划能力 | 4-6天 | ⬜ 待开始 | |
| 阶段十二：Computer Vision 与终端缩略图特效 | 5-7天 | ⬜ 待开始 | |
