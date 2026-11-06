"""agent-planner: 基于大模型 API 的多步骤任务规划 Agent。

核心流程:
    用户输入 -> 规划模块(LLM 拆解子任务) -> 执行器(按序调用工具)
             -> 上下文累积观察 -> 汇总答案

模块划分:
    planner  规划模块, 把自然语言请求拆成结构化子任务序列
    executor 执行器, 调用工具并处理参数错误/失败重试
    context  上下文状态, 保存每一步执行结果, 供后续步骤复用
    tools    内置工具集(计算器/时间/模拟检索/备忘)
"""

from agent_planner.agent import Agent, AgentResult
from agent_planner.context import ExecutionContext, StepRecord
from agent_planner.errors import (
    AgentError,
    PlanParseError,
    StepLimitExceeded,
    ToolExecutionError,
)
from agent_planner.executor import Executor
from agent_planner.llm import BaseLLM, OpenAICompatibleLLM, ScriptedLLM
from agent_planner.planner import Plan, Planner, TaskSpec
from agent_planner.tools import build_default_registry

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentResult",
    "AgentError",
    "BaseLLM",
    "ExecutionContext",
    "Executor",
    "OpenAICompatibleLLM",
    "Plan",
    "PlanParseError",
    "Planner",
    "ScriptedLLM",
    "StepLimitExceeded",
    "StepRecord",
    "TaskSpec",
    "ToolExecutionError",
    "build_default_registry",
]
