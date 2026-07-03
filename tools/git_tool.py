"""GitTool - Git 版本控制工具。

action: status / diff / log / add / commit / branch / checkout / show
注意：所有写操作（add/commit/checkout）执行前会提示用户确认。
不含 push/force/reset --hard 等危险操作。
"""
import subprocess
import os
from typing import Optional, List

from .base import BaseTool


# 允许的子命令白名单，避免注入
_SAFE_SUBCOMMANDS = {
    "status", "diff", "log", "add", "commit", "branch",
    "checkout", "show", "stash", "restore",
}


class GitTool(BaseTool):
    name = "git"
    description = (
        "Git 版本控制。支持 action："
        "status（查看状态）/ diff（差异，可选 --staged）/ log（提交历史）/ "
        "add（暂存，需 file） / commit（提交，需 message）/ "
        "branch（列出/创建分支）/ checkout（切换分支，需 name） / "
        "show（查看某次提交，需 commit_hash）。"
        "不含 push/force/reset --hard。所有写操作执行前会询问用户。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "diff", "log", "add", "commit", "branch", "checkout", "show"],
                "description": "Git 子命令"
            },
            "file": {
                "type": "string",
                "description": "action=add 时可选，指定文件；省略则 add all"
            },
            "message": {
                "type": "string",
                "description": "action=commit 时必填，提交信息"
            },
            "branch_name": {
                "type": "string",
                "description": "action=branch（创建）/ checkout 时为分支名"
            },
            "commit_hash": {
                "type": "string",
                "description": "action=show 时为提交 hash"
            },
            "staged": {
                "type": "boolean",
                "description": "action=diff 时可选，true 表示已暂存的 diff"
            },
            "max_count": {
                "type": "integer",
                "description": "action=log 时可选，最大显示数量，默认 10"
            }
        },
        "required": ["action"]
    }

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()
        if action not in _SAFE_SUBCOMMANDS:
            return f"Error: unsupported action '{action}'. Supported: {sorted(_SAFE_SUBCOMMANDS)}"

        # 写操作需要确认
        if action in ("add", "commit", "checkout", "branch", "restore"):
            confirm = self._confirm(action, kwargs)
            if not confirm:
                return "Cancelled by user."

        try:
            args = self._build_args(action, kwargs)
            if args is None:
                return f"Error: missing required parameter for action '{action}'"
            return self._run_git(args)
        except Exception as e:
            return f"Error: {e}"

    def _confirm(self, action: str, kwargs) -> bool:
        """询问用户确认写操作。"""
        if action == "add":
            target = kwargs.get("file") or "all"
            msg = f"git add {target}"
        elif action == "commit":
            msg = f"git commit -m \"{(kwargs.get('message') or '')[:60]}\""
        elif action == "checkout":
            msg = f"git checkout {kwargs.get('branch_name', '')}"
        elif action == "branch":
            name = kwargs.get("branch_name")
            msg = f"git branch {name}" if name else "git branch (list)"
        else:
            msg = f"git {action}"
        try:
            ans = input(f"\nConfirm: {msg}? [y/N] ").strip().lower()
            return ans in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _build_args(self, action: str, kwargs) -> Optional[List[str]]:
        """构建 git 命令参数列表。返回 None 表示参数缺失。"""
        if action == "status":
            return ["status", "--short"]
        if action == "diff":
            args = ["diff"]
            if kwargs.get("staged"):
                args.append("--staged")
            return args
        if action == "log":
            n = int(kwargs.get("max_count") or 10)
            return ["log", f"-n{n}", "--oneline"]
        if action == "add":
            f = kwargs.get("file")
            if f:
                return ["add", f]
            return ["add", "-A"]
        if action == "commit":
            msg = kwargs.get("message")
            if not msg:
                return None
            return ["commit", "-m", msg]
        if action == "branch":
            name = kwargs.get("branch_name")
            if name:
                return ["branch", name]
            return ["branch"]
        if action == "checkout":
            name = kwargs.get("branch_name")
            if not name:
                return None
            return ["checkout", name]
        if action == "show":
            h = kwargs.get("commit_hash")
            if not h:
                return None
            return ["show", h]
        return None

    def _run_git(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            if result.stderr:
                output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
            if not output.strip():
                return "(no output)"
            if len(output) > 6000:
                output = output[:6000] + f"\n...[truncated, total {len(output)} chars]"
            return output
        except subprocess.TimeoutExpired:
            return "Error: git command timed out (30s)"
        except FileNotFoundError:
            return "Error: git not found in PATH"
