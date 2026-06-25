import os
from tools.base import BaseTool


def _check_path_traversal(path: str) -> None:
    if '..' in path.replace('\\', '/').split('/'):
        raise ValueError("路径穿越检测：不允许使用 '..' 访问上级目录")


class FileReadTool(BaseTool):
    name = "file_read"
    description = "读取文件内容。可以指定起始行和结束行。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "start_line": {"type": "integer", "description": "起始行(从1开始)"},
            "end_line": {"type": "integer", "description": "结束行"}
        },
        "required": ["path"]
    }

    def execute(self, **kwargs) -> str:
        path = kwargs["path"]
        _check_path_traversal(path)
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gbk') as f:
                content = f.read()

        file_size = os.path.getsize(path)
        truncated = False
        if file_size > 100 * 1024:
            lines = content.splitlines(keepends=True)
            if len(lines) > 2000:
                content = ''.join(lines[:2000])
                truncated = True

        if start_line is not None or end_line is not None:
            lines = content.splitlines(keepends=True)
            start = (start_line or 1) - 1
            end = end_line if end_line is not None else len(lines)
            start = max(0, start)
            end = min(len(lines), end)
            content = ''.join(lines[start:end])

        if truncated:
            content += "\n... [文件过大，已截断显示前2000行] ..."

        return content


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "写入内容到文件，覆盖已有文件或创建新文件。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "要写入的内容"}
        },
        "required": ["path", "content"]
    }

    def execute(self, **kwargs) -> str:
        path = kwargs["path"]
        content = kwargs["content"]
        _check_path_traversal(path)

        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"文件已成功写入：{path}"


class FileEditTool(BaseTool):
    name = "file_edit"
    description = "精确编辑文件，将old_string替换为new_string。old_string必须唯一匹配。"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "old_string": {"type": "string", "description": "要被替换的原文"},
            "new_string": {"type": "string", "description": "替换后的新内容"}
        },
        "required": ["path", "old_string", "new_string"]
    }

    def execute(self, **kwargs) -> str:
        path = kwargs["path"]
        old_string = kwargs["old_string"]
        new_string = kwargs["new_string"]
        _check_path_traversal(path)

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='gbk') as f:
                content = f.read()

        count = content.count(old_string)
        if count == 0:
            return f"错误：未找到匹配的原文内容，请检查 old_string 是否正确"
        if count > 1:
            return f"错误：找到 {count} 处匹配，需要提供更精确的 old_string 以确保唯一匹配"

        new_content = content.replace(old_string, new_string, 1)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"文件已成功编辑：{path}"
