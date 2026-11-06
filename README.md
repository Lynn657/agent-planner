# 任务规划 Agent · Agent Planner

[![CI](https://github.com/USERNAME/agent-planner/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/agent-planner/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-54%20passed-brightgreen)]()

基于大模型 API 的**多步骤任务规划 Agent**：把一句自然语言请求拆解成可执行的子任务序列，按序调用工具、维护上下文，最后汇总成自然语言答复。

前后端分离：后端 Flask 提供 REST 接口，前端为独立静态站点（无构建步骤），通过 CORS 跨域调用。

> 本项目是学习实践项目，重点在**工程可运行性与可测试性**：全部 54 个单元测试离线通过，不需要真实模型密钥、不产生 API 费用。

---

## 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [快速开始（Windows 优先）](#快速开始windows-优先)
- [配置说明](#配置说明)
- [REST 接口](#rest-接口)
- [运行测试](#运行测试)
- [项目结构](#项目结构)
- [设计说明](#设计说明)
- [常见问题](#常见问题)

---

## 功能特性

| 能力 | 说明 |
|---|---|
| 多步骤规划 | LLM 将复杂请求拆解为 `{tool, args, reason}` 子任务序列 |
| 工具调度 | Function-Calling 风格的 JSON Schema 工具描述，Pydantic 统一校验入参 |
| 上下文复用 | 逐步记录执行结果，支持跨步骤数据传递 |
| 容错重试 | 规划解析失败自动带错误反馈重试；工具失败按上限重试并记录 |
| 步数上限 | `max_steps` 防止模型规划出循环/超长任务 |
| 汇总降级 | 汇总调用失败时自动退回规则拼接，保证链路不中断 |
| 离线可测 | `ScriptedLLM` 假模型驱动全部测试，无需网络与密钥 |
| 前后端分离 | 前端纯静态（HTML/CSS/JS），可独立部署；后端统一开放 CORS |

内置工具：

| 工具 | 作用 | 参数 |
|---|---|---|
| `calculator` | 安全算术求值（AST 白名单，拒绝代码注入） | `expression` |
| `clock` | 查询指定时区时间 | `timezone` |
| `search` | 本地知识库关键词检索（不联网） | `query` |
| `memo` | 本地 JSON 备忘读写，实现跨步骤记忆 | `action` / `key` / `value` |

---

## 系统架构

```
┌───────────────────────────── 前端 (frontend/) ─────────────────────────────┐
│  index.html + css/style.css + js/app.js                                    │
│  侧边导航 / 任务输入卡片 / 执行时间线 / 工具体系 / 运行记录（localStorage）    │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │ fetch (JSON, CORS)
┌───────────────────────────────▼──────────────── backend/ ──────────────────┐
│  app.py  Flask 网关                                                         │
│    GET  /health      GET /api/tools      POST /api/agent/run               │
│                                                                             │
│  agent_planner/                                                             │
│    planner.py   自然语言 → 结构化计划（Few-Shot + 格式约束 + 重试）           │
│    executor.py  按序执行子任务（工具查找 / 参数校验 / 失败重试）              │
│    context.py   执行上下文（步骤记录、观察文本、结果复用）                     │
│    llm.py       BaseLLM 抽象 / OpenAI 兼容实现 / ScriptedLLM（测试）         │
│    tools/       calculator · clock · search · memo                          │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                     OpenAI 兼容接口（DeepSeek / 通义千问 / Moonshot …）
```

一次运行的完整链路：

```
用户请求
  → 规划：LLM 输出 {"tasks":[...]} → 提取 JSON → Pydantic 校验
  → 执行：逐个工具调用，失败按 max_attempts 重试
  → 观察：每步结果写入 ExecutionContext
  → 汇总：LLM 生成答复（失败则规则拼接兜底）
```

---

## 快速开始（Windows 优先）

### 方式一：一键启动（推荐）

1. 安装 **Python 3.9+**，安装时勾选 **Add Python to PATH**。
2. 双击项目根目录的 **`start.bat`**。
3. 脚本会自动：创建 `backend\.venv` → 用清华镜像装依赖 → 启动服务 → 打开浏览器。
4. 浏览器访问 **http://127.0.0.1:8000**（服务启动后自动弹出）。

停止服务：在命令行窗口按 `Ctrl + C`。

### 方式二：手动命令（PowerShell / CMD）

```powershell
cd 项目目录\backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m flask --app app run --host 127.0.0.1 --port 8000
```

### macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m flask --app app run --host 127.0.0.1 --port 8000
```

> 未配置 `.env` 时：界面、工具体系、健康检查均可正常使用，但提交任务会返回 503 并提示缺少环境变量。

### 没有 API 密钥也能看完整效果

```powershell
cd backend
python demo_server.py
```

`demo_server.py` 使用规则型假模型（`OfflineDemoLLM`），无需密钥即可演示「规划 → 执行 → 时间线」全流程，适合本地验收与录屏。

---

## 配置说明

1. 复制 `.env.example` 为项目根目录下的 `.env`：

```powershell
copy .env.example .env
```

2. 填写三项（以 DeepSeek 为例）：

```ini
LLM_API_BASE=https://api.deepseek.com/v1
LLM_API_KEY=sk-你的密钥
LLM_MODEL=deepseek-chat
LLM_TIMEOUT=60
```

3. 重启服务生效。

> `.env` 已在 `.gitignore` 中排除，不会被提交。也可以用系统环境变量覆盖：
> PowerShell：`$env:LLM_API_KEY="sk-..."`；CMD：`set LLM_API_KEY=sk-...`。

---

## REST 接口

### `GET /health`

```json
{"status": "ok"}
```

### `GET /api/tools`

返回工具清单（Function-Calling 风格）：

```json
[
  {
    "name": "calculator",
    "description": "计算数学表达式, 支持加、减、乘、除、取余、整除与括号",
    "parameters": {"properties": {"expression": {"title": "expression", "type": "string"}}, "required": ["expression"], "type": "object"}
  }
]
```

### `POST /api/agent/run`

请求：

```json
{"query": "帮我算 356*18，把结果记到备忘里，键名用 product"}
```

响应：

```json
{
  "query": "帮我算 356*18，把结果记到备忘里，键名用 product",
  "plan": {"tasks": [{"tool": "calculator", "args": {"expression": "356*18"}, "reason": "先算乘积"}]},
  "steps": [
    {"index": 1, "tool": "calculator", "args": {"expression": "356*18"}, "ok": true, "output": 6408, "error": null, "attempts": 1}
  ],
  "answer": "356×18 的结果是 6408，已写入备忘（键名 product）。",
  "success": true
}
```

错误：`400`（query 缺失/为空）、`503`（未配置 LLM 环境变量）。

PowerShell 调用示例：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/agent/run -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"query":"现在几点了？"}'
```

---

## 运行测试

```powershell
cd backend
.\.venv\Scripts\activate
pip install -r requirements-dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pytest -v
```

或双击根目录 **`run-tests.bat`**。

```
54 passed in 0.67s
```

测试覆盖：工具参数校验与安全边界、JSON 提取与重试、执行器重试次数、Agent 多步骤/部分失败/步数截断、REST 接口与 CORS、静态页面托管。

CI（GitHub Actions）在 Python 3.9 / 3.10 / 3.12 三个版本上跑同一套测试。

---

## 项目结构

```
agent-planner/
├── frontend/                   # 前端（纯静态，可独立部署）
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── backend/
│   ├── app.py                  # Flask 网关（REST + 静态托管 + CORS）
│   ├── demo_server.py          # 离线演示服务器（无需密钥）
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml          # pytest 配置
│   ├── agent_planner/
│   │   ├── agent.py            # 主循环：规划→执行→观察→汇总
│   │   ├── planner.py          # 提示词构建、JSON 提取、重试
│   │   ├── executor.py         # 工具调度与重试
│   │   ├── context.py          # 执行上下文
│   │   ├── llm.py              # BaseLLM / OpenAI 兼容 / ScriptedLLM
│   │   ├── config.py           # .env 与环境变量
│   │   ├── errors.py
│   │   └── tools/              # calculator / clock / search / memo
│   └── tests/                  # pytest（5 个测试文件）
├── .github/workflows/ci.yml
├── .env.example
├── start.bat                   # Windows 一键启动
├── run-tests.bat               # Windows 一键测试
├── LICENSE
└── README.md
```

---

## 设计说明

1. **为什么用 Pydantic 定义工具入参**：工具参数由模型生成，必须由代码侧做二次校验；`args_model` 同时用于生成 JSON Schema（喂给模型）和执行前校验，一份定义两处使用。
2. **为什么用 ScriptedLLM**：真实模型输出不稳定且产生费用，单元测试必须确定性；把 LLM 抽象成接口后，测试可注入脚本化实现。
3. **为什么规划失败要重试**：小模型常输出夹带解释文字或格式不稳定的 JSON；把错误信息作为反馈重新请求，比直接失败更贴近真实工程做法。
4. **为什么汇总要降级**：汇总结算失败不应让整条链路作废，规则拼接虽不优雅但保证可用性。
5. **为什么计算器不用 eval**：表达式来自模型输出，等同不可信输入；AST 白名单求值可避免任意代码执行。

---

## 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| 接口返回 503，提示缺少环境变量 | 没配置 `.env`；复制 `.env.example` 填写后重启 |
| Windows 下报 `ZoneInfoNotFoundError` | 缺少 `tzdata`；`pip install tzdata`（requirements 已按 win32 自动安装） |
| 端口 8000 被占用 | 换端口：`python -m flask --app app run --port 8001`，同时改前端 `API_BASE` 或直接访问新端口页面 |
| pip 安装很慢 | 使用 `-i https://pypi.tuna.tsinghua.edu.cn/simple`（start.bat 默认已带） |
| 中文显示乱码（CMD） | 已用 `chcp 65001`；若仍乱码，改用 Windows Terminal 或 PowerShell |
| 前端页面空白 | 确认后端已启动且通过 `http://127.0.0.1:8000` 访问（不是直接双击 HTML） |
| 模型输出无法解析 | 检查模型是否支持 JSON 输出；可换更强的模型或降低 temperature |

---

## Roadmap

- [ ] 支持多轮对话与长期记忆（会话级上下文持久化）
- [ ] 工具并行执行与依赖图调度
- [ ] 真实检索工具（替换本地模拟语料）
- [ ] 前端接入 SSE，流式展示执行过程
- [ ] 接入 LangGraph，对比原生实现与框架编排差异

---

## License

[MIT](LICENSE)
