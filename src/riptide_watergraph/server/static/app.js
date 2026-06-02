"use strict";
// Like Water Studio — enterprise vanilla-JS SPA over the riptide-watergraph FastAPI server.

let META = null;

// ---------- icons (inline SVG paths) ----------
const ICONS = {
  playground: "M5 3l14 9-14 9V3z",
  chat: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2zM8 9h8M8 13h5",
  sessions: "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z",
  tools: "M14.7 6.3a4 4 0 00-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 005.4-5.4l-2.5 2.5-2-2 2.5-2.5z",
  roles: "M16 11a4 4 0 10-8 0 4 4 0 008 0zM4 21a8 8 0 0116 0",
  eval: "M9 11l3 3 8-8M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
  costs: "M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6",
  monitoring: "M3 3v18h18M7 14l3-4 3 3 5-6",
  connections: "M12 2a10 10 0 100 20 10 10 0 000-20zM2 12h20M12 2a15 15 0 010 20 15 15 0 010-20z",
  tool_runner: "M5 3l14 9-14 9V3zM19 3v18",
  workflows: "M4 5a2 2 0 100 4 2 2 0 000-4zM18 15a2 2 0 100 4 2 2 0 000-4zM18 5a2 2 0 100 4 2 2 0 000-4zM6 7h8a2 2 0 012 2v0M6 7v6a2 2 0 002 2h8",
  history: "M3 3v6h6M3 9a9 9 0 102.5-6.4L3 9M12 7v5l4 2",
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

// Searchable, category-filtered gallery: items[].category drives the chips; renderCard(item)
// builds each card; matches(item, query) decides text search hits.
function gallery(items, renderCard, matches) {
  const wrap = el("div");
  const grid = el("div", { class: "grid" });
  const counter = el("span", { class: "muted" });
  const cats = ["all", ...Array.from(new Set(items.map((i) => i.category))).sort()];
  let activeCat = "all";
  let query = "";
  const search = el("input", { type: "text", placeholder: "Search…",
    oninput: (e) => { query = e.target.value.toLowerCase(); render(); } });
  const chipRow = el("div", { class: "segmented" });
  function render() {
    grid.innerHTML = "";
    const shown = items.filter((i) =>
      (activeCat === "all" || i.category === activeCat) && (!query || matches(i, query)));
    shown.forEach((i) => grid.appendChild(renderCard(i)));
    counter.textContent = `${shown.length} of ${items.length}`;
    chipRow.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("active", b.dataset.cat === activeCat));
  }
  cats.forEach((cat) => {
    const n = cat === "all" ? items.length : items.filter((i) => i.category === cat).length;
    chipRow.appendChild(el("button", { "data-cat": cat,
      onclick: () => { activeCat = cat; render(); } }, `${cat} (${n})`));
  });
  wrap.append(
    el("div", { class: "filterbar" },
      el("div", { style: "display:flex; gap:10px; align-items:center; flex-wrap:wrap" }, search, counter),
      chipRow),
    grid);
  render();
  return wrap;
}

// ---------- run history (localStorage) ----------
const HKEY = "lws-history";
function loadHistory() { try { return JSON.parse(localStorage.getItem(HKEY) || "[]"); } catch (e) { return []; } }
function saveHistory(entry) {
  const h = loadHistory();
  h.unshift(entry);
  try { localStorage.setItem(HKEY, JSON.stringify(h.slice(0, 50))); } catch (e) { /* ignore */ }
}

// ---------- nav + router ----------
const NAV = [
  { group: "Workspace", items: [["chat", "Chat"], ["playground", "Playground"], ["workflows", "Workflows"], ["history", "History"]] },
  { group: "Library", items: [["tools", "Tools"], ["roles", "Roles"], ["tool_runner", "Tool Runner"]] },
  { group: "Insights", items: [["monitoring", "Monitoring"], ["eval", "Eval"], ["costs", "Costs"]] },
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

// Live-trace run: stream nodes from the SSE endpoint, then render the inspector.
function runTrace(body, out, record, done) {
  out.innerHTML = "";
  const steps = el("div", { class: "pills" });
  out.appendChild(panel(el("div", null, el("label", { class: "lbl" }, "Execution trace"),
    el("div", null, el("span", { class: "spinner" }), "streaming…"), steps)));
  const qs = new URLSearchParams({ task: body.task, tenant_id: body.tenant_id, offline: "true" });
  const es = new EventSource("/api/run/trace?" + qs.toString());
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.event === "node") {
      steps.appendChild(el("span", { class: "chip" }, msg.name));
    } else if (msg.event === "result") {
      es.close();
      out.innerHTML = ""; out.appendChild(renderInspector(msg.result)); record(msg.result); done();
    } else if (msg.event === "error") {
      es.close(); out.innerHTML = ""; out.appendChild(panel(el("div", { class: "banner bad" }, msg.detail))); done();
    }
  };
  es.onerror = () => { es.close(); done(); };
}

// =================== Playground ===================
VIEWS.playground = function () {
  const d = (META && META.defaults) || {};
  const connLive = META && META.connection && META.connection.configured;
  let replay = null;
  try { replay = JSON.parse(sessionStorage.getItem("lws-replay") || "null"); sessionStorage.removeItem("lws-replay"); } catch (e) { /* ignore */ }
  const task = el("textarea", { id: "pg-task", placeholder: "Describe a task — e.g. 'find and fix the bug in pkg/m.py' or 'search cats and count the words'" });
  if (replay && replay.task) task.value = replay.task;
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
    const record = (result) => saveHistory({ task: body.task, mode: result.mode,
      final_answer: result.final_answer, when: new Date().toISOString().slice(0, 19).replace("T", " ") });
    if (document.getElementById("pg-trace").checked) {
      runTrace(body, out, record, () => { runBtn.disabled = false; });
      return;
    }
    out.appendChild(el("div", { class: "card" }, el("div", { class: "card-pad" },
      el("span", { class: "spinner" }), "Running…")));
    try {
      const result = await jpost("/run", body);
      out.innerHTML = ""; out.appendChild(renderInspector(result));
      record(result);
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
          switchEl("pg-super", "Supervisor", d.supervisor),
          switchEl("pg-trace", "Live trace", false)),
        el("div", { class: "hint" },
          "Live trace streams node-by-node execution (offline, default options)."),
        card("Advanced", el("div", null,
          el("div", { class: "row" }, numField("pg-react", "ReAct steps", d.react_steps || 1),
            numField("pg-vote", "Vote k", d.vote_k || 1)),
          el("div", { style: "margin-top:12px" },
            el("label", { class: "lbl" }, "Structured output schema (JSON Schema, optional)"),
            schema, schemaErr)), false),
        el("div", { class: "btn-row" }, runBtn)))),
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

// =================== Chat ===================
const PRESETS = { Precise: 0.0, Balanced: 0.4, Creative: 0.8 };

function turnDetails(t) {
  // Collapsible inspector-style details inside an assistant bubble.
  const box = el("div", { class: "details" });
  if (t.plan && t.plan.length) box.appendChild(card("Plan & roles", zip(t.plan, t.roles), false));
  if (t.results && t.results.length) {
    const items = t.results.map((res, i) => {
      const tc = (res.tool_calls || []).map((c) => el("span", { class: "chip" }, (c.function || {}).name || "?"));
      return el("div", { style: "margin-bottom:8px" },
        el("div", { class: "kv" }, el("span", { class: "chip" }, "#" + i),
          el("span", { class: "chip" }, (t.roles && t.roles[i]) || "generalist"), el("strong", null, res.subtask || "")),
        el("div", { class: "muted" }, res.output || ""),
        tc.length ? el("div", { class: "pills" }, ...tc) : null);
    });
    box.appendChild(card("Agent steps", el("div", null, ...items), false));
  }
  if (t.verdicts && t.verdicts.length) {
    const rows = t.verdicts.map((v, i) => el("tr", null, el("td", null, String(i)),
      el("td", null, el("span", { class: v.verdict === "pass" ? "badge ok" : "badge bad" }, v.verdict || "?")),
      el("td", null, v.reason || "")));
    box.appendChild(card("Critic verdicts", el("table", null,
      el("tr", null, el("th", null, "#"), el("th", null, "Verdict"), el("th", null, "Reason")), ...rows), false));
  }
  if (t.metrics && Object.keys(t.metrics).length) box.appendChild(card("Metrics", copyPre(t.metrics), false));
  return box;
}
const SAMPLE_PROMPTS = [
  "What is 21 * 2, and explain it simply?",
  "Search cats, count the words, and uppercase the title",
  "Find and fix the bug in pkg/m.py",
  "Write concise release notes for a 0.8.0 launch",
  "Plan a 3-step research task on renewable energy",
];
const CHATS_KEY = "lws-chats";
function loadChats() { try { return JSON.parse(localStorage.getItem(CHATS_KEY) || "[]"); } catch (e) { return []; } }
function saveChats(list) { try { localStorage.setItem(CHATS_KEY, JSON.stringify(list)); } catch (e) { /* ignore */ } }
function nowTime() { return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function initials(name) {
  const parts = (name || "AI").replace(/[_-]/g, " ").split(/\s+/).filter(Boolean);
  return ((parts[0] || "A")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
}

function bubble(role, contentNode, opts) {
  opts = opts || {};
  const av = role === "user" ? "You" : (opts.agent || "AI");
  const avatar = el("div", { class: "avatar" }, role === "user" ? "U" : initials(av));
  const metaRow = el("div", { class: "msg-meta" },
    el("span", null, role === "user" ? "You" : av),
    opts.ts ? el("span", { class: "msg-ts" }, opts.ts) : null,
    opts.copyText ? el("button", { class: "msg-copy", title: "copy",
      onclick: () => { if (navigator.clipboard) navigator.clipboard.writeText(opts.copyText); toast("Copied", "ok"); } }, "copy") : null);
  return el("div", { class: "msg " + role }, avatar,
    el("div", { class: "msg-body" }, metaRow, contentNode));
}

VIEWS.chat = function () {
  let activeES = null;
  let lastTask = null;
  const chats = loadChats();
  if (!chats.length) chats.push({ id: "chat-1", title: "New chat" });
  let activeId = chats[0].id;

  // --- settings panel ---
  const temp = el("input", { type: "range", id: "c-temp", min: "0", max: "2", step: "0.1", value: "0" });
  const tempVal = el("span", { class: "muted" }, "0.0");
  temp.oninput = () => { tempVal.textContent = parseFloat(temp.value).toFixed(1); };
  const topp = el("input", { type: "number", id: "c-topp", class: "num", min: "0", max: "1", step: "0.05", placeholder: "—" });
  const maxtok = el("input", { type: "number", id: "c-maxtok", class: "num", min: "1", placeholder: "—" });
  const presetRow = el("div", { class: "segmented" },
    ...Object.keys(PRESETS).map((name) => el("button", {
      onclick: () => { temp.value = String(PRESETS[name]); temp.oninput(); } }, name)));
  const knob = (id, label, on) => switchEl(id, label, on);
  const settingsNode = el("div", null,
    el("label", { class: "lbl" }, "Sampling"), presetRow,
    el("div", { style: "margin-top:10px" }, el("label", { class: "lbl" }, "Temperature"),
      el("div", { style: "display:flex; gap:8px; align-items:center" }, temp, tempVal)),
    el("div", { class: "row", style: "margin-top:10px" },
      el("div", null, el("label", { class: "lbl" }, "top_p"), topp),
      el("div", null, el("label", { class: "lbl" }, "max_tokens"), maxtok)),
    el("label", { class: "lbl", style: "margin-top:14px" }, "Per-turn options"),
    el("div", { class: "switches" },
      knob("c-offline", "Offline", true), knob("c-memory", "Memory", false),
      knob("c-guard", "Guardrails", true), knob("c-single", "Single", false),
      knob("c-llm", "LLM composer", false), knob("c-critic", "Critic", false),
      knob("c-super", "Supervisor", false)),
    el("div", { class: "row", style: "margin-top:10px" },
      el("div", null, el("label", { class: "lbl" }, "ReAct steps"),
        el("input", { type: "number", id: "c-react", class: "num", min: "1", value: "1" })),
      el("div", null, el("label", { class: "lbl" }, "Vote k"),
        el("input", { type: "number", id: "c-vote", class: "num", min: "1", value: "1" }))));

  const messages = el("div", { class: "chat-log", id: "chat-log" });
  const input = el("textarea", { id: "chat-input", class: "chat-input", placeholder: "Message the agents…  (Enter to send, Shift+Enter for newline)" });
  const sendBtn = el("button", { class: "btn primary" }, "Send");
  const stopBtn = el("button", { class: "btn", onclick: () => stop() }, "Stop"); stopBtn.disabled = true;
  const regenBtn = el("button", { class: "btn", onclick: () => { if (lastTask) { input.value = lastTask; send(); } } }, "Regenerate");
  const exportBtn = el("button", { class: "btn", onclick: () => exportChat() }, "Export");
  const sessionList = el("div", { class: "chat-sessions-list" });

  function num(id) { const v = document.getElementById(id).value; return v === "" ? null : v; }
  function params(task) {
    const p = { task, offline: document.getElementById("c-offline").checked,
      memory: document.getElementById("c-memory").checked, guardrails: document.getElementById("c-guard").checked,
      single: document.getElementById("c-single").checked, llm_composer: document.getElementById("c-llm").checked,
      critic: document.getElementById("c-critic").checked, supervisor: document.getElementById("c-super").checked,
      react_steps: parseInt(document.getElementById("c-react").value, 10) || 1,
      vote_k: parseInt(document.getElementById("c-vote").value, 10) || 1,
      temperature: parseFloat(temp.value) };
    if (num("c-topp") != null) p.top_p = parseFloat(num("c-topp"));
    if (num("c-maxtok") != null) p.max_tokens = parseInt(num("c-maxtok"), 10);
    return p;
  }
  const agentLabel = (t) => {
    const rs = Array.from(new Set(t.roles || [])).slice(0, 3);
    return rs.length ? rs.join(", ") : "agent";
  };
  function addAssistant(t, ts) {
    const body = el("div", null, el("div", null, t.answer || "(none)"));
    const det = turnDetails(t);
    if (det.childNodes.length) {
      const toggle = el("button", { class: "btn", style: "margin-top:8px",
        onclick: () => { det.style.display = det.style.display === "none" ? "" : "none"; } }, "details");
      det.style.display = "none";
      body.append(toggle, det);
    }
    if (t.blocked) body.appendChild(el("div", { class: "badge bad", style: "margin-top:6px" }, "blocked"));
    messages.appendChild(bubble("agent", body, { agent: agentLabel(t), ts: ts, copyText: t.answer || "" }));
    autoscroll();
  }
  const autoscroll = () => { messages.scrollTop = messages.scrollHeight; };

  function emptyState() {
    const cards = SAMPLE_PROMPTS.map((p) => el("button", { class: "sample-prompt",
      onclick: () => { input.value = p; send(); } }, p));
    return el("div", { class: "chat-empty" },
      el("div", { class: "chat-empty-logo" }, "≈"),
      el("h2", null, "Start a conversation"),
      el("div", { class: "muted" }, "Chat with the multi-agent graph. Try one of these:"),
      el("div", { class: "sample-prompts" }, ...cards));
  }
  async function loadTranscript() {
    messages.innerHTML = "";
    const data = await api("/sessions/" + encodeURIComponent(activeId));
    if (!data.turns.length) { messages.appendChild(emptyState()); return; }
    data.turns.forEach((t) => {
      messages.appendChild(bubble("user", el("div", null, t.task)));
      addAssistant(t, null);
    });
  }
  function stop() { if (activeES) { activeES.close(); activeES = null; } sendBtn.disabled = false; stopBtn.disabled = true; }
  function send() {
    const task = input.value.trim();
    if (!task) return;
    lastTask = task; input.value = "";
    const es0 = messages.querySelector(".chat-empty"); if (es0) es0.remove();
    messages.appendChild(bubble("user", el("div", null, task), { ts: nowTime() }));
    const steps = el("span", { class: "pills" });
    const thinking = el("div", null, el("span", { class: "spinner" }), steps);
    const thinkBubble = bubble("agent", thinking, { agent: "thinking…" });
    messages.appendChild(thinkBubble); autoscroll();
    sendBtn.disabled = true; stopBtn.disabled = false;
    const qs = new URLSearchParams(params(task));
    const es = new EventSource("/api/sessions/" + encodeURIComponent(activeId) + "/messages/stream?" + qs.toString());
    activeES = es;
    es.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.event === "node") { steps.appendChild(el("span", { class: "chip" }, m.name)); autoscroll(); }
      else if (m.event === "result") { es.close(); activeES = null; thinkBubble.remove(); addAssistant(m.result, nowTime()); sendBtn.disabled = false; stopBtn.disabled = true; }
      else if (m.event === "error") { es.close(); activeES = null; thinkBubble.remove(); messages.appendChild(bubble("agent", el("div", { class: "error" }, [].concat(m.detail).join(", ")))); sendBtn.disabled = false; stopBtn.disabled = true; }
    };
    es.onerror = () => { es.close(); activeES = null; sendBtn.disabled = false; stopBtn.disabled = true; };
  }
  sendBtn.onclick = send;
  input.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  async function exportChat() {
    const data = await api("/sessions/" + encodeURIComponent(activeId));
    const md = data.turns.map((t) => "**You:** " + t.task + "\n\n**Agent:** " + (t.answer || "")).join("\n\n---\n\n");
    const blob = new Blob([md || "(empty)"], { type: "text/markdown" });
    const a = el("a", { href: URL.createObjectURL(blob), download: activeId + ".md" }); a.click();
    toast("Exported", "ok");
  }

  // --- conversation list ---
  function renderSessions() {
    sessionList.innerHTML = "";
    loadChats().forEach((c) => {
      const row = el("div", { class: "chat-session" + (c.id === activeId ? " active" : "") },
        el("span", { class: "chat-session-title", onclick: () => { stop(); activeId = c.id; renderSessions(); loadTranscript(); } }, c.title || c.id),
        el("button", { class: "chat-session-x", title: "delete", onclick: async (ev) => {
          ev.stopPropagation();
          await fetch("/sessions/" + encodeURIComponent(c.id), { method: "DELETE" });
          let list = loadChats().filter((x) => x.id !== c.id);
          if (!list.length) list = [{ id: "chat-1", title: "New chat" }];
          saveChats(list);
          if (activeId === c.id) activeId = list[0].id;
          renderSessions(); loadTranscript();
        } }, "×"));
      sessionList.appendChild(row);
    });
  }
  const newChatBtn = el("button", { class: "btn primary", style: "width:100%", onclick: () => {
    const id = "chat-" + Date.now().toString(36);
    const list = loadChats(); list.unshift({ id, title: "New chat" }); saveChats(list);
    activeId = id; renderSessions(); loadTranscript(); input.focus();
  } }, "+ New chat");

  saveChats(chats);
  renderSessions();

  view().append(viewHead("Chat", "Converse with the multi-agent graph; tune the model and per-turn options."),
    el("div", { class: "chat-grid" },
      el("aside", { class: "chat-sessions" }, newChatBtn, sessionList),
      el("div", { class: "chat-main" }, messages,
        el("div", { class: "composer" }, input,
          el("div", { class: "composer-actions" }, sendBtn, stopBtn, regenBtn, exportBtn))),
      el("aside", { class: "chat-settings" }, el("div", { class: "card" },
        el("div", { class: "card-pad" }, el("h2", { style: "margin-top:0" }, "Model & options"), settingsNode)))));
  loadTranscript();
};

// =================== Tools ===================
VIEWS.tools = async function () {
  view().append(viewHead("Tools",
    "Registered tools the agents can call — search and filter by category."));
  const tools = await api("/api/tools");
  const renderCard = (t) => el("div", { class: "card" }, el("div", { class: "card-pad" },
    el("div", { class: "kv" }, el("strong", null, t.name), el("span", { class: "chip" }, t.category),
      el("span", { class: t.side_effecting ? "badge warn" : "badge ok" }, t.side_effecting ? "side-effecting" : "read-only")),
    el("div", { class: "muted" }, t.description),
    card("schema", copyPre(t.json_schema), false)));
  const matches = (t, q) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q);
  view().appendChild(gallery(tools, renderCard, matches));
};

// =================== Roles ===================
VIEWS.roles = async function () {
  view().append(viewHead("Roles", "Specialist agents and their tool allow-lists — search and filter by category."));
  const roles = await api("/api/roles");
  const renderCard = (r) => {
    const tools = r.tools == null ? [] : r.tools;
    const shown = tools.slice(0, 8).map((t) => el("span", { class: "chip" }, t));
    const more = tools.length > 8 ? [el("span", { class: "chip" }, "+" + (tools.length - 8))] : [];
    const chips = r.tools == null ? [el("span", { class: "chip" }, "all tools")] : [...shown, ...more];
    return el("div", { class: "card" }, el("div", { class: "card-pad" },
      el("div", { class: "kv" }, el("strong", null, r.name), el("span", { class: "chip" }, r.category)),
      el("div", { class: "muted", style: "margin-bottom:8px" }, r.description || ""),
      el("div", { class: "pills" }, ...chips)));
  };
  const matches = (r, q) =>
    r.name.toLowerCase().includes(q) || (r.description || "").toLowerCase().includes(q);
  view().appendChild(gallery(roles, renderCard, matches));
};

// =================== Tool Runner ===================
VIEWS.tool_runner = async function () {
  view().append(viewHead("Tool Runner", "Invoke a single read-only tool directly to explore the toolset."));
  const tools = (await api("/api/tools")).filter((t) => !t.side_effecting);
  const dl = el("datalist", { id: "tool-list" }, ...tools.map((t) => el("option", { value: t.name })));
  const pick = el("input", { type: "text", list: "tool-list", placeholder: "tool name, e.g. sha256" });
  const form = el("div", { id: "tr-form" });
  const out = el("div", { id: "tr-out", class: "stack" });
  const runBtn = el("button", { class: "btn primary" }, "Run tool");

  function buildForm() {
    form.innerHTML = "";
    const t = tools.find((x) => x.name === pick.value);
    if (!t) { form.appendChild(el("div", { class: "hint" }, "Pick a read-only tool to see its inputs.")); return; }
    form.appendChild(el("div", { class: "muted", style: "margin-bottom:8px" }, t.description));
    const props = (t.json_schema && t.json_schema.properties) || {};
    Object.keys(props).forEach((key) => {
      const ty = (props[key].type) || "string";
      form.appendChild(el("div", { class: "field", style: "margin-bottom:10px" },
        el("label", { class: "lbl" }, key + " (" + ty + ")"),
        el("input", { type: ty === "integer" || ty === "number" ? "number" : "text",
          "data-key": key, "data-type": ty, class: "tr-arg" })));
    });
  }
  pick.oninput = buildForm;
  runBtn.onclick = async () => {
    const t = tools.find((x) => x.name === pick.value);
    if (!t) { toast("Pick a tool first", "bad"); return; }
    const args = {};
    form.querySelectorAll(".tr-arg").forEach((inp) => {
      const v = inp.value; if (v === "") return;
      const ty = inp.dataset.type;
      args[inp.dataset.key] = ty === "integer" ? parseInt(v, 10)
        : ty === "number" ? parseFloat(v)
        : ty === "array" ? JSON.parse(v) : v;
    });
    runBtn.disabled = true;
    try {
      const r = await jpost("/api/tools/" + encodeURIComponent(t.name) + "/invoke", { arguments: args });
      out.innerHTML = ""; out.appendChild(panel(el("div", null, el("label", { class: "lbl" }, "Result"), copyPre(r.result))));
    } catch (e) { toast(e.message, "bad"); } finally { runBtn.disabled = false; }
  };
  buildForm();
  view().append(el("div", { class: "stack" },
    panel(el("div", null, el("label", { class: "lbl" }, "Tool"), pick, dl,
      el("div", { style: "margin-top:12px" }, form),
      el("div", { class: "btn-row" }, runBtn))), out));
};

// =================== History ===================
VIEWS.history = function () {
  view().append(viewHead("History", "Your recent runs (stored locally in this browser)."));
  const h = loadHistory();
  if (!h.length) { view().appendChild(el("div", { class: "empty" }, "No runs yet. Run a task in the Playground.")); return; }
  const clearBtn = el("button", { class: "btn", onclick: () => {
    try { localStorage.removeItem(HKEY); } catch (e) { /* ignore */ } show("history");
  } }, "Clear history");
  const stack = el("div", { class: "stack" }, el("div", { class: "btn-row" }, clearBtn));
  h.forEach((entry) => {
    const replay = el("button", { class: "btn", onclick: () => {
      sessionStorage.setItem("lws-replay", JSON.stringify(entry)); show("playground");
    } }, "Replay");
    stack.appendChild(panel(el("div", null,
      el("div", { class: "kv" },
        el("span", { class: "badge accent" }, entry.mode || "single"),
        el("span", { class: "muted" }, entry.when || ""), replay),
      el("div", null, el("strong", null, "Task: "), entry.task),
      el("div", { class: "muted", style: "margin-top:4px" }, (entry.final_answer || "").slice(0, 240)))));
  });
  view().appendChild(stack);
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

// =================== Monitoring ===================
function kpi(label, value, sub) {
  return el("div", { class: "kpi" },
    el("div", { class: "kpi-value" }, String(value)),
    el("div", { class: "kpi-label" }, label),
    sub ? el("div", { class: "kpi-sub muted" }, sub) : null);
}
function barChart(series, valueKey, label) {
  // series: [{date/key, <valueKey>}]; renders simple inline-SVG bars (no deps).
  const W = 100, H = 40, n = series.length || 1;
  const max = Math.max(1, ...series.map((s) => s[valueKey] || 0));
  const bw = W / n;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.setAttribute("class", "mini-chart");
  svg.setAttribute("preserveAspectRatio", "none");
  series.forEach((s, i) => {
    const h = ((s[valueKey] || 0) / max) * (H - 2);
    const rect = document.createElementNS(ns, "rect");
    rect.setAttribute("x", String(i * bw + bw * 0.12));
    rect.setAttribute("y", String(H - h));
    rect.setAttribute("width", String(bw * 0.76));
    rect.setAttribute("height", String(h));
    rect.setAttribute("rx", "0.6");
    const title = document.createElementNS(ns, "title");
    title.textContent = (s.date || s.key || "") + ": " + (s[valueKey] || 0);
    rect.appendChild(title);
    svg.appendChild(rect);
  });
  return el("div", null, el("div", { class: "lbl" }, label), svg);
}

VIEWS.monitoring = async function () {
  view().append(viewHead("Monitoring", "Run metrics aggregated from the usage log."));
  const m = await api("/api/monitoring");
  if (!m.totals.runs) { view().appendChild(el("div", { class: "empty" }, "No runs recorded yet. Run a task in Chat or Playground.")); return; }
  const t = m.totals;
  const pct = (x) => x == null ? "—" : Math.round(x * 100) + "%";
  view().append(el("div", { class: "kpi-grid" },
    kpi("Runs", t.runs),
    kpi("Success rate", pct(t.success_rate)),
    kpi("Avg latency", t.avg_latency_ms + " ms"),
    kpi("Tokens", t.total_tokens),
    kpi("Cost", "$" + (t.total_cost_usd || 0).toFixed(4)),
    kpi("Tool valid", pct(t.tool_valid_rate)),
    kpi("Blocked", t.blocked)));

  const modeSeries = Object.keys(m.by_mode).map((k) => ({ key: k, count: m.by_mode[k] }));
  view().append(el("div", { class: "grid" },
    panel(barChart(m.daily, "runs", "Runs per day")),
    panel(barChart(m.daily, "cost_usd", "Cost per day ($)")),
    panel(barChart(modeSeries, "count", "Runs by mode"))));

  const rows = m.recent.map((r) => el("tr", null,
    el("td", { class: "muted" }, r.ts ? new Date(r.ts * 1000).toLocaleString() : "—"),
    el("td", null, r.task),
    el("td", null, el("span", { class: "chip" }, r.mode)),
    el("td", null, r.latency_ms + " ms"),
    el("td", null, String(r.tokens)),
    el("td", null, "$" + (r.cost_usd || 0).toFixed(4)),
    el("td", null, r.blocked ? el("span", { class: "badge bad" }, "blocked")
      : el("span", { class: r.success === false ? "badge warn" : "badge ok" },
          r.success === false ? "needs work" : "ok"))));
  view().append(panel(el("div", null, el("h2", { style: "margin-top:0" }, "Recent runs"),
    el("table", null, el("tr", null, el("th", null, "When"), el("th", null, "Task"),
      el("th", null, "Mode"), el("th", null, "Latency"), el("th", null, "Tokens"),
      el("th", null, "Cost"), el("th", null, "Status")), ...rows))));
};

// =================== Workflows (drag-and-drop canvas) ===================
const WF_W = 184, WF_H = 76;
function runWorkflowTrace(spec, out, done) {
  out.innerHTML = "";
  const steps = el("div", { class: "pills" });
  out.appendChild(panel(el("div", null, el("label", { class: "lbl" }, "Execution trace"),
    el("div", null, el("span", { class: "spinner" }), "running…"), steps)));
  const es = new EventSource("/api/workflows/run/stream?spec=" + encodeURIComponent(JSON.stringify(spec)) + "&offline=true");
  es.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.event === "node") steps.appendChild(el("span", { class: "chip" }, m.name));
    else if (m.event === "result") { es.close(); out.innerHTML = ""; out.appendChild(renderInspector(m.result)); done(); }
    else if (m.event === "error") { es.close(); out.innerHTML = ""; out.appendChild(panel(el("div", { class: "banner bad" }, [].concat(m.detail).join(", ")))); done(); }
  };
  es.onerror = () => { es.close(); done(); };
}

VIEWS.workflows = async function () {
  const roleNames = (META && META.role_names) || ["generalist"];
  let nodes = [];   // {id, role, subtask, x, y, elNode, elSub, elHead}
  let edges = [];   // {source, target, elPath, elHit}
  let nextId = 1, connectFrom = null, selected = null;

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("class", "wf-edges");
  const defs = document.createElementNS(svgNS, "defs");
  defs.innerHTML = '<marker id="wf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="var(--ink-2)"/></marker>';
  svg.appendChild(defs);
  const live = document.createElementNS(svgNS, "path");
  live.setAttribute("class", "wf-edge-live");
  svg.appendChild(live);
  const nodeLayer = el("div", { class: "wf-nodes" });
  const canvas = el("div", { class: "wf-canvas" }, svg, nodeLayer);
  const canvasWrap = el("div", { class: "wf-canvas-wrap" }, canvas);
  const out = el("div", { class: "stack", style: "margin-top:14px" });

  const outPt = (n) => ({ x: n.x + WF_W / 2, y: n.y + WF_H });
  const inPt = (n) => ({ x: n.x + WF_W / 2, y: n.y });
  const edgePath = (a, b) => {
    const dy = Math.max(36, Math.abs(b.y - a.y) * 0.5);
    return `M ${a.x} ${a.y} C ${a.x} ${a.y + dy}, ${b.x} ${b.y - dy}, ${b.x} ${b.y}`;
  };
  const byId = (id) => nodes.find((n) => n.id === id);
  function growCanvas() {
    const w = Math.max(900, ...nodes.map((n) => n.x + WF_W + 60));
    const h = Math.max(560, ...nodes.map((n) => n.y + WF_H + 60));
    canvas.style.width = w + "px"; canvas.style.height = h + "px";
    svg.setAttribute("width", w); svg.setAttribute("height", h);
  }
  function redrawEdges(id) {
    edges.forEach((e) => {
      if (id && e.source !== id && e.target !== id) return;
      const a = byId(e.source), b = byId(e.target);
      if (!a || !b) return;
      const d = edgePath(outPt(a), inPt(b));
      e.elPath.setAttribute("d", d); e.elHit.setAttribute("d", d);
    });
  }
  function wouldCycle(src, tgt) {
    // adding src->tgt creates a cycle if src is reachable from tgt
    const adj = {}; nodes.forEach((n) => (adj[n.id] = []));
    edges.forEach((e) => adj[e.source].push(e.target));
    adj[tgt] = (adj[tgt] || []).concat(src);
    const seen = new Set(); const stack = [tgt];
    while (stack.length) { const c = stack.pop(); if (c === src) return true;
      if (seen.has(c)) continue; seen.add(c); (adj[c] || []).forEach((x) => stack.push(x)); }
    return false;
  }
  function selectNode(n) {
    selected = n;
    nodeLayer.querySelectorAll(".wf-node").forEach((el2) => el2.classList.toggle("sel", n && el2.dataset.id === n.id));
    renderInspector2();
  }
  function addEdge(source, target) {
    if (source === target || edges.some((e) => e.source === source && e.target === target)) return;
    if (wouldCycle(source, target)) { toast("That would create a cycle", "bad"); return; }
    const hit = document.createElementNS(svgNS, "path"); hit.setAttribute("class", "wf-edge-hit");
    const path = document.createElementNS(svgNS, "path"); path.setAttribute("class", "wf-edge");
    path.setAttribute("marker-end", "url(#wf-arrow)");
    const e = { source, target, elPath: path, elHit: hit };
    hit.onclick = () => { svg.removeChild(path); svg.removeChild(hit); edges = edges.filter((x) => x !== e); };
    svg.appendChild(hit); svg.appendChild(path); edges.push(e); redrawEdges(source);
  }
  function addNode(role, x, y, subtask, id) {
    const n = { id: id || ("n" + (nextId++)), role, subtask: subtask || "", x, y };
    const head = el("div", { class: "wf-node-head" }, el("span", null, n.role),
      el("button", { class: "wf-del", title: "delete",
        onclick: (ev) => { ev.stopPropagation(); removeNode(n); } }, "×"));
    const sub = el("div", { class: "wf-node-sub" }, n.subtask || "(click to add instruction)");
    const portIn = el("div", { class: "wf-port in", title: "input" });
    const portOut = el("div", { class: "wf-port out", title: "output (click, then click a target's input)" });
    const node = el("div", { class: "wf-node", "data-id": n.id }, portIn, head, sub, portOut);
    node.style.transform = `translate(${x}px, ${y}px)`;
    node.onclick = (ev) => { ev.stopPropagation(); selectNode(n); };
    portOut.onclick = (ev) => { ev.stopPropagation(); connectFrom = n; toast("Now click a target node's top port", "ok"); };
    portIn.onclick = (ev) => { ev.stopPropagation(); if (connectFrom) { addEdge(connectFrom.id, n.id); connectFrom = null; live.removeAttribute("d"); } };
    // drag the header to move the node
    head.onpointerdown = (ev) => {
      if (ev.target.classList.contains("wf-del")) return;
      ev.preventDefault(); head.setPointerCapture(ev.pointerId);
      const sx = ev.clientX, sy = ev.clientY, ox = n.x, oy = n.y;
      const move = (e2) => { n.x = Math.max(0, ox + (e2.clientX - sx)); n.y = Math.max(0, oy + (e2.clientY - sy));
        node.style.transform = `translate(${n.x}px, ${n.y}px)`; redrawEdges(n.id); };
      const up = () => { head.releasePointerCapture(ev.pointerId); head.onpointermove = null; head.onpointerup = null; growCanvas(); };
      head.onpointermove = move; head.onpointerup = up;
    };
    n.elNode = node; n.elSub = sub; n.elHead = head.firstChild;
    nodes.push(n); nodeLayer.appendChild(node); growCanvas(); selectNode(n);
    return n;
  }
  function removeNode(n) {
    edges.filter((e) => e.source === n.id || e.target === n.id).forEach((e) => {
      svg.removeChild(e.elPath); svg.removeChild(e.elHit); });
    edges = edges.filter((e) => e.source !== n.id && e.target !== n.id);
    nodeLayer.removeChild(n.elNode); nodes = nodes.filter((x) => x !== n);
    if (selected === n) selectNode(null);
  }
  canvas.onclick = () => { connectFrom = null; live.removeAttribute("d"); selectNode(null); };
  canvas.ondragover = (ev) => ev.preventDefault();
  canvas.ondrop = (ev) => {
    ev.preventDefault();
    const role = ev.dataTransfer.getData("text/role"); if (!role) return;
    const r = canvas.getBoundingClientRect();
    addNode(role, ev.clientX - r.left - WF_W / 2, ev.clientY - r.top - WF_H / 2);
  };

  // --- palette (draggable roles) ---
  const palSearch = el("input", { type: "text", placeholder: "Search roles…" });
  const palList = el("div", { class: "wf-pal-list" });
  function renderPalette(q) {
    palList.innerHTML = "";
    roleNames.filter((r) => !q || r.includes(q)).slice(0, 200).forEach((r) => {
      const item = el("div", { class: "wf-pal-item", draggable: "true" }, r);
      item.ondragstart = (ev) => ev.dataTransfer.setData("text/role", r);
      item.onclick = () => addNode(r, 40 + (nodes.length % 3) * 30, 40 + nodes.length * 24);
      palList.appendChild(item);
    });
  }
  palSearch.oninput = () => renderPalette(palSearch.value.toLowerCase());
  renderPalette("");

  // --- inspector ---
  const insp = el("div", { class: "wf-inspector" });
  function renderInspector2() {
    insp.innerHTML = "";
    if (!selected) { insp.appendChild(el("div", { class: "muted" }, "Select a node to edit, or drag a role from the palette.")); return; }
    const roleSel = el("select", { onchange: (e) => { selected.role = e.target.value; selected.elHead.textContent = selected.role; } },
      ...roleNames.map((r) => el("option", { value: r, ...(r === selected.role ? { selected: "selected" } : {}) }, r)));
    const sub = el("textarea", { placeholder: "Instruction for this step…",
      oninput: (e) => { selected.subtask = e.target.value; selected.elSub.textContent = e.target.value || "(click to add instruction)"; } });
    sub.value = selected.subtask;
    insp.append(el("label", { class: "lbl" }, "Role"), roleSel,
      el("label", { class: "lbl", style: "margin-top:10px" }, "Instruction"), sub,
      el("button", { class: "btn", style: "margin-top:10px", onclick: () => removeNode(selected) }, "Delete node"),
      el("div", { class: "hint", style: "margin-top:10px" }, "Side-effecting tools don't execute on the workflow (swarm) path — no human approval there."));
  }
  renderInspector2();

  // --- toolbar ---
  const nameInput = el("input", { type: "text", placeholder: "workflow name", value: "untitled" });
  const goalInput = el("input", { type: "text", placeholder: "optional goal (memory/usage context)" });
  const loadSel = el("select", null, el("option", { value: "" }, "Load…"));
  const traceToggle = switchEl("wf-trace", "Live trace", true);
  const critic = switchEl("wf-critic", "Critic", false);
  const guard = switchEl("wf-guard", "Guardrails", true);
  const runBtn = el("button", { class: "btn primary" }, "Run workflow");

  function buildSpec(forRun) {
    return {
      name: nameInput.value || "untitled", goal: goalInput.value || nameInput.value, mode: "auto",
      nodes: nodes.map((n) => forRun ? { id: n.id, role: n.role, subtask: n.subtask || n.role }
        : { id: n.id, role: n.role, subtask: n.subtask, x: Math.round(n.x), y: Math.round(n.y) }),
      edges: edges.map((e) => ({ source: e.source, target: e.target })),
    };
  }
  runBtn.onclick = async () => {
    if (!nodes.length) { toast("Add at least one node", "bad"); return; }
    runBtn.disabled = true;
    const spec = buildSpec(true);
    if (document.getElementById("wf-trace").checked) {
      runWorkflowTrace(spec, out, () => { runBtn.disabled = false; });
    } else {
      out.innerHTML = ""; out.appendChild(panel(el("div", null, el("span", { class: "spinner" }), "running…")));
      try {
        const r = await jpost("/api/workflows/run", { spec, offline: true,
          guardrails: document.getElementById("wf-guard").checked, critic: document.getElementById("wf-critic").checked });
        out.innerHTML = ""; out.appendChild(renderInspector(r));
      } catch (e) { out.innerHTML = ""; out.appendChild(panel(el("div", { class: "banner bad" }, e.message))); }
      finally { runBtn.disabled = false; }
    }
  };
  async function refreshSaved() {
    const names = await api("/api/workflows");
    loadSel.innerHTML = ""; loadSel.appendChild(el("option", { value: "" }, "Load…"));
    names.forEach((n) => loadSel.appendChild(el("option", { value: n }, n)));
  }
  async function save() {
    try {
      await jpost("/api/workflows", buildSpec(false));
      toast("Workflow saved", "ok"); await refreshSaved();
    } catch (e) { toast([].concat(e.message).join(", "), "bad"); }
  }
  function loadSpec(spec) {
    nodes.slice().forEach(removeNode); nodes = []; edges = [];
    nameInput.value = spec.name || "untitled"; goalInput.value = spec.goal || "";
    (spec.nodes || []).forEach((n) => addNode(n.role, n.x || 40, n.y || 40, n.subtask, n.id));
    nextId = nodes.length + 1;
    (spec.edges || []).forEach((e) => addEdge(e.source, e.target));
    selectNode(null);
  }
  loadSel.onchange = async () => { if (!loadSel.value) return;
    try { loadSpec(await api("/api/workflows/" + encodeURIComponent(loadSel.value))); } catch (e) { toast(e.message, "bad"); } };

  const toolbar = el("div", { class: "wf-toolbar" },
    nameInput, goalInput,
    el("button", { class: "btn", onclick: save }, "Save"), loadSel,
    el("button", { class: "btn", onclick: () => loadSpec({ name: "untitled", nodes: [], edges: [] }) }, "Clear"),
    traceToggle, guard, critic, runBtn);

  view().append(viewHead("Workflows", "Drag roles onto the canvas, connect them into a dependency DAG, and run it."),
    toolbar,
    el("div", { class: "wf-shell" },
      el("aside", { class: "wf-palette" }, el("div", { class: "lbl" }, "Roles"), palSearch, palList),
      canvasWrap,
      el("aside", { class: "wf-inspector-wrap" }, el("div", { class: "card" }, el("div", { class: "card-pad" }, insp)))),
    out);
  growCanvas();
  refreshSaved();
  // pointer-follow for the in-progress connection
  canvas.onpointermove = (ev) => {
    if (!connectFrom) return;
    const r = canvas.getBoundingClientRect();
    live.setAttribute("d", edgePath(outPt(connectFrom), { x: ev.clientX - r.left, y: ev.clientY - r.top }));
  };
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
  show("chat");
}
boot();
