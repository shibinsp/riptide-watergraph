"use strict";
// Like Water Studio — enterprise vanilla-JS SPA over the riptide-watergraph FastAPI server.

let META = null;

// ---------- icons (inline SVG paths) ----------
const ICONS = {
  playground: "M5 3l14 9-14 9V3z",
  sessions: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z",
  tools: "M14.7 6.3a4 4 0 00-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 005.4-5.4l-2.5 2.5-2-2 2.5-2.5z",
  roles: "M16 11a4 4 0 10-8 0 4 4 0 008 0zM4 21a8 8 0 0116 0",
  eval: "M9 11l3 3 8-8M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
  costs: "M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  connections: "M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2a15 15 0 010 20 15 15 0 010-20z",
  sun: "M12 17a5 5 0 100-10 5 5 0 000 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  moon: "M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z",
  copy: "M9 9h10v10H9zM5 15H4V5h10v1",
};
function icon(name) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  const p = document.createElementNS(ns, "path");
  p.setAttribute("d", ICONS[name] || "");
  svg.appendChild(p);
  return svg;
}

// ---------- helpers ----------
async function api(path, opts) {
  const res = await fetch(path, opts);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error((data && data.detail) || res.statusText);
  return data;
}
const jpost = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n[k] = v;
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    n.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return n;
}
const view = () => document.getElementById("view");

function toast(msg, kind) {
  const t = el("div", { class: "toast " + (kind || "") }, msg);
  document.getElementById("toasts").appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 250); }, 3200);
}

function viewHead(title, sub) {
  return el("div", { class: "view-head" }, el("h1", null, title), sub ? el("p", null, sub) : null);
}
function copyPre(obj) {
  const text = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
  const btn = el("button", { class: "btn copy", onclick: () => {
    navigator.clipboard && navigator.clipboard.writeText(text); toast("Copied", "ok");
  } }, "Copy");
  return el("div", { class: "pre-wrap" }, btn, el("pre", null, text));
}
function switchEl(id, label, on) {
  return el("label", { class: "switch" },
    el("input", { type: "checkbox", id, ...(on ? { checked: "checked" } : {}) }),
    el("span", { class: "track" }), el("span", null, label));
}
function card(title, body, open = true) {
  const content = el("div", { class: "card-body" }, body);
  if (!open) content.style.display = "none";
  const chev = el("span", { class: "chev" }, open ? "▾" : "▸");
  const head = el("div", { class: "card-head" }, el("h2", null, title), chev);
  head.onclick = () => {
    const hidden = content.style.display === "none";
    content.style.display = hidden ? "" : "none"; chev.textContent = hidden ? "▾" : "▸";
  };
  return el("div", { class: "card" }, head, content);
}
function panel(body) { return el("div", { class: "card" }, el("div", { class: "card-pad" }, body)); }

// ---------- nav + router ----------
const NAV = [
  { group: "Workspace", items: [["playground", "Playground"], ["sessions", "Sessions"]] },
  { group: "Library", items: [["tools", "Tools"], ["roles", "Roles"]] },
  { group: "Insights", items: [["eval", "Eval"], ["costs", "Costs"]] },
  { group: "System", items: [["connections", "Connections"]] },
];
const VIEWS = {};
function buildNav() {
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  for (const g of NAV) {
    nav.appendChild(el("div", { class: "nav-group-label" }, g.group));
    for (const [id, label] of g.items) {
      nav.appendChild(el("button", { class: "nav-item", "data-view": id, onclick: () => show(id) },
        icon(id), label));
    }
  }
}
function show(name) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  view().innerHTML = "";
  (VIEWS[name] || VIEWS.playground)();
}

// ---------- connection status (top bar) ----------
function renderConnPill(conn) {
  const pill = document.getElementById("conn-pill");
  const label = document.getElementById("conn-pill-label");
  const live = conn && conn.configured;
  pill.classList.toggle("live", !!live);
  label.textContent = live ? (conn.provider + " · " + conn.model) : "Offline";
}

// =================== Playground ===================
VIEWS.playground = function () {
  const d = (META && META.defaults) || {};
  const connLive = META && META.connection && META.connection.configured;
  const task = el("textarea", { id: "pg-task", placeholder: "Describe a task — e.g. 'find and fix the bug in pkg/m.py' or 'search cats and count the words'" });
  const tenant = el("input", { type: "text", id: "pg-tenant", value: d.tenant_id || "default" });
  const schema = el("textarea", { id: "pg-schema", placeholder: '{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]}' });
  const schemaErr = el("div", { class: "banner bad", id: "pg-schema-err" }); schemaErr.style.display = "none";
  const out = el("div", { id: "pg-out", class: "stack" });
  const runBtn = el("button", { class: "btn primary", id: "pg-run" }, "Run task");

  const numField = (id, label, val) => el("div", { class: "field" }, el("label", { class: "lbl" }, label),
    el("input", { type: "number", id, class: "num", min: "1", value: String(val) }));

  runBtn.onclick = async () => {
    schemaErr.style.display = "none";
    let final_schema = null;
    if (schema.value.trim()) {
      try { final_schema = JSON.parse(schema.value); }
      catch (e) { schemaErr.textContent = "Invalid JSON schema: " + e.message; schemaErr.style.display = ""; return; }
    }
    const body = {
      task: task.value, tenant_id: tenant.value || "default",
      offline: document.getElementById("pg-offline").checked,
      single: document.getElementById("pg-single").checked,
      llm_composer: document.getElementById("pg-llm").checked,
      memory: document.getElementById("pg-memory").checked,
      guardrails: document.getElementById("pg-guard").checked,
      critic: document.getElementById("pg-critic").checked,
      supervisor: document.getElementById("pg-super").checked,
      react_steps: parseInt(document.getElementById("pg-react").value, 10) || 1,
      vote_k: parseInt(document.getElementById("pg-vote").value, 10) || 1,
      final_schema,
    };
    runBtn.disabled = true;
    out.innerHTML = "";
    out.appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
      el("span", { class: "spinner" }), "Running…")));
    try {
      const result = await jpost("/run", body);
      out.innerHTML = ""; out.appendChild(renderInspector(result));
    } catch (e) {
      out.innerHTML = ""; out.appendChild(panel(el("div", { class: "banner bad" }, "Run failed: " + e.message)));
      toast("Run failed", "bad");
    } finally { runBtn.disabled = false; }
  };

  view().append(
    viewHead("Playground", "Drive the graph and inspect every layer of the run."),
    el("div", { class: "stack" },
      panel(el("div", null,
        el("label", { class: "lbl" }, "Task"), task,
        el("div", { class: "row", style: "margin-top:14px" },
          el("div", { class: "field" }, el("label", { class: "lbl" }, "Tenant"), tenant),
          el("div", { class: "field" }, el("label", { class: "lbl" }, "Model"),
            el("div", null, el("span", { class: "badge accent" },
              connLive ? META.connection.model : ((META && META.current_model) || "?") + " (offline)")))),
        el("div", { class: "switches", style: "margin-top:16px" },
          switchEl("pg-offline", "Offline", !connLive),
          switchEl("pg-single", "Single agent", d.single),
          switchEl("pg-llm", "LLM composer", d.llm_composer),
          switchEl("pg-memory", "Memory", d.memory),
          switchEl("pg-guard", "Guardrails", d.guardrails),
          switchEl("pg-critic", "Critic", d.critic),
          switchEl("pg-super", "Supervisor", d.supervisor)),
        card("Advanced", el("div", null,
          el("div", { class: "row" }, numField("pg-react", "ReAct steps", d.react_steps || 1),
            numField("pg-vote", "Vote k", d.vote_k || 1)),
          el("div", { style: "margin-top:12px" },
            el("label", { class: "lbl" }, "Structured output schema (JSON Schema, optional)"),
            schema, schemaErr)), false),
        el("div", { class: "btn-row" }, runBtn))),
    out);
};

function zip(plan, roles) {
  const rows = plan.map((p, i) => el("tr", null, el("td", null, String(i)), el("td", null, p),
    el("td", null, el("span", { class: "chip" }, (roles && roles[i]) || "generalist"))));
  return el("table", null, el("tr", null, el("th", null, "#"), el("th", null, "Subtask"), el("th", null, "Role")), ...rows);
}
function renderInspector(r) {
  const wrap = el("div", { class: "stack" });
  wrap.appendChild(panel(el("div", null,
    el("div", { class: "kv" },
      el("span", { class: "badge accent" }, "mode: " + r.mode),
      el("span", { class: r.blocked ? "badge bad" : "badge ok" }, r.blocked ? "blocked" : "allowed"),
      r.success != null ? el("span", { class: r.success ? "badge ok" : "badge warn" }, r.success ? "success" : "needs work") : null,
      el("span", { class: "badge" }, "tools " + r.tool_calls_valid + "/" + r.tool_calls_total)),
    el("label", { class: "lbl" }, "Final answer"),
    el("div", null, r.final_answer || "(none)"))));

  if (r.plan && r.plan.length) wrap.appendChild(card("Plan & roles", zip(r.plan, r.roles)));
  if (r.swarm_decision && Object.keys(r.swarm_decision).length) wrap.appendChild(card("Swarm decision", copyPre(r.swarm_decision), false));
  if (r.results && r.results.length) {
    const items = r.results.map((res, i) => {
      const tc = (res.tool_calls || []).map((c) => {
        const fn = c.function || {};
        return el("tr", null, el("td", null, el("span", { class: "chip" }, fn.name || "?")),
          el("td", null, el("span", { class: "muted" }, fn.arguments || "")));
      });
      return el("div", { style: "margin-bottom:14px" },
        el("div", { class: "kv" }, el("span", { class: "chip" }, "#" + i), el("strong", null, res.subtask || "")),
        el("div", null, res.output || ""),
        tc.length ? el("table", { style: "margin-top:6px" }, el("tr", null, el("th", null, "Tool"), el("th", null, "Arguments")), ...tc) : null);
    });
    wrap.appendChild(card("Worker results", el("div", null, ...items)));
  }
  if (r.verdicts && r.verdicts.length) {
    const rows = r.verdicts.map((v, i) => el("tr", null, el("td", null, String(i)),
      el("td", null, el("span", { class: v.verdict === "pass" ? "badge ok" : "badge bad" }, v.verdict || "?")),
      el("td", null, v.reason || "")));
    wrap.appendChild(card("Critic verdicts", el("table", null,
      el("tr", null, el("th", null, "#"), el("th", null, "Verdict"), el("th", null, "Reason")), ...rows)));
  }
  if (r.structured) wrap.appendChild(card("Structured output", copyPre(r.structured)));
  if ((r.recalled_lessons || []).length || (r.stored_lessons || []).length) {
    const b = el("div");
    (r.recalled_lessons || []).forEach((l) => b.appendChild(el("div", null, "↩ " + l)));
    (r.stored_lessons || []).forEach((l) => b.appendChild(el("div", null, "✎ " + l)));
    wrap.appendChild(card("Memory & lessons", b, false));
  }
  if (r.metrics && Object.keys(r.metrics).length) wrap.appendChild(card("Metrics", copyPre(r.metrics), false));
  const gv = (r.guard_violations || []).concat(r.guard_violations_out || []);
  if (gv.length) wrap.appendChild(panel(el("div", null, el("label", { class: "lbl" }, "Guardrail violations"),
    el("div", { class: "banner bad" }, gv.join(", ")))));
  return wrap;
}

// =================== Connections ===================
VIEWS.connections = function () {
  let provider = (META && META.connection && META.connection.provider) || "offline";
  const models = (META && META.models) || [];
  const dl = el("datalist", { id: "model-list" }, ...models.map((m) => el("option", { value: m })));
  const modelInput = el("input", { type: "text", id: "cx-model", list: "model-list",
    value: (META && META.connection && META.connection.model) || "", placeholder: "e.g. gpt-4o-mini" });
  const keyInput = el("input", { type: "password", id: "cx-key", placeholder: "sk-… (stored in memory only)" });
  const baseInput = el("input", { type: "text", id: "cx-base", placeholder: "https://… (OpenAI-compatible endpoint)",
    value: (META && META.connection && META.connection.api_base) || "" });
  const status = el("div", { id: "cx-status" });
  const baseField = el("div", { class: "field", id: "cx-base-field" },
    el("label", { class: "lbl" }, "Base URL"), baseInput,
    el("div", { class: "hint" }, "Required for Custom (OpenAI-compatible: Azure, vLLM, Ollama, gateways)."));

  function applyProviderVisibility() {
    baseField.style.display = provider === "custom" ? "" : "none";
  }
  const seg = el("div", { class: "segmented" },
    ...[["openai", "OpenAI"], ["anthropic", "Anthropic"], ["custom", "Custom"], ["offline", "Offline"]]
      .map(([id, label]) => {
        const b = el("button", { class: provider === id ? "active" : "", onclick: () => {
          provider = id; seg.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
          b.classList.add("active"); applyProviderVisibility();
        } }, label);
        return b;
      }));

  function renderStatus(c) {
    status.innerHTML = "";
    const banner = c.configured
      ? el("div", { class: "banner ok" }, "Connected to " + c.provider + " · " + c.model +
          (c.key_masked ? "  ·  key " + c.key_masked : ""))
      : el("div", { class: "banner info" }, "Offline — runs use the deterministic DemoGateway (no API key needed).");
    status.appendChild(banner);
  }

  const showKey = el("button", { class: "btn", onclick: () => {
    keyInput.type = keyInput.type === "password" ? "text" : "password";
  } }, "Show");
  const saveBtn = el("button", { class: "btn primary" }, "Save connection");
  const testBtn = el("button", { class: "btn" }, "Test connection");

  function payload() {
    const p = { provider, model: modelInput.value.trim() };
    if (keyInput.value) p.api_key = keyInput.value;
    if (baseInput.value.trim()) p.api_base = baseInput.value.trim();
    return p;
  }
  saveBtn.onclick = async () => {
    saveBtn.disabled = true;
    try {
      const c = await jpost("/api/connection", payload());
      renderStatus(c); renderConnPill(c); if (META) META.connection = c;
      keyInput.value = ""; toast("Connection saved", "ok");
    } catch (e) { toast(e.message, "bad"); } finally { saveBtn.disabled = false; }
  };
  testBtn.onclick = async () => {
    testBtn.disabled = true; testBtn.textContent = "Testing…";
    try {
      const r = await jpost("/api/connection/test", payload());
      toast(r.ok ? ("Connection OK · " + r.model + " · " + r.latency_ms + "ms") : ("Test failed: " + r.detail),
        r.ok ? "ok" : "bad");
    } catch (e) { toast(e.message, "bad"); }
    finally { testBtn.disabled = false; testBtn.textContent = "Test connection"; }
  };

  applyProviderVisibility();
  view().append(
    viewHead("Connections", "Choose the AI provider and credentials used for live (non-offline) runs."),
    el("div", { class: "stack" },
      panel(el("div", null, status)),
      panel(el("div", null,
        el("label", { class: "lbl" }, "Provider"), seg,
        el("div", { class: "row", style: "margin-top:16px" },
          el("div", { class: "field" }, el("label", { class: "lbl" }, "Model"), modelInput, dl),
          el("div", { class: "field" }, el("label", { class: "lbl" }, "API key"),
            el("div", { style: "display:flex; gap:8px" }, keyInput, showKey),
            el("div", { class: "hint" }, "Held in server memory only — never written to disk; shown masked."))),
        el("div", { class: "row", style: "margin-top:14px" }, baseField),
        el("div", { class: "btn-row" }, saveBtn, testBtn))),
      el("div", { class: "hint", style: "max-width:980px" },
        "Security: these endpoints are unauthenticated and the server binds 127.0.0.1 by default. " +
        "Do not expose the Studio publicly. Code-execution tools (run_python/run_command/run_tests) are " +
        "off unless the server is started with RIPTIDE_ENABLE_EXEC=1.")));
  renderStatus((META && META.connection) || { configured: false });
};

// =================== Sessions ===================
VIEWS.sessions = function () {
  const sid = el("input", { type: "text", id: "s-id", value: "studio-1" });
  const msg = el("textarea", { id: "s-msg", placeholder: "Send a follow-up turn; prior answers are fed back as context." });
  const log = el("div", { id: "s-log", class: "stack" });
  const send = el("button", { class: "btn primary" }, "Send");
  const load = el("button", { class: "btn" }, "Load transcript");
  async function transcript() {
    log.innerHTML = "";
    const data = await api("/sessions/" + encodeURIComponent(sid.value));
    if (!data.turns.length) { log.appendChild(el("div", { class: "empty" }, "No turns yet.")); return; }
    data.turns.forEach((t, i) => log.appendChild(panel(el("div", null,
      el("div", { class: "kv" }, el("span", { class: "chip" }, "turn " + (i + 1))),
      el("div", null, el("strong", null, "You: "), t.task),
      el("div", null, el("strong", null, "Agent: "), t.answer || "(none)")))));
  }
  send.onclick = async () => {
    send.disabled = true;
    try { await jpost("/sessions/" + encodeURIComponent(sid.value) + "/messages", { task: msg.value, offline: true }); msg.value = ""; await transcript(); }
    catch (e) { toast(e.message, "bad"); } finally { send.disabled = false; }
  };
  load.onclick = transcript;
  view().append(viewHead("Sessions", "Multi-turn conversations — each turn sees prior answers."),
    el("div", { class: "stack" },
      panel(el("div", null,
        el("div", { class: "row" }, el("div", { class: "field" }, el("label", { class: "lbl" }, "Session id"), sid)),
        el("label", { class: "lbl", style: "margin-top:12px" }, "Message"), msg,
        el("div", { class: "btn-row" }, send, load))), log));
};

// =================== Tools ===================
VIEWS.tools = async function () {
  view().append(viewHead("Tools", "Registered tools the agents can call — including the agentic developer toolset."));
  const grid = el("div", { class: "grid" }); view().appendChild(grid);
  const tools = await api("/api/tools");
  tools.forEach((t) => grid.appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
    el("div", { class: "kv" }, el("strong", null, t.name), el("span", { class: "chip" }, "v" + t.version),
      el("span", { class: t.side_effecting ? "badge warn" : "badge ok" }, t.side_effecting ? "side-effecting" : "read-only")),
    el("div", { class: "muted" }, t.description),
    card("schema", copyPre(t.json_schema), false)))));
  view().appendChild(el("div", { class: "hint", style: "max-width:980px" },
    "File tools are confined to the workspace sandbox. run_python / run_command / run_tests appear only when the server runs with RIPTIDE_ENABLE_EXEC=1."));
};

// =================== Roles ===================
VIEWS.roles = async function () {
  view().append(viewHead("Roles", "Built-in specialist agents and their tool allow-lists."));
  const grid = el("div", { class: "grid" }); view().appendChild(grid);
  const roles = await api("/api/roles");
  roles.forEach((r) => {
    const chips = r.tools == null ? [el("span", { class: "chip" }, "all tools")] : r.tools.map((t) => el("span", { class: "chip" }, t));
    grid.appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
      el("div", { class: "kv" }, el("strong", null, r.name)),
      el("div", { class: "pills" }, ...chips),
      el("div", { class: "muted", style: "margin-top:8px; white-space:pre-wrap" }, r.system_prompt))));
  });
};

// =================== Eval ===================
VIEWS.eval = function () {
  const offline = el("input", { type: "checkbox", id: "ev-offline", checked: "checked" });
  const out = el("div", { id: "ev-out", class: "stack" });
  const runBtn = el("button", { class: "btn primary" }, "Run eval suite");
  runBtn.onclick = async () => {
    runBtn.disabled = true; out.innerHTML = "";
    out.appendChild(panel(el("div", null, el("span", { class: "spinner" }), "Running suite…")));
    try {
      const rep = await jpost("/api/eval", { offline: offline.checked });
      out.innerHTML = "";
      out.appendChild(panel(el("div", { class: "kv" },
        el("span", { class: rep.pass_rate === 1 ? "badge ok" : "badge bad" }, "pass " + rep.n_passed + "/" + rep.n_total),
        el("span", { class: "badge" }, "modes " + JSON.stringify(rep.modes)),
        el("span", { class: "badge" }, "blocked " + rep.blocked),
        el("span", { class: rep.learning_recall ? "badge ok" : "badge warn" }, "recall " + rep.learning_recall))));
      const rows = rep.results.map((x) => el("tr", null, el("td", null, x.task_id),
        el("td", null, el("span", { class: x.passed ? "badge ok" : "badge bad" }, x.passed ? "pass" : "fail")),
        el("td", null, x.mode),
        el("td", null, x.tool_valid_rate == null ? "—" : Math.round(x.tool_valid_rate * 100) + "%"),
        el("td", { class: "muted" }, x.notes || "")));
      out.appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
        el("table", null, el("tr", null, el("th", null, "Task"), el("th", null, "Result"),
          el("th", null, "Mode"), el("th", null, "Tool valid"), el("th", null, "Notes")), ...rows))));
    } catch (e) { out.innerHTML = ""; out.appendChild(panel(el("div", { class: "banner bad" }, e.message))); }
    finally { runBtn.disabled = false; }
  };
  view().append(viewHead("Eval", "Run the offline behavioral suite and view the report."),
    el("div", { class: "stack" },
      panel(el("div", null, el("label", { class: "switch" }, offline, el("span", { class: "track" }),
        el("span", null, "Offline (deterministic; a real model needs a configured connection)")),
        el("div", { class: "btn-row" }, runBtn))), out));
};

// =================== Costs ===================
VIEWS.costs = async function () {
  view().append(viewHead("Costs", "Per-tenant usage and estimated spend."));
  const totals = await api("/api/costs");
  const keys = Object.keys(totals);
  if (!keys.length) { view().appendChild(el("div", { class: "empty" }, "No usage recorded yet. Run a task first.")); return; }
  const rows = keys.map((k) => { const t = totals[k];
    return el("tr", null, el("td", null, t.tenant_id), el("td", null, String(t.runs)),
      el("td", null, String(t.actual_tokens || t.est_tokens)), el("td", null, "$" + (t.cost_usd || 0).toFixed(4)),
      el("td", null, String(t.blocked))); });
  view().appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
    el("table", null, el("tr", null, el("th", null, "Tenant"), el("th", null, "Runs"),
      el("th", null, "Tokens"), el("th", null, "Cost"), el("th", null, "Blocked")), ...rows))));
};

// ---------- theme ----------
function setThemeIcon() {
  const btn = document.getElementById("theme-toggle"); btn.innerHTML = "";
  const dark = document.documentElement.getAttribute("data-theme") === "dark";
  btn.appendChild(icon(dark ? "sun" : "moon"));
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", cur);
  try { localStorage.setItem("lws-theme", cur); } catch (e) { /* ignore */ }
  setThemeIcon();
}

// ---------- boot ----------
async function boot() {
  buildNav();
  document.getElementById("theme-toggle").onclick = toggleTheme;
  document.getElementById("conn-pill").onclick = () => show("connections");
  setThemeIcon();
  try {
    META = await api("/api/meta");
    document.getElementById("version").textContent = "v" + META.version;
    renderConnPill(META.connection);
  } catch (e) { META = { defaults: {}, models: [], current_model: "?", version: "?", connection: { configured: false } }; }
  show("playground");
}
boot();
