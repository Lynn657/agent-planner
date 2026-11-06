"""备忘工具: 把中间结果写入本地 JSON 文件, 实现最简单的跨步骤/跨会话记忆。

存储格式:
    {"k1": "v1", "k2": "v2"}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent_planner.tools.base import BaseTool, ToolResult


class MemoArgs(BaseModel):
    """备忘操作入参。"""

    action: Literal["write", "read"] = Field(description="write 写入, read 读取")
    key: Optional[str] = Field(default=None, description="备忘键; read 时留空表示读取全部")
    value: Optional[str] = Field(default=None, description="写入的内容, write 时必填")


class MemoStore:
    """极简 JSON 备忘存储。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"备忘文件损坏: {self.path}") from exc
        if not isinstance(data, dict):
            raise ValueError("备忘文件结构不是对象")
        return {str(k): str(v) for k, v in data.items()}

    def _dump(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def write(self, key: str, value: str) -> dict[str, str]:
        data = self._load()
        data[key] = value
        self._dump(data)
        return data

    def read(self, key: str | None = None) -> dict[str, str] | str | None:
        data = self._load()
        return data if key is None else data.get(key)


class MemoTool(BaseTool):
    """本地备忘读写工具。"""

    name = "memo"
    description = "读写本地备忘录(JSON 文件), 用于保存计算或检索的中间结果"
    args_model = MemoArgs

    def __init__(self, path: str | Path = "memo.json") -> None:
        self.store = MemoStore(path)

    def execute(self, args: BaseModel) -> ToolResult:
        assert isinstance(args, MemoArgs)
        if args.action == "write":
            if not args.key or args.value is None:
                return ToolResult(
                    tool=self.name, ok=False, error="写入操作需要 key 与 value"
                )
            data = self.store.write(args.key, args.value)
            return ToolResult(tool=self.name, ok=True, output=data)

        result = self.store.read(args.key or None)
        if result is None:
            return ToolResult(
                tool=self.name, ok=False, error=f"未找到备忘键: {args.key}"
            )
        return ToolResult(tool=self.name, ok=True, output=result)
