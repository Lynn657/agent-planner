"""命令行演示: 不启动 Flask, 直接在终端跑 Agent（无需 API 密钥）。

用途:
- 快速验证规划/执行/汇总链路；
- 没有配置模型密钥时也能演示效果；
- 便于把每一步输出贴进技术笔记或答辩材料。

运行:
    cd backend
    python examples/run_offline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from agent_planner.agent import Agent  # noqa: E402
from agent_planner.tools import build_default_registry  # noqa: E402
from demo_server import OfflineDemoLLM  # noqa: E402

CASES = [
    ("多步骤组合", "帮我算 356*18，把结果记到备忘里，键名用 product"),
    ("单工具查询", "现在几点了？"),
    ("本地检索", "帮我查一下 onnx 是什么"),
    ("歧义输入", "那个东西你看着办吧"),
]


def print_result(title: str, query: str, result) -> None:
    print("=" * 70)
    print(f"[{title}] 请求: {query}")

    if result.plan and result.plan.tasks:
        print(f"计划 {len(result.plan.tasks)} 步:")
        for index, task in enumerate(result.plan.tasks, start=1):
            print(f"  {index}. {task.tool}  参数={task.args}  理由={task.reason or '-'}")
    elif result.plan is not None:
        print("计划: 未识别到需要调用工具的子任务")
    else:
        print("计划: 解析失败")

    if result.steps:
        print("执行:")
        for record in result.steps:
            status = "OK  " if record.ok else "FAIL"
            detail = record.output if record.ok else record.error
            print(f"  [{status}] {record.tool} ×{record.attempts}  -> {detail}")

    print(f"答复: {result.answer}")
    print(f"整体成功: {result.success}")


def main() -> None:
    registry = build_default_registry(memo_path=BACKEND_DIR / "memo.json")
    agent = Agent(llm=OfflineDemoLLM(), registry=registry)

    print("离线演示模式（规则型假模型，不调用真实 API）")
    for title, query in CASES:
        print_result(title, query, agent.run(query))
    print("=" * 70)


if __name__ == "__main__":
    main()
