import sys
import subprocess
import os
from .base import BaseTool


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "执行Python代码并返回stdout输出。代码在独立进程中运行。"
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的Python代码"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间(秒)，默认10秒",
                "default": 10
            }
        },
        "required": ["code"]
    }

    def execute(self, code, timeout=10) -> str:
        try:
            result = subprocess.run(
                [sys.executable, '-c', code],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=os.getcwd(),
                timeout=timeout
            )
            output = result.stdout
            if result.returncode != 0:
                output = output + result.stderr
            if len(output) > 4000:
                output = output[:4000] + "[输出过长，已截断...]"
            return output
        except subprocess.TimeoutExpired:
            return f"错误：执行超时（{timeout}秒）"
