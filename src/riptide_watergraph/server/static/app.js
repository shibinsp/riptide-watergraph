"use strict";
// Like Water Studio — vanilla-JS SPA over the riptide-watergraph FastAPI server.

let META = null;

// --- tiny helpers ---
async function api(path, opts) {
  const res = await fetch(path, opts);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText;
    throw new Error(detail);
  }
  return data;
}
function jpost(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null) continue;
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") n[k] = v;
      else n.setAttribute(k, v);
    }
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    n.appendChild(typeof kid === "string" ? document.createTextNode(kid) : kid);
  }
  return n;
}
const view = () => document.getElementById("view");
function clear() { view().innerHTML = ""; }
function pre(obj) { return el("pre", null, JSON.stringify(obj, null, 2)); }
function header(title, sub) {
  return el("div", null, el("h1", null, title), sub ? el("p", { class: "subtitle" }, sub) : null);
}

// collapsible card
function card(title, body, open = true) {
  const content = el("div", { class: "card-body" }, body);
  if (!open) content.style.display = "none";
  const head = el("div", { class: "card-head" },
    el("h2", null, title),
    el("span", { class: "muted" }, open ? "▾" : "▸"));
  head.onclick = () => {
    const hidden = content.style.display === "none";
    content.style.display = hidden ? "" : "none";
    head.lastChild.textContent = hidden ? "▾" : "▸";
  };
  return el("div", { class: "card collapsible" }, head, content);
}

// --- router ---
const VIEWS = {};
function show(name) {
  document.querySelectorAll(".nav-item").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  clear();
  (VIEWS[name] || VIEWS.playground)();
}

// =================== Playground ===================
VIEWS.playground = function () {
  const d = (META && META.defaults) || {};
  const task = el("textarea", { id: "pg-task", placeholder: "Describe a task, e.g. search cats and count the words and uppercase the title" });
  const tenant = el("input", { type: "text", id: "pg-tenant", value: d.tenant_id || "default" });

  const chk = (id, label, on) =>
    el("label", { class: "check" },
      el("input", { type: "checkbox", id, ...(on ? { checked: "checked" } : {}) }), label);
  const numField = (id, label, val) =>
    el("div", { class: "field" }, el("label", null, label),
      el("input", { type: "number", id, class: "num", min: "1", value: String(val) }));

  const schema = el("textarea", { id: "pg-schema", placeholder: '{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"]}' });
  const schemaErr = el("div", { class: "error", id: "pg-schema-err" });
  const out = el("div", { id: "pg-out" });
  const runBtn = el("button", { class: "primary", id: "pg-run" }, "Run task");

  runBtn.onclick = async () => {
    schemaErr.textContent = "";
    let final_schema = null;
    const raw = schema.value.trim();
    if (raw) {
      try { final_schema = JSON.parse(raw); }
      catch (e) { schemaErr.textContent = "Invalid JSON schema: " + e.message; return; }
    }
    const body = {
      task: task.value,
      tenant_id: tenant.value || "default",
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
    out.appendChild(el("div", { class: "spin" }, "Running…"));
    try {
      const result = await jpost("/run", body);
      out.innerHTML = "";
      out.appendChild(renderInspector(result));
    } catch (e) {
      out.innerHTML = "";
      out.appendChild(el("div", { class: "card" }, el("div", { class: "error" }, "Run failed: " + e.message)));
    } finally {
      runBtn.disabled = false;
    }
  };

  view().append(
    header("Playground", "Drive the graph and inspect every layer of the run."),
    el("div", { class: "card" },
      el("label", null, "Task"), task,
      el("div", { class: "row" }, el("div", { class: "field" }, el("label", null, "Tenant"), tenant),
        el("div", { class: "field" }, el("label", null, "Model"),
          el("span", { class: "badge" }, (META && META.current_model) || "?"))),
      el("div", { class: "checks" },
        chk("pg-offline", "Offline", true),
        chk("pg-single", "Single agent", d.single),
        chk("pg-llm", "LLM composer", d.llm_composer),
        chk("pg-memory", "Memory", d.memory),
        chk("pg-guard", "Guardrails", d.guardrails),
        chk("pg-critic", "Critic", d.critic),
        chk("pg-super", "Supervisor", d.supervisor)),
      el("div", { class: "row" },
        numField("pg-react", "ReAct steps", d.react_steps || 1),
        numField("pg-vote", "Vote k", d.vote_k || 1)),
      el("div", { style: "margin-top:12px" },
        el("label", null, "Structured output schema (optional JSON Schema)"), schema, schemaErr),
      el("div", { style: "margin-top:14px" }, runBtn)),
    out,
  );
};

function zip(plan, roles) {
  const rows = [];
  for (let i = 0; i < plan.length; i++) {
    rows.push(el("tr", null, el("td", null, String(i)), el("td", null, plan[i]),
      el("td", null, el("span", { class: "chip" }, (roles && roles[i]) || "generalist"))));
  }
  return el("table", null, el("tr", null, el("th", null, "#"), el("th", null, "subtask"), el("th", null, "role")), ...rows);
}

function renderInspector(r) {
  const wrap = el("div");
  // summary
  const sumBadges = [
    el("span", { class: "badge" }, "mode: " + r.mode),
    el("span", { class: r.blocked ? "badge bad" : "badge ok" }, r.blocked ? "blocked" : "allowed"),
    r.success != null ? el("span", { class: r.success ? "badge ok" : "badge warn" }, r.success ? "success" : "needs work") : null,
    el("span", { class: "badge ghost" }, "tools " + r.tool_calls_valid + "/" + r.tool_calls_total),
  ];
  wrap.appendChild(el("div", { class: "card" },
    el("div", { class: "kv" }, ...sumBadges),
    el("h2", null, "Final answer"),
    el("div", null, r.final_answer || "(none)")));

  if (r.plan && r.plan.length) wrap.appendChild(card("Plan & roles", zip(r.plan, r.roles)));
  if (r.swarm_decision && Object.keys(r.swarm_decision).length)
    wrap.appendChild(card("Swarm decision", pre(r.swarm_decision), false));

  if (r.results && r.results.length) {
    const items = r.results.map((res, i) => {
      const tc = (res.tool_calls || []).map((c) => {
        const fn = (c.function || {});
        return el("tr", null, el("td", null, el("span", { class: "chip" }, fn.name || "?")),
          el("td", null, el("span", { class: "muted" }, fn.arguments || "")));
      });
      return el("div", { style: "margin-bottom:12px" },
        el("div", { class: "kv" }, el("span", { class: "chip" }, "#" + i), el("strong", null, res.subtask || "")),
        el("div", null, res.output || ""),
        tc.length ? el("table", null, el("tr", null, el("th", null, "tool"), el("th", null, "arguments")), ...tc) : null);
    });
    wrap.appendChild(card("Worker results", el("div", null, ...items)));
  }

  if (r.verdicts && r.verdicts.length) {
    const rows = r.verdicts.map((v, i) => el("tr", null, el("td", null, String(i)),
      el("td", null, el("span", { class: v.verdict === "pass" ? "badge ok" : "badge bad" }, v.verdict || "?")),
      el("td", null, v.reason || "")));
    wrap.appendChild(card("Critic verdicts",
      el("table", null, el("tr", null, el("th", null, "#"), el("th", null, "verdict"), el("th", null, "reason")), ...rows)));
  }

  if (r.structured) wrap.appendChild(card("Structured output", pre(r.structured)));

  if ((r.recalled_lessons && r.recalled_lessons.length) || (r.stored_lessons && r.stored_lessons.length)) {
    const body = el("div");
    body.appendChild(el("div", { class: "muted" }, "recalled: " + ((r.recalled_lessons || []).length) +
      " · stored: " + ((r.stored_lessons || []).length)));
    (r.recalled_lessons || []).forEach((l) => body.appendChild(el("div", null, "↩ " + l)));
    (r.stored_lessons || []).forEach((l) => body.appendChild(el("div", null, "✎ " + l)));
    wrap.appendChild(card("Memory & lessons", body, false));
  }

  if (r.metrics && Object.keys(r.metrics).length) wrap.appendChild(card("Metrics", pre(r.metrics), false));

  const gv = (r.guard_violations || []).concat(r.guard_violations_out || []);
  if (gv.length) wrap.appendChild(el("div", { class: "card" },
    el("h2", null, "Guardrail violations"),
    el("div", { class: "error" }, gv.join(", "))));

  return wrap;
}

// =================== Sessions ===================
VIEWS.sessions = function () {
  const sid = el("input", { type: "text", id: "s-id", value: "studio-1" });
  const msg = el("textarea", { id: "s-msg", placeholder: "Send a follow-up turn; prior answers are fed back as context." });
  const log = el("div", { id: "s-log" });
  const sendBtn = el("button", { class: "primary" }, "Send");
  const refreshBtn = el("button", { class: "ghost" }, "Load transcript");

  async function loadTranscript() {
    log.innerHTML = "";
    const data = await api("/sessions/" + encodeURIComponent(sid.value));
    if (!data.turns.length) { log.appendChild(el("div", { class: "empty" }, "No turns yet.")); return; }
    data.turns.forEach((t, i) => log.appendChild(el("div", { class: "card" },
      el("div", { class: "kv" }, el("span", { class: "chip" }, "turn " + (i + 1))),
      el("div", null, el("strong", null, "You: "), t.task),
      el("div", null, el("strong", null, "Agent: "), t.answer || "(none)"))));
  }
  sendBtn.onclick = async () => {
    sendBtn.disabled = true;
    try {
      await jpost("/sessions/" + encodeURIComponent(sid.value) + "/messages",
        { task: msg.value, offline: true });
      msg.value = "";
      await loadTranscript();
    } catch (e) { log.appendChild(el("div", { class: "error" }, e.message)); }
    finally { sendBtn.disabled = false; }
  };
  refreshBtn.onclick = loadTranscript;

  view().append(
    header("Sessions", "Multi-turn conversations — each turn sees prior answers."),
    el("div", { class: "card" },
      el("div", { class: "row" }, el("div", { class: "field" }, el("label", null, "Session id"), sid)),
      el("label", { style: "margin-top:12px" }, "Message"), msg,
      el("div", { style: "margin-top:12px; display:flex; gap:10px" }, sendBtn, refreshBtn)),
    log);
};

// =================== Tools ===================
VIEWS.tools = async function () {
  view().append(header("Tools", "The registered tool catalog the workers can call."));
  const grid = el("div", { class: "grid" });
  view().appendChild(grid);
  const tools = await api("/api/tools");
  tools.forEach((t) => grid.appendChild(el("div", { class: "card" },
    el("div", { class: "kv" }, el("strong", null, t.name),
      el("span", { class: "chip" }, "v" + t.version),
      el("span", { class: t.side_effecting ? "badge warn" : "badge ok" },
        t.side_effecting ? "side-effecting" : "read-only")),
    el("div", { class: "muted" }, t.description),
    card("schema", pre(t.json_schema), false))));
};

// =================== Roles ===================
VIEWS.roles = async function () {
  view().append(header("Roles", "Built-in specialist agents and their tool allow-lists."));
  const grid = el("div", { class: "grid" });
  view().appendChild(grid);
  const roles = await api("/api/roles");
  roles.forEach((r) => {
    const chips = (r.tools == null)
      ? [el("span", { class: "chip" }, "all tools")]
      : r.tools.map((t) => el("span", { class: "chip" }, t));
    grid.appendChild(el("div", { class: "card" },
      el("div", { class: "kv" }, el("strong", null, r.name)),
      el("div", null, ...chips),
      el("div", { class: "muted", style: "margin-top:8px; white-space:pre-wrap" }, r.system_prompt)));
  });
};

// =================== Eval ===================
VIEWS.eval = function () {
  const offline = el("input", { type: "checkbox", id: "ev-offline", checked: "checked" });
  const out = el("div", { id: "ev-out" });
  const runBtn = el("button", { class: "primary" }, "Run eval suite");
  runBtn.onclick = async () => {
    runBtn.disabled = true;
    out.innerHTML = "";
    out.appendChild(el("div", { class: "spin" }, "Running suite…"));
    try {
      const rep = await jpost("/api/eval", { offline: offline.checked });
      out.innerHTML = "";
      out.appendChild(el("div", { class: "card" },
        el("div", { class: "kv" },
          el("span", { class: rep.pass_rate === 1 ? "badge ok" : "badge bad" },
            "pass " + rep.n_passed + "/" + rep.n_total),
          el("span", { class: "badge ghost" }, "modes " + JSON.stringify(rep.modes)),
          el("span", { class: "badge ghost" }, "blocked " + rep.blocked),
          el("span", { class: rep.learning_recall ? "badge ok" : "badge warn" },
            "recall " + rep.learning_recall))));
      const rows = rep.results.map((x) => el("tr", null,
        el("td", null, x.task_id),
        el("td", null, el("span", { class: x.passed ? "badge ok" : "badge bad" }, x.passed ? "pass" : "fail")),
        el("td", null, x.mode),
        el("td", null, x.tool_valid_rate == null ? "—" : Math.round(x.tool_valid_rate * 100) + "%"),
        el("td", { class: "muted" }, x.notes || "")));
      out.appendChild(el("div", { class: "card" },
        el("table", null, el("tr", null, el("th", null, "task"), el("th", null, "result"),
          el("th", null, "mode"), el("th", null, "tool valid"), el("th", null, "notes")), ...rows)));
    } catch (e) {
      out.innerHTML = "";
      out.appendChild(el("div", { class: "card" }, el("div", { class: "error" }, e.message)));
    } finally { runBtn.disabled = false; }
  };
  view().append(
    header("Eval", "Run the offline behavioral suite and view the report."),
    el("div", { class: "card" },
      el("label", { class: "check" }, offline, "Offline (deterministic; real model needs an API key)"),
      el("div", { style: "margin-top:12px" }, runBtn)),
    out);
};

// =================== Costs ===================
VIEWS.costs = async function () {
  view().append(header("Costs", "Per-tenant usage and estimated spend."));
  const totals = await api("/api/costs");
  const keys = Object.keys(totals);
  if (!keys.length) { view().appendChild(el("div", { class: "empty" }, "No usage recorded yet. Run a task first.")); return; }
  const rows = keys.map((k) => {
    const t = totals[k];
    return el("tr", null, el("td", null, t.tenant_id), el("td", null, String(t.runs)),
      el("td", null, String(t.actual_tokens || t.est_tokens)),
      el("td", null, "$" + (t.cost_usd || 0).toFixed(4)), el("td", null, String(t.blocked)));
  });
  view().appendChild(el("div", { class: "card" },
    el("table", null, el("tr", null, el("th", null, "tenant"), el("th", null, "runs"),
      el("th", null, "tokens"), el("th", null, "cost"), el("th", null, "blocked")), ...rows)));
};

// --- boot ---
async function boot() {
  document.querySelectorAll(".nav-item").forEach((b) =>
    (b.onclick = () => show(b.dataset.view)));
  try {
    META = await api("/api/meta");
    document.getElementById("meta-model").textContent = "model: " + META.current_model;
    document.getElementById("meta-version").textContent = "v" + META.version;
  } catch (e) {
    META = { defaults: {}, current_model: "?", version: "?" };
  }
  show("playground");
}
boot();
