// ---------- Autocomplete Component (Hybrid) ----------
class Autocomplete {
  constructor(inputElement, options = {}) {
    this.input = inputElement;
    this.options = options;
    this.debounceTimer = null;
    this.selectedIndex = -1;
    this.isLoading = false;
    this.data = [];

    this.init();
  }

  init() {
    const wrapper = document.createElement("div");
    wrapper.className = "autocomplete-wrapper";
    this.input.parentNode.insertBefore(wrapper, this.input);
    wrapper.appendChild(this.input);

    this.dropdown = document.createElement("div");
    this.dropdown.className = "autocomplete-dropdown";
    wrapper.appendChild(this.dropdown);

    this.input.addEventListener("input", this.handleInput.bind(this));
    this.input.addEventListener("keydown", this.handleKeydown.bind(this));
    this.input.addEventListener("focus", this.handleFocus.bind(this));

    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) this.hideDropdown();
    });
  }

  handleFocus() {
    if (this.input.value.trim() === "") {
      this.fetchSuggestions("");
    } else {
      this.fetchSuggestions(this.input.value.trim());
    }
  }

  handleInput(e) {
    const value = e.target.value.trim();
    if (this.debounceTimer) clearTimeout(this.debounceTimer);
    if (value === "") {
      this.fetchSuggestions("");
      return;
    }
    this.debounceTimer = setTimeout(() => {
      this.fetchSuggestions(value);
    }, 200);
  }

  async fetchSuggestions(query) {
    if (!this.options.apiEndpoint) return;
    this.isLoading = true;
    if(query.length > 0) this.showLoading();

    try {
      const url = `${this.options.apiEndpoint}?q=${encodeURIComponent(query)}&limit=50`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("API Error");
      const json = await res.json();
      this.data = json.values || json.options || [];
      this.renderDropdown();
    } catch (err) {
      console.error(err);
      this.data = [];
      this.hideDropdown();
    } finally {
      this.isLoading = false;
    }
  }

  renderDropdown() {
    this.dropdown.innerHTML = "";
    this.selectedIndex = -1;

    if (this.data.length === 0) {
      if (this.input.value.trim().length > 0) {
        const noRes = document.createElement("div");
        noRes.className = "autocomplete-no-results";
        noRes.textContent = "No matches found";
        this.dropdown.appendChild(noRes);
        this.showDropdown();
      } else {
        this.hideDropdown();
      }
    } else {
      this.data.forEach((item) => {
        const div = document.createElement("div");
        div.className = "autocomplete-item";
        div.textContent = item;
        div.addEventListener("click", () => this.selectItem(item));
        this.dropdown.appendChild(div);
      });
      this.showDropdown();
    }
  }

  showLoading() { }

  showDropdown() { this.dropdown.classList.add("show"); }
  hideDropdown() { this.dropdown.classList.remove("show"); }

  handleKeydown(e) {
    if (!this.dropdown.classList.contains("show")) return;
    const items = this.dropdown.querySelectorAll(".autocomplete-item");
    if (!items.length) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
        this.updateSelection(items);
        break;
      case "ArrowUp":
        e.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
        this.updateSelection(items);
        break;
      case "Enter":
        e.preventDefault();
        if (this.selectedIndex >= 0) this.selectItem(this.data[this.selectedIndex]);
        break;
      case "Escape":
        this.hideDropdown();
        break;
    }
  }

  updateSelection(items) {
    items.forEach((item, i) => {
      item.classList.toggle("highlighted", i === this.selectedIndex);
    });
    if (this.selectedIndex >= 0) items[this.selectedIndex].scrollIntoView({ block: "nearest" });
  }

  selectItem(val) {
    this.input.value = val;
    this.hideDropdown();
    this.input.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const tabButtons = $$(".tab-btn");
  const panels = $$("[data-tab-panel]");
  const resultsTitle = $("#resultsTitle");
  const statusEl = $("#status");
  const runBtn = $("#runBtn");
  const resetBtn = $("#resetBtn");
  const form = $("#filtersForm");

  let activeTab = localStorage.getItem("vaxscope_active_tab") || "signals";
  let trendsChartType = localStorage.getItem("vaxscope_trends_chart_type") || "hbar";
  let onsetChartType = localStorage.getItem("vaxscope_onset_chart_type") || "hbar";

  function setStatus(msg, type = "info") {
    statusEl.textContent = msg;
    statusEl.dataset.type = type;
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

    const filterFields = $$('[data-tabs]');
    filterFields.forEach(el => {
      const allowedTabs = el.dataset.tabs.split(',').map(t => t.trim());
      el.style.display = allowedTabs.includes(tab) ? '' : 'none';
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

  // ---------- Helpers ----------

  function escapeHtml(s) {
    return String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function num(x, digits = 0) {
    if (x == null || x === "") return "";
    const n = Number(x);
    if (!Number.isFinite(n)) return String(x);
    return digits ? n.toFixed(digits) : String(n);
  }

  function fmtDate(x) {
    if (!x) return "";
    return String(x).replace("T", " ").replace("Z", "");
  }

  function isSeriousRow(d) {
    const flags = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"];
    return flags.some((k) => String(d?.[k] || "").toUpperCase() === "Y");
  }

  function pruneEmpty(params) {
    for (const [k, v] of params.entries()) {
      if (v === "" || v == null) params.delete(k);
    }
    return params;
  }

  function baseParamsFromForm() {
    const fd = new FormData(form);
    const params = new URLSearchParams();
    const keys = [
      "year", "sex", "state", "age_min", "age_max",
      "serious_only", "died", "hospital",
      "vax_type", "vax_manu", "symptom_term",
      "limit", "onset_start", "onset_end",
      "onset_days_min", "onset_days_max",
    ];
    keys.forEach((k) => params.set(k, (fd.get(k) || "").toString().trim()));
    const sKeys = ["sort_by", "min_count", "min_vax_total", "min_sym_total", "cc", "base_id_cap"];
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

  // ---------- Render Functions ----------

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

  function renderSearch(data) {
    $("#search_count").textContent = data?.count ?? "0";
    $("#search_limit").textContent = data?.limit ?? "";
    $("#search_time").textContent = data?.time_utc ?? "";
    const tbody = $("#searchTbody");
    tbody.innerHTML = "";
    const results = data?.results || [];

    const normArr = (x) => (x == null ? [] : (Array.isArray(x) ? x.map(String).filter(Boolean) : [String(x).trim()]));
    const listPreview = (arr) => {
      const a = normArr(arr);
      return { preview: a.slice(0,3).join("; ") + (a.length>3?"...":""), full: a.join("; ") };
    };
    const clipText = (x, max=80) => {
      const s = (x??"").toString().replace(/\s+/g," ").trim();
      return { preview: s.length>max ? s.slice(0,max)+"…" : s, full: s };
    };

    for (const d of results) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d?.VAERS_ID ?? "")}</td>
        <td>${escapeHtml(d?.RECVDATE_YEAR ?? d?.YEAR ?? "")}</td>
        <td>${escapeHtml(d?.SEX ?? "")}</td>
        <td>${escapeHtml(d?.AGE_YRS ?? "")}</td>
        <td>${escapeHtml(d?.STATE ?? "")}</td>
        <td>${escapeHtml(fmtDate(d?.VAX_DATE))}</td>
        <td>${escapeHtml(fmtDate(d?.ONSET_DATE))}</td>
        <td>${escapeHtml(d?.ONSET_DAYS ?? "")}</td>
        <td><span class="pill ${isSeriousRow(d) ? "pill-warn" : ""}">${isSeriousRow(d) ? "Y" : ""}</span></td>
        <td title="${escapeHtml(listPreview(d?.VAX_TYPES).full)}">${escapeHtml(listPreview(d?.VAX_TYPES).preview)}</td>
        <td title="${escapeHtml(listPreview(d?.VAX_MANUS).full)}">${escapeHtml(listPreview(d?.VAX_MANUS).preview)}</td>
        <td title="${escapeHtml(listPreview(d?.SYMPTOM_TERMS).full)}">${escapeHtml(listPreview(d?.SYMPTOM_TERMS).preview)}</td>
        <td title="${escapeHtml(clipText(d?.SYMPTOM_TEXT, 120).full)}">${escapeHtml(clipText(d?.SYMPTOM_TEXT, 120).preview)}</td>
      `;
      tbody.appendChild(tr);
    }
    setStatus(`Search loaded: ${results.length} rows (count=${data?.count ?? 0}).`, "ok");
  }

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

    if (typeof window !== "undefined") window._onsetLastData = data;
    const chart = $("#onsetChart");
    if (!chart) return;
    chart.innerHTML = "";

    const days = data?.days || [];
    if (!days.length) {
      chart.textContent = "No onset data for current filters.";
      setStatus(`Onset loaded: 0 days (obs=${data?.obs ?? 0}).`, "ok");
      return;
    }
    const maxN = Math.max(1, ...days.map((b) => b.n || 0));
    const type = onsetChartType || "hbar";
    chart.className = "bars";
    chart.classList.remove("bars-vertical", "line-chart");
    if (type === "vbar") chart.classList.add("bars-vertical");
    else if (type === "line") chart.classList.add("line-chart");

    if (type === "hbar") {
      for (const b of days) {
        const w = Math.round(((b.n || 0) / maxN) * 100);
        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `
          <div class="bar-label" style="width:40px">${b.day}</div>
          <div class="bar"><div class="bar-fill" style="width:${w}%"></div></div>
          <div class="bar-val">${num(b.n)}</div>
        `;
        chart.appendChild(row);
      }
    } else if (type === "vbar") {
      const wrapper = document.createElement("div");
      wrapper.className = "bars-v-wrapper";
      const maxBarHeight = 200;
      for (const b of days) {
        const h = Math.max(4, Math.round(((b.n||0) / maxN) * maxBarHeight));
        const col = document.createElement("div");
        col.className = "bars-v-col";
        col.innerHTML = `
          <div class="bars-v-bar" style="height:${h}px"></div>
          <div class="bars-v-val">${num(b.n)}</div>
          <div class="bars-v-label">${b.day}</div>
        `;
        wrapper.appendChild(col);
      }
      chart.appendChild(wrapper);
    } else {
      renderLineChart(chart, days.map((b) => ({ label: String(b.day), value: b.n || 0 })), maxN);
    }
    setStatus(`Onset loaded: ${days.length} days.`, "ok");
  }

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
    setStatus(`Outcomes loaded.`, "ok");
  }

  function renderTrends(data) {
    $("#trends_N").textContent = data?.N_base ?? "0";
    $("#trends_points").textContent = data?.points ?? "0";
    $("#trends_time").textContent = data?.time_utc ?? "";
    if (typeof window !== "undefined") window._trendsLastData = data;
    const chart = $("#trendsChart");
    if (!chart) return;
    chart.innerHTML = "";
    const series = data?.series || [];
    if (!series.length) {
      chart.textContent = "No trend data.";
      setStatus("Trends loaded: 0 months.", "ok");
      return;
    }
    const maxN = Math.max(1, ...series.map((p) => p.n || 0));
    const type = trendsChartType || "hbar";
    chart.className = "bars";
    chart.classList.remove("bars-vertical", "line-chart");
    if (type === "vbar") chart.classList.add("bars-vertical");
    else if (type === "line") chart.classList.add("line-chart");

    if (type === "hbar") {
      for (const p of series) {
        const w = Math.round(((p.n || 0) / maxN) * 100);
        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `
          <div class="bar-label">${escapeHtml(p.month ?? "")}</div>
          <div class="bar"><div class="bar-fill" style="width:${w}%"></div></div>
          <div class="bar-val">${num(p.n)}</div>
        `;
        chart.appendChild(row);
      }
    } else if (type === "vbar") {
      const wrapper = document.createElement("div");
      wrapper.className = "bars-v-wrapper";
      const maxBarHeight = 200;
      for (const p of series) {
        const h = Math.max(4, Math.round(((p.n||0) / maxN) * maxBarHeight));
        const col = document.createElement("div");
        col.className = "bars-v-col";
        col.innerHTML = `
          <div class="bars-v-bar" style="height:${h}px"></div>
          <div class="bars-v-val">${num(p.n)}</div>
          <div class="bars-v-label">${escapeHtml(p.month ?? "")}</div>
        `;
        wrapper.appendChild(col);
      }
      chart.appendChild(wrapper);
    } else {
      renderLineChart(chart, series.map(p => ({ label: p.month ?? "", value: p.n || 0 })), maxN);
    }
    setStatus(`Trends loaded.`, "ok");
  }

  // FIXED: Added Label Skipping Logic
  function renderLineChart(container, points, maxN) {
    const svgNS = "http://www.w3.org/2000/svg";
    const width = 700, height = 260;
    const padX = 40, padY = 30;
    const innerW = width - padX * 2, innerH = height - padY * 2;
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.classList.add("trend-line-svg");

    // Axis
    const axis = document.createElementNS(svgNS, "path");
    axis.setAttribute("d", `M ${padX} ${padY} V ${height - padY} H ${width - padX}`);
    axis.setAttribute("class", "trend-line-axis");
    axis.setAttribute("fill", "none");
    svg.appendChild(axis);

    const mapped = points.map((pt, i) => ({
      x: padX + (points.length === 1 ? innerW / 2 : (innerW * i) / (points.length - 1)),
      y: height - padY - (maxN ? (pt.value / maxN) * innerH : 0),
      ...pt
    }));

    // Line Path
    const path = document.createElementNS(svgNS, "path");
    let d = "";
    mapped.forEach((pt, i) => { d += (i === 0 ? "M " : " L ") + pt.x + " " + pt.y; });
    path.setAttribute("d", d);
    path.setAttribute("class", "trend-line-path");
    path.setAttribute("fill", "none");
    svg.appendChild(path);

    // Label Skipping Strategy: Aim for ~12 labels max
    const stride = Math.ceil(points.length / 12);

    for (let i = 0; i < mapped.length; i++) {
      const pt = mapped[i];
      const c = document.createElementNS(svgNS, "circle");
      c.setAttribute("cx", pt.x);
      c.setAttribute("cy", pt.y);
      c.setAttribute("r", 3);
      c.setAttribute("class", "trend-line-dot");
      const title = document.createElementNS(svgNS, "title");
      title.textContent = `${pt.label}: ${num(pt.value)}`;
      c.appendChild(title);
      svg.appendChild(c);

      // Only draw label if it matches the stride (avoid overlap)
      if (i % stride === 0) {
        const label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", pt.x);
        label.setAttribute("y", height - padY + 12);
        label.setAttribute("text-anchor", "middle");
        label.textContent = pt.label;
        svg.appendChild(label);
      }
    }
    container.appendChild(svg);
  }

  // ---------- Actions ----------
  let currentMapData = null;
  async function loadGeoMap() {
    const params = baseParamsFromForm();
    setStatus("Loading map...", "info");
    try {
      const data = await fetchJSON("/api/geo/states", params);
      currentMapData = data;
      renderGeoMap(data);
      setStatus(`Map loaded: ${data.total} reports.`, "ok");
    } catch (e) {
      console.error(e);
      setStatus("Failed to load map.", "err");
    }
  }

  function renderGeoMap(data) {
    const container = $("#geoMap");
    const legendContainer = $("#mapLegend");
    if (!container) return;
    container.innerHTML = "";
    if (legendContainer) legendContainer.innerHTML = "";
    const states = data?.states || [];
    if (!states.length) {
      container.innerHTML = '<div class="autocomplete-no-results">No data available.</div>';
      return;
    }
    const metric = $("#mapMetric")?.value || "count";
    const values = states.map(s => s[metric]);
    const minVal = Math.min(...values), maxVal = Math.max(...values);
    if (typeof d3 === 'undefined') { container.innerHTML = 'D3.js failed to load.'; return; }
    const colorScale = d3.scaleSequential().domain([minVal, maxVal]).interpolator(d3.interpolateBlues);

    if (legendContainer) {
      const isPct = metric === "serious_ratio", isAge = metric === "avg_age";
      legendContainer.innerHTML = `<span class="legend-title">${metric}: </span><div class="legend-gradient" id="legendGradient"></div><div class="legend-labels"><span>${num(minVal, isPct?3:isAge?1:0)}</span><span>${num(maxVal, isPct?3:isAge?1:0)}</span></div>`;
      const gEl = document.getElementById("legendGradient");
      if(gEl) for(let i=0; i<10; i++){ const d=document.createElement("div"); d.style.flex="1"; d.style.background=colorScale(minVal+(maxVal-minVal)*(i/9)); gEl.appendChild(d); }
    }

    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json").then(us => {
      const width = container.clientWidth || 960, height = 500;
      const svg = d3.select(container).append("svg").attr("viewBox", [0, 0, width, height]);
      const path = d3.geoPath().projection(d3.geoAlbersUsa().scale(width*1.3).translate([width/2, height/2]));
      const tooltip = d3.select("body").append("div").attr("class", "map-tooltip").style("opacity", 0).style("position", "absolute");
      svg.append("g").selectAll("path").data(topojson.feature(us, us.objects.states).features).join("path")
        .attr("d", path).attr("stroke", "#fff").attr("stroke-width", 0.5)
        .attr("fill", d => {
          const s = states.find(x => x.state === d.properties.name || stateAbbrev(d.properties.name) === x.state);
          return s ? colorScale(s[metric]) : "#1a1a1a";
        })
        .on("mouseover", (e, d) => {
          const s = states.find(x => x.state === d.properties.name || stateAbbrev(d.properties.name) === x.state);
          if(s) {
            tooltip.transition().duration(200).style("opacity", 1);
            tooltip.html(`<div class="tooltip-state">${escapeHtml(s.state)}</div><div class="tooltip-stat">Count: ${num(s.count)}</div><div class="tooltip-stat">Serious: ${(s.serious_ratio*100).toFixed(1)}%</div><div class="tooltip-stat">Age: ${num(s.avg_age, 1)}</div>`).style("left", (e.pageX+10)+"px").style("top", (e.pageY-28)+"px");
          }
        })
        .on("mouseout", () => tooltip.transition().duration(500).style("opacity", 0));
    });
  }

  function stateAbbrev(n){const m={"Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"};return m[n]||n;}

  async function runSignals(p) { renderSignals(await fetchJSON("/api/signals", p)); }
  async function runSearch(p) { renderSearch(await fetchJSON("/api/search", p)); loadGeoMap(); }
  async function runOnset(p) { renderOnset(await fetchJSON("/api/onset", p)); }
  async function runOutcomes(p) { renderOutcomes(await fetchJSON("/api/outcomes", p)); }
  async function runTrends(p) {
    // ADDED: pass clip months directly to backend
    p.set("clip_months", $("#trends_clip_months")?.value||"12");
    renderTrends(await fetchJSON("/api/trends", p));
  }

  async function runActive() {
    const p = baseParamsFromForm();
    const meaningful = ["year","sex","state","age_min","age_max","serious_only","died","hospital","vax_type","vax_manu","symptom_term"];
    if (!meaningful.some(k => p.has(k) && p.get(k).trim()) && !confirm("Running with NO filters may be slow. Continue?")) return;

    // WARNING CHECK for Trend 0
    if (activeTab === "trends") {
      const clip = $("#trends_clip_months")?.value;
      if (clip === "0") {
        if (!confirm("Showing trends for ALL time may clutter the chart and take longer. Continue?")) return;
      }
    }

    setStatus("Loading…", "info");
    try {
      if (activeTab === "signals") return await runSignals(p);
      if (activeTab === "search") return await runSearch(p);
      if (activeTab === "onset") return await runOnset(p);
      if (activeTab === "outcomes") return await runOutcomes(p);
      if (activeTab === "trends") return await runTrends(p);
    } catch (e) { console.error(e); setStatus(e.message || "Request failed.", "err"); }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); runActive(); });
  resetBtn.addEventListener("click", () => { form.reset(); setStatus("Filters reset.", "info"); });
  if ($("#mapMetric")) $("#mapMetric").addEventListener("change", () => { if(currentMapData) renderGeoMap(currentMapData); });

  const setupChartBtns = (sel, storeKey, setter) => {
    const btns = $$(sel);
    btns.forEach(b => b.addEventListener("click", () => {
      const t = b.dataset.chartType;
      localStorage.setItem(storeKey, t);
      if(sel.includes("trends")) trendsChartType = t; else onsetChartType = t;
      btns.forEach(x => x.classList.toggle("active", x.dataset.chartType===t));
      const data = sel.includes("trends") ? window._trendsLastData : window._onsetLastData;
      if(data) sel.includes("trends") ? renderTrends(data) : renderOnset(data);
    }));
    btns.forEach(x => x.classList.toggle("active", x.dataset.chartType===(sel.includes("trends")?trendsChartType:onsetChartType)));
  };

  setupChartBtns(".trends-chart-btn", "vaxscope_trends_chart_type", (t)=>trendsChartType=t);
  setupChartBtns(".onset-chart-btn", "vaxscope_onset_chart_type", (t)=>onsetChartType=t);

  const acFields = [{id:"state", ep:"/api/filter-options/state"},{id:"vax_type", ep:"/api/filter-options/vax_type"},{id:"vax_manu", ep:"/api/filter-options/vax_manu"},{id:"symptom_term", ep:"/api/filter-options/symptom_term"}];
  acFields.forEach(x => { const el=$( `#${x.id}` ); if(el) new Autocomplete(el, {apiEndpoint:x.ep}); });

  setActiveTab(activeTab);
  setStatus("Ready.");
})();