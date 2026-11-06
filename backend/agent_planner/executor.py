"""执行器: 逐个执行子任务, 负责工具查找、参数校验与失败重试。

失败处理策略:
1. 工具不存在 -> 直接记为失败, 不重试(重试也不会成功);
2. 参数校验失败/工具抛异常 -> 最多重试 max_attempts 次(应对偶发性问题);
3. 任何失败都写入 StepRecord 的 error 字段, 由上层决定是否继续后续步骤。
"""

from __future__ import annotations

from agent_planner.context import StepRecord
from agent_planner.planner import TaskSpec
from agent_planner.tools import ToolRegistry


class Executor:
    """子任务执行器。"""

    def __init__(self, registry: ToolRegistry, max_attempts: int = 2) -> None:
        self.registry = registry
        self.max_attempts = max(1, max_attempts)

    def execute(self, task: TaskSpec, index: int) -> StepRecord:
        """执行单个子任务并返回执行记录(不抛异常)。"""
        tool = self.registry.get(task.tool)
        if tool is None:
            return StepRecord(
                index=index,
                tool=task.tool,
                args=task.args,
                ok=False,
                error=f"未注册的工具: {task.tool}, 可用工具: {self.registry.names()}",
                attempts=1,
            )

        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            result = tool.run(task.args)
            if result.ok:
                return StepRecord(
                    index=index,
                    tool=task.tool,
                    args=task.args,
                    ok=True,
                    output=result.output,
                    attempts=attempt,
                )
            last_error = result.error

        return StepRecord(
            index=index,
            tool=task.tool,
            args=task.args,
            ok=False,
            error=last_error or "未知错误",
            attempts=self.max_attempts,
        )
