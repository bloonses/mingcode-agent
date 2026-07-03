# MINGCODE <img src="https://img.shields.io/badge/version-1.0.9-neon?style=flat-square&color=%2300ff88" alt="version"> <img src="https://img.shields.io/badge/python-3.8+-blue?style=flat-square" alt="python">

> ⚡ 赛博朋克风格的终端 AI 编码助手，支持多模型供应商、工具调用、会话持久化、多平台接入

**MINGCODE** 是一个轻量级、高颜值的命令行 AI 编码代理，采用 ReAct 架构，支持工具调用、多模型供应商、会话保存/加载，并可通过微信 / QQ 接入远程使用，开箱即用。

---

## ✨ 特性

- 🎨 **赛博极简 UI** - 霓虹青绿色调，锐利边框，打字机流式输出，代码语法高亮
- 🔌 **多供应商支持** - 兼容任何 OpenAI 格式 API：Ollama / OpenAI / DeepSeek / Qwen / Zhipu / Moonshot / 自定义
- 🛠️ **内置工具系统** - Shell命令执行、文件读写编辑、Python代码运行、网络搜索
- 🧩 **子智能体（Subagent）** - 主 Agent 可自主派生子智能体并行处理独立子任务，支持有限递归
- 💬 **微信接入（ClawBot）** - 扫码登录 iLink Bot，远程通过微信与 MINGCODE 对话
- 🤖 **QQ 接入** - 支持 OneBot 11（NapCat/Lagrange）和 QQ 官方开放平台 Bot（含扫码绑定）
- 💾 **会话持久化** - 自动截断超长对话，支持保存/加载/删除历史会话
- 🧠 **自我进化记忆** - 四类长期记忆（偏好/项目/成功/教训），自动从错误中学习
- ⚙️ **交互式配置** - 内置 `/settings` 向导，无需手动编辑配置文件
- 📦 **一键安装** - 提供图形化安装程序，安装后输入 `mingcode` 即可使用
- 🧪 **TDD 工作流** - 内置专业编码代理提示词，遵循 RED-GREEN-REFACTOR 开发流程

---

## 🚀 快速开始

### 方式一：使用安装程序（推荐用户）

1. 前往 [Releases](https://github.com/yourname/mingcode/releases) 下载最新的 `MINGCODE-Setup-1.0.9.exe`
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

---

## 📖 使用指南

### 首次配置

启动后输入 `/settings` 进入交互式配置向导：

1. 选择 LLM 供应商（Ollama/OpenAI/DeepSeek/Qwen等）
2. 输入 API Key
3. 输入模型名称（例如 `deepseek-chat`、`gpt-4o`、`qwen2.5:7b`）
4. 确认配置保存

### 常用命令

| 命令 | 功能 |
|------|------|
| `/help` | 显示帮助信息 |
| `/settings` | 交互式配置 LLM 供应商 |
| `/config` | 查看当前配置 |
| `/model <name>` | 切换模型 |
| `/tools` | 列出可用工具 |
| `/debug` | 快速诊断（环境+配置+测试请求） |
| `/doctor` | 全面健康检查（依赖/网络/LLM） |
| `/sub <task>` | 启动一次性子智能体处理任务 |
| `/new` | 开始新会话（清空历史） |
| `/save [name]` | 保存当前会话 |
| `/load <name>` | 加载已保存会话 |
| `/sessions` | 列出所有已保存会话 |
| `/delsession <name>` | 删除已保存会话 |
| `/remember <text>` | 手动添加长期记忆 |
| `/memory [type]` | 查看长期记忆（preference/project/success/lesson） |
| `/forget <id>` | 删除指定长期记忆 |
| `/clearmemory` | 清空所有长期记忆 |
| `/wechat login` | 微信 ClawBot 扫码登录 |
| `/wechat start` | 开始监听微信消息 |
| `/wechat stop` | 停止监听微信消息 |
| `/wechat status` | 查看微信 Bot 状态 |
| `/wechat logout` | 微信 Bot 登出 |
| `/qq onebot <sub>` | OneBot 11 子命令（config/connect/stop/status/logout） |
| `/qq official <sub>` | QQ 官方 Bot 子命令（login/config/connect/stop/status/logout） |
| `/clear` | 清空当前对话 |
| `/exit` | 退出（提示保存未保存会话） |

### 核心工作流程

MINGCODE 内置了专业的编码代理工作流：

1. **头脑风暴** - 理解需求，提问澄清，生成产品文档
2. **计划阶段** - 拆解任务，制定精细实施计划
3. **执行阶段** - 使用工具逐步实现，严格遵循 TDD
4. **完成阶段** - 验证测试，清理工作树

### 子智能体（Subagent）

主 Agent 在 ReAct 循环中可自主调用 `task` 工具派生子智能体：

- **独立上下文** - 子智能体有独立的对话记忆，主 Agent 只收到最终答案
- **并行执行** - 同一轮的多个工具调用并行执行（最多 4 个并发）
- **有限递归** - 递归深度 2 层（主 → sub → sub，共 3 层调用链）
- **经验共享** - 子智能体学到的成功/教训写入共享的长期记忆池

也可通过 `/sub <task>` 手动启动一次性子智能体。

### 微信 / QQ 接入

**微信 ClawBot**：`/wechat login` 扫码登录后，`/wechat start` 开始监听。微信消息会转发给 MINGCODE 处理并自动回复。

**QQ OneBot**：需先运行 NapCat / Lagrange 等协议端并登录个人 QQ。`/qq onebot config` 填写 WebSocket 地址，`/qq onebot connect` 连接。

**QQ 官方 Bot**：需在 [q.qq.com](https://q.qq.com) 注册机器人。`/qq official login` 扫码自动绑定（AES-GCM 解密获取 secret），或 `/qq official config` 手动填写 appid + secret，然后 `/qq official connect`。

---

## 🏗️ 项目结构

```
mingcode/
├── config/          # 配置管理
│   └── config.py
├── core/            # 核心引擎
│   ├── agent.py     # ReAct Agent 主循环（并行工具执行）
│   ├── subagent.py  # 子智能体（独立上下文 ReAct）
│   ├── llm.py       # LLM API 客户端
│   ├── memory.py    # 对话记忆与会话管理
│   ├── long_term_memory.py  # 自我进化长期记忆
│   ├── wechat_bot.py     # 微信 ClawBot (iLink) 客户端
│   ├── qq_onebot.py      # QQ OneBot 11 客户端
│   └── qq_official.py    # QQ 官方开放平台 Bot 客户端
├── tools/           # 内置工具
│   ├── base.py      # 工具基类与注册表
│   ├── shell.py     # Shell 命令执行
│   ├── files.py     # 文件读写编辑
│   ├── code.py      # Python 代码执行
│   ├── search.py    # 网络搜索
│   └── subagent.py  # 子智能体工具（task）
├── ui/              # 终端 UI
│   ├── console.py   # Rich 渲染组件
│   └── theme.py     # 赛博主题配色
├── tests/           # 单元测试
├── docs/superpowers/  # 设计文档与实现计划
├── build.bat        # 一键构建脚本
├── main.py          # 程序入口
├── mingcode.bat     # 开发环境启动脚本
├── mingcode.spec    # PyInstaller 打包配置
├── setup.iss        # Inno Setup 安装程序脚本
├── requirements.txt # 运行依赖
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
  max_history: 50

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

## 🎓 学习路线

如果你想从零开始学习复刻这个项目，请参考保姆级学习指南：[MINGCODE_LEARNING_ROADMAP.md](MINGCODE_LEARNING_ROADMAP.md)

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
