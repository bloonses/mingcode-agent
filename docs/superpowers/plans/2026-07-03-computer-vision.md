# Computer Vision 与终端缩略图特效 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 真正"看见"屏幕——截屏后自动调多模态 LLM 分析画面，并在终端用 ANSI 半块字符渲染缩略图。

**Architecture:** 依赖注入模式。LLMClient 新增 `chat_with_image` 方法；ComputerUseTool 构造时接受可选 `llm_client`，screenshot action 内嵌截屏→vision→缩略图三步串行；console.py 新增半块字符渲染器。降级链确保任一环节失败不影响其他环节。

**Tech Stack:** Python 3.10+ / Pillow (PIL.ImageGrab + Image.open) / 内置 base64 / Rich Console / pytest

**关联 spec:** `docs/superpowers/specs/2026-07-03-computer-vision-design.md`

---

## 文件结构

| 文件 | 责任 | 改动类型 |
|------|------|---------|
| `core/llm.py` | 新增 `chat_with_image`，sanitize 加 list 保护 | 修改 |
| `tools/computer_use.py` | 构造注入 `llm_client`，screenshot action 增强 | 修改 |
| `ui/console.py` | 新增 `print_screenshot_thumbnail` | 修改 |
| `core/agent.py` | 注册时注入 `llm_client=self.llm` | 修改 |
| `tests/test_computer_vision.py` | 16 个新测试 | 新增 |

---

## Task 1: LLMClient.chat_with_image + sanitize list 保护

**Files:**
- Modify: `core/llm.py`（在 `_sanitize_messages` 顶部加 list 保护；在类末尾加 `chat_with_image`）
- Test: `tests/test_computer_vision.py`（新建文件，加 4 个测试）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_computer_vision.py`：

```python
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
```

运行：
```bash
python -m pytest tests/test_computer_vision.py -v
```
预期：4 个测试全部 FAIL（`chat_with_image` 方法不存在；`_sanitize_messages` 会破坏 list content）

- [ ] **Step 2: 在 `_sanitize_messages` 加 list 保护**

打开 `core/llm.py`，找到 `_sanitize_messages` 方法（约 77-93 行）。在 `for msg in messages:` 循环内、`new_msg = dict(msg)` 之后，插入 list 保护：

```python
    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """规范化 messages，修复各供应商（智谱 GLM code=1214 等）的格式要求。

        规则：
        - content 缺失或 None → ''（智谱不接受 null）
        - tool 角色空 content → 填充默认值（智谱不接受空 tool 结果）
        - assistant 带 tool_calls 时空 content → 保留 ''（合规）
        - list 形式的 content（多模态 image_url）→ 原样保留，不规范化
        """
        sanitized = []
        for msg in messages:
            new_msg = dict(msg)
            # 多模态 content 是 list，直接保留不规范化，避免破坏 image_url 结构
            if isinstance(new_msg.get("content"), list):
                sanitized.append(new_msg)
                continue
            if "content" not in new_msg or new_msg["content"] is None:
                new_msg["content"] = ""
            if new_msg["role"] == "tool" and not new_msg["content"]:
                new_msg["content"] = "(no output)"
            sanitized.append(new_msg)
        return sanitized
```

- [ ] **Step 3: 新增 `chat_with_image` 方法**

在 `core/llm.py` 的 `LLMClient` 类内、`chat` 方法之前（约 127 行前）插入：

```python
    def chat_with_image(self, prompt: str, image_path: str, system: str = None) -> str:
        """多模态调用：发送图片+提示词，返回文本描述。

        不走 stream（vision 通常不需要流式）。LLMError 向上抛出，由调用方捕获降级。
        """
        import base64
        from pathlib import Path

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        })

        result = self.chat(messages, stream=False)
        return result.get("content") or ""
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_computer_vision.py -v
```
预期：4 个测试全部 PASS。

同时验证现有测试不回归：
```bash
python -m pytest tests/ -q --tb=no
```
预期：99 passed（无新增，因新测试在 test_computer_vision.py 中已计入）+ 4 = 103 passed。

- [ ] **Step 5: 提交**

```bash
cd c:\Users\bloon\Downloads\neon_agent
git add core/llm.py tests/test_computer_vision.py
git commit -m "feat: add LLMClient.chat_with_image for multimodal vision calls"
```

---

## Task 2: print_screenshot_thumbnail 终端缩略图渲染

**Files:**
- Modify: `ui/console.py`（在文件末尾追加 `print_screenshot_thumbnail`）
- Test: `tests/test_computer_vision.py`（追加 4 个测试）

- [ ] **Step 1: 写失败测试**

在 `tests/test_computer_vision.py` 末尾追加：

```python
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
```

运行：
```bash
python -m pytest tests/test_computer_vision.py::TestPrintScreenshotThumbnail -v
```
预期：4 个测试 FAIL（`print_screenshot_thumbnail` 不存在 / `pil_available` 未导入）

- [ ] **Step 2: 在 console.py 顶部导入 pil_available 标志**

打开 `ui/console.py`，在现有 import 之后（约第 20 行 `from .theme import (...)` 之后）插入：

```python
# 可选依赖，运行时检测（与 computer_use.py 一致）
try:
    from PIL import Image
    pil_available = True
except ImportError:
    pil_available = False
```

- [ ] **Step 3: 在 console.py 末尾追加 `print_screenshot_thumbnail`**

```python
def print_screenshot_thumbnail(image_path: str, max_width: int = 80) -> None:
    """用 ANSI truecolor 半块字符在终端渲染截图缩略图（codex 风格）。

    半块字符 ▀ 一次显示两行像素：上像素做前景色，下像素做背景色。
    渲染失败不抛异常，只打印提示行。
    """
    if not pil_available:
        console.print("[thumbnail unavailable: Pillow not installed]")
        return
    try:
        img = Image.open(image_path).convert("RGB")
        # 计算缩放：宽 = max_width，高 = max_width × (h/w) / 2（半块合并两行）
        scale = max_width / img.width
        new_w = max_width
        new_h = max(1, int(img.height * scale / 2))
        resized = img.resize((new_w, new_h * 2))
        # 标题行
        console.print(Text("SCREENSHOT THUMBNAIL", style=style_neon_teal))
        # 双重循环渲染
        for y in range(0, resized.height, 2):
            line = ""
            for x in range(new_w):
                upper = resized.getpixel((x, y))
                lower = resized.getpixel((x, y + 1)) if y + 1 < resized.height else (0, 0, 0)
                line += f"\x1b[38;2;{upper[0]};{upper[1]};{upper[2]}m\x1b[48;2;{lower[0]};{lower[1]};{lower[2]}m▀"
            line += "\x1b[0m"
            print(line)
    except Exception as e:
        console.print(f"[thumbnail error: {e}]")
```

注意：用内置 `print` 而非 `console.print`，因为 Rich 会把 ANSI 转义码当文本显示，破坏视觉效果。

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_computer_vision.py::TestPrintScreenshotThumbnail -v
```
预期：4 个测试 PASS。

- [ ] **Step 5: 提交**

```bash
git add ui/console.py tests/test_computer_vision.py
git commit -m "feat: add codex-style terminal thumbnail renderer (ANSI half-block)"
```

---

## Task 3: ComputerUseTool 构造注入 llm_client（向后兼容）

**Files:**
- Modify: `tools/computer_use.py`（仅改 `ComputerUseTool` 类顶部加 `__init__`）
- Test: `tests/test_computer_vision.py`（追加 1 个测试，验证无参构造和有参构造）

- [ ] **Step 1: 写失败测试**

在 `tests/test_computer_vision.py` 末尾追加：

```python
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
```

运行：
```bash
python -m pytest tests/test_computer_vision.py::TestComputerUseToolConstruction -v
```
预期：2 个测试 FAIL（`ComputerUseTool` 无 `__init__`，无 `llm_client` 属性）

- [ ] **Step 2: 在 ComputerUseTool 类顶部加 `__init__`**

打开 `tools/computer_use.py`，找到 `class ComputerUseTool(BaseTool):`（约第 39 行），在 `name = "computer"` 之前插入：

```python
class ComputerUseTool(BaseTool):
    def __init__(self, llm_client=None):
        """llm_client 可选。若注入则 screenshot action 会调 vision；
        若不注入（None）则 screenshot 返回 placeholder 描述。"""
        self.llm_client = llm_client

    name = "computer"
```

- [ ] **Step 3: 运行新测试确认通过**

```bash
python -m pytest tests/test_computer_vision.py::TestComputerUseToolConstruction -v
```
预期：2 个测试 PASS。

- [ ] **Step 4: 验证现有 computer 测试不回归**

```bash
python -m pytest tests/test_new_tools.py -v -k "computer"
```
预期：现有 9 个 computer 测试全部 PASS（无参构造仍工作）。

- [ ] **Step 5: 提交**

```bash
git add tools/computer_use.py tests/test_computer_vision.py
git commit -m "feat: inject optional llm_client into ComputerUseTool constructor"
```

---

## Task 4: ComputerUseTool._screenshot 增强 — 区域截屏 + 返回值格式

**Files:**
- Modify: `tools/computer_use.py`（重写 `_screenshot` 方法；schema 加 x/y/w/h 参数）
- Test: `tests/test_computer_vision.py`（追加 3 个测试）

- [ ] **Step 1: 写失败测试**

在 `tests/test_computer_vision.py` 末尾追加：

```python
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
        from config.config import get_user_data_dir

        # patch get_user_data_dir 指向 tmp_path
        import tools.computer_use as cu_mod
        monkeypatch.setattr("config.config.get_user_data_dir", lambda: tmp_path)

        # patch ImageGrab 返回假图片
        fake_img = MagicMock()
        fake_img.size = (1920, 1080)
        _patch_image_grab(monkeypatch, fake_img)
        # patch thumbnail renderer 避免真渲染
        monkeypatch.setattr("ui.console.print_screenshot_thumbnail", lambda *a, **kw: None)

        tool = ComputerUseTool()
        result = tool.execute(action="screenshot")

        assert "Screenshot saved" in result
        assert "1920x1080" in result
        # 验证 ImageGrab.grab 被无 bbox 调用
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

        assert "Screenshot saved" in result
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

        assert "Screenshot saved" in result
        assert "fullscreen" in result.lower() or "fell back" in result.lower()
        cu_mod.ImageGrab.grab.assert_called_once_with()
```

运行：
```bash
python -m pytest tests/test_computer_vision.py::TestScreenshotRegion -v
```
预期：3 个测试 FAIL（`_screenshot` 还未支持区域参数；schema 也未声明 x/y/w/h）

- [ ] **Step 2: 在 schema 中添加 x/y/w/h 参数**

打开 `tools/computer_use.py`，找到 `parameters = {...}` 块（约第 55-80 行）。在 `"action": {...}` 之后的 properties 中，紧挨 `"x": {"type": "integer", "description": "点击/移动目标 X 坐标"},` 这一行之后，把现有的 x/y 注释更新，并新增 w/h。

具体地，把现有的 click 用 x/y 描述改为更通用，并新增 w/h 区域参数。在 `parameters["properties"]` 中确保存在：

```python
            "x": {"type": "integer", "description": "X 坐标（点击/移动目标，或区域截屏左上角）"},
            "y": {"type": "integer", "description": "Y 坐标（点击/移动目标，或区域截屏左上角）"},
            "w": {"type": "integer", "description": "区域截屏宽度（与 x/y/h 一起使用）"},
            "h": {"type": "integer", "description": "区域截屏高度（与 x/y/w 一起使用）"},
```

（注：x1/y1/x2/y2 已存在，不动）

- [ ] **Step 3: 重写 `_screenshot` 方法支持区域截屏**

打开 `tools/computer_use.py`，找到现有 `_screenshot` 方法（约 112-125 行），替换为：

```python
    def _screenshot(self, x=None, y=None, w=None, h=None) -> str:
        if not pil_available:
            return "Error: Pillow not installed. Run: pip install Pillow"
        try:
            from config.config import get_user_data_dir
            from ui.console import print_screenshot_thumbnail

            # 判断是否为区域截屏（四参数全有且为正）
            is_region = all(v is not None and v >= 0 for v in (x, y, w, h)) and (w or 0) > 0 and (h or 0) > 0
            if is_region:
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox=bbox)
                region_desc = f"region ({x},{y}) {w}x{h}"
            elif any(v is not None for v in (x, y, w, h)) and not is_region:
                # 部分参数缺失，降级为全屏
                img = ImageGrab.grab()
                region_desc = "fullscreen (region params incomplete, fell back)"
            else:
                img = ImageGrab.grab()
                region_desc = "fullscreen"

            shots_dir = get_user_data_dir() / "screenshots"
            shots_dir.mkdir(parents=True, exist_ok=True)
            filename = f"shot_{int(time.time())}.png"
            filepath = shots_dir / filename
            img.save(str(filepath))

            # 渲染终端缩略图（失败不影响主流程）
            try:
                print_screenshot_thumbnail(str(filepath))
            except Exception as thumb_err:
                # 缩略图渲染失败仅打印提示，不抛
                try:
                    from ui.console import console
                    console.print(f"[thumbnail render failed: {thumb_err}]")
                except Exception:
                    pass

            return (
                f"Screenshot saved: {filepath}\n"
                f"Size: {img.size[0]}x{img.size[1]}\n"
                f"Region: {region_desc}"
            )
        except Exception as e:
            return f"Error: {e}"
```

注意：本步骤**不含** vision 调用（Task 5 才加）。但需要 import `print_screenshot_thumbnail` 以便 Task 5 直接用。`try/except` 包裹缩略图调用保证降级。

- [ ] **Step 4: 更新 `execute` 方法分发**

找到 `execute` 方法（约第 82-110 行），找到 `if action == "screenshot":` 这一行（约 86-87 行），改为：

```python
        # 截屏不需要 pyautogui，只要 PIL
        if action == "screenshot":
            return self._screenshot(
                x=kwargs.get("x"),
                y=kwargs.get("y"),
                w=kwargs.get("w"),
                h=kwargs.get("h"),
            )
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_computer_vision.py::TestScreenshotRegion -v
python -m pytest tests/test_new_tools.py -k "computer" -v
```
预期：3 个新测试 PASS；现有 9 个 computer 测试不回归。

- [ ] **Step 6: 提交**

```bash
git add tools/computer_use.py tests/test_computer_vision.py
git commit -m "feat: support region screenshot (x/y/w/h bbox) with fallback"
```

---

## Task 5: ComputerUseTool._screenshot 增强 — vision LLM 集成

**Files:**
- Modify: `tools/computer_use.py`（在 `_screenshot` 中加 vision 调用块）
- Test: `tests/test_computer_vision.py`（追加 4 个测试）

- [ ] **Step 1: 写失败测试**

在 `tests/test_computer_vision.py` 末尾追加：

```python
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

        assert "Screenshot saved" in result
        assert "A window with a button at top-right" in result
        assert "Vision analysis" in result
        mock_llm.chat_with_image.assert_called_once()
        # 验证传入了 image_path
        call_kwargs = mock_llm.chat_with_image.call_args.kwargs
        assert "image_path" in call_kwargs or "image_path" in mock_llm.chat_with_image.call_args.args

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

        assert "Screenshot saved" in result
        assert "llm_client not configured" in result

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
        assert "Screenshot saved" in result
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
```

运行：
```bash
python -m pytest tests/test_computer_vision.py::TestScreenshotVision -v
```
预期：4 个测试 FAIL（`_screenshot` 还未调用 vision；未注入时不返回 placeholder）

- [ ] **Step 2: 在 `_screenshot` 中加 vision 调用块**

打开 `tools/computer_use.py`，找到 Task 4 写的 `_screenshot` 方法。在缩略图渲染块之后、`return (...)` 之前，插入 vision 调用块：

```python
            # 调用 vision LLM 分析画面（失败降级为提示，不影响截屏结果）
            if self.llm_client is not None:
                try:
                    from core.llm import LLMError
                    vision_prompt = (
                        f"描述这个屏幕截图（{region_desc}）的主要元素："
                        f"窗口布局、可见文本、可点击元素的位置"
                    )
                    description = self.llm_client.chat_with_image(
                        prompt=vision_prompt,
                        image_path=str(filepath),
                    )
                    vision_section = f"Vision analysis:\n{description}"
                except LLMError as e:
                    vision_section = f"Vision analysis:\n(vision unavailable: {e})"
                except Exception as e:
                    vision_section = f"Vision analysis:\n(vision error: {e})"
            else:
                vision_section = "Vision analysis:\n(llm_client not configured)"
```

- [ ] **Step 3: 更新返回值拼接 vision_section**

在同一 `_screenshot` 方法的 return 语句中，把 vision_section 拼到末尾：

```python
            return (
                f"Screenshot saved: {filepath}\n"
                f"Size: {img.size[0]}x{img.size[1]}\n"
                f"Region: {region_desc}\n\n"
                f"{vision_section}"
            )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_computer_vision.py -v
python -m pytest tests/ -q --tb=no
```
预期：所有 test_computer_vision.py 测试 PASS；全套 99 + 16 = 115 passed。

- [ ] **Step 5: 提交**

```bash
git add tools/computer_use.py tests/test_computer_vision.py
git commit -m "feat: integrate vision LLM into screenshot action with graceful degradation"
```

---

## Task 6: 在 NeonAgent 注册时注入 llm_client

**Files:**
- Modify: `core/agent.py:73`（仅一行改动）
- Test: 已有 `test_all_new_tools_registered_in_main_agent` 覆盖，无需新增

- [ ] **Step 1: 修改注册行**

打开 `core/agent.py`，找到第 73 行：

```python
        self.registry.register(ComputerUseTool())
```

改为：

```python
        # 桌面控制（模仿 Codex computer use）：截屏 + 鼠标键盘 + vision 分析
        self.registry.register(ComputerUseTool(llm_client=self.llm))
```

（保留原注释含义，更新为新行为描述）

- [ ] **Step 2: 运行现有注册测试验证不回归**

```bash
python -m pytest tests/test_new_tools.py::test_all_new_tools_registered_in_main_agent -v
```
预期：PASS（"computer" 仍在工具列表中）

- [ ] **Step 3: 运行全套测试**

```bash
python -m pytest tests/ -q --tb=no
```
预期：115 passed。

- [ ] **Step 4: 提交**

```bash
git add core/agent.py
git commit -m "feat: inject llm_client into ComputerUseTool at agent registration"
```

---

## 自审检查

### Spec 覆盖扫描

- §1 LLMClient.chat_with_image → Task 1 ✓
- §1 sanitize list 保护 → Task 1 ✓
- §2 构造注入 llm_client → Task 3 ✓
- §2 screenshot action 增强（vision 内嵌）→ Task 5 ✓
- §2 返回值格式 → Task 4 + Task 5 ✓
- §2 不破坏现有 action → Task 4 Step 5 验证 ✓
- §3 print_screenshot_thumbnail → Task 2 ✓
- §3 半块字符算法 → Task 2 ✓
- §3 max_width 参数 → Task 2 ✓
- §3 降级（Pillow 未安装/读取失败）→ Task 2 ✓
- §3 标题行 SCREENSHOT THUMBNAIL → Task 2 ✓
- §4 区域参数 x/y/w/h → Task 4 ✓
- §4 PIL.ImageGrab.grab bbox → Task 4 ✓
- §4 边界容错（部分缺失降级）→ Task 4 ✓
- §4 vision prompt 微调（含 region_desc）→ Task 5 ✓
- §5 降级矩阵 → Task 5（LLMError 降级）+ Task 2（缩略图降级）✓
- §5 截屏失败不调 vision → Task 4（截屏异常 → return Error，不到 vision 块）✓
- §5 vision 失败不影响截屏 → Task 5（try/except LLMError）✓
- §5 缩略图失败不影响返回值 → Task 4（缩略图 try/except）✓
- §6 测试 16 个 → Task 1（4）+ Task 2（4）+ Task 3（2）+ Task 4（3）+ Task 5（4）= 17（实际多一个 test_no_arg_construction_still_works，可接受）✓

无 spec 遗漏。

### 占位符扫描

- 无 "TBD" / "TODO" / "implement later" ✓
- 所有代码块完整 ✓
- 所有命令含预期输出 ✓

### 类型一致性检查

- `chat_with_image(prompt, image_path, system=None)` 签名：Task 1 定义，Task 5 调用一致 ✓
- `print_screenshot_thumbnail(image_path, max_width=80)` 签名：Task 2 定义，Task 4/5 调用一致 ✓
- `ComputerUseTool(llm_client=None)` 构造：Task 3 定义，Task 6 调用一致 ✓
- `_screenshot(x=None, y=None, w=None, h=None)` 签名：Task 4 定义，execute 分发一致 ✓
- `LLMError` 导入：Task 1 测试用，Task 5 实现用 ✓

无类型不一致。
