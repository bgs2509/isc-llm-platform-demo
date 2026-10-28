const $ = id => document.getElementById(id);
const N = 120;
const hist = {tps: [], srv: [], p50: [], p95: [], gpu: [], kv: [], inflight: [], running: [], waiting: []};
let lastActive = false;
let runsCache = [];

const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const fmt = (x, d = 1) => x == null ? "–" : (Math.abs(x) >= 100 ? x.toFixed(0) : x.toFixed(d));
const push = (k, v) => { hist[k].push(v == null ? null : v); if (hist[k].length > N) hist[k].shift(); };

function line(canvas, series, max) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext("2d");
  g.scale(dpr, dpr);
  const pad = {l: 38, r: 6, t: 6, b: 6};
  if (max == null) {
    max = 0;
    for (const s of series) for (const v of s.data) if (v != null && v > max) max = v;
    max = max > 0 ? max * 1.15 : 1;
  }
  g.font = "11px system-ui";
  g.strokeStyle = css("--grid"); g.fillStyle = css("--muted");
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + (h - pad.t - pad.b) * i / 4;
    g.beginPath(); g.moveTo(pad.l, y); g.lineTo(w - pad.r, y); g.stroke();
    g.fillText(fmt(max * (1 - i / 4), max < 10 ? 1 : 0), 2, y + 4);
  }
  let lx = pad.l + 4;
  for (const s of series) {
    g.strokeStyle = s.color; g.lineWidth = 2; g.beginPath();
    let started = false;
    const off = N - s.data.length;
    s.data.forEach((v, i) => {
      if (v == null) { started = false; return; }
      const x = pad.l + (w - pad.l - pad.r) * (i + off) / (N - 1);
      const y = pad.t + (h - pad.t - pad.b) * (1 - Math.min(v, max) / max);
      if (!started) { g.moveTo(x, y); started = true; } else g.lineTo(x, y);
    });
    g.stroke();
    g.fillStyle = s.color; g.fillRect(lx, h - 12, 10, 3);
    g.fillStyle = css("--muted"); g.fillText(s.label, lx + 14, h - 8);
    lx += 14 + g.measureText(s.label).width + 12;
  }
}

function draw() {
  line($("cTps"), [{data: hist.tps, color: css("--c1"), label: "this run"},
                   {data: hist.srv, color: css("--c2"), label: "model total"}]);
  line($("cTtft"), [{data: hist.p50, color: css("--c3"), label: "p50"},
                    {data: hist.p95, color: css("--c4"), label: "p95"}]);
  line($("cGpu"), [{data: hist.gpu, color: css("--c1"), label: "GPU %"},
                   {data: hist.kv, color: css("--c2"), label: "KV cache %"}], 100);
  line($("cReq"), [{data: hist.inflight, color: css("--c1"), label: "in flight"},
                   {data: hist.running, color: css("--c3"), label: "running"},
                   {data: hist.waiting, color: css("--c4"), label: "waiting"}]);
}

function onTick(t) {
  const r = t.run || {active: false};
  push("tps", r.active ? r.tokens_per_s : null);
  push("srv", t.server_tokens_per_s);
  push("p50", r.active ? r.ttft_p50_s : null);
  push("p95", r.active ? r.ttft_p95_s : null);
  push("gpu", t.gpu_util); push("kv", t.kv_cache_pct);
  push("inflight", r.active ? r.in_flight : null);
  push("running", t.vllm_running); push("waiting", t.vllm_waiting);
  $("kGpu").textContent = fmt(t.gpu_util, 0);
  $("kKv").textContent = fmt(t.kv_cache_pct);
  $("kRun").textContent = `${fmt(t.vllm_running, 0)} / ${fmt(t.vllm_waiting, 0)}`;
  $("kTps").textContent = r.active ? fmt(r.tokens_per_s) : "–";
  $("kTtft").textContent = r.active ? fmt(r.ttft_p95_s, 2) : "–";
  $("kReq").textContent = r.id ? `${r.ok} / ${r.failed} / ${r.cache_hits}` : "–";
  const st = $("runstate");
  if (r.active) { st.textContent = `running ${fmt(r.elapsed_s, 0)} / ${r.duration_s} s`; st.className = "pill run"; }
  else { st.textContent = "idle"; st.className = "pill off"; }
  $("run").disabled = !!r.active;
  if (lastActive && !r.active) loadRuns();
  lastActive = !!r.active;
  draw();
}

function connect() {
  const es = new EventSource("api/stream");
  es.onopen = () => { $("conn").textContent = "live"; $("conn").className = "pill on"; };
  es.onmessage = e => onTick(JSON.parse(e.data));
  es.onerror = () => { $("conn").textContent = "reconnecting…"; $("conn").className = "pill off"; };
}

async function loadConfig() {
  const c = await (await fetch("api/config")).json();
  $("model").textContent = c.model;
  $("tenant").innerHTML = c.tenants.map(t => `<option>${t}</option>`).join("");
}

for (const [id, out] of [["concurrency", "vConc"], ["duration", "vDur"], ["maxtokens", "vTok"]]) {
  $(id).addEventListener("input", () => { $(out).textContent = $(id).value; });
}

$("run").addEventListener("click", async () => {
  $("runmsg").textContent = "";
  const body = {
    tenant: $("tenant").value, concurrency: +$("concurrency").value, duration_s: +$("duration").value,
    max_tokens: +$("maxtokens").value, shape: $("shape").value, gpu_usd_per_hour: +$("price").value,
  };
  const r = await fetch("api/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) $("runmsg").textContent = `Could not start: ${(await r.json()).detail || r.status}`;
});
$("stop").addEventListener("click", () => fetch("api/runs/stop", {method: "POST"}));

async function label(id, value) {
  await fetch(`api/runs/${id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({label: value})});
  loadRuns();
}
window.label = label;

async function loadRuns() {
  runsCache = await (await fetch("api/runs")).json();
  const rows = runsCache.map(r => {
    const s = r.summary, p = r.params;
    const errs = Object.entries(s.errors).map(([k, v]) => `${k}×${v}`).join(" ") || "0";
    return `<tr><td>${r.id}</td><td>${p.tenant}</td><td>${p.concurrency}</td><td>${p.shape}</td>
      <td>${fmt(s.tokens_per_second)}</td><td>${fmt(s.ttft_p95_s, 2)}</td><td>${fmt(s.gpu_util_avg, 0)}</td>
      <td>${s.usd_per_million_tokens == null ? "–" : s.usd_per_million_tokens.toFixed(2)}</td><td>${errs}</td>
      <td>${r.label || ""} <button onclick="label('${r.id}','before')">before</button>
      <button onclick="label('${r.id}','after')">after</button></td></tr>`;
  });
  document.querySelector("#runs tbody").innerHTML = rows.join("") || `<tr><td colspan="10">No runs yet.</td></tr>`;
  const opts = runsCache.map(r => `<option value="${r.id}">${r.label ? r.label + " · " : ""}${r.id} · conc ${r.params.concurrency} · ${r.params.shape}</option>`).join("");
  for (const id of ["cmpA", "cmpB"]) { const prev = $(id).value; $(id).innerHTML = opts; if (prev) $(id).value = prev; }
  const before = runsCache.find(r => r.label === "before"), after = runsCache.find(r => r.label === "after");
  if (before && after) { $("cmpA").value = before.id; $("cmpB").value = after.id; }
  compare();
}

function compare() {
  const a = runsCache.find(r => r.id === $("cmpA").value), b = runsCache.find(r => r.id === $("cmpB").value);
  if (!a || !b) { $("compare").innerHTML = "<p class='hint'>Run a test, label two runs «before» and «after», or pick any two.</p>"; return; }
  const rows = [
    ["Output tokens per second", "tokens_per_second", 1, 1],
    ["Time to first token p95, s", "ttft_p95_s", -1, 2],
    ["Request latency p95, s", "latency_p95_s", -1, 2],
    ["GPU utilization, average %", "gpu_util_avg", 1, 0],
    ["USD per 1M output tokens", "usd_per_million_tokens", -1, 2],
    ["Requests ok", "ok", 1, 0],
    ["Cache hits", "cache_hits", 1, 0],
  ].map(([name, key, better, d]) => {
    const x = a.summary[key], y = b.summary[key];
    let delta = "–", cls = "";
    if (x != null && y != null && x !== 0) {
      const pct = (y - x) / x * 100;
      delta = `${pct > 0 ? "+" : ""}${pct.toFixed(0)} % vs A`;
      cls = pct * better > 0 ? "good" : (pct * better < 0 ? "bad" : "");
    }
    return `<tr><td>${name}</td><td>${fmt(x, d)}</td><td>${fmt(y, d)}</td><td class="${cls}">${delta}</td></tr>`;
  });
  $("compare").innerHTML = `<table><thead><tr><th>Metric</th><th>A</th><th>B</th><th>Change of B</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}
$("cmpA").addEventListener("change", compare);
$("cmpB").addEventListener("change", compare);

window.addEventListener("resize", draw);
loadConfig().then(loadRuns);
connect();
draw();
