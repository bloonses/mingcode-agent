"""配置加载 - 兼容 NeonAgent 结构。"""
import os
import sys
from pathlib import Path
from typing import Dict, Any
import yaml


def get_app_dir() -> Path:
    """获取应用目录。"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()


def get_user_data_dir() -> Path:
    """获取用户数据目录（持久化文件存放处）。"""
    if getattr(sys, 'frozen', False):
        if os.name == 'nt':
            base = os.environ.get('APPDATA', str(Path.home()))
            data_dir = Path(base) / "MINGCODE-LC"
        else:
            data_dir = Path.home() / ".mingcode-lc"
    else:
        data_dir = get_app_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DEFAULT_CONFIG: Dict[str, Any] = {
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 4096,
        "reasoning_effort": None,
    },
    "ui": {
        "theme": "neon",
        "animation": True,
        "show_thinking": True,
        "show_tools": True,
    },
    "tools": {
        "shell": {"enabled": True, "timeout": 30},
        "file": {"enabled": True},
        "python": {"enabled": True, "timeout": 10},
        "search": {"enabled": True, "max_results": 5},
    },
    "memory": {
        "max_history": 50,
    },
    "cognitive": {
        "enabled": True,
        "tot_candidates": 3,
        "max_replans": 3,
        "max_task_retries": 2,
        "self_ask": False,
    },
    "wechat": {"enabled": False, "auto_start": False},
    "qq": {
        "onebot": {"enabled": False, "ws_url": "ws://127.0.0.1:3001", "access_token": "", "auto_start": False},
        "official": {"enabled": False, "appid": "", "secret": "", "auto_start": False},
    },
}


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """递归合并 override 到 base。"""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """加载配置文件，与 DEFAULT_CONFIG 深合并。"""
    config = dict(DEFAULT_CONFIG)
    if not os.path.exists(config_path):
        return config
    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}
    return _deep_merge(config, user_config)


def save_config(config: Dict[str, Any], config_path: str = "config.yaml"):
    """保存配置到文件。"""
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
