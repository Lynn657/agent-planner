"""工具包入口: 统一导出工具类与默认工具集构建函数。"""

from __future__ import annotations

from pathlib import Path

from agent_planner.tools.base import BaseTool, ToolRegistry, ToolResult, ToolSpec
from agent_planner.tools.calculator import CalculatorTool
from agent_planner.tools.clock import ClockTool
from agent_planner.tools.memo import MemoTool
from agent_planner.tools.search import SearchTool

__all__ = [
    "BaseTool",
    "CalculatorTool",
    "ClockTool",
    "MemoTool",
    "SearchTool",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "build_default_registry",
]


def build_default_registry(memo_path: str | Path = "memo.json") -> ToolRegistry:
    """构建内置工具集: 计算器、时间、检索、备忘。"""
    return ToolRegistry(
        [
            CalculatorTool(),
            ClockTool(),
            SearchTool(),
            MemoTool(path=memo_path),
        ]
    )
