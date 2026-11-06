"""模拟检索工具: 在本地小语料库中做关键词匹配。

刻意不接入真实爬虫/外网接口:
1. 避免运行依赖网络与反爬策略, 保证 Demo 可复现;
2. 把"检索工具"作为 Agent 的一环打通, 便于后续替换为真实检索服务。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent_planner.tools.base import BaseTool, ToolResult

DEFAULT_CORPUS: dict[str, str] = {
    "agent": "Agent(智能体)指能感知输入、规划任务并调用工具完成目标的大模型应用形态。",
    "react": "ReAct 是 Reasoning + Acting 的范式: 模型交替进行推理与工具调用, 依据观察结果推进下一步。",
    "onnx": "ONNX 是开放的模型交换格式, 便于把 PyTorch 模型导出到不同推理引擎运行。",
    "rag": "RAG(检索增强生成)先检索外部知识再交给模型生成, 用于缓解模型幻觉与知识时效问题。",
    "lntu": "辽宁工程技术大学是一所以工科为主的高校, 软件工程专业侧重工程实践能力培养。",
}


class SearchArgs(BaseModel):
    """检索入参。"""

    query: str = Field(description="检索关键词, 例如 agent、onnx")


class SearchTool(BaseTool):
    """本地语料检索。"""

    name = "search"
    description = "在本地内置知识库中检索关键词解释(不联网), 返回匹配条目"
    args_model = SearchArgs

    def __init__(self, corpus: dict[str, str] | None = None) -> None:
        self._corpus = corpus or DEFAULT_CORPUS

    def execute(self, args: BaseModel) -> ToolResult:
        assert isinstance(args, SearchArgs)
        keyword = args.query.strip().lower()
        if not keyword:
            return ToolResult(tool=self.name, ok=False, error="检索关键词为空")

        hits = {
            key: value
            for key, value in self._corpus.items()
            if keyword in key.lower() or keyword in value.lower()
        }
        if not hits:
            return ToolResult(tool=self.name, ok=True, output="未命中相关条目")
        return ToolResult(tool=self.name, ok=True, output=hits)
