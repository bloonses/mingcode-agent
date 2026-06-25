import subprocess
import platform
import re
from tools.base import BaseTool


class ShellTool(BaseTool):
    name = "shell"
    description = "执行系统命令并返回输出。在Windows上使用cmd，Linux/macOS使用bash。"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的命令"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒）",
                "default": 30
            }
        },
        "required": ["command"]
    }

    def _decode_output(self, data: bytes) -> str:
        if not data:
            return ""
        encodings = ['utf-8', 'gbk', 'cp936', 'gb2312', 'utf-16-le', 'latin-1']
        for enc in encodings:
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode('utf-8', errors='replace')

    def execute(self, command, timeout=30) -> str:
        dangerous_patterns = [
            r'rm\s+-rf\s+/',
            r'del\s+/f\s+/s',
            r'format\s+[a-zA-Z]:'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return "警告：检测到危险命令，已阻止执行。"
        
        try:
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                command = f'chcp 65001 >nul && {command}'
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout
            )
            
            output = ""
            stdout_str = self._decode_output(result.stdout)
            stderr_str = self._decode_output(result.stderr)
            
            if stdout_str:
                output += stdout_str
            if stderr_str:
                if output:
                    output += "\n"
                output += stderr_str
            
            return output.strip() if output.strip() else "命令执行成功，无输出。"
        
        except subprocess.TimeoutExpired:
            return f"命令执行超时(超过{timeout}秒)"
        except Exception as e:
            return f"执行错误: {str(e)}"
