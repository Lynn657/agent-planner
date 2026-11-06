"""执行器测试: 成功执行、未知工具、失败重试次数。"""

from __future__ import annotations

from agent_planner.executor import Executor
from agent_planner.planner import TaskSpec
from agent_planner.tools import build_default_registry


def build_executor(tmp_path, max_attempts: int = 2) -> Executor:
    registry = build_default_registry(memo_path=tmp_path / "memo.json")
    return Executor(registry, max_attempts=max_attempts)


def test_execute_success(tmp_path) -> None:
    record = build_executor(tmp_path).execute(
        TaskSpec(tool="calculator", args={"expression": "2+2"}), 1
    )
    assert record.ok
    assert record.output == 4
    assert record.index == 1
    assert record.attempts == 1


def test_execute_unknown_tool(tmp_path) -> None:
    record = build_executor(tmp_path).execute(
        TaskSpec(tool="no_such_tool", args={}), 2
    )
    assert not record.ok
    assert "未注册的工具" in (record.error or "")
    # 未知工具不重试
    assert record.attempts == 1


def test_execute_retries_until_exhausted(tmp_path) -> None:
    executor = build_executor(tmp_path, max_attempts=3)
    record = executor.execute(TaskSpec(tool="clock", args={"timezone": "Invalid/Zone"}), 1)
    assert not record.ok
    assert record.attempts == 3


def test_execute_bad_args(tmp_path) -> None:
    record = build_executor(tmp_path).execute(
        TaskSpec(tool="calculator", args={"wrong_key": "1+1"}), 1
    )
    assert not record.ok


def test_execute_memo_write(tmp_path) -> None:
    executor = build_executor(tmp_path)
    record = executor.execute(
        TaskSpec(tool="memo", args={"action": "write", "key": "k", "value": "v"}), 1
    )
    assert record.ok
    assert record.output == {"k": "v"}
