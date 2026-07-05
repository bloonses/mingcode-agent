"""MINGCODE-LC CLI 入口。"""
import sys
from typing import Optional

from ui.console import console, print_assistant_message, print_user_message, print_error
from config.config import load_config


HELP_TEXT = """MINGCODE-LC v0.1.0 - LangChain 版本

可用命令:
  /help              显示此帮助
  /settings          交互式配置 LLM 供应商
  /config            查看当前配置
  /model <name>      切换模型
  /tools             列出可用工具
  /cognitive [on|off] 启用/关闭认知框架
  /new               开始新会话
  /save [name]       保存当前会话
  /load <name>       加载会话
  /sessions          列出已保存会话
  /wechat <sub>      微信 Bot 控制 (login|start|stop|status|logout)
  /qq <proto> <sub>  QQ Bot 控制 (onebot|official) (status|connect|stop)
  /clear             清空当前对话
  /exit              退出
"""


def handle_command(user_input: str, agent=None) -> Optional[str]:
    """处理 / 命令。非命令返回 None。"""
    if not user_input.startswith("/"):
        return None
    cmd = user_input.strip().lower()
    if cmd == "/help":
        return HELP_TEXT
    if cmd == "/exit":
        sys.exit(0)
    if cmd == "/tools" and agent:
        return "\n".join(f"- {t.name}: {t.description}" for t in agent.tools)
    if cmd == "/clear" and agent:
        agent.clear_memory()
        return "(已清空对话)"
    if cmd == "/new" and agent:
        agent.clear_memory()
        return "(新会话已开始)"
    # /save [name]
    if cmd.startswith("/save") and agent:
        parts = user_input.split(maxsplit=1)
        name = parts[1] if len(parts) > 1 else "default"
        try:
            if hasattr(agent, "save_session"):
                agent.save_session(name)
            return f"会话已保存: {name}"
        except Exception as e:
            return f"保存失败: {e}"

    # /load <name>
    if cmd.startswith("/load ") and agent:
        name = user_input.split(maxsplit=1)[1]
        try:
            if hasattr(agent, "load_session"):
                agent.load_session(name)
            return f"会话已加载: {name}"
        except Exception as e:
            return f"加载失败: {e}"

    # /sessions
    if cmd == "/sessions" and agent:
        try:
            sessions = agent.memory.list_sessions() if hasattr(agent, "memory") else []
            return "\n".join(sessions) if sessions else "(无已保存会话)"
        except Exception as e:
            return f"Error: {e}"

    if cmd == "/cognitive" and agent:
        return f"认知框架：{'启用' if agent.cognitive_enabled else '关闭'}"
    if cmd == "/cognitive on" and agent:
        agent.cognitive_enabled = True
        return "认知框架已启用"
    if cmd == "/cognitive off" and agent:
        agent.cognitive_enabled = False
        return "认知框架已关闭，回退到 ReAct"

    # /wechat <sub>
    if cmd.startswith("/wechat") and agent:
        return _handle_wechat(user_input, agent)

    # /qq <protocol> <sub>
    if cmd.startswith("/qq ") and agent:
        return _handle_qq(user_input, agent)

    return f"未知命令: {user_input}，输入 /help 查看可用命令"


def _handle_wechat(user_input, agent):
    """处理 /wechat 命令。"""
    parts = user_input.split()
    if len(parts) < 2:
        return "用法: /wechat <login|start|stop|status|logout>"
    sub = parts[1]
    try:
        wechat_bot = getattr(agent, "wechat_bot", None)
        if not wechat_bot:
            return "微信 Bot 未初始化"
        if sub == "status":
            return str(wechat_bot.get_status())
        if sub == "login":
            return wechat_bot.login()
        if sub == "start":
            return wechat_bot.start()
        if sub == "stop":
            return wechat_bot.stop()
        if sub == "logout":
            return wechat_bot.logout()
        return f"未知子命令: {sub}"
    except Exception as e:
        return f"Error: {e}"


def _handle_qq(user_input, agent):
    """处理 /qq 命令。"""
    parts = user_input.split()
    if len(parts) < 3:
        return "用法: /qq <onebot|official> <sub>"
    protocol = parts[1]
    sub = parts[2]
    try:
        if protocol == "onebot":
            bot = getattr(agent, "qq_onebot", None)
        elif protocol == "official":
            bot = getattr(agent, "qq_official", None)
        else:
            return f"未知协议: {protocol}"
        if bot is None:
            return f"{protocol} Bot 未初始化"
        if sub == "status":
            return str(bot.get_status())
        if sub == "connect":
            return bot.connect()
        if sub == "stop":
            return bot.stop()
        return f"未知子命令: {sub}"
    except Exception as e:
        return f"Error: {e}"


def main():
    """主循环。"""
    config = load_config()
    print_assistant_message("MINGCODE-LC v0.1.0 已启动。输入 /help 查看命令，或直接开始对话。")

    agent = None
    try:
        from core.agent import LangChainAgent
        agent = LangChainAgent(config=config)
    except Exception as e:
        print_error(f"Agent 初始化失败（将仅支持命令模式）: {e}")

    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            print_user_message(user_input)

            cmd_response = handle_command(user_input, agent)
            if cmd_response is not None:
                print_assistant_message(cmd_response)
                continue

            if agent is None:
                print_error("Agent 未初始化，无法对话。请检查配置后重启。")
                continue

            for chunk in agent.chat(user_input):
                print(chunk, end="", flush=True)
            print()
        except (KeyboardInterrupt, EOFError):
            print_assistant_message("再见！")
            break
        except SystemExit:
            raise
        except Exception as e:
            print_error(f"发生错误: {e}")


if __name__ == "__main__":
    main()
