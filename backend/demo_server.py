"""离线演示服务器: 使用规则型假模型, 无需 API 密钥即可体验完整流程。

用途:
- 本地验收界面与执行时间线;
- 演示/录屏时避免真实模型调用费用;
- 网络不通或密钥未配置时的临时替代方案。

注意: 它不是生产实现, 计划由关键词规则生成, 仅为演示服务。

启动:
    python demo_server.py
    # 浏览器打开 http://127.0.0.1:8000
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_planner.agent import Agent
from agent_planner.llm import BaseLLM
from agent_planner.tools import build_default_registry
from agent_planner.tools.calculator import safe_eval
from app import create_app

_BASE_DIR = Path(__file__).resolve().parent

_EXPR_PATTERN = re.compile(r"(\d+(?:\.\d+)?(?:\s*[+\-*/%]\s*\(?\s*\d+(?:\.\d+)?\)?)+)")
_KEY_PATTERN = re.compile(r"(?:键名|键)[^A-Za-z]{0,6}([A-Za-z_][\w-]*)")

_KEYWORDS = ("agent", "react", "onnx", "rag", "lntu")


class OfflineDemoLLM(BaseLLM):
    """关键词规则型假模型: 只用于本地演示。"""

    name = "OfflineDemoLLM"

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        system = messages[0]["content"]
        user_text = messages[-1]["content"]

        if "任务规划器" in system:
            return self._build_plan(user_text)
        return self._summarize(user_text)

    # ---- 规划 ----
    def _build_plan(self, text: str) -> str:
        tasks: list[dict[str, Any]] = []

        expression = self._extract_expression(text)
        if expression:
            tasks.append(
                {
                    "tool": "calculator",
                    "args": {"expression": expression},
                    "reason": "先完成算术计算",
                }
            )
            if self._asks_for_memo(text):
                tasks.append(
                    {
                        "tool": "memo",
                        "args": {
                            "action": "write",
                            "key": self._extract_key(text),
                            "value": self._eval_as_text(expression),
                        },
                        "reason": "把结果写入备忘",
                    }
                )
            return json.dumps({"tasks": tasks}, ensure_ascii=False)

        if "时间" in text or "几点" in text:
            tasks.append(
                {"tool": "clock", "args": {"timezone": "Asia/Shanghai"}, "reason": "查询当前时间"}
            )

        keyword = self._extract_keyword(text)
        if keyword:
            tasks.append(
                {"tool": "search", "args": {"query": keyword}, "reason": "检索概念解释"}
            )

        if self._asks_for_memo(text) and tasks:
            tasks.append(
                {
                    "tool": "memo",
                    "args": {
                        "action": "write",
                        "key": self._extract_key(text),
                        "value": "查询结果",
                    },
                    "reason": "写入备忘",
                }
            )

        return json.dumps({"tasks": tasks}, ensure_ascii=False)

    @staticmethod
    def _extract_expression(text: str) -> str | None:
        match = _EXPR_PATTERN.search(text)
        if not match:
            return None
        return match.group(1).replace(" ", "")

    @staticmethod
    def _extract_key(text: str) -> str:
        match = _KEY_PATTERN.search(text)
        if match:
            return match.group(1)
        return "result"

    @staticmethod
    def _asks_for_memo(text: str) -> bool:
        return "备忘" in text or "记到" in text or "记下" in text

    @staticmethod
    def _eval_as_text(expression: str) -> str:
        """演示用: 先算出结果再写入备忘, 让时间线数据看起来真实。"""
        try:
            value = safe_eval(expression)
        except Exception:
            return expression
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @staticmethod
    def _extract_keyword(text: str) -> str | None:
        lowered = text.lower()
        for keyword in _KEYWORDS:
            if keyword in lowered:
                return keyword
        return None

    # ---- 汇总 ----
    @staticmethod
    def _summarize(text: str) -> str:
        """从执行记录里抽取成功/失败行, 拼成一段答复。"""
        lines = text.split("执行记录:")[-1].split("请给出最终答复")[0].strip()
        if not lines:
            return "已完成。"

        ok_lines: list[str] = []
        fail_lines: list[str] = []
        for raw in lines.splitlines():
            raw = raw.strip()
            match = re.match(r"^\d+\.\s*([\w\-]+)\(", raw)
            tool = match.group(1) if match else "工具"
            if "-> 成功" in raw:
                value = raw.split("-> 成功")[-1].strip().lstrip(":：").strip()
                ok_lines.append(f"{tool} 返回 {value}")
            elif "-> 失败" in raw:
                value = raw.split("-> 失败")[-1].strip().lstrip(":：").strip()
                fail_lines.append(f"{tool} 失败（{value}）")

        parts: list[str] = []
        if ok_lines:
            parts.append("已完成：" + "；".join(ok_lines))
        if fail_lines:
            parts.append("失败：" + "；".join(fail_lines))
        return "。".join(parts) + "。" if parts else "已完成。"


def main() -> None:
    registry = build_default_registry(memo_path=_BASE_DIR / "memo.json")
    agent = Agent(llm=OfflineDemoLLM(), registry=registry)
    app = create_app(agent=agent)

    print("=" * 56)
    print(" 离线演示模式（无需 API 密钥）")
    print(" 打开: http://127.0.0.1:8000")
    print("=" * 56)
    app.run(host="127.0.0.1", port=8000, debug=False)


if __name__ == "__main__":
    main()
