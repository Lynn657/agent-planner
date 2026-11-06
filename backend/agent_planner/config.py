"""运行配置: 全部通过环境变量注入, 不在代码里硬编码密钥。

兼容两种配置方式:
1. 系统环境变量(Windows: setx / PowerShell $env:);
2. 项目根目录下的 .env 文件(推荐), 由 python-dotenv 自动加载。

字段见 .env.example:
    LLM_API_BASE  OpenAI 兼容接口地址, 如 https://api.deepseek.com/v1
    LLM_API_KEY   接口密钥
    LLM_MODEL     模型名称
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# 自动加载 .env: 若未安装 python-dotenv 则退化为纯环境变量
try:
    from dotenv import load_dotenv

    _ENV_CANDIDATES = [
        Path(__file__).resolve().parent.parent / ".env",  # 项目根目录
        Path.cwd() / ".env",  # 当前工作目录
    ]
    for _candidate in _ENV_CANDIDATES:
        if _candidate.exists():
            load_dotenv(_candidate)
            break
except ImportError:  # pragma: no cover - 仅在未安装 dotenv 时触发
    pass


@dataclass(frozen=True)
class Settings:
    """LLM 接入配置。"""

    api_base: str
    api_key: str
    model: str
    timeout: float = 60.0

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量读取配置, 缺失时给出明确提示而不是静默失败。"""
        api_base = os.getenv("LLM_API_BASE", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()

        try:
            timeout = float(os.getenv("LLM_TIMEOUT", "60"))
        except ValueError:
            timeout = 60.0

        missing = [
            name
            for name, value in (
                ("LLM_API_BASE", api_base),
                ("LLM_API_KEY", api_key),
                ("LLM_MODEL", model),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "缺少环境变量: "
                + ", ".join(missing)
                + "。请复制 .env.example 为 .env 并填写后重启服务。"
            )
        return cls(api_base=api_base, api_key=api_key, model=model, timeout=timeout)
