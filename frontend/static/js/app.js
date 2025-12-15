// ---------- Autocomplete Component (Hybrid: Dynamic + Defaults) ----------
class Autocomplete {
  constructor(inputElement, options = {}) {
    this.input = inputElement;
    this.options = options;
    this.debounceTimer = null;
    this.selectedIndex = -1;
    this.isLoading = false;
    this.data = []; // Cache of current suggestions

    this.init();
  }

  init() {
    // 1. Create Wrapper & Dropdown
    const wrapper = document.createElement("div");
    wrapper.className = "autocomplete-wrapper";
    this.input.parentNode.insertBefore(wrapper, this.input);
    wrapper.appendChild(this.input);

    this.dropdown = document.createElement("div");
    this.dropdown.className = "autocomplete-dropdown";
    wrapper.appendChild(this.dropdown);

    // 2. Bind Events
    this.input.addEventListener("input", this.handleInput.bind(this));
    this.input.addEventListener("keydown", this.handleKeydown.bind(this));
    this.input.addEventListener("focus", this.handleFocus.bind(this));

    // Close on click outside
    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) this.hideDropdown();
    });
  }

  // Show default results immediately when clicked
  handleFocus() {
    if (this.input.value.trim() === "") {
      this.fetchSuggestions("");
    } else {
      // If there's already text, search for it
      this.fetchSuggestions(this.input.value.trim());
    }
  }

  handleInput(e) {
    const value = e.target.value.trim();

    if (this.debounceTimer) clearTimeout(this.debounceTimer);

    // Immediate fetch if empty (to show defaults), else debounce
    if (value === "") {
      this.fetchSuggestions("");
      return;
    }

    // Debounce typing (200ms) to save network requests
    this.debounceTimer = setTimeout(() => {
      this.fetchSuggestions(value);
    }, 200);
  }

  async fetchSuggestions(query) {
    if (!this.options.apiEndpoint) return;

    this.isLoading = true;
    // Only show "Loading..." if we are searching, not just clicking empty
    if(query.length > 0) this.showLoading();

    try {
      // Fetch results (backend handles empty 'q' by returning top results)
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
      // Only show "No matches" if the user actually typed something
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

  showLoading() {
    // Optional: Only show loading if meaningful
  }

  showDropdown() {
    this.dropdown.classList.add("show");
  }

  hideDropdown() {
    this.dropdown.classList.remove("show");
  }

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
        if (this.selectedIndex >= 0) {
          this.selectItem(this.data[this.selectedIndex]);
        }
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
    if (this.selectedIndex >= 0) {
      items[this.selectedIndex].scrollIntoView({ block: "nearest" });
    }
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

  function setActiveTab(tab) {
    activeTab = tab;
    localStorage.setItem("vaxscope_active_tab", tab);

    // 1. Toggle Tab Buttons
    tabButtons.forEach((b) => {
      const on = b.dataset.tab === tab;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.classList.toggle("active", on);
    });

    // 2. Toggle Result Panels
    panels.forEach((p) => {
      const on = p.dataset.tabPanel === tab;
      p.hidden = !on;
    });

    // 3. Toggle Filter Fields based on data-tabs attribute
    const filterFields = $$('[data-tabs]');
    filterFields.forEach(el => {
      const allowedTabs = el.dataset.tabs.split(',').map(t => t.trim());
      if (allowedTabs.includes(tab)) {
        el.style.display = ''; // Restore default
      } else {
        el.style.display = 'none';
      }
    });

    // 4. Update Titles & Buttons
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

  // ---------- Form & Helper Functions ----------

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
      "limit", // Included limit in the main keys now
      "onset_start", "onset_end",
      "onset_days_min", "onset_days_max",
    ];
    keys.forEach((k) => params.set(k, (fd.get(k) || "").toString().trim()));

    // signals knobs
    const sKeys = [
      "sort_by", "min_count", "min_vax_total",
      "min_sym_total", "cc", "base_id_cap",
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

    const normArr = (x) => {
      if (x == null) return [];
      if (Array.isArray(x)) return x.map(String).map(s => s.trim()).filter(Boolean);
      const s = String(x).trim();
      return s ? [s] : [];
    };

    const listPreview = (arr, maxItems = 3) => {
      const a = normArr(arr);
      if (!a.length) return { preview: "", full: "" };
      const full = a.join("; ");
      const preview = a.length <= maxItems ? full : (a.slice(0, maxItems).join("; ") + ` …(+${a.length - maxItems})`);
      return { preview, full };
    };

    const clipText = (x, maxLen = 80) => {
      const s = (x ?? "").toString().replace(/\s+/g, " ").trim();
      if (!s) return { preview: "", full: "" };
      const preview = s.length > maxLen ? s.slice(0, maxLen) + "…" : s;
      return { preview, full: s };
    };

    for (const d of results) {
      const yearVal = d?.RECVDATE_YEAR ?? d?.YEAR ?? "";
      const vaxTypes = listPreview(d?.VAX_TYPES);
      const vaxManus = listPreview(d?.VAX_MANUS);
      const symTerms = listPreview(d?.SYMPTOM_TERMS);
      const symptomText = clipText(d?.SYMPTOM_TEXT, 120);
      const onsetDays = (d?.ONSET_DAYS ?? "");
      const onsetDaysCell = onsetDays === null ? "" : String(onsetDays);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${escapeHtml(d?.VAERS_ID ?? "")}</td>
        <td>${escapeHtml(yearVal)}</td>
        <td>${escapeHtml(d?.SEX ?? "")}</td>
        <td>${escapeHtml(d?.AGE_YRS ?? "")}</td>
        <td>${escapeHtml(d?.STATE ?? "")}</td>
        <td>${escapeHtml(fmtDate(d?.VAX_DATE))}</td>
        <td>${escapeHtml(fmtDate(d?.ONSET_DATE))}</td>
        <td>${escapeHtml(onsetDaysCell)}</td>
        <td><span class="pill ${isSeriousRow(d) ? "pill-warn" : ""}">${isSeriousRow(d) ? "Y" : ""}</span></td>

        <td title="${escapeHtml(vaxTypes.full)}">${escapeHtml(vaxTypes.preview)}</td>
        <td title="${escapeHtml(vaxManus.full)}">${escapeHtml(vaxManus.preview)}</td>
        <td title="${escapeHtml(symTerms.full)}">${escapeHtml(symTerms.preview)}</td>

        <td title="${escapeHtml(symptomText.full)}">${escapeHtml(symptomText.preview)}</td>
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
    const labelForBucket = (b) => (b.lo == null || b.hi == null) ? "—" : `${b.lo}–${b.hi}`;

    if (type === "hbar") {
      for (const b of buckets) {
        const w = Math.round(( (b.n || 0) / maxN) * 100);
        const row = document.createElement("div");
        row.className = "bar-row";
        row.innerHTML = `
          <div class="bar-label">${escapeHtml(labelForBucket(b))}</div>
          <div class="bar"><div class="bar-fill" style="width:${w}%"></div></div>
          <div class="bar-val">${num(b.n)}</div>
        `;
        chart.appendChild(row);
      }
    } else if (type === "vbar") {
      const wrapper = document.createElement("div");
      wrapper.className = "bars-v-wrapper";
      const maxBarHeight = 200;
      for (const b of buckets) {
        const h = Math.max(4, Math.round(((b.n||0) / maxN) * maxBarHeight));
        const col = document.createElement("div");
        col.className = "bars-v-col";
        col.innerHTML = `
          <div class="bars-v-bar" style="height:${h}px"></div>
          <div class="bars-v-val">${num(b.n)}</div>
          <div class="bars-v-label">${escapeHtml(labelForBucket(b))}</div>
        `;
        wrapper.appendChild(col);
      }
      chart.appendChild(wrapper);
    } else {
      renderLineChart(chart, buckets.map((b) => ({
        label: labelForBucket(b),
        value: b.n || 0
      })), maxN);
    }
    setStatus(`Onset loaded: ${buckets.length} buckets.`, "ok");
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
      renderLineChart(chart, series.map(p => ({
        label: p.month ?? "",
        value: p.n || 0
      })), maxN);
    }
    setStatus(`Trends loaded.`, "ok");
  }

  function renderLineChart(container, points, maxN) {
    const svgNS = "http://www.w3.org/2000/svg";
    const width = 700, height = 260;
    const padX = 40, padY = 30;
    const innerW = width - padX * 2, innerH = height - padY * 2;
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.classList.add("trend-line-svg");

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

    const path = document.createElementNS(svgNS, "path");
    let d = "";
    mapped.forEach((pt, i) => { d += (i === 0 ? "M " : " L ") + pt.x + " " + pt.y; });
    path.setAttribute("d", d);
    path.setAttribute("class", "trend-line-path");
    path.setAttribute("fill", "none");
    svg.appendChild(path);

    for (const pt of mapped) {
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
    container.appendChild(svg);
  }

  // ---------- Map Helpers ----------
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
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);

    if (typeof d3 === 'undefined') {
      container.innerHTML = 'D3.js failed to load.';
      return;
    }

    const colorScale = d3.scaleSequential()
      .domain([minVal, maxVal])
      .interpolator(d3.interpolateBlues);

    if (legendContainer) {
      const isPct = metric === "serious_ratio";
      const isAge = metric === "avg_age";
      legendContainer.innerHTML = `
        <span class="legend-title">${metric}: </span>
        <div class="legend-gradient" id="legendGradient"></div>
        <div class="legend-labels">
          <span>${num(minVal, isPct ? 3 : isAge ? 1 : 0)}</span>
          <span>${num(maxVal, isPct ? 3 : isAge ? 1 : 0)}</span>
        </div>
      `;
      const gradientEl = document.getElementById("legendGradient");
      if(gradientEl) {
        for(let i=0; i<10; i++){
          const div = document.createElement("div");
          div.style.flex = "1";
          div.style.background = colorScale(minVal + (maxVal-minVal)*(i/9));
          gradientEl.appendChild(div);
        }
      }
    }

    d3.json("https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json").then(us => {
      const width = container.clientWidth || 960;
      const height = 500;
      const svg = d3.select(container).append("svg")
        .attr("viewBox", [0, 0, width, height])
        .attr("width", width).attr("height", height);

      const projection = d3.geoAlbersUsa().scale(width * 1.3).translate([width/2, height/2]);
      const path = d3.geoPath().projection(projection);
      const tooltip = d3.select("body").append("div")
        .attr("class", "map-tooltip").style("opacity", 0).style("position", "absolute");

      const features = topojson.feature(us, us.objects.states).features;
      svg.append("g").selectAll("path").data(features).join("path")
        .attr("d", path)
        .attr("stroke", "#fff").attr("stroke-width", 0.5)
        .attr("fill", d => {
          const sName = d.properties.name;
          const sData = states.find(s => s.state === sName || stateAbbrev(sName) === s.state);
          return sData ? colorScale(sData[metric]) : "#1a1a1a";
        })
        .on("mouseover", (e, d) => {
          const sName = d.properties.name;
          const sData = states.find(s => s.state === sName || stateAbbrev(sName) === s.state);
          if(sData){
             tooltip.transition().duration(200).style("opacity", 1);
             tooltip.html(`
               <div class="tooltip-state">${escapeHtml(sData.state)}</div>
               <div class="tooltip-stat">Count: ${num(sData.count)}</div>
               <div class="tooltip-stat">Serious: ${(sData.serious_ratio*100).toFixed(1)}%</div>
               <div class="tooltip-stat">Age: ${num(sData.avg_age, 1)}</div>
             `).style("left", (e.pageX+10)+"px").style("top", (e.pageY-28)+"px");
          }
        })
        .on("mouseout", () => tooltip.transition().duration(500).style("opacity", 0));
    });
  }

  function stateAbbrev(name) {
    const map = {
      "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK","Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"
    };
    return map[name] || name;
  }

  // ---------- Run Logic ----------
  async function runSignals(params) {
    const data = await fetchJSON("/api/signals", params);
    renderSignals(data);
  }
  async function runSearch(params) {
    const data = await fetchJSON("/api/search", params);
    renderSearch(data);
    loadGeoMap();
  }
  async function runOnset(params) {
    params.set("buckets", $("#onset_buckets")?.value || "30");
    params.set("clip_max_days", $("#onset_clip_max")?.value || "180");
    const data = await fetchJSON("/api/onset", params);
    renderOnset(data);
  }
  async function runOutcomes(params) {
    const data = await fetchJSON("/api/outcomes", params);
    renderOutcomes(data);
  }
  async function runTrends(params) {
    params.set("clip_months", $("#trends_clip_months")?.value || "0");
    const data = await fetchJSON("/api/trends", params);
    renderTrends(data);
  }

  async function runActive() {
    const params = baseParamsFromForm();
    // Warning Check for empty filters
    const meaningful = ["year","sex","state","age_min","age_max","serious_only","died","hospital","vax_type","vax_manu","symptom_term"];
    let hasFilter = false;
    for (const k of meaningful) {
      if (params.has(k) && params.get(k).trim()) { hasFilter = true; break; }
    }
    if (!hasFilter) {
      if (!confirm("Running with NO filters may be slow. Continue?")) return;
    }

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

  // ---------- Events ----------
  form.addEventListener("submit", (e) => { e.preventDefault(); runActive(); });
  resetBtn.addEventListener("click", () => { form.reset(); setStatus("Filters reset.", "info"); });

  if ($("#mapMetric")) $("#mapMetric").addEventListener("change", () => { if(currentMapData) renderGeoMap(currentMapData); });

  const trendsBtns = $$(".trends-chart-btn");
  if (trendsBtns.length) {
    trendsBtns.forEach(b => b.addEventListener("click", () => {
      trendsChartType = b.dataset.chartType;
      localStorage.setItem("vaxscope_trends_chart_type", trendsChartType);
      trendsBtns.forEach(x => x.classList.toggle("active", x.dataset.chartType===trendsChartType));
      if(window._trendsLastData) renderTrends(window._trendsLastData);
    }));
    // set initial active
    trendsBtns.forEach(x => x.classList.toggle("active", x.dataset.chartType===trendsChartType));
  }

  const onsetBtns = $$(".onset-chart-btn");
  if (onsetBtns.length) {
    onsetBtns.forEach(b => b.addEventListener("click", () => {
      onsetChartType = b.dataset.chartType;
      localStorage.setItem("vaxscope_onset_chart_type", onsetChartType);
      onsetBtns.forEach(x => x.classList.toggle("active", x.dataset.chartType===onsetChartType));
      if(window._onsetLastData) renderOnset(window._onsetLastData);
    }));
    // set initial active
    onsetBtns.forEach(x => x.classList.toggle("active", x.dataset.chartType===onsetChartType));
  }

  // Auto-complete init (Dynamic)
  const acFields = [
    {id:"state", ep:"/api/filter-options/state"},
    {id:"vax_type", ep:"/api/filter-options/vax_type"},
    {id:"vax_manu", ep:"/api/filter-options/vax_manu"},
    {id:"symptom_term", ep:"/api/filter-options/symptom_term"}
  ];
  acFields.forEach(x => { const el=$( `#${x.id}` ); if(el) new Autocomplete(el, {apiEndpoint:x.ep}); });

  setActiveTab(activeTab);
  setStatus("Ready.");
})();