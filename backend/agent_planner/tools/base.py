"""工具基类与工具注册表。

设计要点:
1. 每个工具声明一个 pydantic 入参模型(args_model), 由框架统一做参数校验;
2. 工具自动生成 Function-Calling 风格的 JSON Schema 描述, 直接拼进提示词;
3. 执行统一返回 ToolResult, 用 ok 字段标识成功/失败, 而不是靠异常穿透流程。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ToolResult(BaseModel):
    """工具执行结果。"""

    tool: str
    ok: bool
    output: Any = None
    error: str | None = None


class ToolSpec(BaseModel):
    """工具描述(供模型阅读), 结构对齐 Function-Calling 中的 function 定义。"""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """工具抽象基类。

    子类只需声明 name/description/args_model, 并实现 execute。
    """

    name: str
    description: str
    args_model: type[BaseModel]

    def spec(self) -> ToolSpec:
        """生成工具描述, 参数 Schema 由 pydantic 模型自动推导。"""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.args_model.model_json_schema(),
        )

    def run(self, raw_args: dict[str, Any]) -> ToolResult:
        """执行入口: 先校验入参, 再交由具体实现执行。"""
        try:
            args = self.args_model.model_validate(raw_args)
        except ValidationError as exc:
            return ToolResult(tool=self.name, ok=False, error=f"参数校验失败: {exc}")
        try:
            return self.execute(args)
        except Exception as exc:  # noqa: BLE001 - 工具内部异常统一转为失败结果
            return ToolResult(tool=self.name, ok=False, error=f"执行异常: {exc}")

    @abstractmethod
    def execute(self, args: BaseModel) -> ToolResult:
        """具体工具逻辑, 入参已通过校验。"""


class ToolRegistry:
    """工具注册表: 负责按名字查找工具、导出全部工具描述。"""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具名重复: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    def describe(self) -> str:
        """把工具描述序列化为 JSON 文本, 供提示词使用。"""
        import json

        return json.dumps(
            [spec.model_dump() for spec in self.specs()],
            ensure_ascii=False,
            indent=2,
        )

    def __len__(self) -> int:
        return len(self._tools)
