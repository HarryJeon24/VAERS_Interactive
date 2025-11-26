// frontend/static/js/signals.js
(() => {
  const $ = (sel) => document.querySelector(sel);

  const form = $("#filters");
  const runBtn = $("#runBtn");
  const resetBtn = $("#resetBtn");
  const statusEl = $("#status");

  const tbody = $("#signalsBody");
  const table = $("#signalsTable");
  const NEl = $("#N");
  const cachedEl = $("#cached");
  const timeEl = $("#time_utc");

  let lastRows = [];
  let sortState = { key: "prr", dir: "desc" };

  function setStatus(msg, kind = "info") {
    statusEl.textContent = msg;
    statusEl.dataset.kind = kind; // css can style by [data-kind]
  }

  function fmtNum(x, digits = 3) {
    if (x === null || x === undefined) return "—";
    if (typeof x !== "number") return String(x);
    if (!Number.isFinite(x)) return "—";
    // For huge values, use scientific-ish compact
    if (Math.abs(x) >= 1e6) return x.toExponential(2);
    // Integers show as integers
    if (Number.isInteger(x)) return String(x);
    return x.toFixed(digits);
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formToQueryParams() {
    const fd = new FormData(form);
    const params = new URLSearchParams();

    // Only send meaningful values; keep API clean
    for (const [k, vRaw] of fd.entries()) {
      const v = String(vRaw).trim();
      if (v === "") continue;
      if (k === "state") {
        params.set(k, v.toUpperCase());
        continue;
      }
      if (k === "sex") {
        params.set(k, v.toUpperCase());
        continue;
      }
      params.set(k, v);
    }
    return params;
  }

  function renderEmpty(msg) {
    tbody.innerHTML = `<tr><td colspan="10" class="muted">${escapeHtml(msg)}</td></tr>`;
  }

  function renderRows(rows) {
    if (!rows || rows.length === 0) {
      renderEmpty("No results. Try lowering thresholds or changing filters.");
      return;
    }

    const html = rows.map((r) => {
      return `
        <tr>
          <td>${escapeHtml(r.vax_type ?? "")}</td>
          <td title="${escapeHtml(r.vax_manu ?? "")}">${escapeHtml(r.vax_manu ?? "")}</td>
          <td title="${escapeHtml(r.pt ?? "")}">${escapeHtml(r.pt ?? "")}</td>
          <td class="num">${fmtNum(r.a, 0)}</td>
          <td class="num">${fmtNum(r.b, 0)}</td>
          <td class="num">${fmtNum(r.c, 0)}</td>
          <td class="num">${fmtNum(r.d, 0)}</td>
          <td class="num">${fmtNum(r.prr, 3)}</td>
          <td class="num">${fmtNum(r.ror, 3)}</td>
          <td class="num">${r.cc_applied ? "Y" : "N"}</td>
        </tr>
      `;
    }).join("");

    tbody.innerHTML = html;
  }

  function getSortValue(row, key) {
    const v = row[key];
    if (v === null || v === undefined) return Number.NEGATIVE_INFINITY;
    if (typeof v === "boolean") return v ? 1 : 0;
    if (typeof v === "number") return v;
    // string
    return String(v).toLowerCase();
  }

  function sortRows(rows, key, dir, numericHint) {
    const mul = dir === "asc" ? 1 : -1;
    const copy = [...rows];
    copy.sort((a, b) => {
      const va = getSortValue(a, key);
      const vb = getSortValue(b, key);

      if (numericHint) {
        const na = typeof va === "number" ? va : Number.NEGATIVE_INFINITY;
        const nb = typeof vb === "number" ? vb : Number.NEGATIVE_INFINITY;
        if (na < nb) return -1 * mul;
        if (na > nb) return 1 * mul;
        // tie-breaker: pt
        return String(a.pt ?? "").localeCompare(String(b.pt ?? ""));
      } else {
        if (va < vb) return -1 * mul;
        if (va > vb) return 1 * mul;
        return String(a.pt ?? "").localeCompare(String(b.pt ?? ""));
      }
    });
    return copy;
  }

  function applyClientSort(key, numericHint = false) {
    if (!lastRows || lastRows.length === 0) return;

    if (sortState.key === key) {
      sortState.dir = sortState.dir === "desc" ? "asc" : "desc";
    } else {
      sortState.key = key;
      sortState.dir = "desc";
    }

    const sorted = sortRows(lastRows, sortState.key, sortState.dir, numericHint);
    renderRows(sorted);
    setStatus(`Sorted by ${sortState.key} (${sortState.dir})`, "info");
  }

  async function run() {
    const params = formToQueryParams();
    const url = `/api/signals?${params.toString()}`;

    runBtn.disabled = true;
    setStatus("Loading… (first run can be slow)", "loading");

    try {
      const res = await fetch(url, { headers: { "Accept": "application/json" } });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`HTTP ${res.status}: ${txt.slice(0, 300)}`);
      }
      const data = await res.json();

      NEl.textContent = data.N ?? "—";
      cachedEl.textContent = data.cached ? "true" : "false";
      timeEl.textContent = data.time_utc ?? "—";

      lastRows = data.results ?? [];
      // default client-side sort matches UI selection (sort_by) if present
      const sortKey = (params.get("sort_by") || "prr").toLowerCase();
      sortState = { key: sortKey, dir: "desc" };
      const numericHint = ["a", "b", "c", "d", "prr", "ror"].includes(sortKey);
      const sorted = sortRows(lastRows, sortKey, "desc", numericHint);

      renderRows(sorted);

      setStatus(
        `Done. Returned ${lastRows.length} rows. N=${data.N ?? "—"}${data.cached ? " (cached)" : ""}`,
        "ok"
      );
    } catch (e) {
      console.error(e);
      renderEmpty("Error loading results. Check console and API logs.");
      setStatus(`Error: ${e.message}`, "err");
    } finally {
      runBtn.disabled = false;
    }
  }

  // Table header click-to-sort
  table.querySelectorAll("thead th").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (!key) return;
      const numericHint = th.dataset.num === "1";
      applyClientSort(key, numericHint);
    });
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    run();
  });

  resetBtn.addEventListener("click", () => {
    form.reset();
    // keep year to 2023 as your default (optional)
    const yearEl = $("#year");
    if (yearEl) yearEl.value = "2023";
    renderEmpty("Run a query to see results.");
    NEl.textContent = "—";
    cachedEl.textContent = "—";
    timeEl.textContent = "—";
    setStatus("Ready.", "info");
  });

  // Auto-run once on load (small quality-of-life)
  window.addEventListener("load", () => {
    run();
  });
})();
