# tests/test_im_import.py
"""IM 模块导入测试。"""
import pytest


def test_long_term_memory_imports():
    """long_term_memory 应能 import。"""
    from core.long_term_memory import LongTermMemory
    assert LongTermMemory is not None


def test_long_term_memory_instantiates():
    """LongTermMemory 应能实例化。"""
    from core.long_term_memory import LongTermMemory
    mem = LongTermMemory()
    assert mem is not None
    assert hasattr(mem, "memories")


def test_wechat_bot_imports():
    """wechat_bot 模块应能 import（依赖 requests）。"""
    try:
        from core.wechat_bot import WeChatBot
        assert WeChatBot is not None
    except ImportError as e:
        pytest.skip(f"依赖未安装: {e}")


def test_qq_onebot_imports():
    """qq_onebot 模块应能 import。"""
    try:
        from core.qq_onebot import QQOneBot
        assert QQOneBot is not None
    except ImportError as e:
        pytest.skip(f"依赖未安装: {e}")


def test_qq_official_imports():
    """qq_official 模块应能 import。"""
    try:
        from core.qq_official import QQOfficialBot
        assert QQOfficialBot is not None
    except ImportError as e:
        pytest.skip(f"依赖未安装: {e}")


def test_config_get_user_data_dir():
    """config 应提供 get_user_data_dir 函数。"""
    from config.config import get_user_data_dir
    p = get_user_data_dir()
    assert p.exists()
    assert str(p).endswith("mingcode-langchain") or "MINGCODE" in str(p) or "mingcode" in str(p).lower()
