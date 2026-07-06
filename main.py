import sys
import os
import io
from pathlib import Path
from datetime import datetime

from config.config import load_config, save_config, get_app_dir
from core.agent import NeonAgent
from core.subagent import SubAgent
from core.wechat_bot import WeChatBot
from core.qq_onebot import QQOneBot
from core.qq_official import QQOfficialBot
from ui.console import console, print_logo, print_user_message, print_assistant_message, print_error, get_prompt
from ui.theme import NEON_TEAL, NEON_PURPLE
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table


def _print_wechat_qr(data: str) -> None:
    """WeChatBot.login 的回调：在终端显示二维码或状态"""
    if data == "SCANED":
        console.print(f"[{NEON_TEAL}]QR scanned! Confirm on your phone...[/{NEON_TEAL}]")
        return
    if not data:
        console.print("[red]Failed to get QR code from server.[/red]")
        return
    _render_qr_ascii(data, "Scan with WeChat to login MINGCODE Bot:")


def _print_qq_qr(url: str) -> None:
    """QQOfficialBot.qr_login 的回调：终端显示 QQ 扫码配置二维码 URL"""
    if not url:
        console.print("[red]Failed to get QQ bind task.[/red]")
        return
    _render_qr_ascii(url, "Scan with QQ App to bind your official bot:")
    console.print(f"[dim]URL: {url}[/dim]")


def _render_qr_ascii(data: str, title: str) -> None:
    """通用：在终端用 ASCII 显示二维码"""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(data)
        qr.make(fit=True)
        console.print()
        console.print(f"[{NEON_TEAL} bold]{title}[/{NEON_TEAL} bold]")
        console.print()
        buf = io.StringIO()
        qr.print_ascii(invert=True, out=buf)
        console.print(buf.getvalue(), style="white")
        console.print()
    except ImportError:
        console.print(f"[yellow]Install 'qrcode' to display QR. Data: {data}[/yellow]")


def _make_wechat_handler(agent):
    """构造微信消息处理回调：把消息转发给 NeonAgent，返回完整回复文本"""
    def handler(text: str, from_user: str) -> str:
        try:
            chunks = []
            for chunk in agent.chat(text):
                if chunk:
                    chunks.append(chunk)
            return "".join(chunks)
        except Exception as e:
            return f"[处理失败: {e}]"
    return handler


def _make_qq_handler(agent):
    """QQ 消息处理回调（OneBot & Official 通用）：
    OneBot: handler(text, user_id, group_id_or_None)
    Official: handler(text, user_id, target_id, scope)"""
    def onebot_handler(text: str, user_id: str, group_id) -> str:
        try:
            chunks = [c for c in agent.chat(text) if c]
            return "".join(chunks)
        except Exception as e:
            return f"[处理失败: {e}]"

    def official_handler(text: str, user_id: str, target_id: str, scope: str) -> str:
        try:
            chunks = [c for c in agent.chat(text) if c]
            return "".join(chunks)
        except Exception as e:
            return f"[处理失败: {e}]"
    return onebot_handler, official_handler


def handle_todo_command(arg: str, agent) -> bool:
    """处理 /todo 命令族，与 AI 共享同一 TodoList 实例。

    子命令：list / add / start / done / pending / delete / clear
    """
    todo = agent.todo_list
    parts = arg.split(maxsplit=1) if arg else []
    sub = parts[0].lower() if parts else "list"
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub in ("list", "ls", ""):
        items = todo.list()
        if not items:
            console.print(f"[{NEON_TEAL}]No todos.[/{NEON_TEAL}]")
            return True
        console.print()
        table = Table(title=f"Todos ({len(items)})", border_style=NEON_TEAL)
        table.add_column("ID", style=NEON_TEAL, width=8)
        table.add_column("Status", width=12)
        table.add_column("Content")
        status_icon = {"pending": "[ ] pending", "in_progress": "[~] in_progress", "completed": "[x] completed"}
        for it in items:
            table.add_row(it["id"], status_icon.get(it["status"], it["status"]), it["content"])
        console.print(table)
        console.print()
        return True

    if sub == "add":
        if not rest:
            console.print("[yellow]Usage: /todo add <content>[/yellow]")
            return True
        new_id = todo.add(rest)
        todo.save()
        console.print(f"[{NEON_TEAL}]Added todo {new_id}: {rest}[/{NEON_TEAL}]")
        return True

    if sub in ("start", "done", "pending"):
        if not rest:
            console.print(f"[yellow]Usage: /todo {sub} <id>[/yellow]")
            return True
        status_map = {"start": "in_progress", "done": "completed", "pending": "pending"}
        target_status = status_map[sub]
        if todo.update_status(rest, target_status):
            todo.save()
            console.print(f"[{NEON_TEAL}]Todo {rest} -> {target_status}[/{NEON_TEAL}]")
        else:
            console.print(f"[red]Failed: todo '{rest}' not found or status invalid[/red]")
        return True

    if sub == "delete":
        if not rest:
            console.print("[yellow]Usage: /todo delete <id>[/yellow]")
            return True
        if todo.delete(rest):
            todo.save()
            console.print(f"[{NEON_TEAL}]Deleted todo {rest}[/{NEON_TEAL}]")
        else:
            console.print(f"[red]Todo not found: {rest}[/red]")
        return True

    if sub == "clear":
        removed = todo.clear_completed()
        todo.save()
        console.print(f"[{NEON_TEAL}]Cleared {removed} completed todo(s)[/{NEON_TEAL}]")
        return True

    console.print(f"[yellow]Unknown subcommand: {sub}. Try: list / add / start / done / pending / delete / clear[/yellow]")
    return True


def handle_slash_command(cmd, arg, agent, config, wechat_bot: WeChatBot,
                         qq_onebot: QQOneBot, qq_official: QQOfficialBot) -> bool:
    if cmd in ['/help', '/?']:
        console.print()
        console.print(f"[{NEON_TEAL} bold]MINGCODE Help[/{NEON_TEAL} bold]")
        console.print()
        console.print("[bold]General:[/bold]")
        console.print("  /help, /?       Show this help message")
        console.print("  /clear          Clear conversation history")
        console.print("  /exit, /quit    Exit MINGCODE")
        console.print()
        console.print("[bold]Model & Config:[/bold]")
        console.print("  /model <name>   Switch to a different model")
        console.print("  /reasoning [off|low|medium|high]  Set reasoning effort (thinking models only)")
        console.print("  /cognitive [on|off]  Toggle cognitive controller (Plan-Reflect)")
        console.print("  /config         Show current configuration + token usage bar")
        console.print("  /tokens         Show token usage panel (by model, calls, avg per call)")
        console.print("  /compress       Manually compress context (LLM summarizes early conversation)")
        console.print("  /settings       Configure LLM provider (interactive)")
        console.print("  /tools          List available tools")
        console.print("  /debug          Show diagnostic info + test API call")
        console.print("  /doctor         Full health check (config/deps/network/LLM)")
        console.print()
        console.print("[bold]Session Management:[/bold]")
        console.print("  /new            Start a new session (clear history)")
        console.print("  /save [name]    Save current session")
        console.print("  /load [name]    Load a saved session")
        console.print("  /sessions       List all saved sessions")
        console.print("  /delsession <n> Delete a saved session")
        console.print()
        console.print("[bold]Long-term Memory (Self-Evolving):[/bold]")
        console.print("  /remember <text> Manually add a memory / user preference")
        console.print("  /memory [type]  Show all saved memories (type: preference/project/success/lesson)")
        console.print("  /forget <id>    Delete a specific memory by ID")
        console.print("  /clearmemory    Clear all long-term memories")
        console.print()
        console.print("[bold]Subagent:[/bold]")
        console.print("  /sub <task>     Run a one-off subagent for a task")
        console.print()
        console.print("[bold]Knowledge Base (RAG):[/bold]")
        console.print("  /kb                       List recent knowledge notes")
        console.print("  /kb search <query>        Search notes by keyword")
        console.print("  /kb read <id>             Read a note by ID")
        console.print("  /kb stats                 Show knowledge base stats")
        console.print("  /kb add <title> | <body>   Manually add a note")
        console.print("  /kb delete <id>           Delete a note by ID")
        console.print()
        console.print("[bold]Todo List:[/bold]")
        console.print("  /todo           List all todos (pending + in_progress + completed)")
        console.print("  /todo add <text>        Add a new todo")
        console.print("  /todo start <id>         Mark todo as in_progress")
        console.print("  /todo done <id>          Mark todo as completed")
        console.print("  /todo pending <id>       Reset todo to pending")
        console.print("  /todo delete <id>        Delete a todo")
        console.print("  /todo clear              Remove all completed todos")
        console.print()
        console.print("[bold]WeChat ClawBot:[/bold]")
        console.print("  /wechat login   Scan QR code to login WeChat bot")
        console.print("  /wechat start   Start listening & auto-reply via MINGCODE")
        console.print("  /wechat stop    Stop listening")
        console.print("  /wechat status  Show WeChat bot status")
        console.print("  /wechat logout  Logout & clear credentials")
        console.print()
        console.print("[bold]QQ Bots:[/bold]")
        console.print("  /qq onebot <connect|stop|status|logout|config>")
        console.print("                  OneBot 11 (NapCat/Lagrange) client")
        console.print("  /qq official <login|connect|stop|status|logout|config>")
        console.print("                  login: QR-scan to auto-configure (QQ App)")
        console.print("                  config: manually enter appid + secret")
        console.print()
        return True
    elif cmd == '/clear' or cmd == '/new' or cmd == '/newsession':
        agent.clear_memory()
        agent.memory.current_session_name = None
        console.print(f"[{NEON_TEAL}]New session started. History cleared.[/{NEON_TEAL}]")
        return True
    elif cmd == '/save':
        session_name = arg.strip() if arg else None
        saved_name = agent.memory.save(session_name)
        console.print(f"[{NEON_TEAL}]Session saved as: {saved_name}[/{NEON_TEAL}]")
        return True
    elif cmd == '/load':
        if not arg:
            sessions = agent.memory.list_sessions()
            if not sessions:
                console.print("[yellow]No saved sessions found.[/yellow]")
                return True
            console.print()
            table = Table(title="Saved Sessions", border_style=NEON_TEAL)
            table.add_column("#", style="dim", width=4)
            table.add_column("Name", style=NEON_TEAL)
            table.add_column("Saved At", style="dim")
            table.add_column("Msgs", justify="right", width=6)
            table.add_column("Preview")
            for i, s in enumerate(sessions[:15], 1):
                saved_at = s['saved_at'].replace('T', ' ')[:19]
                table.add_row(str(i), s['name'], saved_at, s['message_count'], s['preview'])
            console.print(table)
            console.print()
            choice = Prompt.ask("Enter session name or number to load", default="")
            if not choice:
                return True
            if choice.isdigit() and 1 <= int(choice) <= len(sessions):
                arg = sessions[int(choice)-1]['name']
            else:
                arg = choice
        name = arg.strip()
        if agent.memory.load(name):
            console.print(f"[{NEON_TEAL}]Session loaded: {name}[/{NEON_TEAL}]")
            console.print()
            for msg in agent.memory.messages:
                role = msg.get('role')
                content = msg.get('content')
                if role == 'user':
                    print_user_message(content or "")
                elif role == 'assistant':
                    if not content:
                        continue
                    print_assistant_message(content)
                # system / tool 消息不回显
        else:
            console.print(f"[red]Session not found: {name}[/red]")
        return True
    elif cmd == '/sessions' or cmd == '/ls':
        sessions = agent.memory.list_sessions()
        if not sessions:
            console.print("[yellow]No saved sessions.[/yellow]")
            return True
        console.print()
        table = Table(title=f"Saved Sessions ({len(sessions)})", border_style=NEON_TEAL)
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style=NEON_TEAL)
        table.add_column("Saved At", style="dim")
        table.add_column("Msgs", justify="right", width=6)
        table.add_column("Preview")
        for i, s in enumerate(sessions[:20], 1):
            saved_at = s['saved_at'].replace('T', ' ')[:19]
            table.add_row(str(i), s['name'], saved_at, s['message_count'], s['preview'])
        console.print(table)
        if len(sessions) > 20:
            console.print(f"[dim]... and {len(sessions)-20} more[/dim]")
        console.print()
        return True
    elif cmd == '/delsession' or cmd == '/delete':
        if not arg:
            console.print("[yellow]Usage: /delsession <session-name>[/yellow]")
            return True
        name = arg.strip()
        if agent.memory.delete_session(name):
            console.print(f"[{NEON_TEAL}]Session deleted: {name}[/{NEON_TEAL}]")
        else:
            console.print(f"[red]Session not found: {name}[/red]")
        return True
    elif cmd == '/remember':
        if not arg:
            console.print("[yellow]Usage: /remember <content to remember>[/yellow]")
            console.print("Example: /remember I prefer using Rich library for terminal UI")
            return True
        content = arg.strip()
        parts = content.split()
        mem_type = "preference"
        type_keywords = {
            "preference": "preference",
            "prefer": "preference",
            "lesson": "lesson",
            "mistake": "lesson",
            "error": "lesson",
            "project": "project",
            "success": "success",
            "works": "success",
        }
        lower_start = parts[0].lower().rstrip(':')
        if lower_start in type_keywords:
            mem_type = type_keywords[lower_start]
            content = " ".join(parts[1:])
        mem_id = agent.remember(content, memory_type=mem_type)
        type_names = {
            "preference": "user preference",
            "project": "project knowledge",
            "success": "successful experience",
            "lesson": "lesson learned"
        }
        console.print(f"[{NEON_TEAL}]Saved as {type_names[mem_type]} (ID: {mem_id})[/{NEON_TEAL}]")
        return True
    elif cmd == '/memory':
        mem_type = arg.strip().lower() if arg else None
        valid_types = {"preference", "project", "success", "lesson"}
        if mem_type and mem_type not in valid_types:
            console.print(f"[yellow]Invalid type. Valid types: {', '.join(valid_types)}[/yellow]")
            mem_type = None
        memories = agent.long_term_memory.get_all(mem_type)
        if not memories:
            console.print("[yellow]No memories saved yet.[/yellow]")
            console.print("[dim]I automatically learn from errors and successes. Use /remember to teach me.[/dim]")
            return True
        type_icons = {
            "preference": "[blue]PREF[/blue]",
            "project": "[yellow]PROJ[/yellow]",
            "success": "[green]OK  [/green]",
            "lesson": "[red]FAIL[/red]"
        }
        console.print()
        table = Table(title=f"Long-term Memories ({len(memories)})", border_style=NEON_TEAL)
        table.add_column("ID", style="dim", width=10)
        table.add_column("Type", width=8)
        table.add_column("Content")
        table.add_column("Used", justify="right", width=6)
        for mem in memories:
            icon = type_icons.get(mem["type"], "📝")
            content = mem["content"]
            if len(content) > 80:
                content = content[:77] + "..."
            table.add_row(mem["id"], icon, content, str(mem.get("use_count", 0)))
        console.print(table)
        console.print()
        return True
    elif cmd == '/forget':
        if not arg:
            console.print("[yellow]Usage: /forget <memory-id>[/yellow]")
            return True
        mem_id = arg.strip()
        if agent.long_term_memory.delete(mem_id):
            console.print(f"[{NEON_TEAL}]Memory {mem_id} deleted[/{NEON_TEAL}]")
        else:
            console.print(f"[red]Memory not found: {mem_id}[/red]")
        return True
    elif cmd == '/clearmemory':
        confirm = Confirm.ask("Are you sure you want to DELETE ALL long-term memories?", default=False)
        if confirm:
            removed = agent.long_term_memory.clear()
            console.print(f"[{NEON_TEAL}]Cleared {removed} memories[/{NEON_TEAL}]")
        else:
            console.print("[yellow]Cancelled[/yellow]")
        return True
    elif cmd == '/todo':
        return handle_todo_command(arg, agent)
    elif cmd == '/model':
        if not arg:
            console.print(f"[{NEON_TEAL}]Current model: {agent.llm.model}[/{NEON_TEAL}]")
            return True
        agent.llm.model = arg.strip()
        config['llm']['model'] = arg.strip()
        save_config(config)
        console.print(f"[{NEON_TEAL}]Switched to model: {agent.llm.model}[/{NEON_TEAL}]")
        return True
    elif cmd == '/reasoning':
        if not arg:
            current = agent.llm.reasoning_effort or "off"
            console.print(f"[{NEON_TEAL}]Reasoning effort: {current}[/{NEON_TEAL}]")
            console.print(f"[{NEON_TEAL}]Options: off / low / medium / high[/{NEON_TEAL}]")
            console.print(f"[{NEON_TEAL}]Note: 仅推理模型（如 o1/r1/qwen3-thinking）生效[/{NEON_TEAL}]")
            return True
        val = arg.strip().lower()
        if val == "off":
            val = None
        if val not in (None, "low", "medium", "high"):
            console.print(f"[{NEON_TEAL}]Invalid value. Use: off / low / medium / high[/{NEON_TEAL}]")
            return True
        agent.llm.reasoning_effort = val
        config['llm']['reasoning_effort'] = val
        save_config(config)
        display = val or "off"
        console.print(f"[{NEON_TEAL}]Reasoning effort set to: {display}[/{NEON_TEAL}]")
        return True
    elif cmd == '/cognitive':
        if not arg:
            enabled = config.get('cognitive', {}).get('enabled', True)
            status = "on" if enabled else "off"
            console.print(f"[{NEON_TEAL}]Cognitive controller: {status}[/{NEON_TEAL}]")
            console.print(f"[{NEON_TEAL}]Options: on / off[/{NEON_TEAL}]")
            return True
        val = arg.strip().lower()
        if val in ("on", "off"):
            config['cognitive']['enabled'] = (val == "on")
            save_config(config)
            agent._cognitive_enabled = (val == "on")
            agent._cognitive_controller = None
            console.print(f"[{NEON_TEAL}]Cognitive controller: {val}[/{NEON_TEAL}]")
        else:
            console.print(f"[{NEON_TEAL}]Invalid value. Use: on / off[/{NEON_TEAL}]")
        return True
    elif cmd == '/config':
        console.print()
        console.print(f"[{NEON_TEAL} bold]Configuration[/{NEON_TEAL} bold]")
        llm_config = config.get('llm', {})
        mem_config = config.get('memory', {})
        console.print(f"  Base URL:    {llm_config.get('base_url', 'N/A')}")
        console.print(f"  API Key:     {'*' * 8}{llm_config.get('api_key', '')[-4:] if len(str(llm_config.get('api_key', ''))) > 4 else '****'}")
        console.print(f"  Model:       {agent.llm.model}")
        console.print(f"  Temperature: {llm_config.get('temperature', 0.7)}")
        console.print(f"  Max Tokens:  {llm_config.get('max_tokens', 4096)}")
        console.print(f"  Reasoning:   {llm_config.get('reasoning_effort') or 'off'}")
        console.print(f"  Max History:       {mem_config.get('max_history', 50)} turns (legacy)")
        console.print(f"  Context Tokens:    {agent.memory.max_context_tokens} (compress at {agent.memory.get_compress_threshold()} = 2/3)")
        console.print(f"  Keep Recent Turns: {agent.memory.keep_recent_turns}")
        # 当前压缩状态
        status = agent.memory.compression_status()
        pct = (status["current_tokens"] * 100 // max(1, status["max_context_tokens"])) if status["max_context_tokens"] else 0
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        console.print(f"  Tokens:            [{bar}] {status['current_tokens']}/{status['max_context_tokens']} ({pct}%)")
        if status["has_summary"]:
            console.print(f"  Summary:           [green]yes[/green] (early conversation compressed)")
        if agent.memory.current_session_name:
            console.print(f"  Session:     {agent.memory.current_session_name}")
        console.print()
        return True
    elif cmd == '/compress':
        # 手动触发上下文压缩
        status_before = agent.memory.compression_status()
        if not status_before["has_summary"] and status_before["message_count"] <= agent.memory.keep_recent_turns * 2:
            console.print(f"[yellow]Not enough messages to compress (need > {agent.memory.keep_recent_turns * 2} messages, have {status_before['message_count']}).[/yellow]")
            return True
        console.print(f"[{NEON_TEAL}]Compressing context (LLM summarizing early conversation)...[/{NEON_TEAL}]")
        ok = agent.memory.compress_now()
        status_after = agent.memory.compression_status()
        if ok:
            saved = status_before["current_tokens"] - status_after["current_tokens"]
            console.print(f"[green]✓ Compressed[/green]  {status_before['current_tokens']} → {status_after['current_tokens']} tokens (saved {saved})")
            console.print(f"  Messages: {status_before['message_count']} → {status_after['message_count']}")
        else:
            console.print(f"[yellow]Nothing to compress[/yellow]  (need more than {agent.memory.keep_recent_turns * 2} non-summary messages)")
        return True
    elif cmd == '/settings':
        run_settings_wizard(agent, config)
        return True
    elif cmd == '/tools':
        tools = agent.registry.list_tools()
        console.print()
        console.print(f"[{NEON_TEAL} bold]Available Tools ({len(tools)})[/{NEON_TEAL} bold]")
        for tool in tools:
            console.print(f"  • {tool}")
        console.print()
        return True
    elif cmd == '/sub':
        if not arg.strip():
            console.print("[yellow]Usage: /sub <task description>[/yellow]")
            return True
        task = arg.strip()
        console.print(f"[{NEON_TEAL}]Starting subagent...[/{NEON_TEAL}]")
        sub = SubAgent(llm=agent.llm, long_term_memory=agent.long_term_memory, depth=2)
        result = sub.run(task)
        console.print()
        print_assistant_message(f"[子智能体] {result}")
        console.print()
        return True
    elif cmd == '/kb':
        kb = agent.knowledge_base
        if not getattr(kb, "enabled", False):
            console.print("[yellow]Knowledge base is disabled (config: knowledge_base.enabled)[/yellow]")
            return True
        sub = (arg or "").split(maxsplit=1)
        action = sub[0].lower() if sub and sub[0] else "list"
        rest = sub[1].strip() if len(sub) > 1 else ""

        if action in ("list", "ls", ""):
            notes = kb.list_notes(limit=20)
            if not notes:
                console.print(f"[yellow]No notes yet.[/yellow]  Search results will be auto-stored when web_search/web_fetch runs.")
                console.print(f"[dim]Vault: {kb.vault_path}[/dim]")
                return True
            console.print()
            console.print(f"[{NEON_TEAL} bold]═══ Knowledge Base ({len(notes)} recent) ═══[/{NEON_TEAL} bold]")
            table = Table(border_style=NEON_TEAL, show_lines=False)
            table.add_column("#", style="dim", width=4)
            table.add_column("ID", style=NEON_TEAL, width=22)
            table.add_column("Title", width=40)
            table.add_column("Tags", width=24)
            table.add_column("Created", style="dim", width=20)
            for i, n in enumerate(notes, 1):
                tags_str = ", ".join(n["tags"][:3]) + ("..." if len(n["tags"]) > 3 else "")
                created = (n.get("created") or "").replace("T", " ")[5:19]
                table.add_row(str(i), n["id"], n["title"][:40], tags_str, created)
            console.print(table)
            console.print(f"[dim]Vault: {kb.vault_path}[/dim]")
            console.print()
            return True

        if action == "search":
            if not rest:
                console.print("[yellow]Usage: /kb search <query>[/yellow]")
                return True
            results = kb.search(rest, top_k=5)
            if not results:
                console.print(f"[yellow]No notes found for '{rest}'[/yellow]")
                return True
            console.print()
            console.print(f"[{NEON_TEAL} bold]Search: '{rest}' ({len(results)} hits)[/{NEON_TEAL} bold]")
            for i, r in enumerate(results, 1):
                console.print(f"\n[{NEON_TEAL}]{i}. {r['title']}[/{NEON_TEAL}] [dim]score={r['score']}[/dim]")
                console.print(f"   [dim]ID: {r['id']}[/dim]")
                if r.get("tags"):
                    console.print(f"   [dim]Tags: {', '.join(r['tags'])}[/dim]")
                console.print(f"   {r['preview']}")
            console.print()
            return True

        if action == "read":
            if not rest:
                console.print("[yellow]Usage: /kb read <id>[/yellow]")
                return True
            note = kb.get_note(rest.strip())
            if not note:
                console.print(f"[red]Note not found: {rest}[/red]")
                return True
            console.print()
            console.print(f"[{NEON_TEAL} bold]{note['title']}[/{NEON_TEAL} bold]")
            console.print(f"[dim]ID: {note['id']}[/dim]")
            console.print(f"[dim]Created: {note['created']}[/dim]")
            if note.get("tags"):
                console.print(f"[dim]Tags: {', '.join(note['tags'])}[/dim]")
            if note.get("query"):
                console.print(f"[dim]Query: {note['query']}[/dim]")
            if note.get("urls"):
                console.print("[dim]URLs:[/dim]")
                for u in note["urls"]:
                    console.print(f"[dim]  - {u}[/dim]")
            console.print()
            console.print(note["content"])
            console.print()
            return True

        if action == "stats":
            s = kb.stats()
            console.print()
            console.print(f"[{NEON_TEAL} bold]═══ Knowledge Base Stats ═══[/{NEON_TEAL} bold]")
            console.print()
            console.print(f"  Enabled:      {s['enabled']}")
            console.print(f"  Auto-store:   {s['auto_store']}")
            console.print(f"  Total notes:  {s['total_notes']}")
            console.print(f"  Vault path:   {s['vault_path']}")
            if s["top_tags"]:
                console.print()
                console.print("[bold]Top Tags[/bold]")
                for tag, cnt in s["top_tags"]:
                    console.print(f"  {tag}: {cnt}")
            console.print()
            return True

        if action == "add":
            if not rest or "|" not in rest:
                console.print("[yellow]Usage: /kb add <title> | <body>[/yellow]")
                return True
            title, body = rest.split("|", 1)
            title = title.strip()
            body = body.strip()
            if not title or not body:
                console.print("[yellow]Both title and body are required.[/yellow]")
                return True
            result = kb.store_text(title, body, source="manual")
            if result.get("error"):
                console.print(f"[red]{result['error']}[/red]")
                return True
            console.print(f"[{NEON_TEAL}]Added note: {result['title']}[/{NEON_TEAL}]")
            console.print(f"  [dim]ID: {result['id']}[/dim]")
            console.print(f"  [dim]Tags: {', '.join(result['tags'])}[/dim]")
            return True

        if action in ("delete", "del", "rm"):
            if not rest:
                console.print("[yellow]Usage: /kb delete <id>[/yellow]")
                return True
            if kb.delete_note(rest.strip()):
                console.print(f"[{NEON_TEAL}]Deleted note: {rest}[/{NEON_TEAL}]")
            else:
                console.print(f"[red]Note not found: {rest}[/red]")
            return True

        console.print(f"[yellow]Unknown /kb action: {action}. Try: list / search / read / stats / add / delete[/yellow]")
        return True
    elif cmd == '/tokens':
        tracker = agent.token_tracker
        s = tracker.summary()
        console.print()
        console.print(f"[{NEON_PURPLE} bold]═══ Token Usage ═══[/{NEON_PURPLE} bold]")
        console.print()
        if s["call_count"] == 0:
            console.print(f"[dim]No LLM calls recorded yet.[/dim]")
            console.print()
            return True
        # 概览
        console.print("[bold]Session Total[/bold]")
        console.print(f"  Calls:         {s['call_count']}")
        console.print(f"  Prompt:        {s['total_prompt']:,} tokens")
        console.print(f"  Completion:    {s['total_completion']:,} tokens")
        console.print(f"  Total:         {s['total_tokens']:,} tokens")
        console.print(f"  Avg per call:  {s['avg_per_call']:,} tokens")
        console.print()
        # 按模型分组
        grouped = tracker.by_model()
        if len(grouped) > 1 or (len(grouped) == 1 and list(grouped.keys())[0] != (config.get('llm', {}).get('model', ''))):
            console.print("[bold]By Model[/bold]")
            table = Table(border_style=NEON_PURPLE, show_lines=False)
            table.add_column("Model", style=NEON_PURPLE)
            table.add_column("Calls", justify="right", width=8)
            table.add_column("Prompt", justify="right", width=12)
            table.add_column("Completion", justify="right", width=12)
            table.add_column("Total", justify="right", width=12)
            for m, st in grouped.items():
                table.add_row(m, str(st["calls"]), f"{st['prompt']:,}", f"{st['completion']:,}", f"{st['total']:,}")
            console.print(table)
            console.print()
        # 最近 5 次调用
        recent = tracker.calls[-5:]
        console.print(f"[bold]Recent Calls (last {len(recent)})[/bold]")
        rtable = Table(border_style=NEON_PURPLE, show_lines=False)
        rtable.add_column("#", style="dim", width=4)
        rtable.add_column("Model", style=NEON_PURPLE)
        rtable.add_column("Prompt", justify="right", width=10)
        rtable.add_column("Completion", justify="right", width=10)
        rtable.add_column("Total", justify="right", width=10)
        rtable.add_column("Time", style="dim", width=20)
        for i, c in enumerate(recent, 1):
            ts = c["timestamp"].replace("T", " ")[5:19]
            rtable.add_row(str(i), c["model"] or "unknown", f"{c['prompt_tokens']:,}",
                           f"{c['completion_tokens']:,}", f"{c['total_tokens']:,}", ts)
        console.print(rtable)
        console.print()
        return True
    elif cmd == '/debug':
        console.print()
        console.print(f"[{NEON_TEAL} bold]═══ MINGCODE Diagnostic ═══[/{NEON_TEAL} bold]")
        console.print()
        console.print("[bold]Environment[/bold]")
        console.print(f"  Version:       1.4.0")
        console.print(f"  Python:       {sys.version.split()[0]}")
        console.print(f"  Platform:     {sys.platform}")
        console.print(f"  Frozen:       {getattr(sys, 'frozen', False)}")
        console.print(f"  App Dir:      {get_app_dir()}")
        from config.config import get_user_data_dir
        console.print(f"  Data Dir:     {get_user_data_dir()}")
        console.print(f"  Config File:  {get_user_data_dir() / 'config.yaml'}")
        console.print()
        console.print("[bold]LLM Config[/bold]")
        llm = config.get('llm', {})
        api_key = str(llm.get('api_key', ''))
        console.print(f"  Base URL:     {llm.get('base_url', 'N/A')}")
        console.print(f"  Model:        {llm.get('model', 'N/A')}")
        console.print(f"  API Key:      {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****'}")
        console.print(f"  Temperature:  {llm.get('temperature', 0.7)}")
        console.print(f"  Max Tokens:   {llm.get('max_tokens', 4096)}")
        console.print(f"  Reasoning:    {agent.llm.reasoning_effort or 'off'}")
        console.print()
        console.print("[bold]Session[/bold]")
        console.print(f"  Messages:     {len(agent.memory.messages)}")
        console.print(f"  Session:      {agent.memory.current_session_name or '(unsaved)'}")
        console.print(f"  Tools:        {', '.join(agent.registry.list_tools())}")
        console.print()
        console.print(f"[{NEON_TEAL}]Sending test request (hi)...[/{NEON_TEAL}]")
        try:
            resp = agent.llm.chat([{"role": "user", "content": "hi"}], stream=False)
            content = resp.get('content', '') or ''
            console.print(f"  [green]OK[/green] - Response: {content[:60]}{'...' if len(content) > 60 else ''}")
        except Exception as e:
            console.print(f"  [red]FAILED[/red]: {e}")
            if hasattr(e, 'status_code') and e.status_code:
                console.print(f"  [red]Status[/red]: {e.status_code}")
            if hasattr(e, 'message') and e.message:
                console.print(f"  [red]Message[/red]: {e.message}")
        console.print()
        return True
    elif cmd == '/doctor':
        console.print()
        console.print(f"[{NEON_TEAL} bold]═══ MINGCODE Doctor ═══[/{NEON_TEAL} bold]")
        console.print()
        issues = []
        # 1. Config file
        from config.config import get_user_data_dir, get_config_path
        cfg_path = get_config_path()
        if cfg_path.exists():
            console.print(f"  [green]✓[/green] Config file exists: {cfg_path}")
        else:
            console.print(f"  [yellow]![/yellow] Config file missing (will auto-create on first run)")
        # 2. LLM config
        llm = config.get('llm', {})
        if not llm.get('base_url'):
            issues.append("LLM base_url is empty")
            console.print("  [red]✗[/red] LLM base_url is empty")
        else:
            console.print(f"  [green]✓[/green] LLM base_url set: {llm['base_url']}")
        if not llm.get('api_key') and 'localhost' not in llm.get('base_url', '') and '127.0.0.1' not in llm.get('base_url', ''):
            issues.append("API key is empty but base_url is not localhost")
            console.print("  [red]✗[/red] API key is empty (required for cloud providers)")
        else:
            console.print("  [green]✓[/green] API key configured")
        if not llm.get('model'):
            issues.append("Model name is empty")
            console.print("  [red]✗[/red] Model name is empty")
        else:
            console.print(f"  [green]✓[/green] Model set: {llm['model']}")
        # 3. Dependencies
        console.print()
        console.print("[bold]Dependencies[/bold]")
        for mod_name in ['requests', 'rich', 'yaml', 'duckduckgo_search', 'pygments', 'qrcode', 'websocket', 'cryptography']:
            try:
                __import__(mod_name)
                console.print(f"  [green]✓[/green] {mod_name}")
            except ImportError:
                issues.append(f"Missing dependency: {mod_name}")
                console.print(f"  [red]✗[/red] {mod_name} (missing)")
        # 4. Network connectivity to LLM
        console.print()
        console.print("[bold]Network Test[/bold]")
        try:
            import requests as _req
            base = llm.get('base_url', '')
            if base:
                r = _req.get(base.replace('/v1', '') + '/models', timeout=10, headers={"Authorization": f"Bearer {llm.get('api_key', '')}"})
                if r.status_code < 500:
                    console.print(f"  [green]✓[/green] Reached {base} (status {r.status_code})")
                else:
                    console.print(f"  [yellow]![/yellow] Server returned {r.status_code} from {base}")
            else:
                console.print("  [red]✗[/red] No base_url to test")
                issues.append("No base_url configured")
        except Exception as e:
            issues.append(f"Network error: {str(e)[:80]}")
            console.print(f"  [red]✗[/red] Cannot reach {llm.get('base_url', '?')}: {str(e)[:80]}")
        # 5. Data dir writable
        from config.config import get_user_data_dir
        data_dir = get_user_data_dir()
        try:
            test_file = data_dir / ".doctor_test"
            test_file.write_text("ok", encoding='utf-8')
            test_file.unlink()
            console.print(f"  [green]✓[/green] Data dir writable: {data_dir}")
        except Exception as e:
            issues.append(f"Data dir not writable: {e}")
            console.print(f"  [red]✗[/red] Data dir not writable: {data_dir}")
        # 6. Test actual LLM call
        console.print()
        console.print("[bold]LLM Test Call (3 retries)[/bold]")
        last_error = None
        success = False
        for attempt in range(1, 4):
            try:
                resp = agent.llm.chat([{"role": "user", "content": "say ok"}], stream=False)
                console.print(f"  [green]✓[/green] Attempt {attempt}/3: LLM responded: {(resp.get('content') or '')[:40]}")
                success = True
                break
            except Exception as e:
                last_error = e
                console.print(f"  [yellow]![/yellow] Attempt {attempt}/3 failed: {e}")
                if attempt < 3:
                    import time as _time
                    _time.sleep(2)
        if not success:
            issues.append(f"LLM call failed after 3 retries: {last_error}")
            console.print(f"  [red]✗[/red] All 3 attempts failed")
            e = last_error
            if hasattr(e, 'status_code') and e.status_code == 400:
                console.print(f"  [dim]400 usually means model name wrong, or messages format issue[/dim]")
                console.print(f"  [dim]Response: {getattr(e, 'message', '')[:200]}[/dim]")
            elif hasattr(e, 'status_code') and e.status_code == 401:
                console.print(f"  [dim]401 = invalid API key, run /settings to fix[/dim]")
            elif hasattr(e, 'status_code') and e.status_code == 404:
                console.print(f"  [dim]404 = model not found, check /model name[/dim]")
            elif hasattr(e, 'status_code') and e.status_code == 429:
                console.print(f"  [dim]429 = rate limit exceeded, wait and retry[/dim]")
        # Summary
        console.print()
        if not issues:
            console.print(f"[{NEON_TEAL} bold]All checks passed ✓[/{NEON_TEAL} bold]")
        else:
            console.print(f"[red bold]Found {len(issues)} issue(s):[/red bold]")
            for i, iss in enumerate(issues, 1):
                console.print(f"  [red]{i}.[/red] {iss}")
            console.print()
            console.print("[dim]Fix hints:[/dim]")
            console.print("[dim]  • /settings 重新配置 LLM[/dim]")
            console.print("[dim]  • /model <name> 切换模型名[/dim]")
            console.print("[dim]  • pip install -r requirements.txt 补依赖[/dim]")
        console.print()
        return True
    elif cmd == '/wechat':
        sub_parts = arg.split(maxsplit=1) if arg else []
        sub = sub_parts[0].lower() if sub_parts else ''
        if sub == 'login':
            if wechat_bot.is_logged_in:
                console.print("[yellow]Already logged in. Use /wechat logout first.[/yellow]")
                return True
            console.print(f"[{NEON_TEAL}]Starting WeChat login...[/{NEON_TEAL}]")
            if wechat_bot.login(print_qr=_print_wechat_qr):
                console.print(f"[{NEON_TEAL}]WeChat login successful![/{NEON_TEAL}]")
                console.print(f"  Bot ID:  {wechat_bot.bot_id}")
                console.print(f"  User ID: {wechat_bot.user_id}")
            else:
                console.print("[red]WeChat login failed or QR expired.[/red]")
            return True
        elif sub == 'start':
            if not wechat_bot.is_logged_in:
                console.print("[red]Not logged in. Use /wechat login first.[/red]")
                return True
            if wechat_bot.is_listening:
                console.print("[yellow]Already listening.[/yellow]")
                return True
            if wechat_bot.start_listening(_make_wechat_handler(agent)):
                console.print(f"[{NEON_TEAL}]WeChat bot started. MINGCODE will auto-reply to messages.[/{NEON_TEAL}]")
            else:
                console.print("[red]Failed to start WeChat bot.[/red]")
            return True
        elif sub == 'stop':
            wechat_bot.stop_listening()
            console.print(f"[{NEON_TEAL}]WeChat bot stopped.[/{NEON_TEAL}]")
            return True
        elif sub == 'status':
            console.print()
            console.print(f"[{NEON_TEAL} bold]WeChat Bot Status[/{NEON_TEAL} bold]")
            console.print(f"  Logged in:  {'Yes' if wechat_bot.is_logged_in else 'No'}")
            if wechat_bot.is_logged_in:
                console.print(f"  Bot ID:     {wechat_bot.bot_id}")
                console.print(f"  User ID:    {wechat_bot.user_id}")
                console.print(f"  Listening:  {'Yes' if wechat_bot.is_listening else 'No'}")
                console.print(f"  Contacts:   {len(wechat_bot.context_tokens)} user(s)")
            console.print()
            return True
        elif sub == 'logout':
            wechat_bot.logout()
            console.print(f"[{NEON_TEAL}]WeChat logged out.[/{NEON_TEAL}]")
            return True
        else:
            console.print("[yellow]Usage: /wechat <login|start|stop|status|logout>[/yellow]")
            return True
    elif cmd == '/qq':
        parts = arg.split(maxsplit=1) if arg else []
        backend = parts[0].lower() if parts else ''
        sub_arg = parts[1] if len(parts) > 1 else ''
        onebot_h, official_h = _make_qq_handler(agent)
        if backend == 'onebot':
            return _handle_qq_onebot(sub_arg, qq_onebot, onebot_h)
        elif backend == 'official':
            return _handle_qq_official(sub_arg, qq_official, official_h)
        else:
            console.print("[yellow]Usage: /qq <onebot|official> <connect|stop|status|logout|config>[/yellow]")
            return True
    elif cmd in ['/exit', '/quit']:
        if wechat_bot.is_listening:
            wechat_bot.stop_listening()
        if qq_onebot.is_listening:
            qq_onebot.stop_listening()
        if qq_official.is_listening:
            qq_official.stop_listening()
        if agent.memory.messages and not agent.memory.current_session_name:
            save = Confirm.ask("Save current session before exiting?", default=False)
            if save:
                name = agent.memory.save()
                console.print(f"[{NEON_TEAL}]Session saved as: {name}[/{NEON_TEAL}]")
        console.print(f"\n[{NEON_TEAL}]Goodbye![/{NEON_TEAL}]\n")
        return False
    else:
        console.print("[yellow]Unknown command. Type /help for available commands.[/yellow]")
        return True


def _handle_qq_onebot(sub: str, bot: QQOneBot, handler) -> bool:
    sub = sub.strip().lower()
    if sub == 'config':
        ws_url = Prompt.ask("  OneBot WebSocket URL (e.g. ws://127.0.0.1:3001)")
        token = Prompt.ask("  Access Token (Enter for none)", default="", password=True)
        http_base = Prompt.ask("  HTTP API base (Enter to derive from WS URL)", default="")
        bot.configure(ws_url, token, http_base)
        console.print(f"[{NEON_TEAL}]OneBot config saved.[/{NEON_TEAL}]")
        return True
    elif sub == 'connect' or sub == 'start':
        if not bot.is_configured:
            console.print("[red]Not configured. Run /qq onebot config first.[/red]")
            return True
        if bot.is_listening:
            console.print("[yellow]Already listening.[/yellow]")
            return True
        if bot.start_listening(handler):
            console.print(f"[{NEON_TEAL}]OneBot client started. WS: {bot.ws_url}[/{NEON_TEAL}]")
            console.print("[dim]Connecting in background...[/dim]")
        else:
            console.print("[red]Failed to start. Check ws_url.[/red]")
        return True
    elif sub == 'stop':
        bot.stop_listening()
        console.print(f"[{NEON_TEAL}]OneBot stopped.[/{NEON_TEAL}]")
        return True
    elif sub == 'status':
        console.print()
        console.print(f"[{NEON_TEAL} bold]QQ OneBot Status[/{NEON_TEAL} bold]")
        console.print(f"  Configured: {'Yes' if bot.is_configured else 'No'}")
        if bot.is_configured:
            console.print(f"  WS URL:     {bot.ws_url}")
            console.print(f"  Self ID:    {bot.self_id or '(pending)'}")
            console.print(f"  Connected:  {'Yes' if bot.is_connected else 'No'}")
            console.print(f"  Listening:  {'Yes' if bot.is_listening else 'No'}")
        console.print()
        return True
    elif sub == 'logout':
        bot.logout()
        console.print(f"[{NEON_TEAL}]OneBot config cleared.[/{NEON_TEAL}]")
        return True
    else:
        console.print("[yellow]Usage: /qq onebot <config|connect|stop|status|logout>[/yellow]")
        return True


def _handle_qq_official(sub: str, bot: QQOfficialBot, handler) -> bool:
    sub = sub.strip().lower()
    if sub == 'login':
        if bot.is_configured:
            console.print("[yellow]Already configured. Use /qq official logout first.[/yellow]")
            return True
        console.print(f"[{NEON_TEAL}]Starting QQ official bot QR setup...[/{NEON_TEAL}]")
        console.print("[dim]Requires an official bot created at https://q.qq.com[/dim]")
        if bot.qr_login(print_qr=_print_qq_qr):
            console.print(f"[{NEON_TEAL}]QQ official bot bound![/{NEON_TEAL}]")
            console.print(f"  App ID: {bot.appid}")
        else:
            console.print("[red]QR setup failed or expired.[/red]")
        return True
    elif sub == 'config':
        appid = Prompt.ask("  App ID")
        secret = Prompt.ask("  App Secret", password=True)
        token = Prompt.ask("  Bot Token (Enter for none)", default="", password=True)
        bot.configure(appid, secret, token)
        console.print(f"[{NEON_TEAL}]Official Bot config saved.[/{NEON_TEAL}]")
        return True
    elif sub == 'connect' or sub == 'start':
        if not bot.is_configured:
            console.print("[red]Not configured. Run /qq official config first.[/red]")
            return True
        if bot.is_listening:
            console.print("[yellow]Already listening.[/yellow]")
            return True
        if bot.start_listening(handler):
            console.print(f"[{NEON_TEAL}]Official Bot started (appid={bot.appid}).[/{NEON_TEAL}]")
            console.print("[dim]Connecting in background...[/dim]")
        else:
            console.print("[red]Failed to start. Check appid/secret.[/red]")
        return True
    elif sub == 'stop':
        bot.stop_listening()
        console.print(f"[{NEON_TEAL}]Official Bot stopped.[/{NEON_TEAL}]")
        return True
    elif sub == 'status':
        console.print()
        console.print(f"[{NEON_TEAL} bold]QQ Official Bot Status[/{NEON_TEAL} bold]")
        console.print(f"  Configured: {'Yes' if bot.is_configured else 'No'}")
        if bot.is_configured:
            console.print(f"  App ID:     {bot.appid}")
            console.print(f"  Intents:    {bot.intents}")
            console.print(f"  Connected:  {'Yes' if bot.is_connected else 'No'}")
            console.print(f"  Listening:  {'Yes' if bot.is_listening else 'No'}")
        console.print()
        return True
    elif sub == 'logout':
        bot.logout()
        console.print(f"[{NEON_TEAL}]Official Bot config cleared.[/{NEON_TEAL}]")
        return True
    else:
        console.print("[yellow]Usage: /qq official <login|config|connect|stop|status|logout>[/yellow]")
        return True


def run_settings_wizard(agent, config):
    PROVIDERS = {
        "1": {"name": "Ollama (Local)", "base_url": "http://localhost:11434/v1", "api_key": "ollama"},
        "2": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "api_key": ""},
        "3": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "api_key": ""},
        "4": {"name": "Qwen (通义千问)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": ""},
        "5": {"name": "Zhipu (智谱AI)", "base_url": "https://open.bigmodel.cn/api/paas/v4", "api_key": ""},
        "6": {"name": "Moonshot (Kimi)", "base_url": "https://api.moonshot.cn/v1", "api_key": ""},
        "7": {"name": "Custom (自定义)", "base_url": "", "api_key": ""},
    }
    
    console.print()
    console.print(f"[{NEON_TEAL} bold]╔══════════════════════════════════════╗[/{NEON_TEAL} bold]")
    console.print(f"[{NEON_TEAL} bold]║        LLM Provider Setup           ║[/{NEON_TEAL} bold]")
    console.print(f"[{NEON_TEAL} bold]╚══════════════════════════════════════╝[/{NEON_TEAL} bold]")
    console.print()
    console.print("[bold]Select a provider:[/bold]")
    console.print()
    for key, prov in PROVIDERS.items():
        console.print(f"  [{NEON_TEAL}]{key}[/{NEON_TEAL}]. {prov['name']}")
    console.print()
    
    choice = Prompt.ask("Enter your choice", default="1")
    
    if choice not in PROVIDERS:
        console.print("[red]Invalid choice![/red]")
        return
    
    provider = PROVIDERS[choice]
    
    if choice == "7":
        base_url = Prompt.ask("  Base URL (e.g., https://api.example.com/v1)")
        api_key = Prompt.ask("  API Key (press Enter for none)", default="", password=True)
    else:
        base_url = provider["base_url"]
        api_key = provider["api_key"]
        if not api_key and choice != "1":
            api_key = Prompt.ask(f"  Enter your API key for {provider['name']}", password=True)
        console.print(f"  Base URL: {base_url}")
    
    model = Prompt.ask("  Model name", default=config['llm'].get('model', 'qwen2.5:7b'))
    
    try:
        temp_str = Prompt.ask("  Temperature (0.0-1.0)", default=str(config['llm'].get('temperature', 0.7)))
        temperature = float(temp_str)
    except ValueError:
        temperature = 0.7
    
    try:
        tokens_str = Prompt.ask("  Max tokens", default=str(config['llm'].get('max_tokens', 4096)))
        max_tokens = int(tokens_str)
    except ValueError:
        max_tokens = 4096
    effort_str = Prompt.ask("  Reasoning effort (off/low/medium/high)",
                            default=str(config['llm'].get('reasoning_effort') or "off"))
    effort_str = effort_str.strip().lower()
    if effort_str in ("off", "", "none"):
        reasoning_effort = None
    elif effort_str in ("low", "medium", "high"):
        reasoning_effort = effort_str
    else:
        reasoning_effort = None  # 兜底

    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Provider:  {provider['name']}")
    console.print(f"  Base URL:  {base_url}")
    console.print(f"  API Key:   {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****' if api_key else 'None'}")
    console.print(f"  Model:     {model}")
    console.print(f"  Temp:      {temperature}")
    console.print(f"  MaxTokens: {max_tokens}")
    console.print(f"  Reasoning: {reasoning_effort or 'off'}")
    console.print()
    
    confirm = Confirm.ask("Save these settings?", default=True)
    if confirm:
        config['llm']['base_url'] = base_url
        config['llm']['api_key'] = api_key
        config['llm']['model'] = model
        config['llm']['temperature'] = temperature
        config['llm']['max_tokens'] = max_tokens
        config['llm']['reasoning_effort'] = reasoning_effort
        save_config(config)

        agent.llm.base_url = base_url
        agent.llm.api_key = api_key
        agent.llm.model = model
        agent.llm.temperature = temperature
        agent.llm.max_tokens = max_tokens
        agent.llm.reasoning_effort = reasoning_effort
        
        agent.clear_memory()
        
        console.print(f"[{NEON_TEAL}]Settings saved! Conversation history cleared.[/{NEON_TEAL}]")
    else:
        console.print("[yellow]Settings not saved.[/yellow]")
    console.print()


def main():
    config = load_config()

    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

    print_logo()

    agent = NeonAgent(config)
    wechat_bot = WeChatBot()
    qq_onebot = QQOneBot()
    qq_official = QQOfficialBot()
    onebot_h, official_h = _make_qq_handler(agent)

    wechat_cfg = config.get('wechat', {})
    if wechat_cfg.get('enabled') and wechat_cfg.get('auto_start') and wechat_bot.is_logged_in:
        if wechat_bot.start_listening(_make_wechat_handler(agent)):
            console.print(f"[{NEON_TEAL}]WeChat bot auto-started.[/{NEON_TEAL}]")

    qq_cfg = config.get('qq', {})
    ob_cfg = qq_cfg.get('onebot', {})
    if ob_cfg.get('enabled') and ob_cfg.get('auto_start') and qq_onebot.is_configured:
        if qq_onebot.start_listening(onebot_h):
            console.print(f"[{NEON_TEAL}]QQ OneBot auto-started.[/{NEON_TEAL}]")
    of_cfg = qq_cfg.get('official', {})
    if of_cfg.get('enabled') and of_cfg.get('auto_start') and qq_official.is_configured:
        if qq_official.start_listening(official_h):
            console.print(f"[{NEON_TEAL}]QQ Official Bot auto-started.[/{NEON_TEAL}]")

    console.print(f"[{NEON_TEAL}]Type /help for commands, or just ask anything.[/{NEON_TEAL}]\n")

    while True:
        try:
            user_input = console.input(get_prompt())
            if not user_input.strip():
                continue

            if user_input.startswith('/'):
                parts = user_input.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ''
                if not handle_slash_command(cmd, arg, agent, config, wechat_bot,
                                            qq_onebot, qq_official):
                    break
                continue

            print_user_message(user_input)
            full_response = ""
            try:
                for chunk in agent.chat(user_input):
                    if chunk:
                        full_response += chunk
                if full_response:
                    print_assistant_message(full_response)
                    # 显示 token 消耗
                    token_line = agent.token_tracker.format_compact()
                    if token_line:
                        console.print(f"[{NEON_PURPLE}]{token_line}[/{NEON_PURPLE}]", style="dim")
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted[/yellow]")
                continue

        except KeyboardInterrupt:
            console.print("\n[yellow]Press Ctrl+D or type /exit to quit[/yellow]")
            continue
        except EOFError:
            console.print(f"\n[{NEON_TEAL}]Goodbye![/{NEON_TEAL}]")
            if wechat_bot.is_listening:
                wechat_bot.stop_listening()
            if qq_onebot.is_listening:
                qq_onebot.stop_listening()
            if qq_official.is_listening:
                qq_official.stop_listening()
            break
        except Exception as e:
            print_error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
