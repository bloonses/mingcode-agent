"""MathTool - 精确数学运算。

使用 decimal.Decimal 避免浮点误差，支持大数、精确小数。
action: calc（算术表达式求值）/ sqrt / pow / gcd / lcm
"""
import decimal
import math
import re
from typing import Optional

from .base import BaseTool


# 安全的表达式求值：仅允许数字、运算符、括号、空格、小数点
_SAFE_EXPR_RE = re.compile(r'^[\d\.\+\-\*\/\(\)\s,]*$')


class MathTool(BaseTool):
    name = "math"
    description = (
        "精确数学运算，避免浮点误差。支持 action："
        "calc（算术表达式如 '1.1 + 2.2'，返回精确结果）/ "
        "sqrt（平方根，可指定精度）/ "
        "pow（幂运算）/ "
        "gcd（最大公约数，多参数）/ "
        "lcm（最小公倍数，多参数）。"
        "使用 decimal.Decimal 实现，适合财务/科学计算。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["calc", "sqrt", "pow", "gcd", "lcm"],
                "description": "运算类型"
            },
            "expression": {
                "type": "string",
                "description": "action=calc 时必填，算术表达式如 '0.1 + 0.2' 或 '(3 * 4) / 2'"
            },
            "number": {
                "type": "number",
                "description": "action=sqrt/pow 时为底数"
            },
            "exponent": {
                "type": "number",
                "description": "action=pow 时为指数"
            },
            "numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "action=gcd/lcm 时为整数列表"
            },
            "precision": {
                "type": "integer",
                "description": "action=sqrt 时可选，小数位数，默认 50"
            }
        },
        "required": ["action"]
    }

    def execute(self, **kwargs) -> str:
        action = (kwargs.get("action") or "").strip().lower()

        if action == "calc":
            return self._calc(kwargs.get("expression"))
        if action == "sqrt":
            return self._sqrt(kwargs.get("number"), kwargs.get("precision", 50))
        if action == "pow":
            return self._pow(kwargs.get("number"), kwargs.get("exponent"))
        if action == "gcd":
            return self._gcd(kwargs.get("numbers"))
        if action == "lcm":
            return self._lcm(kwargs.get("numbers"))
        return f"Error: unknown action '{action}'. Supported: calc/sqrt/pow/gcd/lcm"

    def _calc(self, expr: Optional[str]) -> str:
        if not expr:
            return "Error: expression is required for calc action"
        expr = expr.strip()
        if not _SAFE_EXPR_RE.match(expr):
            return f"Error: expression contains disallowed characters. Allowed: digits, + - * / ( ) , ."
        try:
            # 把数字字面量替换为 Decimal('...') 以获得精度
            # 例如 0.1 + 0.2 -> Decimal('0.1') + Decimal('0.2')
            cleaned = expr.replace(",", "")
            decimal.getcontext().prec = 50
            decimal_expr = re.sub(r"(\d+\.?\d*)", r"Decimal('\1')", cleaned)
            result = eval(decimal_expr, {"__builtins__": {}}, {"Decimal": decimal.Decimal})
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def _sqrt(self, number, precision) -> str:
        if number is None:
            return "Error: number is required for sqrt action"
        try:
            decimal.getcontext().prec = int(precision) + 10
            d = decimal.Decimal(str(number))
            if d < 0:
                return f"Error: sqrt of negative number {number}"
            return str(d.sqrt())
        except Exception as e:
            return f"Error: {e}"

    def _pow(self, number, exponent) -> str:
        if number is None or exponent is None:
            return "Error: number and exponent are required for pow action"
        try:
            decimal.getcontext().prec = 50
            base = decimal.Decimal(str(number))
            exp = decimal.Decimal(str(exponent))
            return str(base ** exp)
        except Exception as e:
            return f"Error: {e}"

    def _gcd(self, numbers) -> str:
        if not numbers:
            return "Error: numbers list is required for gcd action"
        try:
            nums = [int(n) for n in numbers]
            if not nums:
                return "Error: at least one number required"
            result = nums[0]
            for n in nums[1:]:
                result = math.gcd(result, n)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def _lcm(self, numbers) -> str:
        if not numbers:
            return "Error: numbers list is required for lcm action"
        try:
            nums = [int(n) for n in numbers]
            if not nums:
                return "Error: at least one number required"
            result = nums[0]
            for n in nums[1:]:
                result = result * n // math.gcd(result, n)
            return str(result)
        except Exception as e:
            return f"Error: {e}"
