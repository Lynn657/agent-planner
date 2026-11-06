"""执行上下文: 保存用户原始请求与每一步的工具调用记录。

作用有三:
1. 让后续步骤能复用前面步骤的输出(跨步骤数据传递);
2. 作为汇总答案时喂给模型的"观察(Observation)";
3. 便于测试断言与日志排查。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class StepRecord(BaseModel):
    """单步执行记录。"""

    index: int = Field(description="步骤序号, 从 1 开始")
    tool: str = Field(description="工具名")
    args: dict[str, Any] = Field(default_factory=dict, description="工具入参")
    ok: bool = Field(description="是否执行成功")
    output: Any = Field(default=None, description="工具输出")
    error: Optional[str] = Field(default=None, description="失败原因")
    attempts: int = Field(default=1, description="实际尝试次数")


class ExecutionContext(BaseModel):
    """一次 Agent 运行的完整上下文。"""

    query: str = Field(description="用户原始请求")
    steps: list[StepRecord] = Field(default_factory=list, description="已执行的步骤")

    def add_step(self, record: StepRecord) -> None:
        """追加一步执行记录。"""
        self.steps.append(record)

    def last_output(self) -> Any:
        """最近一次成功步骤的输出, 供后续步骤引用。"""
        for record in reversed(self.steps):
            if record.ok:
                return record.output
        return None

    def to_observations(self) -> str:
        """把执行记录整理成纯文本观察, 用于拼接汇总提示词。"""
        if not self.steps:
            return "(无执行记录)"
        lines: list[str] = []
        for record in self.steps:
            if record.ok:
                lines.append(
                    f"{record.index}. {record.tool}({record.args}) -> 成功: {record.output}"
                )
            else:
                lines.append(
                    f"{record.index}. {record.tool}({record.args}) -> 失败: {record.error}"
                )
        return "\n".join(lines)

    def all_succeeded(self) -> bool:
        """全部步骤是否都成功。"""
        return bool(self.steps) and all(record.ok for record in self.steps)
