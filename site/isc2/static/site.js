// isc-2 site: interactions and live widgets. Plain JavaScript, no external scripts.
//
// Live data comes only from the console under the same origin (/console/api/...). For every widget the order of
// sources is: live answer -> latest saved run (with its date) -> the value baked into the page at build time.
// A failed request never changes the page: the build-time value stays.
(function () {
  "use strict";
  var API = "/console/api";

  // ---- helpers ------------------------------------------------------------------------------------
  function all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function ok(x) { return typeof x === "number" && isFinite(x); }
  function fix(x, nd) {
    return Number(x).toLocaleString("en-US", { minimumFractionDigits: nd, maximumFractionDigits: nd });
  }
  function signed(x, nd) {
    var s = Number(x).toFixed(nd);
    return Number(s) === 0 ? "0" : (x > 0 ? "+" : "") + s;
  }
  function setLive(name, text) {
    all('[data-live="' + name + '"]').forEach(function (el) { el.textContent = text; });
  }
  function dayOf(unixSeconds) { return new Date(unixSeconds * 1000).toISOString().slice(0, 10); }
  function clock() { return new Date().toTimeString().slice(0, 8); }
  function getJSON(path) {
    return fetch(API + path, { headers: { Accept: "application/json" } }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    });
  }
  function sparkPath(values) {
    var v = values.filter(ok);
    if (v.length < 2) { return ""; }
    var lo = Math.min.apply(null, v), hi = Math.max.apply(null, v), span = (hi - lo) || 1, step = 100 / (v.length - 1);
    return "M" + v.map(function (x, i) { return (step * i).toFixed(0) + " " + (30 - 26 * (x - lo) / span).toFixed(0); }).join(" L");
  }
  function setSpark(svg, values) {
    var p = svg && svg.querySelector("path");
    var d = sparkPath(values);
    if (p && d) { p.setAttribute("d", d); }
  }
  var PILL = { live: ["pill live", "live"], saved: ["pill saved", "saved run"], build: ["pill build", "build"] };
  function setPill(container, kind, date) {
    if (!container) { return; }
    all("[data-pill]", container).forEach(function (el) {
      el.className = PILL[kind][0];
      el.textContent = PILL[kind][1] + (date ? " " + date : "");
    });
  }
  function holder(name) {
    var el = document.querySelector('[data-live="' + name + '"]');
    return el && (el.closest(".widget") || el.closest("section"));
  }
  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (k) { el.appendChild(typeof k === "string" ? document.createTextNode(k) : k); });
    return el;
  }
  function safeLink(url, label) {
    if (!/^https?:\/\//.test(url)) { return document.createTextNode(label); }
    return h("a", { href: url, target: "_blank", rel: "noopener" }, [label]);
  }
  var savedRuns = null;
  function latestRuns() {
    if (savedRuns) { return savedRuns; }
    savedRuns = getJSON("/runs").catch(function () { return []; });
    return savedRuns;
  }

  // ---- pickers, concurrency slider, incident filter ------------------------------------------------
  all("[data-picker]").forEach(function (group) {
    var controls = all("[data-show]", group);
    function show(key) {
      controls.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.show === key)); });
      all("[data-panel]", group).forEach(function (p) { p.hidden = p.dataset.panel !== key; });
    }
    controls.forEach(function (c) {
      c.addEventListener("click", function () { show(c.dataset.show); });
      c.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(c.dataset.show); }
      });
    });
    if (controls.length) { show(controls[0].dataset.show); }
  });

  var slider = document.getElementById("conc");
  if (slider) {
    var levels = JSON.parse(slider.getAttribute("data-levels") || "[]");
    var updateSlider = function () {
      var r = levels[Number(slider.value)];
      if (!r) { return; }
      var f = levels[0];
      all("[data-conc]").forEach(function (el) { el.textContent = r.c; });
      all(".bars rect[data-c]").forEach(function (b) { b.classList.toggle("on", Number(b.dataset.c) === r.c); });
      var cells = {
        tps: fix(r.tps, 1), tpsx: fix(r.tps / f.tps, 1) + " x",
        ttft: fix(r.ttft, 2) + " s", ttftd: signed(r.ttft - f.ttft, 2) + " s",
        cost: fix(r.cost, 2) + " USD", costd: signed((r.cost / f.cost - 1) * 100, 0) + " %"
      };
      Object.keys(cells).forEach(function (k) {
        all('[data-f="' + k + '"]').forEach(function (el) { el.textContent = cells[k]; });
      });
    };
    slider.addEventListener("input", updateSlider);
    updateSlider();
  }

  var filters = all("[data-layer-filter]");
  filters.forEach(function (f) {
    f.addEventListener("click", function () {
      var layer = f.dataset.layerFilter;
      filters.forEach(function (x) { x.setAttribute("aria-pressed", String(x === f)); });
      all(".card[data-layer]").forEach(function (card) {
        card.hidden = layer !== "all" && card.dataset.layer !== layer;
      });
    });
  });

  // ---- strip of page 1 and home widget 1: /api/stream (live while a run is active), else the latest run ----
  var stripBox = holder("strip-running"), w1Box = holder("w1-tps");
  if (stripBox || w1Box) {
    var tpsSeries = [];
    var showSaved = function () {
      latestRuns().then(function (runs) {
        var run = runs.filter(function (r) { return r.summary; })[0];
        if (!run) { return; }
        var s = run.summary, date = dayOf(run.finished_at);
        if (ok(s.tokens_per_second)) { setLive("strip-tps", fix(s.tokens_per_second, 1)); setLive("w1-tps", fix(s.tokens_per_second, 1)); }
        if (ok(s.gpu_util_avg)) { setLive("strip-gpu", fix(s.gpu_util_avg, 0)); }
        if (ok(s.ttft_p95_s)) { setLive("w1-ttft", fix(s.ttft_p95_s, 2)); }
        setLive("strip-date", date);
        setPill(stripBox, "saved", date);
        setPill(w1Box, "saved", date);
      });
    };
    var wasActive = false;
    showSaved();
    if (window.EventSource) {
      var es = new EventSource(API + "/stream");
      es.onmessage = function (ev) {
        var t;
        try { t = JSON.parse(ev.data); } catch (e) { return; }
        var active = !!(t && t.run && t.run.active);
        if (!active) {
          if (wasActive) { savedRuns = null; showSaved(); }
          wasActive = false;
          return;
        }
        wasActive = true;
        var tps = ok(t.server_tokens_per_s) ? t.server_tokens_per_s : null;
        if (ok(t.vllm_running)) { setLive("strip-running", fix(t.vllm_running, 0)); setLive("w1-running", fix(t.vllm_running, 0)); }
        if (ok(t.vllm_waiting)) { setLive("strip-waiting", fix(t.vllm_waiting, 0)); }
        if (ok(t.kv_cache_pct)) { setLive("strip-kv", fix(t.kv_cache_pct, 0)); setLive("w1-kv", fix(t.kv_cache_pct, 0)); }
        if (ok(t.gpu_util)) { setLive("strip-gpu", fix(t.gpu_util, 0)); }
        if (tps !== null) {
          setLive("strip-tps", fix(tps, 1)); setLive("w1-tps", fix(tps, 1));
          tpsSeries.push(tps);
          if (tpsSeries.length > 30) { tpsSeries.shift(); }
          setSpark(document.querySelector('[data-live="w1-spark"]'), tpsSeries);
        }
        if (ok(t.run.ttft_p95_s)) { setLive("w1-ttft", fix(t.run.ttft_p95_s, 2)); }
        setPill(stripBox, "live");
        setPill(w1Box, "live");
      };
    }
  }

  // ---- health of page 2 and home widget 2: /api/status?view=health --------------------------------------
  var healthBox = holder("health-checked"), w2Box = holder("w2-up");
  if (healthBox || w2Box) {
    var health = function () {
      getJSON("/status?view=health").then(function (d) {
        if (!d || d.error) { return; }
        var state = { vllm: d.vllm, gpu: d.gpu, gateway: d.gateway, console: d.console,
                      prometheus: d.prometheus === true ? "up" : (d.prometheus === false ? "down" : "unknown") };
        var up = 0;
        Object.keys(state).forEach(function (k) {
          if (state[k] === "up") { up += 1; }
          all('[data-health="' + k + '"]').forEach(function (el) {
            el.textContent = state[k];
            el.className = "pill " + (state[k] === "up" ? "live" : (state[k] === "down" ? "firing" : "inactive"));
          });
        });
        setLive("health-checked", clock());
        setLive("w2-up", String(up));
        setPill(healthBox, "live");
        setPill(w2Box, "live");
      }).catch(function () {});
    };
    health();
    setInterval(health, 15000);
  }

  // ---- teams of page 3 and home widget 3: /api/status?view=teams, idle -> latest saved run of the team ----
  var TEAMS = ["research", "engineering", "operations"];
  var teamsBox = document.querySelector("[data-team-f]") && (document.querySelector("[data-team-f]").closest("section")),
      w3Box = holder("w3-tps");
  if (teamsBox || w3Box) {
    var teams = function () {
      getJSON("/status?view=teams").then(function (rows) {
        if (!Array.isArray(rows)) { return null; }
        var by = {};
        rows.forEach(function (r) { by[r.team] = r; });
        var busy = rows.some(function (r) { return ok(r.requests_per_s) && r.requests_per_s > 0; });
        if (busy) { return { source: "live", by: by }; }
        return null;
      }).catch(function () { return null; }).then(function (live) {
        if (live) { return live; }
        return latestRuns().then(function (runs) {
          var by = {};
          TEAMS.forEach(function (t) {
            var run = runs.filter(function (r) { return r.summary && r.params && r.params.tenant === t; })[0];
            if (run) {
              by[t] = { requests_per_s: run.summary.requests_per_second, tokens_per_s: run.summary.tokens_per_second,
                        date: dayOf(run.finished_at) };
            }
          });
          return Object.keys(by).length ? { source: "saved", by: by } : null;
        });
      }).then(function (res) {
        if (!res) { return; }
        var total = 0, date = null;
        TEAMS.forEach(function (t) {
          var r = res.by[t];
          if (!r) { return; }
          date = r.date || date;
          total += ok(r.tokens_per_s) ? r.tokens_per_s : 0;
          all('[data-team-f="' + t + '.rps"]').forEach(function (el) { el.textContent = fix(r.requests_per_s || 0, 2); });
          all('[data-team-f="' + t + '.tps"]').forEach(function (el) { el.textContent = fix(r.tokens_per_s || 0, 0); });
          setLive("w3-" + t, fix(r.requests_per_s || 0, 2) + " req/s");
        });
        setLive("w3-tps", fix(total, 0));
        setPill(teamsBox, res.source === "live" ? "live" : "saved", res.source === "saved" ? date : null);
        setPill(w3Box, res.source === "live" ? "live" : "saved", res.source === "saved" ? date : null);
      });
    };
    teams();
    setInterval(teams, 5000);
  }

  // ---- evaluation board of page 4 and home widget 4: /api/agent/eval (the saved evaluation run) ---------
  var evalBox = holder("eval-hit"), w4Box = holder("w4-hit"), rowsBox = document.getElementById("eval-rows");
  if (evalBox || w4Box) {
    var evalRow = function (r) {
      var good = r.kind === "blog" ? r.hit : r.tool_ok;
      var label = r.kind === "blog" ? (good ? "hit" : "miss") : (good ? "tool ok" : "wrong tool");
      var src = h("span", {}, ["Sources cited: "]);
      var list = r.sources || [];
      if (!list.length) { src.appendChild(document.createTextNode("none")); }
      list.forEach(function (s, i) {
        if (i) { src.appendChild(document.createTextNode(", ")); }
        src.appendChild(safeLink(s.url, s.title));
      });
      var detail = [h("span", {}, ["First tool: ", h("code", {}, [r.first_tool || "none"])]), src,
                    h("span", {}, ["Claims supported: " + r.claims_supported + " of " + r.claims_total]),
                    h("span", {}, ["Answer: " + (r.answer || "")])];
      if (r.judge_error) { detail.push(h("span", {}, ["Judge error: " + r.judge_error])); }
      return h("details", { "class": "row" }, [
        h("summary", {}, [h("span", { "class": "q" }, [r.id + " \u00b7 " + r.question]),
                          h("span", { "class": "pill " + (good ? "live" : "firing") }, [label]),
                          h("span", {}, [fix(r.latency_s, 1) + " s"])]),
        h("div", {}, detail)]);
    };
    getJSON("/agent/eval").then(function (d) {
      var s = d.summary, ch = d.chunking, date = (d.finished || d.started || "").slice(0, 16);
      var map = {
        "eval-hit": String(s.hits), "eval-tool": String(s.tool_ok), "eval-claims-ok": String(s.claims_supported),
        "eval-claims-total": String(s.claims_total), "eval-p95": fix(s.latency_p95_s, 1) + " s",
        "eval-usd": fix(s.usd_per_1k_questions, 2) + " USD", "eval-date": date,
        "w4-hit": String(s.hits), "w4-tool": String(s.tool_ok), "w4-claims-ok": String(s.claims_supported),
        "w4-claims-total": String(s.claims_total), "w4-p95": fix(s.latency_p95_s, 1),
        "w4-usd": fix(s.usd_per_1k_questions, 2), "w4-date": date
      };
      if (ch) {
        map["eval-ch-kind-chunks"] = String(ch.kind.chunks);
        map["eval-ch-kind-hits"] = ch.kind.hits + " of " + ch.blog_total;
        map["eval-ch-fixed-chunks"] = String(ch.fixed.chunks);
        map["eval-ch-fixed-hits"] = ch.fixed.hits + " of " + ch.blog_total;
      }
      Object.keys(map).forEach(function (k) { setLive(k, map[k]); });
      setLive("eval-note", "read from the console now");
      if (rowsBox && Array.isArray(d.rows) && d.rows.length) {
        while (rowsBox.firstChild) { rowsBox.removeChild(rowsBox.firstChild); }
        d.rows.forEach(function (r) { rowsBox.appendChild(evalRow(r)); });
      }
      setPill(evalBox, "saved");
      setPill(w4Box, "saved");
    }).catch(function () {});
  }

  // ---- signals and alerts of page 5 and home widget 5: /api/status?view=signals and ?view=alerts -------
  var sigBox = document.querySelector("[data-sig]") && document.querySelector("[data-sig]").closest("section"),
      alertBox = holder("alerts-checked"), w5Box = holder("w5-firing");
  if (sigBox || alertBox || w5Box) {
    var alerts = function () {
      getJSON("/status?view=alerts").then(function (rows) {
        if (!Array.isArray(rows)) { return; }
        var firing = 0;
        rows.forEach(function (r) {
          if (r.state === "firing") { firing += 1; }
          all('tr[data-rule="' + r.name + '"]').forEach(function (tr) {
            var pill = tr.querySelector("[data-state]"), cell = tr.querySelector("[data-value]");
            pill.textContent = r.state;
            pill.className = "pill " + (r.state === "firing" ? "firing" : (r.state === "pending" ? "saved" : "inactive"));
            if (ok(r.value)) { cell.textContent = Number.isInteger(r.value) ? String(r.value) : fix(r.value, 2); }
            else { cell.innerHTML = "&mdash;"; }
          });
          if (r.name === "ModelQueueBuildingUp" && ok(r.value)) { setLive("w5-queue", fix(r.value, 0)); }
        });
        setLive("w5-firing", String(firing));
        setLive("alerts-checked", clock());
        setPill(alertBox, "live");
        setPill(w5Box, "live");
      }).catch(function () {});
    };
    var signals = function () {
      getJSON("/status?view=signals").then(function (d) {
        if (!d || d.error) { return null; }
        var usage = d.usage && d.usage.value;
        if (ok(usage) && usage > 0) { return { source: "live", d: d }; }
        return null;
      }).catch(function () { return null; }).then(function (live) {
        if (live) { return live; }
        // idle: the latest saved run stands in for the five numbers
        return latestRuns().then(function (runs) {
          var run = runs.filter(function (r) { return r.summary; })[0];
          if (!run) { return null; }
          var s = run.summary, errs = 0, err5 = 0;
          Object.keys(s.errors || {}).forEach(function (code) {
            errs += s.errors[code];
            if (code.charAt(0) === "5") { err5 += s.errors[code]; }
          });
          var req = s.requests || 1;
          return { source: "saved", date: dayOf(run.finished_at), d: {
            reliability: { value: 100 * (1 - err5 / req) }, latency: { value: s.ttft_p95_s },
            usage: { value: s.tokens_per_second }, errors: { value: 100 * errs / req },
            cost: { value: s.usd_per_million_tokens } } };
        });
      }).then(function (res) {
        if (!res) { return; }
        var d = res.d, fmt = { reliability: [1, " %"], latency: [2, " s"], usage: [0, ""], errors: [1, " %"], cost: [2, " USD"] };
        Object.keys(fmt).forEach(function (k) {
          var v = d[k] && d[k].value;
          if (!ok(v)) { return; }
          all('[data-sig="' + k + '"]').forEach(function (el) { el.textContent = fix(v, fmt[k][0]) + fmt[k][1]; });
          var tile = document.querySelector('[data-sig="' + k + '"]');
          tile = tile && tile.closest(".tile");
          if (tile && res.source === "live") { setSpark(tile.querySelector("svg.spark"), (d[k].series || []).map(function (p) { return p[1]; })); }
        });
        if (ok(d.errors && d.errors.value)) { setLive("w5-err", fix(d.errors.value, 1)); }
        if (ok(d.cost && d.cost.value)) { setLive("w5-cost", fix(d.cost.value, 2)); }
        if (res.source === "live") { setSpark(document.querySelector('[data-live="w5-spark"]'), (d.usage.series || []).map(function (p) { return p[1]; })); }
        setPill(sigBox, res.source === "live" ? "live" : "saved", res.source === "saved" ? res.date : null);
      });
    };
    alerts();
    signals();
    setInterval(alerts, 15000);
    setInterval(signals, 15000);
  }

  // ---- ask the agent (page 4): POST /api/agent/ask as the team research ------------------------------------
  var form = document.getElementById("ask-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("ask-input"), out = document.getElementById("ask-out");
      var steps = document.getElementById("ask-steps"), button = form.querySelector("button");
      var question = input.value.trim();
      if (!question) { return; }
      out.hidden = false;
      document.getElementById("ask-q").textContent = question;
      while (steps.firstChild) { steps.removeChild(steps.firstChild); }
      steps.appendChild(h("div", {}, ["Asking the agent ..."]));
      button.disabled = true;
      fetch(API + "/agent/ask", {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ tenant: "research", question: question })
      }).then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      }).then(function (d) {
        while (steps.firstChild) { steps.removeChild(steps.firstChild); }
        (d.steps || []).forEach(function (s, i) {
          var res = s.result, text;
          if (Array.isArray(res)) { text = res.length + " results"; }
          else if (res && res.error) { text = "error: " + res.error; }
          else { text = JSON.stringify(res).slice(0, 160); }
          steps.appendChild(h("div", {}, [h("span", { "class": "pill build" }, ["step " + (i + 1)]), " ",
                                          h("code", {}, [s.tool + "(" + JSON.stringify(s.args || {}) + ")"]), " \u2192 " + text]));
        });
        steps.appendChild(h("div", {}, [h("b", {}, ["Answer."]), " " + (d.answer || "(empty)")]));
        var srcs = h("div", {}, ["Sources: "]);
        var list = d.sources || [];
        if (!list.length) { srcs.appendChild(document.createTextNode("none")); }
        list.forEach(function (s, i) {
          if (i) { srcs.appendChild(document.createTextNode(" \u00b7 ")); }
          srcs.appendChild(safeLink(s.url, s.title));
        });
        steps.appendChild(srcs);
        steps.appendChild(h("div", { "class": "src" }, [
          h("span", {}, [fix(d.latency_s || 0, 1) + " s"]),
          h("span", {}, [(d.prompt_tokens || 0) + " prompt + " + (d.completion_tokens || 0) + " completion tokens"]),
          h("span", {}, [(d.rounds || 0) + " rounds of 3"]), h("span", {}, ["accounted to team research"])]));
      }).catch(function (err) {
        while (steps.firstChild) { steps.removeChild(steps.firstChild); }
        steps.appendChild(h("div", {}, ["The agent could not answer (" + err.message + "). Try again in a moment."]));
      }).then(function () { button.disabled = false; });
    });
  }
})();
