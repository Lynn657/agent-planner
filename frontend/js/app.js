/**
 * 任务规划 Agent · 前端交互逻辑
 * 与后端通过 REST 通信，接口契约：
 *   GET  /health          -> {status:"ok"}
 *   GET  /api/tools        -> [{name, description, parameters}]
 *   POST /api/agent/run    -> {query, plan, steps, answer, success}
 */
(function () {
  "use strict";

  // 后端地址：同源部署留空；本地直接双击打开 HTML 时指向本机 Flask
  var API_BASE = (
    window.AGENT_API_BASE ||
    (location.protocol === "file:" ? "http://127.0.0.1:8000" : "")
  ).replace(/\/$/, "");

  var HISTORY_KEY = "agent-planner-runs";
  var HISTORY_LIMIT = 12;

  var el = {
    statusPill: document.getElementById("statusPill"),
    queryInput: document.getElementById("queryInput"),
    sendBtn: document.getElementById("sendBtn"),
    fillSample: document.getElementById("fillSample"),
    clearBtn: document.getElementById("clearBtn"),
    sampleGrid: document.getElementById("sampleGrid"),
    resultWrap: document.getElementById("resultWrap"),
    timeline: document.getElementById("timeline"),
    stepSummary: document.getElementById("stepSummary"),
    answerText: document.getElementById("answerText"),
    toolGrid: document.getElementById("toolGrid"),
    historyList: document.getElementById("historyList"),
    tabSwitch: document.getElementById("tabSwitch"),
    sideNav: document.getElementById("sideNav")
  };

  /* ---------------- 示例任务 ---------------- */
  var SAMPLES = [
    {
      icon: "∑",
      title: "算数并写入备忘",
      desc: "先计算 356×18，再把结果保存到备忘",
      query: "帮我算 356*18，把结果记到备忘里，键名用 product",
      grad: "linear-gradient(135deg,#eaf2fe,#d8e7fd)"
    },
    {
      icon: "◷",
      title: "查询当前时间",
      desc: "查询上海时区当前时间",
      query: "现在几点了？",
      grad: "linear-gradient(135deg,#e7f8f4,#d4f1ea)"
    },
    {
      icon: "⌕",
      title: "本地知识检索",
      desc: "检索 Agent、ONNX 等概念解释",
      query: "帮我查一下 agent 和 onnx 分别是什么",
      grad: "linear-gradient(135deg,#f2edfe,#e3dafb)"
    },
    {
      icon: "◈",
      title: "组合任务",
      desc: "查时间 + 检索概念，一并写入备忘",
      query: "现在几点？顺便查一下 rag 是什么，把时间和解释都记到备忘里",
      grad: "linear-gradient(135deg,#fff2e8,#ffe4d2)"
    }
  ];

  /* ---------------- 小工具 ---------------- */
  function toast(message) {
    var node = document.createElement("div");
    node.className = "toast";
    node.textContent = message;
    document.body.appendChild(node);
    requestAnimationFrame(function () {
      node.classList.add("show");
    });
    setTimeout(function () {
      node.classList.remove("show");
      setTimeout(function () {
        node.remove();
      }, 300);
    }, 2600);
  }

  function setStatus(text, tone) {
    if (!el.statusPill) return;
    el.statusPill.className = "status-pill" + (tone ? " " + tone : "");
    el.statusPill.innerHTML = "<i></i>" + text;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ---------------- 面板切换 ---------------- */
  function switchPanel(name) {
    document.querySelectorAll(".panel").forEach(function (panel) {
      panel.classList.toggle("active", panel.id === "panel-" + name);
    });
    document.querySelectorAll(".tab-pill").forEach(function (pill) {
      pill.classList.toggle("active", pill.dataset.panel === name);
    });
    document.querySelectorAll(".nav-item").forEach(function (item) {
      item.classList.toggle("active", item.dataset.panel === name);
    });
    if (name === "tools") loadTools();
    if (name === "history") renderHistory();
  }

  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-panel]");
    if (target) {
      switchPanel(target.dataset.panel);
    }
  });

  /* ---------------- 示例卡片 ---------------- */
  function renderSamples() {
    if (!el.sampleGrid) return;
    el.sampleGrid.innerHTML = SAMPLES.map(function (item, index) {
      return (
        '<button class="sample-card" data-sample="' + index + '">' +
        '<div class="sample-thumb" style="background:' + item.grad + '">' +
        '<span>' + item.icon + '</span>' +
        '<span style="font-size:11px;color:#6b7290">示例 ' + (index + 1) + "</span>" +
        "</div>" +
        '<div class="sample-body">' +
        "<strong>" + escapeHtml(item.title) + "</strong>" +
        "<span>" + escapeHtml(item.desc) + "</span>" +
        "</div>" +
        "</button>"
      );
    }).join("");

    el.sampleGrid.querySelectorAll(".sample-card").forEach(function (card) {
      card.addEventListener("click", function () {
        var item = SAMPLES[Number(card.dataset.sample)];
        el.queryInput.value = item.query;
        el.queryInput.focus();
        el.queryInput.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
  }

  /* ---------------- 工具体系 ---------------- */
  function describeType(schema) {
    if (!schema) return "any";
    if (schema.type) return schema.type;
    // Optional 字段在 JSON Schema 中表现为 anyOf: [{type:"string"}, {type:"null"}]
    if (Array.isArray(schema.anyOf)) {
      return schema.anyOf
        .map(function (item) {
          return item.type || "any";
        })
        .join("|");
    }
    return "any";
  }

  function loadTools() {
    if (!el.toolGrid) return;
    el.toolGrid.innerHTML = '<div class="empty-tip">正在读取后端工具列表…</div>';

    fetch(API_BASE + "/api/tools")
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function (tools) {
        if (!Array.isArray(tools) || tools.length === 0) {
          el.toolGrid.innerHTML = '<div class="empty-tip">后端未返回工具</div>';
          return;
        }
        el.toolGrid.innerHTML = tools.map(function (tool) {
          var props = (tool.parameters && tool.parameters.properties) || {};
          var paramText = Object.keys(props).length
            ? Object.keys(props)
                .map(function (key) {
                  return key + ": " + describeType(props[key]);
                })
                .join(" · ")
            : "无参数";
          return (
            '<div class="tool-card">' +
            "<code>" + escapeHtml(tool.name) + "</code>" +
            "<p>" + escapeHtml(tool.description || "") + "</p>" +
            '<div class="tool-params">' + escapeHtml(paramText) + "</div>" +
            "</div>"
          );
        }).join("");
      })
      .catch(function () {
        el.toolGrid.innerHTML =
          '<div class="empty-tip">无法连接后端：请先在 backend 目录运行 ' +
          "<code>flask --app app run --port 8000</code></div>";
      });
  }

  /* ---------------- 执行时间线 ---------------- */
  function renderSteps(steps) {
    if (!el.timeline) return;
    if (!steps || steps.length === 0) {
      el.timeline.innerHTML =
        '<div class="empty-tip">本次未调用工具，模型直接给出了答复</div>';
      return;
    }

    el.timeline.innerHTML = steps.map(function (step, index) {
      var cls = step.ok ? "" : " failed";
      var tagClass = step.ok ? (step.attempts > 1 ? " retry" : "") : " fail";
      var tagText = step.ok
        ? step.attempts > 1
          ? "重试 " + step.attempts + " 次后成功"
          : "成功"
        : "失败";
      var meta = "参数：" + escapeHtml(JSON.stringify(step.args || {}));
      var detail = step.ok
        ? formatOutput(step.output)
        : escapeHtml(step.error || "未知错误");

      return (
        '<div class="step-card' + cls + '" style="animation-delay:' + index * 40 + 'ms">' +
        '<div class="step-index">' + step.index + "</div>" +
        '<div class="step-body">' +
        '<div class="step-head">' +
        '<span class="step-tool">' + escapeHtml(step.tool) + "</span>" +
        '<span class="step-tag' + tagClass + '">' + tagText + "</span>" +
        "</div>" +
        '<div class="step-meta">' + meta + "</div>" +
        '<div class="step-output">' + detail + "</div>" +
        "</div>" +
        "</div>"
      );
    }).join("");
  }

  function formatOutput(output) {
    if (output === null || output === undefined) return "（无输出）";
    if (typeof output === "string") return escapeHtml(output);
    try {
      return escapeHtml(JSON.stringify(output, null, 2));
    } catch (err) {
      return escapeHtml(String(output));
    }
  }

  /* ---------------- 运行历史 ---------------- */
  function readHistory() {
    try {
      var raw = localStorage.getItem(HISTORY_KEY);
      var data = raw ? JSON.parse(raw) : [];
      return Array.isArray(data) ? data : [];
    } catch (err) {
      return [];
    }
  }

  function writeHistory(items) {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
    } catch (err) {
      /* 隐私模式下写入失败不阻断主流程 */
    }
  }

  function saveRun(result) {
    var items = readHistory();
    items.unshift({
      time: new Date().toLocaleString("zh-CN", { hour12: false }),
      query: result.query,
      answer: result.answer,
      success: Boolean(result.success),
      steps: (result.steps || []).length
    });
    writeHistory(items.slice(0, HISTORY_LIMIT));
  }

  function renderHistory() {
    if (!el.historyList) return;
    var items = readHistory();
    if (items.length === 0) {
      el.historyList.innerHTML =
        '<div class="empty-tip">还没有运行记录，先在「任务规划」里发一条任务吧</div>';
      return;
    }
    el.historyList.innerHTML = items.map(function (item) {
      return (
        '<div class="history-item">' +
        '<div class="h-top"><span>' + escapeHtml(item.time) + "</span>" +
        "<span>" + (item.success ? "成功" : "含失败步骤") + " · " + item.steps + " 步</span></div>" +
        '<div class="h-query">' + escapeHtml(item.query) + "</div>" +
        '<div class="h-answer">' + escapeHtml(item.answer) + "</div>" +
        "</div>"
      );
    }).join("");
  }

  /* ---------------- 发送任务 ---------------- */
  var sending = false;

  function setSending(flag) {
    sending = flag;
    if (!el.sendBtn) return;
    el.sendBtn.disabled = flag;
    el.sendBtn.textContent = flag ? "…" : "↑";
  }

  function submit() {
    if (sending) return;
    var query = (el.queryInput.value || "").trim();
    if (!query) {
      toast("请先描述你的任务");
      el.queryInput.focus();
      return;
    }

    setSending(true);
    setStatus("运行中", "");

    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, 90000);

    fetch(API_BASE + "/api/agent/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query }),
      signal: controller.signal
    })
      .then(function (resp) {
        return resp
          .json()
          .catch(function () {
            return {};
          })
          .then(function (body) {
            if (!resp.ok) {
              throw new Error(body.error || "请求失败（HTTP " + resp.status + "）");
            }
            return body;
          });
      })
      .then(function (result) {
        el.resultWrap.hidden = false;
        renderSteps(result.steps);
        el.answerText.textContent = result.answer || "（无答复）";

        var total = (result.steps || []).length;
        var failed = (result.steps || []).filter(function (step) {
          return !step.ok;
        }).length;
        el.stepSummary.textContent =
          "共 " + total + " 步" + (failed ? "，" + failed + " 步失败" : "，全部成功");

        el.answerText.parentElement.classList.toggle("failed-answer", failed > 0);
        saveRun(result);
        setStatus(result.success ? "运行完成" : "部分步骤失败", result.success ? "ok" : "bad");
      })
      .catch(function (error) {
        setStatus("调用失败", "bad");
        toast(
          error.name === "AbortError"
            ? "请求超时，请检查后端是否已启动"
            : "无法连接后端：" + error.message
        );
      })
      .finally(function () {
        clearTimeout(timer);
        setSending(false);
      });
  }

  /* ---------------- 健康检查 ---------------- */
  function checkHealth() {
    fetch(API_BASE + "/health")
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function () {
        setStatus("后端已连接", "ok");
      })
      .catch(function () {
        setStatus("后端未启动", "bad");
      });
  }

  /* ---------------- 事件绑定 ---------------- */
  function bind() {
    if (el.sendBtn) el.sendBtn.addEventListener("click", submit);

    if (el.queryInput) {
      el.queryInput.addEventListener("keydown", function (event) {
        if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
          event.preventDefault();
          submit();
        }
      });
    }

    if (el.clearBtn) {
      el.clearBtn.addEventListener("click", function () {
        el.queryInput.value = "";
        el.resultWrap.hidden = true;
        el.queryInput.focus();
      });
    }

    if (el.fillSample) {
      el.fillSample.addEventListener("click", function () {
        var item = SAMPLES[Math.floor(Math.random() * SAMPLES.length)];
        el.queryInput.value = item.query;
        el.queryInput.focus();
      });
    }

    if (el.tabSwitch) {
      el.tabSwitch.querySelectorAll(".tab-pill").forEach(function (pill) {
        pill.addEventListener("click", function () {
          switchPanel(pill.dataset.panel);
        });
      });
    }

    if (el.sideNav) {
      el.sideNav.querySelectorAll(".nav-item").forEach(function (item) {
        item.addEventListener("click", function () {
          switchPanel(item.dataset.panel);
        });
      });
    }
  }

  /* ---------------- 初始化 ---------------- */
  function init() {
    renderSamples();
    bind();
    checkHealth();
    renderHistory();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
