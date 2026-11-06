"""Flask 后端网关: 提供 REST 接口, 并可直接托管前端静态页面。

前后端分离说明:
- 前端位于 ../frontend, 是纯静态站点(无构建步骤), 可独立部署;
- 后端统一开放 CORS, 前端也可部署到任意域名/端口调用本服务;
- 为方便本地调试, 后端同时把前端挂载在根路径, 启动一个服务即可访问界面。

接口:
    GET  /               前端页面(仅本地调试便利)
    GET  /health         健康检查
    GET  /api/tools      工具清单(Function-Calling 风格描述)
    POST /api/agent/run  提交任务: {"query": "..."}

启动(Windows / macOS / Linux 通用):
    cd backend
    python -m flask --app app run --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request, send_from_directory

from agent_planner.agent import Agent
from agent_planner.config import Settings
from agent_planner.llm import OpenAICompatibleLLM
from agent_planner.tools import build_default_registry

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
DEFAULT_MEMO_PATH = BASE_DIR / "memo.json"


def build_default_agent(memo_path: Path | str = DEFAULT_MEMO_PATH) -> Agent:
    """按环境变量构建真实 Agent(首次请求时才执行, 避免导入期读取密钥)。"""
    settings = Settings.from_env()
    llm = OpenAICompatibleLLM(
        api_base=settings.api_base,
        api_key=settings.api_key,
        model=settings.model,
        timeout=settings.timeout,
    )
    return Agent(llm=llm, registry=build_default_registry(memo_path=memo_path))


def create_app(agent: Optional[Agent] = None) -> Flask:
    """创建 Flask 应用。

    Args:
        agent: 可选注入的 Agent; 传入时不触发真实模型调用(便于测试与演示)
    """
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
    app.json.ensure_ascii = False  # 让 jsonify 返回中文而非 \uXXXX

    state: dict[str, Any] = {
        "agent": agent,
        "registry": agent.registry if agent is not None else None,
    }

    def get_agent() -> Agent:
        if state["agent"] is None:
            state["agent"] = build_default_agent()
        return state["agent"]

    def get_registry() -> Any:
        if state["registry"] is None:
            state["registry"] = build_default_registry()
        return state["registry"]

    @app.before_request
    def handle_preflight() -> Any:
        """浏览器跨域预检请求直接返回 204。"""
        if request.method == "OPTIONS":
            return ("", 204)
        return None

    @app.after_request
    def add_cors_headers(response: Any) -> Any:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.get("/")
    def index() -> Any:
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.get("/api/tools")
    def list_tools() -> Any:
        """返回全部工具的 Function-Calling 描述, 供前端展示与调试。"""
        specs = get_registry().specs()
        return jsonify([spec.model_dump(mode="json") for spec in specs])

    @app.post("/api/agent/run")
    def run_agent() -> Any:
        payload = request.get_json(silent=True) or {}
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "query 字段必填且为非空字符串"}), 400

        try:
            result = get_agent().run(query)
        except RuntimeError as exc:
            # 典型场景: 未配置 LLM 环境变量(见 .env.example)
            return jsonify({"error": str(exc)}), 503

        return jsonify(result.model_dump(mode="json"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
