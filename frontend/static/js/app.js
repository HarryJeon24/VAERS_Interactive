// ---------- Remote Autocomplete Component (searchable dropdown) ----------
class Autocomplete {
  constructor(inputElement, options = {}) {
    this.input = inputElement;
    this.options = {
      apiEndpoint: null,      // e.g. "/api/filter-options/state"
      queryParam: "q",        // backend uses ?q=
      minChars: 2,            // start searching after N chars
      limit: 50,              // max suggestions
      debounceMs: 150,        // debounce typing
      ...options,
    };

    this.filteredData = [];
    this.selectedIndex = -1;
    this.isLoading = false;
    this.lastQuery = "";
    this._debounceTimer = null;

    this.init();
  }

  init() {
    // Wrap input in autocomplete wrapper
    const wrapper = document.createElement("div");
    wrapper.className = "autocomplete-wrapper";
    this.input.parentNode.insertBefore(wrapper, this.input);
    wrapper.appendChild(this.input);

    // Create dropdown
    this.dropdown = document.createElement("div");
    this.dropdown.className = "autocomplete-dropdown";
    wrapper.appendChild(this.dropdown);

    // Bind events
    this.input.addEventListener("input", this.handleInput.bind(this));
    this.input.addEventListener("focus", this.handleFocus.bind(this));
    this.input.addEventListener("keydown", this.handleKeydown.bind(this));

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) this.hideDropdown();
    });
  }

  handleFocus() {
    // If there is already a value, show suggestions for it
    const v = (this.input.value || "").trim();
    if (v.length >= this.options.minChars) {
      this.fetchAndRender(v);
    } else {
      // Do nothing for empty focus (avoid pulling huge lists)
      this.hideDropdown();
    }
  }

  handleInput(e) {
    const value = (e.target.value || "").trim();

    if (this._debounceTimer) clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      if (value.length < this.options.minChars) {
        this.hideDropdown();
        return;
      }
      this.fetchAndRender(value);
    }, this.options.debounceMs);
  }

  handleKeydown(e) {
    if (!this.dropdown.classList.contains("show")) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        this.selectedIndex = Math.min(this.selectedIndex + 1, this.filteredData.length - 1);
        this.updateSelection();
        break;

      case "ArrowUp":
        e.preventDefault();
        this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
        this.updateSelection();
        break;

      case "Enter":
        if (this.selectedIndex >= 0) {
          e.preventDefault();
          this.selectItem(this.filteredData[this.selectedIndex]);
        }
        break;

      case "Escape":
        this.hideDropdown();
        break;
    }
  }

  updateSelection() {
    const items = this.dropdown.querySelectorAll(".autocomplete-item");
    items.forEach((item, index) => {
      item.classList.toggle("highlighted", index === this.selectedIndex);
    });

    if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
      items[this.selectedIndex].scrollIntoView({ block: "nearest" });
    }
  }

  selectItem(value) {
    this.input.value = value;
    this.hideDropdown();
    this.input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  async fetchAndRender(query) {
    if (!this.options.apiEndpoint) return;
    if (query === this.lastQuery && this.dropdown.classList.contains("show")) return;

    this.lastQuery = query;
    this.isLoading = true;
    this.showLoading();

    try {
      const url = new URL(this.options.apiEndpoint, window.location.origin);
      url.searchParams.set(this.options.queryParam, query);
      url.searchParams.set("limit", String(this.options.limit));

      const response = await fetch(url.toString(), { headers: { "Accept": "application/json" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const result = await response.json();

      // Support several shapes: {values:[]}, {options:[]}, []
      const values = result?.values || result?.options || result || [];
      this.filteredData = Array.isArray(values) ? values.slice(0, this.options.limit) : [];

      this.isLoading = false;
      this.selectedIndex = -1;
      this.renderDropdown();
    } catch (error) {
      console.error(`Autocomplete fetch failed for ${this.input.id}:`, error);
      this.isLoading = false;
      this.filteredData = [];
      this.renderDropdown(true);
    }
  }

  renderDropdown(isError = false) {
    this.dropdown.innerHTML = "";

    if (isError) {
      const div = document.createElement("div");
      div.className = "autocomplete-no-results";
      div.textContent = "Failed to load suggestions";
      this.dropdown.appendChild(div);
      this.showDropdown();
      return;
    }

    if (this.filteredData.length === 0) {
      const div = document.createElement("div");
      div.className = "autocomplete-no-results";
      div.textContent = "No results found";
      this.dropdown.appendChild(div);
      this.showDropdown();
      return;
    }

    this.filteredData.forEach((item) => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.textContent = item;
      div.addEventListener("click", () => this.selectItem(item));
      this.dropdown.appendChild(div);
    });

    this.showDropdown();
  }

  showLoading() {
    this.dropdown.innerHTML = "";
    const div = document.createElement("div");
    div.className = "autocomplete-loading";
    div.textContent = "Loading...";
    this.dropdown.appendChild(div);
    this.showDropdown();
  }

  showDropdown() {
    this.dropdown.classList.add("show");
  }

  hideDropdown() {
    this.dropdown.classList.remove("show");
    this.selectedIndex = -1;
  }
}

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
  let trendsChartType = localStorage.getItem("vaxscope_trends_chart_type") || "hbar";
  let onsetChartType = localStorage.getItem("vaxscope_onset_chart_type") || "hbar";

  function setStatus(msg, type = "info") {
    statusEl.textContent = msg;
    statusEl.dataset.type = type;
  }

  // Show/hide & enable/disable filters based on data-tabs
  function updateFilterVisibility(tab) {
    const tabbed = $$("[data-tabs]");
    const preserveDisplay = new Set(["otherFiltersSection"]); // keep collapse behavior

    tabbed.forEach((el) => {
      const tabs = (el.dataset.tabs || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);

      const shouldShow = tabs.includes(tab);

      // Hide/show element
      if (!shouldShow) {
        el.style.display = "none";
      } else {
        // special cases
        if (el.id === "signalsControls") {
          el.style.display = "block";
        } else if (preserveDisplay.has(el.id)) {
          // do not force open; keep whatever collapse state is
          // BUT if it was hidden due to another tab, keep it hidden until user expands
          // (we do nothing here)
        } else {
          el.style.display = "";
        }
      }

      // Disable inputs inside hidden blocks so they don't get sent
      const controls = el.querySelectorAll("input, select, textarea, button");
      controls.forEach((c) => {
        // don't disable run/reset (not inside tabbed blocks anyway, but safe)
        if (c.id === "runBtn" || c.id === "resetBtn") return;
        c.disabled = !shouldShow;
      });
    });

    // If not Search tab, ensure the collapsible advanced area is not "stuck open"
    const otherSection = $("#otherFiltersSection");
    if (otherSection && tab !== "search") {
      otherSection.style.display = "none";
      const icon = $(".toggle-icon", $("#toggleOtherFilters") || document);
      if (icon) icon.classList.remove("expanded");
    }
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

    // Apply per-tab filter visibility
    updateFilterVisibility(tab);

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

    // Only include ENABLED inputs (hidden tab filters are disabled)
    for (const [k, v] of fd.entries()) {
      const el = form.querySelector(`[name="${CSS.escape(k)}"]`);
      if (el && el.disabled) continue;
      params.set(k, (v || "").toString().trim());
    }

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
    return String(x).replace("T", " ").replace("Z", "");
  }

  function isSeriousRow(d) {
    const flags = ["DIED", "HOSPITAL", "L_THREAT", "DISABLE", "BIRTH_DEFECT"];
    return flags.some((k) => String(d?.[k] || "").toUpperCase() === "Y");
  }

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

    window._onsetLastData = data;

    const chart = $("#onsetChart");
    if (!chart) return;
    chart.innerHTML = "";

    const buckets = data?.buckets || [];
    if (!buckets.length) {
      chart.textContent = "No onset data for current filters.";
      setStatus(`Onset loaded: 0 buckets (obs=${data?.obs ?? 0}).`, "ok");
      return;
    }

    const maxN = Math.max(1, ...buckets.map((b) => b.n || 0));
    const type = onsetChartType || "hbar";

    chart.className = "bars";
    chart.classList.remove("bars-vertical", "line-chart");
    if (type === "vbar") chart.classList.add("bars-vertical");
    else if (type === "line") chart.classList.add("line-chart");

    const labelForBucket = (b) => {
      const lo = b.lo;
      const hi = b.hi;
      return lo == null || hi == null ? "—" : `${lo}–${hi}`;
    };

    if (type === "hbar") {
      for (const b of buckets) {
        const label = labelForBucket(b);
        const value = b.n || 0;
        const w = Math.round((value / maxN) * 100);

        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `
          <div class="bar-label">${escapeHtml(label)}</div>
          <div class="bar">
            <div class="bar-fill" style="width:${w}%"></div>
          </div>
          <div class="bar-val">${num(value)}</div>
        `;
        chart.appendChild(row);
      }
    } else if (type === "vbar") {
      const wrapper = document.createElement("div");
      wrapper.className = "bars-v-wrapper";
      const maxBarHeight = 200;

      for (const b of buckets) {
        const label = labelForBucket(b);
        const value = b.n || 0;
        const h = Math.max(4, Math.round((value / maxN) * maxBarHeight));

        const col = document.createElement("div");
        col.className = "bars-v-col";
        col.innerHTML = `
          <div class="bars-v-bar" style="height:${h}px"></div>
          <div class="bars-v-val">${num(value)}</div>
          <div class="bars-v-label">${escapeHtml(label)}</div>
        `;
        wrapper.appendChild(col);
      }
      chart.appendChild(wrapper);
    } else {
      const svgNS = "http://www.w3.org/2000/svg";
      const width = 700;
      const height = 260;
      const padX = 40;
      const padY = 30;
      const innerW = width - padX * 2;
      const innerH = height - padY * 2;

      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.classList.add("trend-line-svg");

      const axis = document.createElementNS(svgNS, "path");
      axis.setAttribute("d", `M ${padX} ${padY} V ${height - padY} H ${width - padX}`);
      axis.setAttribute("class", "trend-line-axis");
      axis.setAttribute("fill", "none");
      svg.appendChild(axis);

      const points = buckets.map((b, i) => {
        const label = labelForBucket(b);
        const value = b.n || 0;
        const x = padX + (buckets.length === 1 ? innerW / 2 : (innerW * i) / (buckets.length - 1));
        const y = height - padY - (maxN ? (value / maxN) * innerH : 0);
        return { x, y, label, value };
      });

      const path = document.createElementNS(svgNS, "path");
      let d = "";
      points.forEach((pt, i) => (d += (i === 0 ? "M " : " L ") + pt.x + " " + pt.y));
      path.setAttribute("d", d);
      path.setAttribute("class", "trend-line-path");
      path.setAttribute("fill", "none");
      svg.appendChild(path);

      for (const pt of points) {
        const c = document.createElementNS(svgNS, "circle");
        c.setAttribute("cx", pt.x);
        c.setAttribute("cy", pt.y);
        c.setAttribute("r", 3);
        c.setAttribute("class", "trend-line-dot");
        const title = document.createElementNS(svgNS, "title");
        title.textContent = `${pt.label}: ${num(pt.value)}`;
        c.appendChild(title);
        svg.appendChild(c);

        const label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", pt.x);
        label.setAttribute("y", height - padY + 12);
        label.setAttribute("text-anchor", "middle");
        label.textContent = pt.label;
        svg.appendChild(label);
      }

      chart.appendChild(svg);
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

    window._trendsLastData = data;

    const chart = $("#trendsChart");
    if (!chart) return;
    chart.innerHTML = "";

    const series = data?.series || [];
    if (!series.length) {
      chart.textContent = "No trend data for current filters.";
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
          <div class="bar">
            <div class="bar-fill" style="width:${w}%"></div>
          </div>
          <div class="bar-val">${num(p.n)}</div>
        `;
        chart.appendChild(row);
      }
    } else if (type === "vbar") {
      const wrapper = document.createElement("div");
      wrapper.className = "bars-v-wrapper";
      const maxBarHeight = 200;

      for (const p of series) {
        const value = p.n || 0;
        const h = Math.max(4, Math.round((value / maxN) * maxBarHeight));

        const col = document.createElement("div");
        col.className = "bars-v-col";
        col.innerHTML = `
          <div class="bars-v-bar" style="height:${h}px"></div>
          <div class="bars-v-val">${num(value)}</div>
          <div class="bars-v-label">${escapeHtml(p.month ?? "")}</div>
        `;
        wrapper.appendChild(col);
      }

      chart.appendChild(wrapper);
    } else {
      const svgNS = "http://www.w3.org/2000/svg";
      const width = 700;
      const height = 260;
      const padX = 40;
      const padY = 30;
      const innerW = width - padX * 2;
      const innerH = height - padY * 2;

      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.classList.add("trend-line-svg");

      const axis = document.createElementNS(svgNS, "path");
      axis.setAttribute("d", `M ${padX} ${padY} V ${height - padY} H ${width - padX}`);
      axis.setAttribute("class", "trend-line-axis");
      axis.setAttribute("fill", "none");
      svg.appendChild(axis);

      const points = series.map((p, i) => {
        const x = padX + (series.length === 1 ? innerW / 2 : (innerW * i) / (series.length - 1));
        const value = p.n || 0;
        const y = height - padY - (maxN ? (value / maxN) * innerH : 0);
        return { x, y, p };
      });

      const path = document.createElementNS(svgNS, "path");
      let d = "";
      points.forEach((pt, i) => (d += (i === 0 ? "M " : " L ") + pt.x + " " + pt.y));
      path.setAttribute("d", d);
      path.setAttribute("class", "trend-line-path");
      path.setAttribute("fill", "none");
      svg.appendChild(path);

      for (const pt of points) {
        const c = document.createElementNS(svgNS, "circle");
        c.setAttribute("cx", pt.x);
        c.setAttribute("cy", pt.y);
        c.setAttribute("r", 3);
        c.setAttribute("class", "trend-line-dot");
        const title = document.createElementNS(svgNS, "title");
        title.textContent = `${pt.p.month}: ${num(pt.p.n)}`;
        c.appendChild(title);
        svg.appendChild(c);

        const label = document.createElementNS(svgNS, "text");
        label.setAttribute("x", pt.x);
        label.setAttribute("y", height - padY + 12);
        label.setAttribute("text-anchor", "middle");
        label.textContent = pt.p.month ?? "";
        svg.appendChild(label);
      }

      chart.appendChild(svg);
    }

    setStatus(`Trends loaded: ${series.length} months.`, "ok");
  }

  // ---------- Run per tab ----------
  async function runSignals(params) {
    const data = await fetchJSON("/api/signals", params);
    renderSignals(data);
  }

  async function runSearch(params) {
    // ensure a reasonable default limit for search
    if (!params.has("limit")) params.set("limit", "50");

    const data = await fetchJSON("/api/search", params);
    renderSearch(data);

    // Auto-load geographic map after search
    await loadGeoMap();
  }

  let currentMapData = null;

  async function loadGeoMap() {
    const params = baseParamsFromForm();
    if (!params.has("limit")) params.set("limit", "50");

    setStatus("Loading map...", "info");

    try {
      const data = await fetchJSON("/api/geo/states", params);
      currentMapData = data;
      renderGeoMap(data);
      setStatus(`Map loaded: ${data.total} reports across ${data.states.length} states.`, "ok");
    } catch (e) {
      console.error(e);
      setStatus(e.message || "Failed to load map.", "err");
    }
  }

  function renderGeoMap(data) {
    const container = $("#geoMap");
    const legendContainer = $("#mapLegend");

    if (!container) return;

    container.innerHTML = "";
    if (legendContainer) legendContainer.innerHTML = "";

    const states = data?.states || [];
    if (states.length === 0) {
      container.innerHTML = '<div class="autocomplete-no-results">No data available for current filters.</div>';
      return;
    }

    const metric = $("#mapMetric")?.value || "count";

    // Determine value range for color scale
    const values = states.map((s) => s[metric]);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);

    if (typeof d3 === "undefined") {
      container.innerHTML = '<div class="autocomplete-no-results">D3.js failed to load. Please refresh.</div>';
      return;
    }

    const colorScale = d3.scaleSequential()
      .domain([minValue, maxValue])
      .interpolator(d3.interpolateBlues);

    if (legendContainer) renderLegend(legendContainer, metric, minValue, maxValue, colorScale);

    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json")
      .then((us) => {
        const width = container.clientWidth || 960;
        const height = 500;

        const svg = d3.select(container)
          .append("svg")
          .attr("viewBox", [0, 0, width, height])
          .attr("width", width)
          .attr("height", height);

        const projection = d3.geoAlbersUsa()
          .scale(width * 1.3)
          .translate([width / 2, height / 2]);

        const path = d3.geoPath().projection(projection);

        const tooltip = d3.select("body").append("div")
          .attr("class", "map-tooltip")
          .style("opacity", 0)
          .style("position", "absolute");

        const features = topojson.feature(us, us.objects.states).features;

        svg.append("g")
          .selectAll("path")
          .data(features)
          .join("path")
          .attr("d", path)
          .attr("fill", (d) => {
            const stateName = d.properties.name;
            const stateData = states.find((s) => s.state === stateName || stateAbbrev(stateName) === s.state);
            return stateData ? colorScale(stateData[metric]) : "#1a1a1a";
          })
          .attr("stroke", "#fff")
          .attr("stroke-width", 0.5)
          .on("mouseover", (event, d) => {
            const stateName = d.properties.name;
            const stateData = states.find((s) => s.state === stateName || stateAbbrev(stateName) === s.state);
            if (!stateData) return;

            tooltip.transition().duration(200).style("opacity", 1);
            tooltip.html(`
              <div class="tooltip-state">${escapeHtml(stateData.state)}</div>
              <div class="tooltip-stat">Reports: ${num(stateData.count)}</div>
              <div class="tooltip-stat">Serious: ${num(stateData.serious_count)} (${(stateData.serious_ratio * 100).toFixed(1)}%)</div>
              <div class="tooltip-stat">Avg Age: ${num(stateData.avg_age, 1)}</div>
            `)
              .style("left", (event.pageX + 10) + "px")
              .style("top", (event.pageY - 28) + "px");
          })
          .on("mouseout", () => {
            tooltip.transition().duration(500).style("opacity", 0);
          });
      })
      .catch(() => {
        container.innerHTML = '<div class="autocomplete-no-results">Failed to load map visualization.</div>';
      });
  }

  function renderLegend(container, metric, minValue, maxValue, colorScale) {
    const metricLabels = {
      count: "Report Count",
      serious_ratio: "Serious Ratio",
      avg_age: "Average Age",
    };

    container.innerHTML = `
      <span class="legend-title">${escapeHtml(metricLabels[metric])}: </span>
      <div class="legend-gradient" id="legendGradient"></div>
      <div class="legend-labels">
        <span>${num(minValue, metric === "serious_ratio" ? 3 : metric === "avg_age" ? 1 : 0)}</span>
        <span>${num(maxValue, metric === "serious_ratio" ? 3 : metric === "avg_age" ? 1 : 0)}</span>
      </div>
    `;

    const gradientEl = document.getElementById("legendGradient");
    if (!gradientEl) return;

    const steps = 10;
    for (let i = 0; i < steps; i++) {
      const value = minValue + (maxValue - minValue) * (i / (steps - 1));
      const color = colorScale(value);
      const div = document.createElement("div");
      div.style.flex = "1";
      div.style.background = color;
      gradientEl.appendChild(div);
    }
  }

  function stateAbbrev(fullName) {
    const abbrevs = {
      "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
      "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
      "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
      "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
      "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
      "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
      "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
      "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
      "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
      "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    };
    return abbrevs[fullName] || fullName;
  }

  async function runOnset(params) {
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

  // ---------- events ----------
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    runActive();
  });

  resetBtn.addEventListener("click", () => {
    form.reset();
    setStatus("Filters reset.", "info");
  });

  // Map metric selector
  const mapMetric = $("#mapMetric");
  if (mapMetric) {
    mapMetric.addEventListener("change", () => {
      if (currentMapData) renderGeoMap(currentMapData);
    });
  }

  // Collapsible "Other Filter Options" toggle
  const toggleOtherFilters = $("#toggleOtherFilters");
  const otherFiltersSection = $("#otherFiltersSection");
  const toggleIcon = toggleOtherFilters ? $(".toggle-icon", toggleOtherFilters) : null;

  if (toggleOtherFilters && otherFiltersSection) {
    toggleOtherFilters.addEventListener("click", () => {
      const isHidden = otherFiltersSection.style.display === "none";
      otherFiltersSection.style.display = isHidden ? "block" : "none";
      if (toggleIcon) toggleIcon.classList.toggle("expanded", isHidden);
    });
  }

  // Trends chart-type toggle
  const trendsChartButtons = $$(".trends-chart-btn");
  function setTrendsChartType(type) {
    trendsChartType = type || "hbar";
    localStorage.setItem("vaxscope_trends_chart_type", trendsChartType);

    trendsChartButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.chartType === trendsChartType);
    });

    if (window._trendsLastData) renderTrends(window._trendsLastData);
  }

  if (trendsChartButtons.length) {
    trendsChartButtons.forEach((btn) => {
      btn.addEventListener("click", () => setTrendsChartType(btn.dataset.chartType));
    });
    setTrendsChartType(trendsChartType);
  }

  // Onset chart-type toggle
  const onsetChartButtons = $$(".onset-chart-btn");
  function setOnsetChartType(type) {
    onsetChartType = type || "hbar";
    localStorage.setItem("vaxscope_onset_chart_type", onsetChartType);

    onsetChartButtons.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.chartType === onsetChartType);
    });

    if (window._onsetLastData) renderOnset(window._onsetLastData);
  }

  if (onsetChartButtons.length) {
    onsetChartButtons.forEach((btn) => {
      btn.addEventListener("click", () => setOnsetChartType(btn.dataset.chartType));
    });
    setOnsetChartType(onsetChartType);
  }

  // ---------- Autocomplete initialization (remote searchable dropdown) ----------
  const autocompleteFields = [
    { id: "state", endpoint: "/api/filter-options/state" },
    { id: "vax_type", endpoint: "/api/filter-options/vax_type" },
    { id: "vax_manu", endpoint: "/api/filter-options/vax_manu" },
    { id: "symptom_term", endpoint: "/api/filter-options/symptom_term" },

    // Search-only advanced
    { id: "other_meds", endpoint: "/api/filter-options/other_meds" },
    { id: "cur_ill", endpoint: "/api/filter-options/cur_ill" },
    { id: "history", endpoint: "/api/filter-options/history" },
    { id: "prior_vax", endpoint: "/api/filter-options/prior_vax" },
    { id: "allergies", endpoint: "/api/filter-options/allergies" },
  ];

  autocompleteFields.forEach(({ id, endpoint }) => {
    const input = $(`#${id}`);
    if (!input) return;
    new Autocomplete(input, { apiEndpoint: endpoint, minChars: 2, limit: 50 });
  });

  // ---------- init ----------
  setActiveTab(activeTab);
  setStatus("Ready.");
})();
