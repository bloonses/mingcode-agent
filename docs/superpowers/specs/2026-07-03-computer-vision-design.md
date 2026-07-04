# Computer Vision 与终端缩略图特效设计

**日期**: 2026-07-03
**状态**: 设计已确认，待实现
**关联**: 扩展 `tools/computer_use.py` 与 `core/llm.py`，对标 Codex computer use

## 背景与目标

当前 `ComputerUseTool` 已具备截屏、点击、输入、按键等 11 个 action，但截屏仅返回文件路径，AI 无法"看见"屏幕内容。本次扩展对标 Codex computer use，目标是：

1. **让 AI 真正看见屏幕**：截屏后自动调用多模态 LLM 分析画面，返回描述
2. **终端内渲染缩略图**：用 ANSI truecolor 半块字符渲染截图缩略图，无需打开图片查看器
3. **区域截屏**：支持 `x/y/w/h` 参数只截取屏幕局部，减少 token 消耗

## 非目标

- 不新增独立 VisionTool（避免新工具类）
- 不新增 LLM 配置段（复用现有 model）
- 不实现点击位置高亮、动作流面板、pulse 动画（YAGNI）
- 不实现跨平台 Unicode 输入（保持 Windows `clip` 命令方案）

## 设计决策概览

| 维度 | 选择 | 理由 |
|------|------|------|
| Vision 模型 | 复用现有 model | YAGNI，避免新增配置 |
| Vision 集成 | screenshot 内嵌 | 一次调用拿到一切，符合 codex 体验 |
| 区域截屏 | 绝对坐标 x/y/w/h | 直接对标 codex crop |
| 特效 | 终端半块字符缩略图 | codex 标志性特效 |
| 架构模式 | 依赖注入 LLMClient | 与 AskUserTool 一致 |

## §1 — LLMClient 扩展

### 改动位置

`core/llm.py`

### 新增方法

```python
def chat_with_image(self, prompt: str, image_path: str, system: str = None) -> str:
    """多模态调用：发送图片+提示词，返回文本描述"""
```

### messages 构造

`user` 角色的 `content` 为 list 形式（OpenAI vision 标准）：

```python
content = [
    {"type": "text", "text": prompt},
    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
]
```

`b64` 由内置 `base64` 模块编码图片文件得到，不依赖 Pillow。

### 调用方式

- 不走 stream（vision 通常不需要流式）
- 内部调 `self.chat(messages, stream=False)`
- 返回 `result["content"]` 字符串

### sanitize 保护

`_sanitize_messages` 需加一条保护：若 `content` 是 list，**直接跳过**规范化，避免破坏 image_url 结构。

```python
def _sanitize_messages(self, messages):
    sanitized = []
    for msg in messages:
        new_msg = dict(msg)
        if isinstance(new_msg.get("content"), list):
            sanitized.append(new_msg)
            continue  # 跳过 list 形式 content 的规范化
        # ... 原有逻辑
```

### 配置

- **不新增配置**：复用 `self.base_url/api_key/model`
- model 是否支持 vision 由用户在 `/settings` 自行配置（如 `glm-4v` / `qwen-vl-plus` / `gpt-4o`）

### 降级处理

`chat_with_image` 内部不捕获异常，由调用方（ComputerUseTool）捕获 `LLMError` 并降级。

## §2 — ComputerUseTool 增强

### 改动位置

`tools/computer_use.py` + `core/agent.py`

### 构造函数注入

```python
class ComputerUseTool(BaseTool):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
```

`core/agent.py` 注册处改为：
```python
self.registry.register(ComputerUseTool(llm_client=self.llm))
```

`ComputerUseTool()` 无参构造仍需工作（向后兼容，用于测试）。

### screenshot action 增强

**新增可选参数**（在现有 schema 基础上）：
- `x` / `y`：区域左上角坐标
- `w` / `h`：区域宽高

四者全有才走区域截屏，否则全屏。

### 执行流程

```
1. 截屏（PIL.ImageGrab.grab(bbox=(x,y,x+w,y+h)) 或全屏）
2. 保存到 user_data_dir/screenshots/shot_{ts}.png
3. 调 print_screenshot_thumbnail(filepath) 渲染终端缩略图
4. 若 self.llm_client 存在：
       try: description = llm_client.chat_with_image(
               prompt="描述这个屏幕截图的主要元素：窗口布局、可见文本、可点击元素的位置",
               image_path=filepath)
           except LLMError: description = "(vision unavailable: {error})"
   否则: description = "(llm_client not configured)"
5. 返回组合字符串
```

### 返回值格式

```
Screenshot saved: C:\Users\...\shot_1234567890.png
Size: 800x600
Region: (100, 50) 800x600  # 仅区域截屏时显示

Vision analysis:
（描述内容）

（终端已渲染缩略图）
```

### 不破坏现有 action

其余 11 个 action 零改动。

## §3 — 终端缩略图渲染

### 改动位置

`ui/console.py`

### 新增函数

```python
def print_screenshot_thumbnail(image_path: str, max_width: int = 80) -> None:
```

### 算法

用 ANSI truecolor 半块字符渲染：
- `▀`（U+2580）一次显示两行像素：上像素做前景色，下像素做背景色
- 2 个垂直像素合并为 1 个终端字符

### 渲染流程

```
1. PIL.Image.open(image_path).convert("RGB")
2. 计算缩放比：scale = max_width / img.width
   new_w = max_width
   new_h = max(1, int(img.height * scale / 2))  # /2 因半块字符
3. img.resize((new_w, new_h * 2))
4. 双重循环：
   for y in range(0, resized.height, 2):
       line = ""
       for x in range(new_w):
           upper = resized.getpixel((x, y))
           lower = resized.getpixel((x, y+1)) if y+1 < h else (0,0,0)
           line += f"\x1b[38;2;{upper[0]};{upper[1]};{upper[2]}m\x1b[48;2;{lower[0]};{lower[1]};{lower[2]}m▀"
       print(line)
5. 结尾 \x1b[0m 重置
```

### 视觉风格

- **不加 Panel 边框**：缩略图本身是位图，套 Panel 会破坏像素对齐
- **不加标题**：在缩略图上方一行用 `style_neon_teal` 打印 `SCREENSHOT THUMBNAIL`，保持赛博极简
- **不加动画**：缩略图是静态快照，pulse 动画会干扰视觉（YAGNI）

### 降级

- Pillow 未安装 → 打印 `[thumbnail unavailable: Pillow not installed]`
- 图片读取失败 → 打印 `[thumbnail error: {e}]`

### 性能

- 80×30 字符 = 2400 个半块字符
- 每字符 ~50 字节 ANSI = ~120KB 输出
- Console 一次性 print，不用 Live（静态图无需刷新）

### 调用方

`ComputerUseTool._screenshot()` 内部直接调用 `print_screenshot_thumbnail(filepath)`。

工具直接打 console 违反"工具不直接打 console"惯例，但 codex 风格特效就是要在执行时即时渲染。缩略图是给人看的，AI 只需路径和 vision 描述，故不混入返回值。

## §4 — 区域截屏语义

### 参数定义

```python
"x": {"type": "integer", "description": "区域左上角 X（区域截屏时必填）"},
"y": {"type": "integer", "description": "区域左上角 Y（区域截屏时必填）"},
"w": {"type": "integer", "description": "区域宽度（区域截屏时必填）"},
"h": {"type": "integer", "description": "区域高度（区域截屏时必填）"},
```

`x`/`y`/`w`/`h` 均为可选；**四者全有**才走区域截屏，否则全屏。

### PIL.ImageGrab.grab 调用

```python
if all(v is not None for v in (x, y, w, h)):
    bbox = (x, y, x + w, y + h)
    img = ImageGrab.grab(bbox=bbox)
    region_desc = f"region ({x},{y}) {w}x{h}"
else:
    img = ImageGrab.grab()
    region_desc = "fullscreen"
```

### 边界容错（不报错，符合 codex 风格）

- 越界：`x+w > 屏幕宽度` → PIL 自动裁剪到屏幕边界，不报错
- 部分缺失：`x`/`y` 有但 `w`/`h` 缺 → 降级为全屏，返回值带提示
- 负值：`w`/`h` ≤ 0 → 降级为全屏
- 全 0：等价全屏

### 缩略图自适应

区域截屏的缩略图 `max_width` 不变（仍 80 列），等比缩放即可。小区域会放大显示，不影响视觉。

### vision prompt 微调

区域截屏时 prompt 加定位上下文：
```python
prompt = f"描述这个屏幕截图（{region_desc}）的主要元素：可见文本、可点击元素的位置"
```

## §5 — 错误处理与降级矩阵

### 降级链（优先级从高到低）

| 条件 | screenshot 返回值 | 缩略图 | vision 描述 |
|------|------------------|--------|------------|
| 全部正常 | 路径+尺寸+区域+描述 | 渲染 | LLM 返回 |
| `llm_client=None` | 路径+尺寸+区域 | 渲染 | `"(llm_client not configured)"` |
| model 不支持 vision（4xx） | 路径+尺寸+区域 | 渲染 | `"(vision unavailable: {error})"` |
| vision 超时 | 路径+尺寸+区域 | 渲染 | `"(vision timeout)"` |
| Pillow 未安装 | 错误信息 | 不渲染 | 不调用 |
| 截屏失败（权限/锁屏） | `Error: {e}` | 不渲染 | 不调用 |

### 关键原则

- **截屏失败不调 vision**：避免无谓的 LLM 调用浪费 token
- **vision 失败不影响截屏**：路径和缩略图照常返回
- **缩略图失败不影响返回值**：缩略图是装饰，渲染失败只在终端打印一行提示

### 异常捕获边界

`ComputerUseTool._screenshot()` 内部：
- 截屏异常 → 整个 action 返回 `Error: {e}`（外层 `safe_execute` 已兜底）
- vision 调用异常 → 在 try/except 内降级为提示字符串，**不向上抛**
- 缩略图渲染异常 → 在 try/except 内降级为打印提示，**不向上抛**

### 不做的事

- **不重试**：vision 失败一次就降级，不重试（YAGNI，AI 可自行决定再截一次）
- **不缓存**：每次截屏都是新画面，缓存无意义
- **不异步**：截屏+vision+缩略图三步串行，符合现有工具同步调用模式

## §6 — 测试策略（TDD）

遵循项目惯例 RED-GREEN，测试文件 `tests/test_computer_vision.py`。

### LLMClient 测试（4 个）

```python
class TestLLMClientChatWithImage:
    def test_chat_with_image_returns_content(self, tmp_path, mock_llm_response)
    def test_chat_with_image_builds_image_url_payload(self, tmp_path)
    def test_chat_with_image_handles_vision_unsupported_error(self, tmp_path)
    def test_sanitize_messages_preserves_list_content(self)
```

第 4 个最关键——验证 sanitize 不破坏 list 形式的 content。

### ComputerUseTool 测试（8 个）

```python
class TestComputerUseToolScreenshot:
    def test_screenshot_fullscreen_saves_and_returns_path(self, tmp_path)
    def test_screenshot_region_uses_bbox(self, tmp_path)
    def test_screenshot_region_partial_params_falls_back_to_fullscreen(self, tmp_path)
    def test_screenshot_with_llm_client_calls_vision(self, tmp_path, mock_llm)
    def test_screenshot_without_llm_client_returns_placeholder(self, tmp_path)
    def test_screenshot_vision_error_degrades_gracefully(self, tmp_path, mock_llm_failing)
    def test_screenshot_calls_thumbnail_renderer(self, tmp_path)
    def test_screenshot_pillow_unavailable_returns_error(self, monkeypatch)
```

关键 mock：
- `PIL.ImageGrab.grab` → 返回 MagicMock img（避免真截屏）
- `img.save` → 写入 tmp_path 下的假 PNG
- `llm_client.chat_with_image` → MagicMock 返回固定描述

### 缩略图渲染测试（4 个）

```python
class TestPrintScreenshotThumbnail:
    def test_thumbnail_renders_half_block_chars(self, tmp_path, capsys)
    def test_thumbnail_respects_max_width(self, tmp_path, capsys)
    def test_thumbnail_pillow_missing_prints_placeholder(self, monkeypatch, capsys)
    def test_thumbnail_image_error_prints_error_message(self, tmp_path, capsys)
```

第一个断言关键：输出应包含 `\x1b[38;2;` 和 `▀` 字符。

### 现有测试不回归

- `tests/test_new_tools.py` 的 40 个 computer 测试不应受影响
- `ComputerUseTool()` 无参构造仍需工作（向后兼容，用于测试）

### 测试规模

- 新增约 16 个测试
- 总计 99 + 16 = 115 个测试

### 不测的

- **不测真实 vision LLM 调用**：需 API key + 真实截屏，CI 不可控
- **不测终端实际渲染像素**：capsys 只能验证 ANSI 转义码存在，无法验证视觉效果
- **不测区域越界**：PIL 行为，不应测第三方库

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `core/llm.py` | 修改 | 新增 `chat_with_image`，sanitize 加 list 保护 |
| `tools/computer_use.py` | 修改 | 构造注入 `llm_client`，screenshot action 增强 |
| `ui/console.py` | 修改 | 新增 `print_screenshot_thumbnail` |
| `core/agent.py` | 修改 | 注册时注入 `llm_client=self.llm` |
| `tests/test_computer_vision.py` | 新增 | 16 个新测试 |

## 依赖

无新增依赖（Pillow 已在 requirements.txt）。
