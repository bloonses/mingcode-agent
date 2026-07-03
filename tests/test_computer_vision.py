"""Computer Vision 与终端缩略图特效的单元测试。"""
import base64
from unittest.mock import patch, MagicMock

import pytest


# ============== LLMClient.chat_with_image ==============

def _make_llm(tmp_path):
    """构造一个 LLMClient，指向不存在的端点（测试用 mock 拦截请求）。"""
    from core.llm import LLMClient
    return LLMClient({
        "base_url": "http://localhost:11434/v1",
        "api_key": "test-key",
        "model": "test-model",
    })


class TestLLMClientChatWithImage:
    def test_chat_with_image_returns_content(self, tmp_path):
        """chat_with_image 应返回 LLM 响应的 content 字符串。"""
        # 准备一张假 PNG（1x1 红点）
        img_path = tmp_path / "fake.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        llm = _make_llm(tmp_path)
        fake_response = {"role": "assistant", "content": "A red pixel", "tool_calls": None}
        with patch.object(llm, "chat", return_value=fake_response) as mock_chat:
            result = llm.chat_with_image("describe", str(img_path))
        assert result == "A red pixel"
        # 验证 chat 被调用
        mock_chat.assert_called_once()

    def test_chat_with_image_builds_image_url_payload(self, tmp_path):
        """user content 应为 list 形式，包含 text 和 image_url 两个 item。"""
        img_path = tmp_path / "fake.png"
        # 写入可识别的 base64 内容
        img_path.write_bytes(b"FAKE_PNG_DATA_FOR_TEST")

        llm = _make_llm(tmp_path)
        fake_response = {"role": "assistant", "content": "ok", "tool_calls": None}
        captured_messages = []

        def capture_chat(messages, **kwargs):
            captured_messages.extend(messages)
            return fake_response

        with patch.object(llm, "chat", side_effect=capture_chat):
            llm.chat_with_image("describe this", str(img_path))

        assert len(captured_messages) == 1
        user_msg = captured_messages[0]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)
        assert len(user_msg["content"]) == 2
        # 第一项是 text
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "describe this"
        # 第二项是 image_url
        assert user_msg["content"][1]["type"] == "image_url"
        url = user_msg["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        # 验证 base64 内容可解回原数据
        b64_part = url.split(",", 1)[1]
        assert base64.b64decode(b64_part) == b"FAKE_PNG_DATA_FOR_TEST"

    def test_chat_with_image_propagates_llm_error(self, tmp_path):
        """LLMError 应向上抛出，由调用方（ComputerUseTool）捕获降级。"""
        from core.llm import LLMError

        img_path = tmp_path / "fake.png"
        img_path.write_bytes(b"\x89PNG")
        llm = _make_llm(tmp_path)

        with patch.object(llm, "chat", side_effect=LLMError(400, "model does not support images")):
            with pytest.raises(LLMError):
                llm.chat_with_image("describe", str(img_path))

    def test_sanitize_messages_preserves_list_content(self):
        """sanitize 不应破坏 list 形式的 content（image_url 结构）。"""
        llm = _make_llm(None)  # tmp_path 这里不用
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "hi"},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ]}
        ]
        result = llm._sanitize_messages(messages)
        assert isinstance(result[0]["content"], list)
        assert len(result[0]["content"]) == 2
        assert result[0]["content"][1]["type"] == "image_url"


# ============== print_screenshot_thumbnail ==============

def _make_test_png(path, width=4, height=4, color=(255, 0, 0)):
    """创建测试用 PNG（纯色填充）。"""
    from PIL import Image
    img = Image.new("RGB", (width, height), color)
    img.save(str(path))


class TestPrintScreenshotThumbnail:
    def test_thumbnail_renders_half_block_chars(self, tmp_path, capsys):
        """输出应包含 ANSI truecolor 转义码和 ▀ 半块字符。"""
        from ui.console import print_screenshot_thumbnail
        img_path = tmp_path / "test.png"
        _make_test_png(img_path, width=4, height=4, color=(255, 0, 0))
        print_screenshot_thumbnail(str(img_path), max_width=4)
        captured = capsys.readouterr()
        # 应包含 ANSI 前景色码
        assert "\x1b[38;2;255;0;0m" in captured.out
        # 应包含半块字符
        assert "▀" in captured.out
        # 结尾应重置
        assert "\x1b[0m" in captured.out

    def test_thumbnail_respects_max_width(self, tmp_path, capsys):
        """max_width 应限制输出宽度（每行 ▀ 字符数 <= max_width）。"""
        from ui.console import print_screenshot_thumbnail
        img_path = tmp_path / "wide.png"
        _make_test_png(img_path, width=100, height=20, color=(0, 255, 0))
        print_screenshot_thumbnail(str(img_path), max_width=10)
        captured = capsys.readouterr()
        # 找到包含 ▀ 的行，验证每行 ▀ 数量 <= 10
        lines_with_block = [line for line in captured.out.split("\n") if "▀" in line]
        for line in lines_with_block:
            # 去掉 ANSI 转义码后数 ▀
            import re
            stripped = re.sub(r"\x1b\[[0-9;]*m", "", line)
            assert stripped.count("▀") <= 10

    def test_thumbnail_pillow_missing_prints_placeholder(self, monkeypatch, capsys):
        """Pillow 未安装时应打印占位提示，不抛异常。"""
        import ui.console as console_mod
        monkeypatch.setattr(console_mod, "pil_available", False, raising=False)
        from ui.console import print_screenshot_thumbnail
        print_screenshot_thumbnail("any.png")
        captured = capsys.readouterr()
        assert "Pillow not installed" in captured.out or "unavailable" in captured.out

    def test_thumbnail_image_error_prints_error_message(self, tmp_path, capsys):
        """图片读取失败时应打印错误信息，不抛异常。"""
        from ui.console import print_screenshot_thumbnail
        bad_path = tmp_path / "nonexistent.png"
        print_screenshot_thumbnail(str(bad_path), max_width=4)
        captured = capsys.readouterr()
        assert "thumbnail error" in captured.out.lower() or "error" in captured.out.lower()


# ============== ComputerUseTool 构造注入 ==============

class TestComputerUseToolConstruction:
    def test_no_arg_construction_still_works(self):
        """无参构造（向后兼容，用于现有测试和未配置 vision 的场景）。"""
        from tools.computer_use import ComputerUseTool
        tool = ComputerUseTool()
        assert tool.llm_client is None
        assert tool.name == "computer"

    def test_llm_client_injection(self):
        """有参构造应注入 llm_client。"""
        from tools.computer_use import ComputerUseTool
        mock_llm = MagicMock()
        tool = ComputerUseTool(llm_client=mock_llm)
        assert tool.llm_client is mock_llm


# ============== screenshot 区域截屏 ==============

def _patch_image_grab(monkeypatch, fake_img):
    """patch PIL.ImageGrab.grab 返回 fake_img。"""
    import tools.computer_use as cu_mod
    monkeypatch.setattr(cu_mod, "pil_available", True, raising=False)
    monkeypatch.setattr(cu_mod, "ImageGrab", MagicMock(), raising=False)
    cu_mod.ImageGrab.grab = MagicMock(return_value=fake_img)


class TestScreenshotRegion:
    def test_screenshot_fullscreen_saves_and_returns_path(self, tmp_path, monkeypatch):
        """全屏截屏应保存文件并返回路径。"""
        from tools.computer_use import ComputerUseTool

        # patch get_user_data_dir 指向 tmp_path
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        # patch ImageGrab 返回假图片
        fake_img = MagicMock()
        fake_img.size = (1920, 1080)
        _patch_image_grab(monkeypatch, fake_img)
        # patch thumbnail renderer 避免真渲染
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()
        result = tool.execute(action="screenshot")

        assert "Screenshot captured" in result
        assert "1920x1080" in result
        # 验证 ImageGrab.grab 被无 bbox 调用
        import tools.computer_use as cu_mod
        cu_mod.ImageGrab.grab.assert_called_once_with()

    def test_screenshot_region_uses_bbox(self, tmp_path, monkeypatch):
        """区域截屏应传 bbox 给 ImageGrab.grab。"""
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (800, 600)
        import tools.computer_use as cu_mod
        _patch_image_grab(monkeypatch, fake_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()
        result = tool.execute(action="screenshot", x=100, y=50, w=800, h=600)

        assert "Screenshot captured" in result
        assert "800x600" in result
        # 验证 bbox 参数
        cu_mod.ImageGrab.grab.assert_called_once_with(bbox=(100, 50, 900, 650))

    def test_screenshot_region_partial_params_falls_back_to_fullscreen(self, tmp_path, monkeypatch):
        """部分区域参数缺失应降级为全屏，返回值带提示。"""
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (1920, 1080)
        import tools.computer_use as cu_mod
        _patch_image_grab(monkeypatch, fake_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()
        # 只传 x 不传 w/h，应降级
        result = tool.execute(action="screenshot", x=100)

        assert "Screenshot captured" in result
        assert "fullscreen" in result.lower() or "fell back" in result.lower()
        cu_mod.ImageGrab.grab.assert_called_once_with()


# ============== screenshot vision 集成 ==============

class TestScreenshotVision:
    def test_screenshot_with_llm_client_calls_vision(self, tmp_path, monkeypatch):
        """注入 llm_client 时，screenshot 应调 chat_with_image 返回描述。"""
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (800, 600)
        _patch_image_grab(monkeypatch, fake_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        mock_llm = MagicMock()
        mock_llm.chat_with_image.return_value = "A window with a button at top-right"
        tool = ComputerUseTool(llm_client=mock_llm)

        result = tool.execute(action="screenshot")

        assert "Screenshot captured" in result
        assert "A window with a button at top-right" in result
        assert "Vision analysis" in result
        mock_llm.chat_with_image.assert_called_once()
        # 验证传入了 image_path（位置参数或关键字参数均可）
        call_args = mock_llm.chat_with_image.call_args
        # 第二个位置参数（args[1]）或 image_path kwarg 应为 filepath 字符串
        if call_args.args and len(call_args.args) >= 2:
            assert str(call_args.args[1]).endswith(".png")
        else:
            assert str(call_args.kwargs.get("image_path")).endswith(".png")

    def test_screenshot_without_llm_client_returns_placeholder(self, tmp_path, monkeypatch):
        """未注入 llm_client 时，返回 placeholder 描述。"""
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (800, 600)
        _patch_image_grab(monkeypatch, fake_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()  # 无 llm_client
        result = tool.execute(action="screenshot")

        assert "Screenshot captured" in result
        assert "llm_client not configured" in result

    def test_screenshot_file_removed_after_use(self, tmp_path, monkeypatch):
        """截图在 vision 分析后应被删除，避免磁盘累积。"""
        import os
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        # 用真实的 PIL Image 让 save 真正写文件，验证后续 os.remove 删除
        from PIL import Image
        real_img = Image.new("RGB", (100, 100), (0, 0, 0))
        import tools.computer_use as cu_mod
        monkeypatch.setattr(cu_mod, "pil_available", True, raising=False)
        monkeypatch.setattr(cu_mod, "ImageGrab", MagicMock(), raising=False)
        cu_mod.ImageGrab.grab = MagicMock(return_value=real_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()
        result = tool.execute(action="screenshot")

        assert "Screenshot captured" in result
        assert "temp file removed" in result
        # screenshots 目录应无残留 png
        shots_dir = tmp_path / "screenshots"
        if shots_dir.exists():
            pngs = list(shots_dir.glob("*.png"))
            assert pngs == [], f"截图文件未删除: {pngs}"

    def test_screenshot_vision_error_degrades_gracefully(self, tmp_path, monkeypatch):
        """vision LLM 抛 LLMError 时，应降级为提示，不影响截屏结果。"""
        from tools.computer_use import ComputerUseTool
        from core.llm import LLMError
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (800, 600)
        _patch_image_grab(monkeypatch, fake_img)
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        mock_llm = MagicMock()
        mock_llm.chat_with_image.side_effect = LLMError(400, "model does not support images")
        tool = ComputerUseTool(llm_client=mock_llm)

        result = tool.execute(action="screenshot")

        # 截屏结果仍存在
        assert "Screenshot captured" in result
        # vision 描述为降级提示
        assert "vision unavailable" in result.lower()
        assert "model does not support images" in result

    def test_screenshot_calls_thumbnail_renderer(self, tmp_path, monkeypatch):
        """screenshot 应调用 print_screenshot_thumbnail。"""
        from tools.computer_use import ComputerUseTool
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        fake_img = MagicMock()
        fake_img.size = (800, 600)
        _patch_image_grab(monkeypatch, fake_img)

        thumb_called = []
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail",
                            lambda path, **kw: thumb_called.append(path))

        tool = ComputerUseTool()
        tool.execute(action="screenshot")

        assert len(thumb_called) == 1
        assert thumb_called[0].endswith(".png")
