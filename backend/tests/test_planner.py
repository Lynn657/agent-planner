"""规划模块测试: JSON 提取、结构校验、失败重试与反馈提示。"""

from __future__ import annotations

import pytest

from agent_planner.errors import PlanParseError
from agent_planner.llm import ScriptedLLM
from agent_planner.planner import Planner, Plan, extract_json

TOOLS_DESC = '[{"name": "calculator", "description": "计算"}]'

VALID_PLAN = '{"tasks": [{"tool": "calculator", "args": {"expression": "1+1"}}]}'


def make_planner(responses: list[str], retries: int = 2) -> Planner:
    return Planner(ScriptedLLM(responses), TOOLS_DESC, max_retries=retries)


class TestExtractJson:
    def test_plain_json(self) -> None:
        assert extract_json(VALID_PLAN) == VALID_PLAN

    def test_markdown_fence(self) -> None:
        assert extract_json("```json\n" + VALID_PLAN + "\n```") == VALID_PLAN

    def test_noise_around_json(self) -> None:
        text = "好的，计划如下：\n" + VALID_PLAN + "\n希望对你有帮助。"
        assert extract_json(text) == VALID_PLAN

    def test_nested_object(self) -> None:
        payload = '{"tasks": [{"tool": "memo", "args": {"a": {"b": 1}}}]}'
        assert extract_json(payload) == payload

    def test_missing_json(self) -> None:
        with pytest.raises(ValueError):
            extract_json("完全不是 JSON")


class TestPlanner:
    def test_plan_valid(self) -> None:
        plan = make_planner([VALID_PLAN]).plan("1+1 等于多少")
        assert isinstance(plan, Plan)
        assert plan.tasks[0].tool == "calculator"
        assert plan.tasks[0].args == {"expression": "1+1"}

    def test_empty_tasks_allowed(self) -> None:
        plan = make_planner(['{"tasks": []}']).plan("你好")
        assert plan.tasks == []

    def test_retry_after_invalid_output(self) -> None:
        planner = make_planner(["这不是 JSON", VALID_PLAN])
        assert planner.plan("1+1").tasks[0].tool == "calculator"

    def test_retry_prompt_contains_feedback(self) -> None:
        llm = ScriptedLLM(["这不是 JSON", VALID_PLAN])
        Planner(llm, TOOLS_DESC, max_retries=2).plan("x")
        # 第二次调用的 user 消息里应带有上一轮的错误反馈
        assert "上一次输出存在问题" in llm.calls[1][-1]["content"]

    def test_retry_exhausted_raises(self) -> None:
        with pytest.raises(PlanParseError) as exc_info:
            make_planner(["坏输出", "还是坏输出"], retries=1).plan("x")
        assert "无法解析" in str(exc_info.value)
        assert exc_info.value.raw_output == "还是坏输出"

    def test_structurally_wrong_json_raises_after_retries(self) -> None:
        # 合法 JSON 但 tasks 不是数组, 校验失败后应重试并最终抛错
        with pytest.raises(PlanParseError):
            make_planner(['{"tasks": "not-a-list"}', '{"tasks": "still-wrong"}']).plan("x")

    def test_task_reason_optional(self) -> None:
        plan = make_planner([VALID_PLAN]).plan("1+1")
        assert plan.tasks[0].reason is None
