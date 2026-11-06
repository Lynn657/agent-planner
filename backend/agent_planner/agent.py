"""Agent 主循环: 规划 -> 执行 -> 观察 -> 汇总。

与 ReAct 的对应关系:
- Reason: 规划模块把请求拆成带 reason 的子任务;
- Act: 执行器按序调用工具;
- Observe: 每一步结果写入 ExecutionContext, 作为后续步骤与汇总的依据。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from agent_planner.context import ExecutionContext, StepRecord
from agent_planner.errors import PlanParseError
from agent_planner.executor import Executor
from agent_planner.llm import BaseLLM
from agent_planner.planner import Plan, Planner
from agent_planner.tools import ToolRegistry

_SUMMARY_SYSTEM = (
    "你是结果汇总助手。根据用户请求和工具执行记录, 用简洁中文回答用户。\n"
    "要求: 1. 只陈述执行记录中真实存在的结果, 不要编造; "
    "2. 若有步骤失败, 在答案中如实说明失败原因; "
    "3. 不要输出 JSON。"
)


class AgentResult(BaseModel):
    """一次完整运行的返回结果。"""

    query: str = Field(description="用户原始请求")
    plan: Optional[Plan] = Field(default=None, description="规划结果, 规划失败时为 None")
    steps: list[StepRecord] = Field(default_factory=list, description="执行记录")
    answer: str = Field(description="给用户的最终答复")
    success: bool = Field(description="整体是否成功")


class Agent:
    """多步骤任务规划 Agent。"""

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry,
        max_steps: int = 8,
        max_parse_retries: int = 2,
        max_tool_attempts: int = 2,
        summarize: bool = True,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_steps = max(1, max_steps)
        self.planner = Planner(
            llm=llm,
            tools_description=registry.describe(),
            max_retries=max_parse_retries,
        )
        self.executor = Executor(registry, max_attempts=max_tool_attempts)
        self.summarize = summarize

    def run(self, query: str) -> AgentResult:
        """处理一条用户请求。"""
        if not query or not query.strip():
            return AgentResult(query=query, answer="请求为空, 请提供具体任务", success=False)

        context = ExecutionContext(query=query)

        try:
            plan = self.planner.plan(query)
        except PlanParseError as exc:
            return AgentResult(
                query=query,
                plan=None,
                steps=[],
                answer=f"任务规划失败, 请换个说法重试。原因: {exc}",
                success=False,
            )

        # 步骤上限用于防止模型规划出超长/循环任务
        scheduled = plan.tasks[: self.max_steps]
        for index, task in enumerate(scheduled, start=1):
            record = self.executor.execute(task, index)
            context.add_step(record)

        answer = (
            self._summarize_answer(query, context)
            if self.summarize and context.steps
            else self._fallback_answer(context)
        )

        success = context.all_succeeded() if context.steps else True
        return AgentResult(
            query=query,
            plan=plan,
            steps=context.steps,
            answer=answer,
            success=success,
        )

    def _summarize_answer(self, query: str, context: ExecutionContext) -> str:
        """调用模型把执行记录汇总成自然语言。模型异常时降级为规则拼接。"""
        messages = [
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"用户请求: {query}\n\n"
                    f"执行记录:\n{context.to_observations()}\n\n"
                    "请给出最终答复。"
                ),
            },
        ]
        try:
            text = self.llm.chat(messages).strip()
        except Exception:  # noqa: BLE001 - 汇总失败不应影响整条链路
            return self._fallback_answer(context)
        if "```" in text:
            text = text.replace("```", "").strip()
        return text or self._fallback_answer(context)

    @staticmethod
    def _fallback_answer(context: ExecutionContext) -> str:
        """不依赖模型的结果整理, 保证链路可用。"""
        if not context.steps:
            return "未执行任何工具。"
        parts: list[str] = []
        for record in context.steps:
            if record.ok:
                parts.append(f"{record.tool}: {record.output}")
            else:
                parts.append(f"{record.tool} 执行失败: {record.error}")
        return "；".join(parts)
