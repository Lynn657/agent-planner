"""REST 接口测试: 健康检查、工具清单、任务执行、参数校验、CORS、前端页面。"""

from __future__ import annotations

import json

import pytest

from agent_planner.agent import Agent
from agent_planner.llm import ScriptedLLM
from agent_planner.tools import build_default_registry
from app import create_app

PLAN = json.dumps(
    {
        "tasks": [
            {"tool": "calculator", "args": {"expression": "10+5"}},
            {"tool": "clock", "args": {}},
        ]
    }
)


@pytest.fixture()
def client(tmp_path):
    registry = build_default_registry(memo_path=tmp_path / "memo.json")
    agent = Agent(llm=ScriptedLLM([PLAN, "10 加 5 等于 15，当前时间已获取。"]), registry=registry)
    app = create_app(agent=agent)
    app.config.update(TESTING=True)
    return app.test_client()


def test_health(client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_list_tools(client) -> None:
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    payload = resp.get_json()
    names = {item["name"] for item in payload}
    assert names == {"calculator", "clock", "search", "memo"}
    # 每个工具都应带 Function-Calling 风格的参数 Schema
    assert all("parameters" in item for item in payload)


def test_run_agent_success(client) -> None:
    resp = client.post("/api/agent/run", json={"query": "算 10+5 并查时间"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["success"] is True
    assert len(payload["steps"]) == 2
    assert payload["answer"].startswith("10 加 5")


def test_run_agent_missing_query(client) -> None:
    resp = client.post("/api/agent/run", json={})
    assert resp.status_code == 400
    assert "query" in resp.get_json()["error"]


def test_run_agent_blank_query(client) -> None:
    resp = client.post("/api/agent/run", json={"query": "   "})
    assert resp.status_code == 400


def test_run_agent_invalid_json(client) -> None:
    resp = client.post("/api/agent/run", data="not-json", content_type="application/json")
    assert resp.status_code == 400


def test_cors_preflight(client) -> None:
    resp = client.options("/api/agent/run")
    assert resp.status_code == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_frontend_index_served(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["Content-Type"]
    assert "任务规划 Agent" in resp.get_data(as_text=True)


def test_static_css_served(client) -> None:
    resp = client.get("/css/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["Content-Type"]
