(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ---------- Tabs ----------
  const tabButtons = $$(".tab-btn");
  const panels = $$("[data-tab-panel]");
  const resultsTitle = $("#resultsTitle");
  const statusEl = $("#status");
  const runBtn = $("#runBtn");
  const resetBtn = $("#resetBtn");
  const form = $("#filtersForm");

  let activeTab = localStorage.getItem("vaxscope_active_tab") || "signals";

  function setStatus(msg, type = "info") {
    statusEl.textContent = msg;
    statusEl.dataset.type = type; // for CSS hooks if wanted
  }

  function setActiveTab(tab) {
    activeTab = tab;
    localStorage.setItem("vaxscope_active_tab", tab);

    tabButtons.forEach((b) => {
      const on = b.dataset.tab === tab;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.classList.toggle("active", on);
    });

    panels.forEach((p) => {
      const on = p.dataset.tabPanel === tab;
      p.hidden = !on;
    });

    const titleMap = {
      signals: "Signals",
      search: "Search",
      onset: "Onset",
      outcomes: "Outcomes",
      trends: "Trends",
    };
    resultsTitle.textContent = titleMap[tab] || "Results";

    const runMap = {
      signals: "Run Signals",
      search: "Run Search",
      onset: "Run Onset",
      outcomes: "Run Outcomes",
      trends: "Run Trends",
    };
    runBtn.textContent = runMap[tab] || "Run";
  }

  tabButtons.forEach((b) => {
    b.addEventListener("click", () => {
      setActiveTab(b.dataset.tab);
      setStatus(`Ready: ${resultsTitle.textContent}.`);
    });
  });

  // ---------- Form -> params helpers ----------
  function pruneEmpty(params) {
    for (const [k, v] of params.entries()) {
      if (v === "" || v == null) params.delete(k);
    }
    return params;
  }

  function baseParamsFromForm() {
    const fd = new FormData(form);
    const params = new URLSearchParams();

    // common filters
    const keys = [
      "year",
      "sex",
      "state",
      "age_min",
      "age_max",
      "serious_only",
      "vax_type",
      "vax_manu",
      "symptom_term",
      "symptom_text",
      "onset_start",
      "onset_end",
    ];
    keys.forEach((k) => params.set(k, (fd.get(k) || "").toString().trim()));

    // signals knobs (harmless for other tabs; only signals endpoint uses them)
    const sKeys = [
      "sort_by",
      "limit",
      "min_count",
      "min_vax_total",
      "min_sym_total",
      "cc",
      "base_id_cap",
    ];
    sKeys.forEach((k) => params.set(k, (fd.get(k) || "").toString().trim()));

    return pruneEmpty(params);
  }

  async function fetchJSON(path, params) {
    const url = `${path}?${params.toString()}`;
    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} for ${url}\n${text}`);
    }
    return res.json();
  }

  function fmtDate(x) {
    if (!x) return "";
    // backend returns isoformat; keep as-is but shorten
    return String(x).replace("T", " ").replace("Z", "");
  }

  function isSeriousRow(d) {
    const flags = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"];
    return flags.some((k) => String(d?.[k] || "").toUpperCase() === "Y");
  }

  // ---------- Render: Signals ----------
  function renderSignals(data) {
    $("#signals_N").textContent = data?.N ?? "0";
    $("#signals_cached").textContent = String(data?.cached ?? "false");
    $("#signals_time").textContent = data?.time_utc ?? "";

    const tbody = $("#signalsTbody");
    tbody.innerHTML = "";

    const rows = data?.rows || [];
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(r.vax_type ?? "")}</td>
        <td>${escapeHtml(r.vax_manu ?? "")}</td>
        <td>${escapeHtml(r.symptom ?? "")}</td>
        <td>${num(r.a)}</td>
        <td>${num(r.b)}</td>
        <td>${num(r.c)}</td>
        <td>${num(r.d)}</td>
        <td>${num(r.prr, 3)}</td>
        <td>${escapeHtml(r.prr_ci ?? "")}</td>
        <td>${num(r.ror, 3)}</td>
        <td>${escapeHtml(r.ror_ci ?? "")}</td>
      `;
      tbody.appendChild(tr);
    }

    setStatus(`Signals loaded: ${rows.length} rows (N=${data?.N ?? 0}).`, "ok");
  }

  // ---------- Render: Search ----------
  function renderSearch(data) {
    $("#search_count").textContent = data?.count ?? "0";
    $("#search_limit").textContent = data?.limit ?? "";
    $("#search_time").textContent = data?.time_utc ?? "";

    const tbody = $("#searchTbody");
    tbody.innerHTML = "";
    const results = data?.results || [];

    for (const d of results) {
      const txt = (d?.SYMPTOM_TEXT || "").toString().replace(/\s+/g, " ").trim();
      const snippet = txt.length > 120 ? txt.slice(0, 120) + "…" : txt;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d?.VAERS_ID ?? "")}</td>
        <td>${escapeHtml(d?.YEAR ?? "")}</td>
        <td>${escapeHtml(d?.SEX ?? "")}</td>
        <td>${escapeHtml(d?.AGE_YRS ?? "")}</td>
        <td>${escapeHtml(d?.STATE ?? "")}</td>
        <td>${escapeHtml(fmtDate(d?.VAX_DATE))}</td>
        <td>${escapeHtml(fmtDate(d?.ONSET_DATE))}</td>
        <td><span class="pill ${isSeriousRow(d) ? "pill-warn" : ""}">${isSeriousRow(d) ? "Y" : ""}</span></td>
        <td title="${escapeHtml(txt)}">${escapeHtml(snippet)}</td>
      `;
      tbody.appendChild(tr);
    }

    setStatus(`Search loaded: ${results.length} rows (count=${data?.count ?? 0}).`, "ok");
  }

  // ---------- Render: Onset ----------
  function renderOnset(data) {
    $("#onset_N").textContent = data?.N_base ?? "0";
    $("#onset_obs").textContent = data?.obs ?? "0";
    $("#onset_time").textContent = data?.time_utc ?? "";

    const summary = $("#onsetSummary");
    const stats = data?.stats || {};
    summary.innerHTML = `
      <div class="pill">min: <b>${num(stats.min)}</b></div>
      <div class="pill">max: <b>${num(stats.max)}</b></div>
      <div class="pill">avg: <b>${num(stats.avg, 2)}</b></div>
    `;

    const chart = $("#onsetChart");
    chart.innerHTML = "";

    const buckets = data?.buckets || [];
    const maxN = Math.max(1, ...buckets.map((b) => b.n || 0));

    for (const b of buckets) {
      const lo = b.lo;
      const hi = b.hi;
      const label = (lo == null || hi == null) ? "—" : `${lo}–${hi}`;
      const w = Math.round(((b.n || 0) / maxN) * 100);

      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <div class="bar-label">${escapeHtml(label)}</div>
        <div class="bar">
          <div class="bar-fill" style="width:${w}%"></div>
        </div>
        <div class="bar-val">${num(b.n)}</div>
      `;
      chart.appendChild(row);
    }

    setStatus(`Onset loaded: ${buckets.length} buckets (obs=${data?.obs ?? 0}).`, "ok");
  }

  // ---------- Render: Outcomes ----------
  function renderOutcomes(data) {
    $("#outcomes_N").textContent = data?.N_base ?? "0";
    $("#outcomes_time").textContent = data?.time_utc ?? "";

    const kpis = $("#outcomesKpis");
    kpis.innerHTML = "";

    const total = data?.total ?? 0;
    const items = data?.outcomes || [];

    for (const it of items) {
      const pct = total > 0 ? (100 * (it.count || 0) / total) : 0;
      const card = document.createElement("div");
      card.className = "kpi";
      card.innerHTML = `
        <div class="kpi-title">${escapeHtml(it.key)}</div>
        <div class="kpi-value">${num(it.count)}</div>
        <div class="kpi-sub">${pct.toFixed(2)}%</div>
      `;
      kpis.appendChild(card);
    }

    setStatus(`Outcomes loaded (total=${total}).`, "ok");
  }

  // ---------- Render: Trends ----------
  function renderTrends(data) {
    $("#trends_N").textContent = data?.N_base ?? "0";
    $("#trends_points").textContent = data?.points ?? "0";
    $("#trends_time").textContent = data?.time_utc ?? "";

    const chart = $("#trendsChart");
    chart.innerHTML = "";

    const series = data?.series || [];
    const maxN = Math.max(1, ...series.map((p) => p.n || 0));

    for (const p of series) {
      const w = Math.round(((p.n || 0) / maxN) * 100);
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <div class="bar-label">${escapeHtml(p.month ?? "")}</div>
        <div class="bar">
          <div class="bar-fill" style="width:${w}%"></div>
        </div>
        <div class="bar-val">${num(p.n)}</div>
      `;
      chart.appendChild(row);
    }

    setStatus(`Trends loaded: ${series.length} months.`, "ok");
  }

  // ---------- Run per tab ----------
  async function runSignals(params) {
    const data = await fetchJSON("/api/signals", params);
    renderSignals(data);
  }

  async function runSearch(params) {
    // Search endpoint expects "limit" already; we reuse the same input.
    const data = await fetchJSON("/api/search", params);
    renderSearch(data);
  }

  async function runOnset(params) {
    // Add panel controls
    const buckets = $("#onset_buckets")?.value || "30";
    const clipMax = $("#onset_clip_max")?.value || "180";
    params.set("buckets", buckets);
    params.set("clip_max_days", clipMax);

    const data = await fetchJSON("/api/onset", params);
    renderOnset(data);
  }

  async function runOutcomes(params) {
    const data = await fetchJSON("/api/outcomes", params);
    renderOutcomes(data);
  }

  async function runTrends(params) {
    const clipMonths = $("#trends_clip_months")?.value || "0";
    params.set("clip_months", clipMonths);

    const data = await fetchJSON("/api/trends", params);
    renderTrends(data);
  }

  async function runActive() {
    const params = baseParamsFromForm();
    setStatus("Loading…", "info");

    try {
      if (activeTab === "signals") return await runSignals(params);
      if (activeTab === "search") return await runSearch(params);
      if (activeTab === "onset") return await runOnset(params);
      if (activeTab === "outcomes") return await runOutcomes(params);
      if (activeTab === "trends") return await runTrends(params);
      setStatus("Unknown tab.", "err");
    } catch (e) {
      console.error(e);
      setStatus(e.message || "Request failed.", "err");
    }
  }

  // ---------- misc ----------
  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function num(x, digits = 0) {
    if (x == null || x === "") return "";
    const n = Number(x);
    if (!Number.isFinite(n)) return String(x);
    return digits ? n.toFixed(digits) : String(n);
  }

  // ---------- events ----------
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    runActive();
  });

  resetBtn.addEventListener("click", () => {
    form.reset();
    setStatus("Filters reset.", "info");
  });

  // ---------- init ----------
  setActiveTab(activeTab);
  setStatus("Ready.");
})();
