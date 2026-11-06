"""歧义输入测试: 模糊请求、空计划、幻觉工具名、参数缺失、部分失败。

对应用户简历中"覆盖正常任务、歧义输入、工具异常等场景"的第三条。
"""

from __future__ import annotations

import json

from agent_planner.agent import Agent
from agent_planner.llm import ScriptedLLM
from agent_planner.tools import build_default_registry


def build_agent(responses: list[str], tmp_path, **kwargs) -> Agent:
    registry = build_default_registry(memo_path=tmp_path / "memo.json")
    return Agent(llm=ScriptedLLM(responses), registry=registry, **kwargs)


EMPTY_PLAN = json.dumps({"tasks": []})


def test_vague_request_returns_clarify_hint(tmp_path) -> None:
    """模型判断无需工具时, 不能返回"未执行任何工具"这种无信息量的答复。"""
    result = build_agent([EMPTY_PLAN], tmp_path).run("帮我弄一下那个东西")

    assert result.steps == []
    assert "没有识别出需要调用工具" in result.answer
    assert result.success is True


def test_vague_request_does_not_call_summary_model(tmp_path) -> None:
    """空计划没有执行记录, 不应浪费一次汇总调用。"""
    llm = ScriptedLLM([EMPTY_PLAN])
    agent = Agent(llm=llm, registry=build_default_registry(memo_path=tmp_path / "memo.json"))
    agent.run("随便说点什么")

    assert len(llm.calls) == 1  # 只有规划这一次调用


def test_vague_mixed_language_request(tmp_path) -> None:
    """中英混杂 + 指代不明的输入, 同样走澄清分支而不是报错。"""
    result = build_agent([EMPTY_PLAN], tmp_path).run("那个 thing 你看着办吧 ok?")

    assert result.steps == []
    assert "请补充更具体的信息" in result.answer


def test_hallucinated_tool_name_fails_gracefully(tmp_path) -> None:
    """模型编造不存在的工具时, 记录失败但不崩溃、不中断整个任务。"""
    plan = json.dumps({"tasks": [{"tool": "search_web", "args": {"query": "agent"}}]})
    result = build_agent([plan, "没有可用的联网工具, 执行失败。"], tmp_path).run(
        "联网帮我搜一下 agent"
    )

    assert not result.success
    assert len(result.steps) == 1
    assert not result.steps[0].ok
    assert "未注册" in (result.steps[0].error or "")
    assert result.answer


def test_hallucinated_tool_does_not_block_next_step(tmp_path) -> None:
    """单个步骤失败后, 后续步骤仍应按计划继续执行。"""
    plan = json.dumps(
        {
            "tasks": [
                {"tool": "search_web", "args": {"query": "agent"}},
                {"tool": "calculator", "args": {"expression": "3+4"}},
            ]
        }
    )
    result = build_agent([plan, "第一步工具不存在, 第二步算出 7。"], tmp_path).run(
        "先联网搜, 再算 3+4"
    )

    assert len(result.steps) == 2
    assert result.steps[0].ok is False
    assert result.steps[1].ok is True
    assert result.steps[1].output == 7
    assert not result.success


def test_missing_argument_is_retried_then_marked_failed(tmp_path) -> None:
    """参数缺失属于可重试错误: 按 max_attempts 重试后记录失败。"""
    plan = json.dumps({"tasks": [{"tool": "calculator", "args": {}}]})
    result = build_agent([plan, "缺少表达式参数, 未能计算。"], tmp_path).run("帮我算一下")

    assert not result.success
    assert result.steps[0].attempts == 2
    assert not result.steps[0].ok


def test_ambiguous_request_with_steps_still_summarizes(tmp_path) -> None:
    """有可执行步骤时, 即使请求表述含糊, 也应给出基于执行记录的答复。"""
    plan = json.dumps({"tasks": [{"tool": "clock", "args": {}}]})
    result = build_agent([plan, "当前时间为 ...（按执行记录汇总）"], tmp_path).run(
        "现在啥时候了来着"
    )

    assert len(result.steps) == 1
    assert result.steps[0].ok
    assert result.answer == "当前时间为 ...（按执行记录汇总）"
