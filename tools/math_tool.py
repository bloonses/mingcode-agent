"""精确数学工具（避免浮点误差）。"""
from decimal import Decimal, InvalidOperation, DivisionByZero
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class MathCalcInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate (e.g. '0.1 + 0.2', '10 / 3')")


@tool(args_schema=MathCalcInput)
def math_calc(expression: str) -> str:
    """Evaluate a mathematical expression with decimal precision."""
    try:
        safe_expr = expression.replace("^", "**")
        result = eval(safe_expr, {"__builtins__": {}}, {"Decimal": Decimal})
        if isinstance(result, Decimal):
            return str(result.quantize(Decimal("0.000001")) if result != result.to_integral_value() else result)
        return str(result)
    except DivisionByZero:
        return "Error: Division by zero"
    except InvalidOperation as e:
        return f"Error: Invalid operation - {e}"
    except Exception as e:
        return f"Error: {e}"
