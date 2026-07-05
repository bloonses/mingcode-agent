# MINGCODE-LC <img src="https://img.shields.io/badge/version-lc--v0.1.0-neon?style=flat-square&color=%2300ff88" alt="version"> <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square" alt="python"> <img src="https://img.shields.io/badge/stack-LangChain%20%2B%20LangGraph-9cf?style=flat-square" alt="stack">

> ⚡ MINGCODE 的 LangChain 版本，用 LangGraph StateGraph 重写认知框架

**MINGCODE-LC** 是 [MINGCODE](../neon_agent) 的 LangChain 等价实现，用 LangGraph StateGraph 替代手撸状态机，用 @tool 装饰器替代 BaseTool ABC，用 ConversationMemory + save/load 替代手动会话持久化。

## 状态：Phase 1-4 已完成（LangGraph 认知框架 + 21 工具 + IM 集成 + 打包脚本，122 测试全过）

## 特性

- **LangGraph StateGraph** - 5 节点认知框架（plan → execute → reflect → replan → done），声明式状态机替代手撸 while/if 循环
- **Tree of Thoughts (ToT)** - Planner 生成多候选方案，自评估打分选最优
- **L1/L2/L3 三级降级** - L1 ReAct 单步 → L2 多任务循环 → L3 ToT 复杂规划，按任务复杂度自动路由
- **Self-Ask** - 自提问分解子问题
- **21 个工具** - shell / files / code / search / ask_user / time / math / http / git / todo / subagent / plan_tot / computer_use，全部 @tool 装饰器 + Pydantic 入参校验
- **IM 集成** - 微信 Bot（wechat_bot）、QQ OneBot、QQ 官方、长期记忆（copy 自原版）
- **桌面控制** - computer_use 工具支持屏幕截图与鼠标键盘操作
- **会话持久化** - save / load / sessions 命令，会话存储到本地
- **赛博极简 UI** - Rich 终端渲染，霓虹青绿色调（#00ff88），流式输出 + 工具调用可视化
- **打包就绪** - PyInstaller spec + build.bat，一键生成单文件 exe

## 快速开始

```bash
# 安装 uv
pip install uv

# 同步依赖
uv sync

# 运行
python main.py

# 或安装到 PATH
uv pip install -e .
mingcode-lc
```

## 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/settings` | 交互式配置 LLM 供应商 |
| `/config` | 查看当前配置 |
| `/model <name>` | 切换模型 |
| `/tools` | 列出可用工具 |
| `/cognitive [on\|off]` | 启用/关闭认知框架 |
| `/new` | 开始新会话 |
| `/save [name]` | 保存当前会话 |
| `/load <name>` | 加载会话 |
| `/sessions` | 列出已保存会话 |
| `/wechat <sub>` | 微信 Bot 控制（login\|start\|stop\|status\|logout） |
| `/qq <proto> <sub>` | QQ Bot 控制（onebot\|official）（status\|connect\|stop） |
| `/clear` | 清空当前对话 |
| `/exit` | 退出 |

## 与 NeonAgent 对比

简要对比见下表，完整对比文档见 [COMPARISON.md](COMPARISON.md)。

| 维度 | NeonAgent | MINGCODE-LC |
|------|-----------|-------------|
| 状态机 | while/if 循环 | LangGraph StateGraph |
| 工具 | BaseTool ABC + 自定义 Registry | @tool + Pydantic |
| 记忆 | 手动 list + JSON 持久化 | ConversationMemory + save/load |
| LLM | requests 手撸 | ChatOpenAI |
| 流式 | 自定义 generator | LangChain BaseCallbackHandler |
| 依赖大小 | ~10 MB | ~200 MB（LangChain 生态） |

## 项目结构

详见 [docs/superpowers/specs/2026-07-05-langchain-version-design.md](docs/superpowers/specs/2026-07-05-langchain-version-design.md)

## 测试

```bash
python -m pytest tests/ -v
```
