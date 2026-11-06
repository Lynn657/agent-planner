# 前端说明（纯静态站点）

本目录是独立的前端，只有三个文件，**没有构建步骤、没有 npm 依赖**：

```
frontend/
├── index.html
├── css/style.css
└── js/app.js
```

## 本地调试

方式一（推荐）：直接访问后端，后端会托管本目录

```powershell
cd backend
python -m flask --app app run --port 8000
# 打开 http://127.0.0.1:8000
```

方式二：单独用静态服务器打开，后端在另一个端口

```powershell
cd frontend
python -m http.server 5500
# 打开 http://127.0.0.1:5500
# 此时页面会自动请求 http://127.0.0.1:8000（见下方 API_BASE 规则）
```

> 不建议直接双击 `index.html`（`file://` 协议）：浏览器会拦截跨域请求，
> 但代码已做了兜底，会自动把接口地址指向 `http://127.0.0.1:8000`。

## API 地址规则

`js/app.js` 顶部：

```js
var API_BASE = (
  window.AGENT_API_BASE ||
  (location.protocol === "file:" ? "http://127.0.0.1:8000" : "")
).replace(/\/$/, "");
```

| 场景 | 实际请求地址 |
|---|---|
| 由后端托管（同源） | `/health`、`/api/tools`、`/api/agent/run` |
| `file://` 直接打开 | `http://127.0.0.1:8000/...` |
| 部署到 GitHub Pages 等独立域名 | 需在 `index.html` 里注入 `window.AGENT_API_BASE = "https://你的后端域名"` |

## 独立部署

前端可直接托管到 GitHub Pages / Vercel / 对象存储静态站点。部署后需：

1. 在 `index.html` 的 `<head>` 里、`app.js` 加载之前加一行：

```html
<script>window.AGENT_API_BASE = "https://你的后端域名";</script>
```

2. 后端已统一开放 CORS（`Access-Control-Allow-Origin: *`），无需额外配置。

## 交互说明

- `Ctrl + Enter` / `⌘ + Enter` 发送任务
- 示例卡片点击后自动填入输入框
- 运行记录保存在浏览器 `localStorage`（key: `agent-planner-runs`，最多 12 条）
- 顶部胶囊实时反映后端连接状态（`/health`）
- 执行时间线中：绿=成功、黄=重试后成功、红=失败
