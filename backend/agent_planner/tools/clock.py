"""时间工具: 返回指定时区的当前时间。

支持注入时间提供函数, 便于测试固定时间而不依赖真实时钟。
"""

from __future__ import annotations

from datetime import datetime, tzinfo
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from agent_planner.tools.base import BaseTool, ToolResult


class ClockArgs(BaseModel):
    """时间查询入参。"""

    timezone: str = Field(default="Asia/Shanghai", description="IANA 时区名")


class ClockTool(BaseTool):
    """查询当前时间。"""

    name = "clock"
    description = "查询指定时区的当前日期与时间, 默认 Asia/Shanghai"
    args_model = ClockArgs

    def __init__(self, now_provider: Callable[[tzinfo], datetime] | None = None) -> None:
        # 默认取系统当前时间; 测试可传入固定时间
        self._now_provider = now_provider or (lambda tz: datetime.now(tz))

    def execute(self, args: BaseModel) -> ToolResult:
        assert isinstance(args, ClockArgs)
        try:
            tz = ZoneInfo(args.timezone)
        except ZoneInfoNotFoundError:
            return ToolResult(
                tool=self.name,
                ok=False,
                error=f"未知时区: {args.timezone}",
            )

        current = self._now_provider(tz)
        return ToolResult(
            tool=self.name,
            ok=True,
            output=current.strftime("%Y-%m-%d %H:%M:%S"),
        )
