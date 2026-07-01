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
from ui.theme import NEON_TEAL
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
        console.print("  /config         Show current configuration")
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
                if msg['role'] == 'user':
                    print_user_message(msg['content'])
                elif msg['role'] == 'assistant':
                    print_assistant_message(msg['content'])
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
    elif cmd == '/model':
        if not arg:
            console.print(f"[{NEON_TEAL}]Current model: {agent.llm.model}[/{NEON_TEAL}]")
            return True
        agent.llm.model = arg.strip()
        config['llm']['model'] = arg.strip()
        save_config(config)
        console.print(f"[{NEON_TEAL}]Switched to model: {agent.llm.model}[/{NEON_TEAL}]")
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
        console.print(f"  Max History: {mem_config.get('max_history', 20)} turns")
        if agent.memory.current_session_name:
            console.print(f"  Session:     {agent.memory.current_session_name}")
        console.print()
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
    elif cmd == '/debug':
        console.print()
        console.print(f"[{NEON_TEAL} bold]═══ MINGCODE Diagnostic ═══[/{NEON_TEAL} bold]")
        console.print()
        console.print("[bold]Environment[/bold]")
        console.print(f"  Version:       1.0.4")
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
        console.print("[bold]LLM Test Call[/bold]")
        try:
            resp = agent.llm.chat([{"role": "user", "content": "say ok"}], stream=False)
            console.print(f"  [green]✓[/green] LLM responded: {(resp.get('content') or '')[:40]}")
        except Exception as e:
            issues.append(f"LLM call failed: {e}")
            console.print(f"  [red]✗[/red] LLM call failed: {e}")
            if hasattr(e, 'status_code') and e.status_code == 400:
                console.print(f"  [dim]400 usually means model name wrong, or messages format issue[/dim]")
                console.print(f"  [dim]Response: {getattr(e, 'message', '')[:200]}[/dim]")
            elif hasattr(e, 'status_code') and e.status_code == 401:
                console.print(f"  [dim]401 = invalid API key, run /settings to fix[/dim]")
            elif hasattr(e, 'status_code') and e.status_code == 404:
                console.print(f"  [dim]404 = model not found, check /model name[/dim]")
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
    
    console.print()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  Provider:  {provider['name']}")
    console.print(f"  Base URL:  {base_url}")
    console.print(f"  API Key:   {'*' * 8}{api_key[-4:] if len(api_key) > 4 else '****' if api_key else 'None'}")
    console.print(f"  Model:     {model}")
    console.print(f"  Temp:      {temperature}")
    console.print(f"  MaxTokens: {max_tokens}")
    console.print()
    
    confirm = Confirm.ask("Save these settings?", default=True)
    if confirm:
        config['llm']['base_url'] = base_url
        config['llm']['api_key'] = api_key
        config['llm']['model'] = model
        config['llm']['temperature'] = temperature
        config['llm']['max_tokens'] = max_tokens
        save_config(config)
        
        agent.llm.base_url = base_url
        agent.llm.api_key = api_key
        agent.llm.model = model
        agent.llm.temperature = temperature
        agent.llm.max_tokens = max_tokens
        
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
