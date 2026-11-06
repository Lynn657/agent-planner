"""计算器工具: 安全的算术表达式求值。

安全说明:
不使用 eval, 而是用 ast 解析后只允许白名单内的运算符,
避免"表达式里塞入函数调用/属性访问"带来的代码执行风险。
"""

from __future__ import annotations

import ast
import operator

from pydantic import BaseModel, Field

from agent_planner.tools.base import BaseTool, ToolResult

_MAX_EXPR_LEN = 200
_MAX_POW_EXPONENT = 100

_BIN_OPS: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS: dict[type[ast.unaryop], object] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def safe_eval(expression: str) -> float:
    """计算四则运算表达式, 仅支持数字、括号、+ - * / % // 与一元正负号。

    Raises:
        ValueError: 表达式非法或包含不允许的节点
    """
    expression = expression.strip()
    if not expression:
        raise ValueError("表达式为空")
    if len(expression) > _MAX_EXPR_LEN:
        raise ValueError("表达式过长")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"表达式语法错误: {exc.msg}") from exc

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise ValueError("只允许数字常量")
            return float(node.value)
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type is ast.Pow:
                exponent = _eval(node.right)
                if abs(exponent) > _MAX_POW_EXPONENT:
                    raise ValueError("指数过大")
                return _eval(node.left) ** exponent
            func = _BIN_OPS.get(op_type)
            if func is None:
                raise ValueError(f"不支持的运算符: {op_type.__name__}")
            return func(_eval(node.left), _eval(node.right))  # type: ignore[operator]
        if isinstance(node, ast.UnaryOp):
            func = _UNARY_OPS.get(type(node.op))
            if func is None:
                raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
            return func(_eval(node.operand))  # type: ignore[operator]
        raise ValueError(f"不支持的表达式节点: {type(node).__name__}")

    return _eval(tree.body)


class CalculatorArgs(BaseModel):
    """计算器入参。"""

    expression: str = Field(description="算术表达式, 例如 356*18 或 (12+8)/4")


class CalculatorTool(BaseTool):
    """对算术表达式求值。"""

    name = "calculator"
    description = "计算数学表达式, 支持加、减、乘、除、取余、整除与括号"
    args_model = CalculatorArgs

    def execute(self, args: BaseModel) -> ToolResult:
        assert isinstance(args, CalculatorArgs)
        value = safe_eval(args.expression)
        # 整数结果不带小数尾巴, 便于阅读
        output: float | int = int(value) if value.is_integer() else round(value, 6)
        return ToolResult(tool=self.name, ok=True, output=output)
