"""Office 文档工具测试。

测试覆盖：
1. schema 测试（4 个）：验证 to_schema() 结构
2. 依赖缺失测试（4 个）：mock _import_xxx 返回 None，验证友好错误
3. Word 读写集成测试：实际创建 + 读取 .docx
4. Excel 读写集成测试：实际创建 + 读取 .xlsx
5. PPT 读写集成测试：实际创建 + 读取 .pptx
6. PDF 读写集成测试：实际创建 + 读取 .pdf
"""
import json
import os
from unittest.mock import patch

import pytest


# ============== Schema 测试 ==============

def test_word_tool_schema():
    from tools.office import WordTool
    schema = WordTool().to_schema()
    assert schema["function"]["name"] == "word"
    assert schema["function"]["parameters"]["type"] == "object"
    props = schema["function"]["parameters"]["properties"]
    assert "action" in props
    assert "path" in props
    assert "content" in props
    assert "max_chars" in props
    assert props["action"]["enum"] == ["read", "write"]
    assert "path" in schema["function"]["parameters"]["required"]
    assert "action" in schema["function"]["parameters"]["required"]


def test_pdf_tool_schema():
    from tools.office import PdfTool
    schema = PdfTool().to_schema()
    assert schema["function"]["name"] == "pdf"
    assert schema["function"]["parameters"]["type"] == "object"
    props = schema["function"]["parameters"]["properties"]
    assert "action" in props
    assert "path" in props
    assert "content" in props
    assert "max_pages" in props
    assert props["action"]["enum"] == ["read", "write"]
    assert "action" in schema["function"]["parameters"]["required"]
    assert "path" in schema["function"]["parameters"]["required"]


def test_excel_tool_schema():
    from tools.office import ExcelTool
    schema = ExcelTool().to_schema()
    assert schema["function"]["name"] == "excel"
    assert schema["function"]["parameters"]["type"] == "object"
    props = schema["function"]["parameters"]["properties"]
    assert "action" in props
    assert "path" in props
    assert "sheet" in props
    assert "data" in props
    assert "max_rows" in props
    assert props["action"]["enum"] == ["read", "write"]
    assert "action" in schema["function"]["parameters"]["required"]
    assert "path" in schema["function"]["parameters"]["required"]


def test_ppt_tool_schema():
    from tools.office import PptTool
    schema = PptTool().to_schema()
    assert schema["function"]["name"] == "ppt"
    assert schema["function"]["parameters"]["type"] == "object"
    props = schema["function"]["parameters"]["properties"]
    assert "action" in props
    assert "path" in props
    assert "slides" in props
    assert "max_slides" in props
    assert props["action"]["enum"] == ["read", "write"]
    assert "action" in schema["function"]["parameters"]["required"]
    assert "path" in schema["function"]["parameters"]["required"]


# ============== 依赖缺失测试 ==============

def test_word_tool_missing_dependency():
    from tools.office import WordTool
    with patch("tools.office._import_docx", return_value=None):
        result = WordTool().execute(action="read", path="dummy.docx")
    assert "python-docx" in result
    assert "pip install" in result


def test_pdf_tool_missing_read_dependency():
    from tools.office import PdfTool
    with patch("tools.office._import_pypdf", return_value=None):
        result = PdfTool().execute(action="read", path="dummy.pdf")
    assert "pypdf" in result
    assert "pip install" in result


def test_pdf_tool_missing_write_dependency():
    from tools.office import PdfTool
    with patch("tools.office._import_reportlab_canvas", return_value=None):
        result = PdfTool().execute(action="write", path="dummy.pdf", content="hi")
    assert "reportlab" in result
    assert "pip install" in result


def test_excel_tool_missing_dependency():
    from tools.office import ExcelTool
    with patch("tools.office._import_openpyxl", return_value=None):
        result = ExcelTool().execute(action="read", path="dummy.xlsx")
    assert "openpyxl" in result
    assert "pip install" in result


def test_ppt_tool_missing_dependency():
    from tools.office import PptTool
    with patch("tools.office._import_pptx", return_value=None):
        result = PptTool().execute(action="read", path="dummy.pptx")
    assert "python-pptx" in result
    assert "pip install" in result


# ============== 参数校验测试 ==============

def test_word_unknown_action():
    from tools.office import WordTool
    result = WordTool().execute(action="bogus", path="x.docx")
    assert "Error" in result


def test_word_missing_path():
    from tools.office import WordTool
    result = WordTool().execute(action="read")
    assert "Error" in result


def test_word_write_missing_content(tmp_path):
    from tools.office import WordTool
    p = str(tmp_path / "x.docx")
    result = WordTool().execute(action="write", path=p)
    assert "Error" in result


# ============== Word 读写集成测试 ==============

def test_word_write_and_read_roundtrip(tmp_path):
    from tools.office import WordTool
    p = str(tmp_path / "test.docx")
    content = "第一段落\n第二段落\n第三段落"
    write_res = WordTool().execute(action="write", path=p, content=content)
    assert "成功" in write_res
    assert os.path.exists(p)

    read_res = WordTool().execute(action="read", path=p)
    assert "第一段落" in read_res
    assert "第二段落" in read_res
    assert "第三段落" in read_res


def test_word_read_nonexistent(tmp_path):
    from tools.office import WordTool
    p = str(tmp_path / "no_such.docx")
    read_res = WordTool().execute(action="read", path=p)
    assert "Error" in read_res
    assert "not found" in read_res.lower() or "不存在" in read_res


def test_word_max_chars_truncation(tmp_path):
    from tools.office import WordTool
    p = str(tmp_path / "long.docx")
    content = "A" * 1000 + "\n" + "B" * 1000
    WordTool().execute(action="write", path=p, content=content)
    # 限制 100 字符
    read_res = WordTool().execute(action="read", path=p, max_chars=100)
    assert "截断" in read_res or "truncat" in read_res.lower()


# ============== Excel 读写集成测试 ==============

def test_excel_write_and_read_roundtrip(tmp_path):
    from tools.office import ExcelTool
    p = str(tmp_path / "test.xlsx")
    data = [["姓名", "年龄"], ["张三", 20], ["李四", 25]]
    write_res = ExcelTool().execute(
        action="write", path=p, data=json.dumps(data), sheet="Sheet1"
    )
    assert "成功" in write_res
    assert os.path.exists(p)

    read_res = ExcelTool().execute(action="read", path=p, sheet="Sheet1")
    assert "姓名" in read_res
    assert "张三" in read_res
    assert "20" in read_res
    # 验证 Markdown 表格格式
    assert "|" in read_res
    assert "---" in read_res


def test_excel_read_nonexistent(tmp_path):
    from tools.office import ExcelTool
    p = str(tmp_path / "no_such.xlsx")
    read_res = ExcelTool().execute(action="read", path=p)
    assert "Error" in read_res


def test_excel_read_missing_sheet(tmp_path):
    from tools.office import ExcelTool
    p = str(tmp_path / "test.xlsx")
    ExcelTool().execute(
        action="write", path=p, data=json.dumps([["a", "b"]]), sheet="Sheet1"
    )
    read_res = ExcelTool().execute(action="read", path=p, sheet="NotExist")
    assert "Error" in read_res
    assert "NotExist" in read_res or "not found" in read_res.lower()


def test_excel_write_invalid_data(tmp_path):
    from tools.office import ExcelTool
    p = str(tmp_path / "bad.xlsx")
    # 非 JSON 字符串
    res = ExcelTool().execute(action="write", path=p, data="not a json")
    assert "Error" in res


# ============== PPT 读写集成测试 ==============

def test_ppt_write_and_read_roundtrip(tmp_path):
    from tools.office import PptTool
    p = str(tmp_path / "test.pptx")
    slides = [
        {"title": "封面", "content": "这是封面内容\n第二行"},
        {"title": "第二页", "content": "正文内容"},
    ]
    write_res = PptTool().execute(
        action="write", path=p, slides=json.dumps(slides)
    )
    assert "成功" in write_res
    assert os.path.exists(p)

    read_res = PptTool().execute(action="read", path=p)
    assert "封面" in read_res
    assert "第二页" in read_res
    assert "这是封面内容" in read_res
    assert "正文内容" in read_res
    assert "[Slide 1]" in read_res
    assert "[Slide 2]" in read_res


def test_ppt_read_nonexistent(tmp_path):
    from tools.office import PptTool
    p = str(tmp_path / "no_such.pptx")
    read_res = PptTool().execute(action="read", path=p)
    assert "Error" in read_res


def test_ppt_write_missing_slides(tmp_path):
    from tools.office import PptTool
    p = str(tmp_path / "no_slides.pptx")
    res = PptTool().execute(action="write", path=p)
    assert "Error" in res


# ============== PDF 读写集成测试 ==============

def test_pdf_write_and_read_roundtrip(tmp_path):
    from tools.office import PdfTool
    p = str(tmp_path / "test.pdf")
    content = "Hello World\n这是第二行\nThird line"
    write_res = PdfTool().execute(action="write", path=p, content=content)
    assert "成功" in write_res
    assert os.path.exists(p)

    read_res = PdfTool().execute(action="read", path=p)
    assert "[Page 1]" in read_res
    assert "Hello World" in read_res


def test_pdf_read_nonexistent(tmp_path):
    from tools.office import PdfTool
    p = str(tmp_path / "no_such.pdf")
    read_res = PdfTool().execute(action="read", path=p)
    assert "Error" in read_res


def test_pdf_write_missing_content(tmp_path):
    from tools.office import PdfTool
    p = str(tmp_path / "no_content.pdf")
    res = PdfTool().execute(action="write", path=p)
    assert "Error" in res


def test_pdf_multiline_write(tmp_path):
    """多行内容应该写到 PDF 中（验证不会因为行多而崩溃）。"""
    from tools.office import PdfTool
    p = str(tmp_path / "multi.pdf")
    lines = [f"Line {i}" for i in range(100)]
    content = "\n".join(lines)
    write_res = PdfTool().execute(action="write", path=p, content=content)
    assert "成功" in write_res
    read_res = PdfTool().execute(action="read", path=p)
    assert "Line 0" in read_res
