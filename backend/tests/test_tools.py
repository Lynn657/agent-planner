"""工具单元测试: 计算器 / 时间 / 检索 / 备忘。

全部离线运行, 不依赖网络与真实模型。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from agent_planner.tools.calculator import CalculatorTool, safe_eval
from agent_planner.tools.clock import ClockTool
from agent_planner.tools.memo import MemoTool
from agent_planner.tools.search import SearchTool


class TestCalculator:
    def test_multiplication(self) -> None:
        result = CalculatorTool().run({"expression": "356*18"})
        assert result.ok
        assert result.output == 6408

    def test_parentheses_and_division(self) -> None:
        assert CalculatorTool().run({"expression": "(12+8)/4"}).output == 5

    def test_float_result(self) -> None:
        assert CalculatorTool().run({"expression": "7/2"}).output == 3.5

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('dir')",
            "open('/etc/passwd').read()",
            "lambda: 1",
        ],
    )
    def test_rejects_code_execution(self, expression: str) -> None:
        """表达式里出现函数调用/属性访问必须被拒绝。"""
        result = CalculatorTool().run({"expression": expression})
        assert not result.ok

    def test_rejects_huge_exponent(self) -> None:
        assert not CalculatorTool().run({"expression": "9**9999"}).ok

    def test_missing_argument(self) -> None:
        result = CalculatorTool().run({})
        assert not result.ok
        assert "参数校验失败" in (result.error or "")

    def test_safe_eval_division_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            safe_eval("1/0")


class TestClock:
    def test_fixed_time(self) -> None:
        fixed = datetime(2026, 11, 6, 20, 0, 0)
        tool = ClockTool(now_provider=lambda tz: fixed.replace(tzinfo=tz))
        result = tool.run({"timezone": "Asia/Shanghai"})
        assert result.ok
        assert result.output == "2026-11-06 20:00:00"

    def test_default_timezone(self) -> None:
        result = ClockTool().run({})
        assert result.ok
        assert len(result.output) == 19  # YYYY-MM-DD HH:MM:SS

    def test_unknown_timezone(self) -> None:
        result = ClockTool().run({"timezone": "Mars/Base"})
        assert not result.ok
        assert "未知时区" in (result.error or "")


class TestSearch:
    def test_hit(self) -> None:
        result = SearchTool().run({"query": "onnx"})
        assert result.ok
        assert "onnx" in result.output

    def test_miss_returns_message(self) -> None:
        result = SearchTool().run({"query": "不存在的关键词xyz"})
        assert result.ok
        assert result.output == "未命中相关条目"

    def test_empty_query(self) -> None:
        assert not SearchTool().run({"query": "  "}).ok


class TestMemo:
    def test_write_then_read(self, tmp_path) -> None:
        tool = MemoTool(path=tmp_path / "memo.json")
        write_result = tool.run({"action": "write", "key": "product", "value": "6408"})
        assert write_result.ok
        assert write_result.output == {"product": "6408"}

        read_result = tool.run({"action": "read", "key": "product"})
        assert read_result.ok
        assert read_result.output == "6408"

    def test_read_all(self, tmp_path) -> None:
        tool = MemoTool(path=tmp_path / "memo.json")
        tool.run({"action": "write", "key": "a", "value": "1"})
        tool.run({"action": "write", "key": "b", "value": "2"})
        assert tool.run({"action": "read"}).output == {"a": "1", "b": "2"}

    def test_read_missing_key(self, tmp_path) -> None:
        tool = MemoTool(path=tmp_path / "memo.json")
        assert not tool.run({"action": "read", "key": "none"}).ok

    def test_write_requires_value(self, tmp_path) -> None:
        tool = MemoTool(path=tmp_path / "memo.json")
        assert not tool.run({"action": "write", "key": "k"}).ok

    def test_invalid_action(self, tmp_path) -> None:
        tool = MemoTool(path=tmp_path / "memo.json")
        assert not tool.run({"action": "delete"}).ok
