# 🚀 MINGCODE 保姆级复刻学习路线

**总周期：4-6周 | 每日投入：1-2小时 | 目标：1:1完整复刻**

---

## 📋 学前准备
- [ ] 安装 Python 3.8+（推荐3.10/3.11）
- [ ] 安装 VS Code + Python 插件
- [ ] 注册一个 LLM API 账号（DeepSeek 最便宜，或者本地装 Ollama）

---

## 🟢 阶段一：Python 项目工程化基础（3-5天）
**目标：掌握现代Python项目结构和开发规范**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 模块化与包管理 | ⭐⭐⭐⭐⭐ | `__init__.py`、相对导入、绝对导入 |
| 类型提示（Type Hints） | ⭐⭐⭐⭐⭐ | `typing` 模块、`List/Dict/Optional/Generator` |
| 虚拟环境 | ⭐⭐⭐⭐ | `venv`、依赖隔离 |
| 路径处理 | ⭐⭐⭐⭐ | `pathlib.Path` 替代 `os.path` |
| 面向对象进阶 | ⭐⭐⭐⭐ | 抽象基类（ABC）、@property 装饰器 |
| 异常处理 | ⭐⭐⭐ | 自定义异常、try-except 最佳实践 |

### 🎯 练习任务
1. 创建标准项目目录结构：
   ```
   my_agent/
   ├── config/        # 配置模块
   ├── core/          # 核心逻辑
   ├── tools/         # 工具模块
   ├── ui/            # UI模块
   └── main.py        # 入口
   ```
2. 每个目录创建 `__init__.py`，练习跨模块导入
3. 用 `pathlib.Path` 写一个读取当前目录文件列表的脚本
4. 写一个抽象基类 `BaseClass`，定义抽象方法，然后实现子类

### 📂 对应项目文件参考
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py#L1-L15) - 项目路径处理
- [tools/base.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/base.py#L1-L20) - 抽象基类示例

### ✅ 验收标准
- [ ] 能熟练在不同模块间互相导入
- [ ] 所有函数参数和返回值都有类型提示
- [ ] 会用 `pathlib` 处理路径，不硬编码分隔符

---

## 🟢 阶段二：终端 UI 开发 - Rich 库深度掌握（5-7天）
**目标：做出 MINGCODE 那样炫酷的赛博风格终端界面**

> 💡 Rich 是这个项目的 UI 灵魂，务必多花时间练习！

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| Console 对象 | ⭐⭐⭐⭐⭐ | 控制台输出基础 |
| Text 样式 | ⭐⭐⭐⭐⭐ | 颜色、加粗、斜体、样式组合 |
| Panel 面板 | ⭐⭐⭐⭐⭐ | 带边框的面板，box.SQUARE 直角边框 |
| Syntax 代码高亮 | ⭐⭐⭐⭐ | Markdown 代码块语法高亮 |
| Live 动态更新 | ⭐⭐⭐⭐ | 打字机流式输出效果 |
| Progress + Spinner | ⭐⭐⭐⭐ | Thinking... 加载动画 |
| Prompt 交互式输入 | ⭐⭐⭐⭐ | 密码输入、确认框、选项选择 |
| Group 组合渲染 | ⭐⭐⭐ | 多个组件组合在一起 |

### 🎯 练习任务（按顺序做）
1. **Task 1**：用 Rich 打印彩色 "Hello World"，尝试红/绿/蓝/霓虹青（#00ff88）
2. **Task 2**：打印 MINGCODE 的大 ASCII Logo（参考 [console.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/console.py#L32-L39)）
3. **Task 3**：创建两个 Panel：蓝色边框 "YOU"、青绿色边框 "MINGCODE"，用 box.SQUARE
4. **Task 4**：实现 Markdown 代码块渲染 - 把 ```python ... ``` 渲染成 Syntax 高亮
5. **Task 5**：用 Live 实现打字机效果 - 一个字一个字输出面板内容
6. **Task 6**：做一个 spinner 加载动画，显示 "Thinking..."，3秒后消失
7. **Task 7**：用 Prompt.ask() 做一个交互式问答（名字、年龄、密码输入）

### 📂 对应项目文件参考
- [ui/theme.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/theme.py) - 颜色和样式定义
- [ui/console.py](file:///c:/Users/bloon/Downloads/neon_agent/ui/console.py) - 所有 UI 渲染函数
  - `print_logo()` - 打印 Logo
  - `print_user_message()` - 用户消息面板
  - `print_assistant_message()` - AI回复（含打字机效果）
  - `print_thinking_spinner()` - 思考动画

### ✅ 验收标准
- [ ] 能复刻 MINGCODE 的启动界面（大 Logo + 欢迎文字）
- [ ] 用户/AI/工具/结果四种面板样式都能实现
- [ ] Markdown 代码块能正确高亮
- [ ] 打字机流式输出流畅不卡顿

---

## 🟡 阶段三：LLM API 对接（4-6天）
**目标：实现与大模型的对话，支持流式输出**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| REST API 基础 | ⭐⭐⭐⭐⭐ | POST 请求、headers、JSON |
| requests 库 | ⭐⭐⭐⭐⭐ | HTTP 请求、stream=True 流式响应 |
| OpenAI API 格式 | ⭐⭐⭐⭐⭐ | /chat/completions 接口、消息格式 |
| SSE 流式响应 | ⭐⭐⭐⭐⭐ | Server-Sent Events、逐行解析 |
| 生成器（Generator） | ⭐⭐⭐⭐⭐ | yield 逐块返回内容 |
| 多供应商兼容 | ⭐⭐⭐⭐ | base_url 切换支持不同厂商 |

### 🎯 练习任务
1. **Task 1**：用 requests 写一个最简单的非流式调用，向 DeepSeek/OpenAI 发请求，获取回复
2. **Task 2**：改成流式调用（stream=True），用 for 循环逐块打印返回内容
3. **Task 3**：封装成 `LLMClient` 类，包含 `__init__`（设置 base_url/api_key/model）和 `chat()` 方法
4. **Task 4**：chat() 方法改造成生成器，用 yield 返回每个 token，而不是一次性返回
5. **Task 5**：测试不同的 base_url：
   - Ollama: `http://localhost:11434/v1`
   - DeepSeek: `https://api.deepseek.com/v1`
   - 确保换个 URL 就能用，不用改其他代码

### 📂 对应项目文件参考
- [core/llm.py](file:///c:/Users/bloon/Downloads/neon_agent/core/llm.py) - LLM 客户端实现
  - 注意 `@property` 动态 headers 技巧
  - 流式响应解析逻辑

### 💡 关键提示
```python
# 流式响应解析的核心代码模式
response = requests.post(url, headers=headers, json=data, stream=True)
for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            # 解析 JSON，提取 content
```

### ✅ 验收标准
- [ ] 能成功调用至少一个 LLM API 得到回复
- [ ] 流式输出正常，一个字一个字蹦出来
- [ ] 切换 base_url 就能换供应商，代码不用改

---

## 🟡 阶段四：对话记忆管理（2-3天）
**目标：实现多轮对话，记住上下文**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 消息列表管理 | ⭐⭐⭐⭐⭐ | system/user/assistant 角色 |
| 滑动窗口 | ⭐⭐⭐⭐ | 保留最近 N 轮对话，避免 token 超限 |
| 系统提示词（System Prompt） | ⭐⭐⭐⭐⭐ | Agent 的"人设"和工作流程指令 |

### 🎯 练习任务
1. **Task 1**：实现 `ConversationMemory` 类
   - `add_message(role, content)` 添加消息
   - `get_messages()` 获取所有消息
   - `clear()` 清空历史
2. **Task 2**：添加滑动窗口功能 - 只保留最近 10-20 轮对话
3. **Task 3**：实现系统提示词构建，把 MINGCODE 的工作流写进去
   - （参考 [memory.py](file:///c:/Users/bloon/Downloads/neon_agent/core/memory.py#L9-L60)）

### 📂 对应项目文件参考
- [core/memory.py](file:///c:/Users/bloon/Downloads/neon_agent/core/memory.py) - 对话记忆和系统提示词

### ✅ 验收标准
- [ ] 可以多轮对话，LLM 能记住之前说的话
- [ ] 输入 `/clear` 能清空对话历史
- [ ] 系统提示词正确注入

---

## 🟠 阶段五：工具系统 - ReAct Agent 核心（7-10天）
**目标：这是最核心的部分！实现 Agent 思考→调用工具→观察→回答的完整循环**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| ReAct 模式 | ⭐⭐⭐⭐⭐ | Thought → Action → Observation 循环 |
| 工具注册机制 | ⭐⭐⭐⭐⭐ | 装饰器/注册表模式动态管理工具 |
| JSON 格式解析 | ⭐⭐⭐⭐⭐ | 从 LLM 回复中提取工具调用 |
| subprocess 模块 | ⭐⭐⭐⭐ | 执行 Shell 命令 |
| 文件读写 | ⭐⭐⭐⭐ | 安全的文件操作 |
| 正则表达式 | ⭐⭐⭐⭐ | 解析工具调用格式 |

### 🎯 练习任务（逐个实现工具）
1. **Task 1**：先搭基础框架
   - 写 `BaseTool` 抽象基类，定义 `name/description/parameters/execute()`
   - 写 `ToolRegistry` 注册表，能注册工具、列出工具、执行工具
2. **Task 2**：实现 Shell 工具 - 能执行终端命令并返回输出
3. **Task 3**：实现文件工具 - FileRead / FileWrite / FileEdit
4. **Task 4**：实现网络搜索工具 - duckduckgo-search 库
5. **Task 5**：实现网页获取工具 - requests 抓取网页，简单 HTML 清理
6. **Task 6**：实现 Python 代码执行工具（可选，注意安全）
7. **Task 7**：**核心！实现 Agent 循环**
   - 给 LLM 发送工具列表
   - 检测 LLM 是否要调用工具
   - 如果调用工具：打印工具调用面板 → 执行工具 → 把结果加回对话 → 继续让 LLM 回答
   - 如果不调用工具：直接返回给用户

### 📂 对应项目文件参考
- [tools/base.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/base.py) - 工具基类和注册表
- [tools/shell.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/shell.py) - Shell 命令执行
- [tools/files.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/files.py) - 文件操作
- [tools/search.py](file:///c:/Users/bloon/Downloads/neon_agent/tools/search.py) - 网页搜索
- [core/agent.py](file:///c:/Users/bloon/Downloads/neon_agent/core/agent.py) - 核心 Agent 循环！重点看

### 💡 关键提示
工具定义的格式要在系统提示词里告诉 LLM，例如：
```
你可以使用以下工具：
- shell: 执行命令
- read_file: 读取文件
...
当你需要调用工具时，用以下格式：
[TOOL_CALL]
{
  "name": "tool_name",
  "arguments": {"key": "value"}
}
[/TOOL_CALL]
```

### ✅ 验收标准
- [ ] Agent 能根据用户问题自动决定是否调用工具
- [ ] 每个工具都能正常工作
- [ ] 工具调用结果能正确返回给 LLM 继续推理
- [ ] 工具调用时有紫色 TOOL 面板，结果有灰色 RESULT 面板

---

## 🟠 阶段六：配置系统与交互体验（3-4天）
**目标：实现 YAML 配置、交互式设置向导**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| YAML 配置 | ⭐⭐⭐⭐⭐ | pyyaml 库读写 yaml 文件 |
| 交互式向导 | ⭐⭐⭐⭐ | Rich Prompt/Confirm 做配置界面 |
| 默认值处理 | ⭐⭐⭐⭐ | 配置不存在时用默认值 |
| 斜杠命令 | ⭐⭐⭐⭐ | /help /settings /model /config 等命令解析 |

### 🎯 练习任务
1. **Task 1**：定义 DEFAULT_CONFIG 字典，包含 llm 配置（base_url/api_key/model/temperature/max_tokens）
2. **Task 2**：实现 `load_config()` 和 `save_config()` 读写 config.yaml
3. **Task 3**：实现斜杠命令解析 - 检测用户输入是否以 `/` 开头，分发到对应处理函数
4. **Task 4**：实现 `/settings` 交互式配置向导
   - 列出供应商选项（Ollama/OpenAI/DeepSeek/Qwen等）
   - 让用户选，然后输入 API Key、模型名、参数
   - 预览配置，确认后保存
5. **Task 5**：实现 `/help` `/clear` `/model` `/config` `/tools` 命令

### 📂 对应项目文件参考
- [config/config.py](file:///c:/Users/bloon/Downloads/neon_agent/config/config.py) - 配置加载保存
- [main.py](file:///c:/Users/bloon/Downloads/neon_agent/main.py#L17-L158) - 斜杠命令和设置向导

### ✅ 验收标准
- [ ] 配置能持久化到 config.yaml
- [ ] /settings 向导工作正常
- [ ] 修改配置后不用重启程序（至少重启后生效）
- [ ] 所有 / 命令都能正常使用

---

## 🔴 阶段七：打包分发与一键安装（2-3天）
**目标：让其他人双击 setup.bat 就能装好，输入 mingcode 就能启动**

### 📚 核心知识点
| 知识点 | 重要程度 | 说明 |
|--------|---------|------|
| 批处理脚本（.bat） | ⭐⭐⭐⭐ | Windows 批处理基础语法 |
| 环境变量 PATH | ⭐⭐⭐⭐ | 用户 PATH vs 系统 PATH |
| PowerShell 调用 | ⭐⭐⭐⭐ | 在 bat 里调用 PowerShell 修改环境变量 |
| 依赖清单 | ⭐⭐⭐⭐ | requirements.txt 格式 |

### 🎯 练习任务
1. **Task 1**：写 `requirements.txt`，列出所有依赖包
2. **Task 2**：写 `mingcode.bat` 启动脚本
   - 切到脚本所在目录
   - 执行 python main.py 并透传所有参数
3. **Task 3**：写 `setup.bat` 一键安装脚本
   - 检查 Python 是否安装，版本够不够
   - pip install -r requirements.txt（加国内镜像 fallback）
   - 创建 mingcode.bat
   - 用 PowerShell 把项目目录加到用户 PATH
   - 生成默认 config.yaml
   - 创建 uninstall.bat
4. **Task 4**：在一台没装过的机器上测试整个流程

### 📂 对应项目文件参考
- [setup.bat](file:///c:/Users/bloon/Downloads/neon_agent/setup.bat) - 一键安装脚本
- [mingcode.bat](file:///c:/Users/bloon/Downloads/neon_agent/mingcode.bat) - 启动脚本
- [requirements.txt](file:///c:/Users/bloon/Downloads/neon_agent/requirements.txt) - 依赖清单

### ✅ 验收标准
- [ ] 把项目拷贝到另一台 Windows 机器，双击 setup.bat 能成功安装
- [ ] 打开新终端，输入 mingcode 能在任意目录启动
- [ ] 运行 uninstall.bat 能从 PATH 移除

---

## 🎓 进阶扩展（可选，学完上面再做）
- [ ] 支持 Linux/macOS（写 .sh 脚本）
- [ ] 对话历史保存到文件
- [ ] 本地 RAG 知识库功能
- [ ] 支持 Function Calling 原生 API（不只用正则解析）
- [ ] 更多工具：Git 操作、数据库查询等

---

## 📚 推荐学习资源
| 资源 | 用途 |
|------|------|
| [Rich 官方文档](https://rich.readthedocs.io/) | UI 开发必看，有很多示例 |
| [OpenAI API 文档](https://platform.openai.com/docs/api-reference) | API 格式标准 |
| Python 官方文档 - typing 模块 | 类型提示参考 |
| ReAct 论文（可选） | 理解 Agent 原理：https://arxiv.org/abs/2210.03629 |

---

## 💡 学习建议
1. **不要抄代码，要理解后自己写** - 先看参考文件理解思路，然后关掉自己写
2. **每完成一个小任务就运行测试** - 不要攒一大堆代码再调试
3. **遇到 bug 先自己排查** - print 调试、看错误信息，实在解决不了再对照源码
4. **阶段二（Rich）和阶段五（Agent）是重点** - 这两个部分花时间最多
5. **建议用 Git 提交** - 每个阶段完成后 commit 一次，方便回滚

---

## 📊 学习进度追踪
| 阶段 | 预计天数 | 状态 | 完成日期 |
|------|---------|------|---------|
| 阶段一：Python 工程化基础 | 3-5天 | ⬜ 待开始 | |
| 阶段二：Rich 终端 UI | 5-7天 | ⬜ 待开始 | |
| 阶段三：LLM API 对接 | 4-6天 | ⬜ 待开始 | |
| 阶段四：对话记忆管理 | 2-3天 | ⬜ 待开始 | |
| 阶段五：工具系统与 Agent | 7-10天 | ⬜ 待开始 | |
| 阶段六：配置系统 | 3-4天 | ⬜ 待开始 | |
| 阶段七：打包分发 | 2-3天 | ⬜ 待开始 | |
