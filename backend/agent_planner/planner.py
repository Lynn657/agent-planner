"""规划模块: 把自然语言请求拆解为结构化子任务序列。

提示词策略(Few-Shot + 格式强约束):
1. system 提示词说明角色、可用工具与输出格式;
2. 附带一组"输入 -> 计划"的示例, 提升小模型输出稳定性;
3. 解析失败时把错误信息作为反馈重新请求, 而不是直接抛给用户。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from agent_planner.errors import PlanParseError
from agent_planner.llm import BaseLLM

_JSON_ONLY_HINT = (
    "只输出一个 JSON 对象, 不要输出解释文字、不要使用 Markdown 代码块。"
    '格式: {"tasks": [{"tool": "工具名", "args": {"参数名": "参数值"}, "reason": "为什么需要这一步"}]}'
    "。若无需调用任何工具, 返回 {\"tasks\": []}。"
)

_FEW_SHOT = [
    {
        "role": "user",
        "content": "帮我算 356*18, 然后把结果记到备忘里, 键名用 product",
    },
    {
        "role": "assistant",
        "content": (
            '{"tasks": ['
            '{"tool": "calculator", "args": {"expression": "356*18"}, "reason": "先算出乘积"},'
            '{"tool": "memo", "args": {"action": "write", "key": "product", "value": "上一步的计算结果"},'
            ' "reason": "把结果写入备忘"}'
            "]}"
        ),
    },
    {
        "role": "user",
        "content": "现在几点了?",
    },
    {
        "role": "assistant",
        "content": (
            '{"tasks": [{"tool": "clock", "args": {"timezone": "Asia/Shanghai"},'
            ' "reason": "查询当前时间"}]}'
        ),
    },
]


class TaskSpec(BaseModel):
    """单个子任务。"""

    tool: str = Field(description="要调用的工具名")
    args: dict[str, Any] = Field(default_factory=dict, description="工具入参")
    reason: Optional[str] = Field(default=None, description="该步骤的理由, 便于排查规划质量")


class Plan(BaseModel):
    """一次规划结果。"""

    tasks: list[TaskSpec] = Field(default_factory=list, description="按执行顺序排列的子任务")


def extract_json(text: str) -> str:
    """从模型输出中提取第一个完整的 JSON 对象。

    兼容两类常见"脏输出":
    1. 被 ```json ... ``` 代码块包裹;
    2. JSON 前后夹带解释性文字。
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().endswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    if start == -1:
        raise ValueError("输出中未找到 JSON 对象")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : index + 1]
    raise ValueError("JSON 括号未闭合")


def build_plan_messages(
    query: str,
    tools_description: str,
    feedback: str | None = None,
) -> list[dict[str, str]]:
    """构造规划提示词。"""
    system = (
        "你是任务规划器, 负责把用户的复杂请求拆解成若干可执行的子任务。\n"
        f"可用工具及其参数 Schema:\n{tools_description}\n\n"
        "拆解要求:\n"
        "1. 按执行顺序排列, 后一步可以引用前一步的结果;\n"
        "2. 只使用上面列出的工具名, 参数名必须与 Schema 一致;\n"
        "3. 能一步完成就不要拆成两步, 不要编造工具。\n"
        + _JSON_ONLY_HINT
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(_FEW_SHOT)
    user_content = f"用户请求: {query}"
    if feedback:
        user_content += f"\n\n上一次输出存在问题: {feedback}\n请修正后重新输出合法 JSON。"
    messages.append({"role": "user", "content": user_content})
    return messages


class Planner:
    """规划器: 调模型 + 解析 + 失败重试。"""

    def __init__(
        self,
        llm: BaseLLM,
        tools_description: str,
        max_retries: int = 2,
    ) -> None:
        self.llm = llm
        self.tools_description = tools_description
        self.max_retries = max_retries

    def plan(self, query: str) -> Plan:
        """生成计划。

        Raises:
            PlanParseError: 重试耗尽仍无法得到合法的结构化计划
        """
        feedback: str | None = None
        last_raw: str | None = None

        for _ in range(self.max_retries + 1):
            messages = build_plan_messages(query, self.tools_description, feedback)
            raw = self.llm.chat(messages)
            last_raw = raw
            try:
                payload = json.loads(extract_json(raw))
                return Plan.model_validate(payload)
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                # 把解析错误转化成下一轮的修复提示
                feedback = str(exc)[:200]

        raise PlanParseError(
            f"规划失败: 已重试 {self.max_retries} 次仍无法解析模型输出", raw_output=last_raw
        )
