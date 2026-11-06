"""Agent 端到端测试(离线): 多步骤执行、部分失败、规划失败、步数上限。"""

from __future__ import annotations

import json

import pytest

from agent_planner.agent import Agent
from agent_planner.llm import ScriptedLLM
from agent_planner.tools import build_default_registry


def build_agent(responses: list[str], tmp_path, **kwargs) -> Agent:
    registry = build_default_registry(memo_path=tmp_path / "memo.json")
    return Agent(llm=ScriptedLLM(responses), registry=registry, **kwargs)


TWO_STEP_PLAN = json.dumps(
    {
        "tasks": [
            {"tool": "calculator", "args": {"expression": "356*18"}, "reason": "算乘积"},
            {
                "tool": "memo",
                "args": {"action": "write", "key": "product", "value": "6408"},
                "reason": "写入备忘",
            },
        ]
    },
    ensure_ascii=False,
)


def test_multi_step_run(tmp_path) -> None:
    agent = build_agent([TWO_STEP_PLAN, "结果是 6408，已写入备忘。"], tmp_path)
    result = agent.run("帮我算 356*18 并记到备忘")

    assert result.success
    assert result.answer == "结果是 6408，已写入备忘。"
    assert [step.tool for step in result.steps] == ["calculator", "memo"]
    assert result.steps[0].output == 6408
    assert (tmp_path / "memo.json").exists()


def test_partial_failure_marks_unsuccessful(tmp_path) -> None:
    plan = json.dumps(
        {
            "tasks": [
                {"tool": "calculator", "args": {"expression": "open('x')"}},
                {"tool": "clock", "args": {}},
            ]
        }
    )
    agent = build_agent([plan, "第一步失败，第二步成功。"], tmp_path)
    result = agent.run("组合任务")

    assert not result.success
    assert result.steps[0].ok is False
    assert result.steps[1].ok is True


def test_plan_parse_failure_returns_friendly_answer(tmp_path) -> None:
    agent = build_agent(["无法解析的输出", "还是无法解析"], tmp_path)
    result = agent.run("随便说说")

    assert not result.success
    assert result.plan is None
    assert "任务规划失败" in result.answer
    assert result.steps == []


def test_max_steps_truncates(tmp_path) -> None:
    plan = json.dumps(
        {"tasks": [{"tool": "clock", "args": {}} for _ in range(5)]}
    )
    agent = build_agent([plan, "只执行了前两步。"], tmp_path, max_steps=2)
    result = agent.run("重复查时间")

    assert len(result.steps) == 2
    assert len(result.plan.tasks) == 5


def test_empty_query_rejected(tmp_path) -> None:
    agent = build_agent(['{"tasks": []}'], tmp_path)
    result = agent.run("   ")
    assert not result.success
    assert "请求为空" in result.answer


@pytest.mark.parametrize("summarize", [True, False])
def test_answer_with_or_without_summarize(tmp_path, summarize: bool) -> None:
    agent = build_agent([TWO_STEP_PLAN, "汇总答案"], tmp_path, summarize=summarize)
    result = agent.run("算并记录")

    if summarize:
        assert result.answer == "汇总答案"
    else:
        # 关闭汇总时走规则拼接, 应包含工具名与结果
        assert "calculator" in result.answer
        assert "6408" in result.answer


def test_no_tools_plan(tmp_path) -> None:
    agent = build_agent(['{"tasks": []}'], tmp_path)
    result = agent.run("你好")
    assert result.steps == []
    assert result.success
