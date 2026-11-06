"""统一异常定义。

Agent 运行过程中可能出现三类问题, 分别用不同异常区分, 便于上层按类型处理:
- 规划失败(模型输出无法解析成合法计划): PlanParseError
- 工具执行失败(参数错误/运行报错): ToolExecutionError
- 步骤数超限(疑似死循环): StepLimitExceeded
"""


class AgentError(Exception):
    """Agent 运行错误基类。"""


class PlanParseError(AgentError):
    """规划结果解析失败: 模型输出不是合法的结构化计划。"""

    def __init__(self, message: str, raw_output: str | None = None) -> None:
        super().__init__(message)
        # 保留模型原始输出, 便于日志排查与提示词迭代
        self.raw_output = raw_output


class ToolExecutionError(AgentError):
    """工具执行失败: 工具不存在、入参校验失败或执行过程抛出异常。"""

    def __init__(self, tool: str, message: str) -> None:
        super().__init__(f"[{tool}] {message}")
        self.tool = tool


class StepLimitExceeded(AgentError):
    """执行步骤数超过上限, 通常意味着规划出现循环或任务过于复杂。"""
