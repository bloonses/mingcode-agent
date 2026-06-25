import sys
import os
from pathlib import Path
from datetime import datetime

from config.config import load_config, save_config, get_app_dir
from core.agent import NeonAgent
from ui.console import console, print_logo, print_user_message, print_assistant_message, print_error, get_prompt
from ui.theme import NEON_TEAL
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table


def handle_slash_command(cmd, arg, agent, config) -> bool:
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
    elif cmd in ['/exit', '/quit']:
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
                if not handle_slash_command(cmd, arg, agent, config):
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
            break
        except Exception as e:
            print_error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
