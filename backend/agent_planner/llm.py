"""大模型客户端抽象与两种实现。

设计要点:
1. BaseLLM 把"调用模型"抽象成一个方法, 上层规划/汇总逻辑不关心具体厂商;
2. OpenAICompatibleLLM 走标准 /chat/completions 协议, 可对接 DeepSeek、通义千问等;
3. ScriptedLLM 按预置脚本返回固定文本, 让全部单元测试离线可跑(不产生真实请求与费用)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests


class BaseLLM(ABC):
    """大模型调用接口。"""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        """输入消息列表, 返回模型输出文本。

        Args:
            messages: OpenAI 格式的消息列表, 如 [{"role": "user", "content": "..."}]
            temperature: 采样温度, 规划场景建议 0 以保证输出稳定
        """


class OpenAICompatibleLLM(BaseLLM):
    """OpenAI 兼容协议实现 (DeepSeek / 通义千问 / Moonshot 等均可)。"""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        resp = requests.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # 接口返回结构与预期不符
            raise RuntimeError(f"模型返回结构异常: {data}") from exc


class ScriptedLLM(BaseLLM):
    """脚本化假模型: 按顺序返回预置文本, 用于单元测试与本地联调。

    Args:
        responses: 预置响应序列
        repeat_last: 序列用完后是否重复最后一条(默认 True, 避免测试因多调用报错)
    """

    def __init__(self, responses: list[str], repeat_last: bool = True) -> None:
        if not responses:
            raise ValueError("responses 不能为空")
        self._responses = list(responses)
        self._repeat_last = repeat_last
        self._index = 0
        # 记录每次调用输入, 供测试断言提示词内容
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.0) -> str:
        self.calls.append(messages)
        if self._index < len(self._responses):
            output = self._responses[self._index]
            self._index += 1
            return output
        if self._repeat_last:
            return self._responses[-1]
        raise RuntimeError("ScriptedLLM 响应已耗尽")
