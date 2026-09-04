/* ==========================================================================
   Lawrence-Douglas County Public Health — Dashboard logic
   Loads two static JSON files (produced by the Jupyter notebook) and
   renders responsive Chart.js line charts. No build step, no CDN needed.
   ========================================================================== */

(function () {
  "use strict";

  // ---- Mobile nav toggle ----
  const navToggle = document.getElementById("navToggle");
  const mainNav = document.getElementById("mainNav");
  navToggle.addEventListener("click", () => {
    const open = mainNav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", String(open));
  });
  mainNav.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", () => {
      mainNav.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    })
  );

  document.getElementById("year").textContent = new Date().getFullYear();

  // ---- Brand color tokens (mirrors styles.css) ----
  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();

  const PATHOGEN_META = {
    covid: {
      label: "COVID-19",
      strong: color("--covid-strong"),
      soft: color("--covid-soft"),
    },
    influenza: {
      label: "Influenza",
      strong: color("--flu-strong"),
      soft: color("--flu-soft"),
    },
    rsv: {
      label: "RSV",
      strong: color("--rsv-strong"),
      soft: color("--rsv-soft"),
    },
  };

  const DATA_URLS = {
    ed: "assets/data/ed_visits.json",
    ww: "assets/data/wastewater.json",
  };

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 11;
  Chart.defaults.color = "#575757";

  function hexToRgba(hex, alpha) {
    const h = hex.replace("#", "");
    const bigint = parseInt(h, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r},${g},${b},${alpha})`;
  }

  // ---- Fetch both datasets ----
  Promise.all([
    fetch(DATA_URLS.ed).then((r) => r.json()),
    fetch(DATA_URLS.ww).then((r) => r.json()),
  ])
    .then(([edData, wwData]) => {
      renderLastUpdated(edData, wwData);
      renderStatGrid(edData, wwData);
      Object.keys(PATHOGEN_META).forEach((key) => {
        renderEdChart(key, edData);
        renderWastewaterChart(key, wwData);
      });
    })
    .catch((err) => {
      console.error("Failed to load dashboard data:", err);
      document.getElementById("statGrid").innerHTML =
        '<div class="state-msg">Data could not be loaded. Check that assets/data/*.json exist.</div>';
    });

  // ---- Last updated badge ----
  function renderLastUpdated(edData, wwData) {
    const dates = [edData.generated, wwData.generated].filter(Boolean).sort();
    const latest = dates[dates.length - 1];
    document.getElementById("lastUpdated").textContent = latest
      ? formatDate(latest)
      : "unknown";
  }

  // ---- "At a glance" stat cards ----
  function renderStatGrid(edData, wwData) {
    const grid = document.getElementById("statGrid");
    grid.innerHTML = "";

    Object.keys(PATHOGEN_META).forEach((key) => {
      const meta = PATHOGEN_META[key];
      const edSeries = findPathogen(edData.pathogens, key);
      const wwSeries = findPathogen(wwData.pathogens, key);

      const current = edSeries ? lastNonNull(edSeries.current) : null;
      const previous = edSeries ? valueAtSameIndex(edSeries.current, edSeries.previous) : null;
      const delta = current != null && previous != null && previous !== 0
        ? ((current - previous) / previous) * 100
        : null;

      const wwLatest = wwSeries && wwSeries.points.length
        ? wwSeries.points[wwSeries.points.length - 1]
        : null;

      const deltaClass = delta == null ? "flat" : delta > 5 ? "up" : delta < -5 ? "down" : "flat";
      const deltaText = delta == null
        ? "No comparison available"
        : `${delta > 0 ? "▲" : delta < 0 ? "▼" : "►"} ${Math.abs(delta).toFixed(0)}% vs. same week last year`;

      const card = document.createElement("div");
      card.className = "stat-card";
      card.style.setProperty("--stat-color", meta.strong);
      card.innerHTML = `
        <div class="stat-card__label"><span class="stat-card__swatch"></span>${meta.label} — ED visits</div>
        <div class="stat-card__value">${current != null ? current.toFixed(1) : "—"}
          <span class="stat-card__unit">${edData.unit || ""}</span>
        </div>
        <div class="stat-card__delta ${deltaClass}">${deltaText}</div>
      `;
      grid.appendChild(card);

      const wwCard = document.createElement("div");
      wwCard.className = "stat-card";
      wwCard.style.setProperty("--stat-color", meta.soft);
      wwCard.innerHTML = `
        <div class="stat-card__label"><span class="stat-card__swatch"></span>${meta.label} — Wastewater</div>
        <div class="stat-card__value">${wwLatest ? wwLatest.value.toLocaleString() : "—"}
          <span class="stat-card__unit">${wwData.unit || ""}</span>
        </div>
        <div class="stat-card__delta flat">${wwLatest ? "As of " + formatDate(wwLatest.date) : "No data"}</div>
      `;
      grid.appendChild(wwCard);
    });
  }

  // ---- ED chart: category axis (week labels), current vs. previous year ----
  function renderEdChart(key, edData) {
    const canvas = document.getElementById(`chart-${key}-ed`);
    if (!canvas) return;
    const series = findPathogen(edData.pathogens, key);
    if (!series) return;
    const meta = PATHOGEN_META[key];

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: series.week_labels,
        datasets: [
          {
            label: series.current_label || "Current",
            data: series.current,
            borderColor: meta.strong,
            backgroundColor: hexToRgba(meta.strong, 0.12),
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2.5,
            spanGaps: true,
          },
          {
            label: series.previous_label || "Previous",
            data: series.previous,
            borderColor: meta.soft,
            borderDash: [6, 4],
            fill: false,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2,
            spanGaps: true,
          },
        ],
      },
      options: baseLineOptions(edData.unit, "category"),
    });
  }

  // ---- Wastewater chart: linear/time-ish axis using epoch-day numbers ----
  function renderWastewaterChart(key, wwData) {
    const canvas = document.getElementById(`chart-${key}-ww`);
    if (!canvas) return;
    const series = findPathogen(wwData.pathogens, key);
    if (!series) return;
    const meta = PATHOGEN_META[key];

    const points = series.points.map((p) => ({
      x: dateToEpochDay(p.date),
      y: p.value,
    }));

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        datasets: [
          {
            label: meta.label,
            data: points,
            borderColor: meta.strong,
            backgroundColor: hexToRgba(meta.strong, 0.15),
            fill: true,
            tension: 0.25,
            pointRadius: 0,
            pointHoverRadius: 4,
            borderWidth: 2.5,
          },
        ],
      },
      options: {
        ...baseLineOptions(wwData.unit, "linear"),
        scales: {
          x: {
            type: "linear",
            ticks: {
              callback: (val) => formatEpochDay(val),
              maxRotation: 0,
              autoSkip: true,
              maxTicksLimit: 6,
            },
            grid: { display: false },
          },
          y: {
            beginAtZero: true,
            grid: { color: "#e2e6e9" },
            title: { display: !!wwData.unit, text: wwData.unit, font: { size: 10 } },
          },
        },
        plugins: {
          ...baseLineOptions(wwData.unit, "linear").plugins,
          tooltip: {
            callbacks: {
              title: (items) => formatEpochDay(items[0].parsed.x),
            },
          },
        },
      },
    });
  }

  function baseLineOptions(unit, xType) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 14, boxHeight: 3, padding: 14 },
        },
        tooltip: { backgroundColor: "#26292c", padding: 10, cornerRadius: 8 },
      },
      scales:
        xType === "category"
          ? {
              x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
              y: {
                beginAtZero: true,
                grid: { color: "#e2e6e9" },
                title: { display: !!unit, text: unit, font: { size: 10 } },
              },
            }
          : undefined,
    };
  }

  // ---- helpers ----
  function findPathogen(list, key) {
    return (list || []).find((p) => p.key === key);
  }
  function lastNonNull(arr) {
    for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return arr[i];
    return null;
  }
  function valueAtSameIndex(currentArr, previousArr) {
    for (let i = currentArr.length - 1; i >= 0; i--) {
      if (currentArr[i] != null) return previousArr[i] ?? null;
    }
    return null;
  }
  function dateToEpochDay(dateStr) {
    return Math.floor(new Date(dateStr + "T00:00:00").getTime() / 86400000);
  }
  function formatEpochDay(epochDay) {
    const d = new Date(epochDay * 86400000);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function formatDate(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }
})();
