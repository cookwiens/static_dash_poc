/* ==========================================================================
   Lawrence-Douglas County Public Health — Dashboard logic
   Loads three static JSON files (produced by the Jupyter notebook) and
   renders responsive Chart.js line charts, plus a staff-authored narrative.
   No build step, no CDN needed.
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
    narrative: "assets/data/narrative.json",
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

  // ---- Fetch all three datasets ----
  Promise.all([
    fetch(DATA_URLS.ed).then((r) => r.json()),
    fetch(DATA_URLS.ww).then((r) => r.json()),
    fetch(DATA_URLS.narrative).then((r) => r.json()).catch(() => null),
  ])
    .then(([edData, wwData, narrativeData]) => {
      renderLastUpdated(edData, wwData, narrativeData);
      renderNarrative(narrativeData);
      Object.keys(PATHOGEN_META).forEach((key) => {
        const edSeries = findPathogen(edData.pathogens, key);
        const wwSeries = findPathogen(wwData.pathogens, key);
        if (!edSeries || !wwSeries) return;

        const shared = computeSharedXAxis(edSeries.dates, wwSeries.points.map((p) => p.date));
        renderEdChart(key, edSeries, edData.unit, shared);
        renderWastewaterChart(key, wwSeries, wwData.unit, shared);
      });
    })
    .catch((err) => {
      console.error("Failed to load dashboard data:", err);
      document.getElementById("narrativeBox").innerHTML =
        '<p class="state-msg">Data could not be loaded. Check that assets/data/*.json exist.</p>';
    });

  // ---- Last updated badge ----
  function renderLastUpdated(edData, wwData, narrativeData) {
    const dates = [edData.generated, wwData.generated, narrativeData && narrativeData.generated]
      .filter(Boolean)
      .sort();
    const latest = dates[dates.length - 1];
    document.getElementById("lastUpdated").textContent = latest ? formatDate(latest) : "unknown";
  }

  // ---- Narrative summary (staff-authored, limited HTML allowed) ----
  const ALLOWED_NARRATIVE_TAGS = ["b", "i", "hr", "br", "strong", "em", "u", "p"];

  function sanitizeNarrativeHtml(raw, allowedTags) {
    allowedTags = allowedTags || ALLOWED_NARRATIVE_TAGS;
    const template = document.createElement("template");
    template.innerHTML = raw;

    function walk(node) {
      // Snapshot childNodes first since we mutate the tree while iterating.
      Array.from(node.childNodes).forEach((child) => {
        if (child.nodeType === Node.ELEMENT_NODE) {
          const tag = child.tagName.toLowerCase();
          walk(child); // sanitize children before deciding this node's fate
          if (tag === "script" || tag === "style") {
            child.remove(); // drop disallowed + inherently unsafe tags entirely
          } else if (!allowedTags.includes(tag)) {
            // Unwrap: keep the text/children, discard the tag itself
            while (child.firstChild) node.insertBefore(child.firstChild, child);
            node.removeChild(child);
          } else {
            // Allowed tag — strip all attributes (blocks onclick=, href=javascript:, etc.)
            Array.from(child.attributes).forEach((attr) => child.removeAttribute(attr.name));
          }
        }
        // text nodes pass through untouched
      });
    }

    walk(template.content);
    return template.innerHTML;
  }

  function renderNarrative(narrativeData) {
    const box = document.getElementById("narrativeBox");
    if (!narrativeData || !narrativeData.html || !narrativeData.html.trim()) {
      box.innerHTML = '<p class="state-msg">No current situation summary has been posted yet.</p>';
      return;
    }
    box.innerHTML = sanitizeNarrativeHtml(narrativeData.html);
  }

  // ---- Shared x-axis (ED weeks + wastewater samples, same range & ticks) ----
  function computeSharedXAxis(edDates, wwDates) {
    const allDays = [...edDates, ...wwDates].map(dateToEpochDay);
    const min = Math.min(...allDays);
    const max = Math.max(...allDays);
    const span = Math.max(max - min, 1);
    const targetTicks = 6;
    let stepDays = 7;
    while (span / stepDays > targetTicks) stepDays += 7;
    return { min, max, stepSize: stepDays };
  }

  function sharedXScale(shared) {
    return {
      type: "linear",
      min: shared.min,
      max: shared.max,
      ticks: {
        stepSize: shared.stepSize,
        callback: (val) => formatEpochDay(val),
        maxRotation: 0,
        autoSkip: false,
      },
      grid: { display: false },
    };
  }

  // ---- ED chart: linear date axis, current vs. previous year overlaid at same x ----
  function renderEdChart(key, series, unit, shared) {
    const canvas = document.getElementById(`chart-${key}-ed`);
    if (!canvas) return;
    const meta = PATHOGEN_META[key];
    const xs = series.dates.map(dateToEpochDay);

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        datasets: [
          {
            label: series.current_label || "Current",
            data: xs.map((x, i) => ({ x, y: series.current[i] })),
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
            data: xs.map((x, i) => ({ x, y: series.previous[i] })),
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
      options: baseLineOptions(unit, shared),
    });
  }

  // ---- Wastewater chart: same shared date axis, irregular sample spacing ----
  function renderWastewaterChart(key, series, unit, shared) {
    const canvas = document.getElementById(`chart-${key}-ww`);
    if (!canvas) return;
    const meta = PATHOGEN_META[key];

    const points = series.points.map((p) => ({ x: dateToEpochDay(p.date), y: p.value }));

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
      options: baseLineOptions(unit, shared, { titleFromEpoch: true }),
    });
  }

  function baseLineOptions(unit, shared, opts) {
    opts = opts || {};
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: { boxWidth: 14, boxHeight: 3, padding: 14 },
        },
        tooltip: {
          backgroundColor: "#26292c",
          padding: 10,
          cornerRadius: 8,
          callbacks: opts.titleFromEpoch
            ? { title: (items) => formatEpochDay(items[0].parsed.x) }
            : undefined,
        },
      },
      scales: {
        x: sharedXScale(shared),
        y: {
          beginAtZero: true,
          grid: { color: "#e2e6e9" },
          title: { display: !!unit, text: unit, font: { size: 10 } },
        },
      },
    };
  }

  // ---- helpers ----
  function findPathogen(list, key) {
    return (list || []).find((p) => p.key === key);
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
