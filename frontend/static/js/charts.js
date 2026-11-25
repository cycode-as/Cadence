/**
 * CADENCE Chart.js Renderer & Live Updater
 * Reads JSON config embedded in `<script type="application/json" id="<canvasId>-data">`
 * and redraws smoothly on theme toggle or `cadence:ws-event`.
 */
(function () {
  const instances = new Map();

  const PALETTE = [
    "#4A5D23", // Olive
    "#1B2A4A", // Navy
    "#C3B091", // Khaki
    "#D97706", // Amber
    "#2F855A", // Forest Green
    "#B91C1C", // Crimson
  ];

  function getThemeColors() {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      text: isDark ? "#E8EDF5" : "#1B2432",
      muted: isDark ? "#9AA7BA" : "#5B6472",
      grid: isDark ? "rgba(154, 167, 186, 0.14)" : "rgba(27, 36, 50, 0.08)",
      surface: isDark ? "#18202C" : "#FFFFFF",
    };
  }

  function normalizeDatasets(rawConfig, chartType) {
    const datasets = (rawConfig.datasets || []).map((ds, idx) => {
      const baseColor = ds.color || PALETTE[idx % PALETTE.length];
      if (chartType === "doughnut" || chartType === "pie") {
        return {
          ...ds,
          backgroundColor: ds.backgroundColor || PALETTE.slice(0, (ds.data || []).length),
          borderColor: getThemeColors().surface,
          borderWidth: 2,
        };
      }
      if (chartType === "line") {
        return {
          tension: 0.3,
          fill: ds.fill !== undefined ? ds.fill : true,
          borderWidth: 2.5,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderColor: baseColor,
          backgroundColor: ds.backgroundColor || "rgba(74, 93, 35, 0.14)",
          ...ds,
        };
      }
      return {
        borderRadius: 6,
        maxBarThickness: 42,
        backgroundColor: ds.backgroundColor || baseColor,
        ...ds,
      };
    });
    return datasets;
  }

  function buildChart(canvas) {
    if (!window.Chart) return;
    const dataScript = document.getElementById(`${canvas.id}-data`);
    if (!dataScript) return;

    let rawConfig;
    try {
      rawConfig = JSON.parse(dataScript.textContent || "{}");
    } catch (_err) {
      return;
    }

    const existing = instances.get(canvas.id);
    if (existing) {
      existing.destroy();
      instances.delete(canvas.id);
    }

    const chartType = rawConfig.type || "bar";
    const colors = getThemeColors();
    const isCircular = chartType === "doughnut" || chartType === "pie";

    const chart = new window.Chart(canvas.getContext("2d"), {
      type: chartType,
      data: {
        labels: rawConfig.labels || [],
        datasets: normalizeDatasets(rawConfig, chartType),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: isCircular ? "nearest" : "index",
          intersect: false,
        },
        plugins: {
          legend: {
            display: rawConfig.show_legend !== undefined ? rawConfig.show_legend : isCircular || (rawConfig.datasets || []).length > 1,
            position: isCircular ? "bottom" : "top",
            labels: {
              color: colors.text,
              boxWidth: 12,
              font: { size: 12 },
            },
          },
          tooltip: {
            backgroundColor: "#1B2A4A",
            titleColor: "#FFFFFF",
            bodyColor: "#F4EFE6",
          },
        },
        scales: isCircular
          ? {}
          : {
              x: {
                ticks: { color: colors.muted, font: { size: 11 } },
                grid: { display: false },
              },
              y: {
                beginAtZero: true,
                suggestedMax: rawConfig.suggested_max || undefined,
                ticks: { color: colors.muted, font: { size: 11 } },
                grid: { color: colors.grid },
              },
            },
        onClick: function (_evt, elements) {
          if (!elements || !elements.length) return;
          const idx = elements[0].index;
          if (rawConfig.drill && window.CadenceDrill && typeof window.CadenceDrill.onBarClick === "function") {
            window.CadenceDrill.onBarClick(rawConfig.drill, idx, canvas.dataset.drillEndpoint);
          }
        },
      },
    });

    instances.set(canvas.id, chart);
  }

  function initAll() {
    document.querySelectorAll('canvas[data-cadence-chart="true"]').forEach(buildChart);
  }

  async function refreshFromEndpoint(canvas) {
    const endpoint = canvas.dataset.analyticsUrl;
    if (!endpoint) return;
    try {
      const res = await fetch(endpoint, { headers: { Accept: "application/json" } });
      if (!res.ok) return;
      const fresh = await res.json();
      const script = document.getElementById(`${canvas.id}-data`);
      if (script) {
        script.textContent = JSON.stringify(fresh);
      }
      buildChart(canvas);
    } catch (_err) {
      // Non-fatal in standalone/mock mode
    }
  }

  document.addEventListener("DOMContentLoaded", initAll);
  document.body.addEventListener("htmx:afterSwap", initAll);

  // Redraw when user switches light/dark theme
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === "data-theme") {
        initAll();
        break;
      }
    }
  });
  observer.observe(document.documentElement, { attributes: true });

  // Redraw or refetch charts on relevant WebSocket updates
  document.addEventListener("cadence:ws-event", (evt) => {
    const name = evt.detail && evt.detail.event;
    if (name === "dashboard.refresh" || name === "attendance.updated" || name === "leave.updated") {
      document.querySelectorAll('canvas[data-cadence-chart="true"]').forEach((canvas) => {
        if (canvas.dataset.analyticsUrl) {
          refreshFromEndpoint(canvas);
        } else {
          buildChart(canvas);
        }
      });
    }
  });

  window.CadenceCharts = {
    initAll,
    buildChart,
    instances,
  };
})();
