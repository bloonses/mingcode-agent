"""配置加载测试。"""
import os
import tempfile
from config.config import load_config, DEFAULT_CONFIG


def test_default_config_has_llm_section():
    assert "llm" in DEFAULT_CONFIG
    assert "base_url" in DEFAULT_CONFIG["llm"]
    assert "api_key" in DEFAULT_CONFIG["llm"]
    assert "model" in DEFAULT_CONFIG["llm"]


def test_default_config_has_cognitive_section():
    assert "cognitive" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["cognitive"]["enabled"] is True
    assert DEFAULT_CONFIG["cognitive"]["self_ask"] is False
    assert DEFAULT_CONFIG["cognitive"]["tot_candidates"] == 3


def test_load_config_returns_default_when_no_file():
    config = load_config("nonexistent.yaml")
    assert config["llm"]["base_url"] == "http://localhost:11434/v1"
    assert config["cognitive"]["enabled"] is True


def test_load_config_reads_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
llm:
  base_url: "https://api.deepseek.com/v1"
  api_key: "sk-test"
  model: "deepseek-chat"
""")
    config = load_config(str(config_file))
    assert config["llm"]["model"] == "deepseek-chat"
    assert config["cognitive"]["enabled"] is True
