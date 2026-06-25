import os
import sys
from pathlib import Path
import yaml


def get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()


def get_user_data_dir() -> Path:
    if getattr(sys, 'frozen', False):
        if os.name == 'nt':
            base = os.environ.get('APPDATA', str(Path.home()))
            data_dir = Path(base) / "MINGCODE"
        else:
            data_dir = Path.home() / ".mingcode"
    else:
        data_dir = get_app_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "skills").mkdir(parents=True, exist_ok=True)
    return data_dir


DEFAULT_CONFIG = {
    "llm": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5:7b",
        "temperature": 0.7,
        "max_tokens": 4096
    },
    "ui": {
        "theme": "neon",
        "animation": True,
        "show_thinking": True,
        "show_tools": True
    },
    "tools": {
        "shell": {
            "enabled": True,
            "timeout": 30
        },
        "file": {
            "enabled": True
        },
        "python": {
            "enabled": True,
            "timeout": 10
        },
        "search": {
            "enabled": True,
            "max_results": 5
        }
    },
    "memory": {
        "max_history": 20
    }
}

CONFIG_TEMPLATE = """# MINGCODE 配置文件
# LLM 大语言模型配置
llm:
  # API 服务地址
  base_url: "http://localhost:11434/v1"
  # API 密钥
  api_key: "ollama"
  # 使用的模型名称
  model: "qwen2.5:7b"
  # 采样温度，值越高回复越随机
  temperature: 0.7
  # 最大生成 token 数
  max_tokens: 4096

# 用户界面配置
ui:
  # 界面主题
  theme: "neon"
  # 是否启用动画效果
  animation: true
  # 是否显示思考过程
  show_thinking: true
  # 是否显示工具调用
  show_tools: true

# 工具配置
tools:
  # Shell 命令执行工具
  shell:
    enabled: true
    timeout: 30
  # 文件操作工具
  file:
    enabled: true
  # Python 代码执行工具
  python:
    enabled: true
    timeout: 10
  # 网络搜索工具
  search:
    enabled: true
    max_results: 5

# 记忆配置
memory:
  # 最大保留对话轮数（每轮=用户提问+AI回复）
  # 超过后自动丢弃最早的对话，避免token超限
  max_history: 20
"""


def get_config_path() -> Path:
    return get_user_data_dir() / "config.yaml"


def load_config():
    config_path = get_config_path()
    
    if not config_path.exists() and getattr(sys, 'frozen', False):
        portable_config = get_app_dir() / "config.yaml"
        if portable_config.exists():
            import shutil
            shutil.copy2(portable_config, config_path)
    
    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(config_path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    config = DEFAULT_CONFIG.copy()
    if loaded:
        for section, values in loaded.items():
            if section in config and isinstance(values, dict):
                config[section].update(values)
            else:
                config[section] = values
    return config


def save_config(config):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
