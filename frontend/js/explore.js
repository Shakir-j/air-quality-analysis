/**
 * explore.js
 * ──────────
 * Data exploration controller:
 * - Multi-city comparative rankings
 * - Inter-pollutant correlation heatmaps
 * - City x Pollutant distribution matrix
 * - Seasonal pollution patterns
 * - Multi-year time-series trends
 */

let currentExploreTab = "city-comparison";

async function renderExploreViews() {
  const pollutant = document.getElementById("exp-pollutant")?.value || "PM2.5";
  onExploreTabSwitch(currentExploreTab, pollutant);
  loadSecondaryExploreCharts();
}

function onExploreTabSwitch(tabValue, pollutantOverride) {
  currentExploreTab = tabValue;
  const pollutant = pollutantOverride || document.getElementById("exp-pollutant")?.value || "PM2.5";

  const titleEl = document.getElementById("explore-chart-title");
  const subEl = document.getElementById("explore-chart-subtitle");

  switch (tabValue) {
    case "city-comparison":
      if (titleEl) titleEl.textContent = `Pollution levels by city (${pollutant})`;
      if (subEl) subEl.textContent = `Comparing historical mean ${pollutant} concentrations across all 10 monitored metropolitan centers.`;
      renderExploreCityComparison(pollutant);
      break;

    case "time-trend":
      if (titleEl) titleEl.textContent = `How ${pollutant} changed over time`;
      if (subEl) subEl.textContent = `Long-term historical trajectory (2010–2023) across major metropolitan regions.`;
      renderExploreTimeTrend(pollutant);
      break;

    case "correlations":
      if (titleEl) titleEl.textContent = "How pollutants move together";
      if (subEl) subEl.textContent = "Pearson correlation coefficients across particulates, combustion gases, and meteorological factors.";
      renderExploreCorrelations();
      break;

    case "city-pollutant-heatmap":
      if (titleEl) titleEl.textContent = "City × Pollutant distribution";
      if (subEl) subEl.textContent = "Cross-regional concentration matrix for all major monitored atmospheric pollutants.";
      renderExploreCityPollutantMatrix();
      break;

    case "seasonal-patterns":
      if (titleEl) titleEl.textContent = "Seasonal pollution patterns";
      if (subEl) subEl.textContent = "Mean PM2.5 concentration across Winter, Pre-Monsoon, Monsoon, and Post-Monsoon.";
      renderExploreSeasonalMatrix();
      break;
  }
}

// ── 1. City Comparison Bar Chart ─────────────────────────────────────────────
async function renderExploreCityComparison(pollutant) {
  const data = await apiGet(`/api/comparison?cities=Delhi,Patna,Lucknow,Ahmedabad,Kolkata,Mumbai,Pune,Hyderabad,Chennai,Bengaluru&pollutant=${encodeURIComponent(pollutant)}`);
  if (!data || !data.cities) return;

  const cities = data.cities.map((c) => c.city);
  const values = data.cities.map((c) => c.pollutant_avg || c.mean_pm25);
  const colors = data.cities.map((c) => c.color);

  const trace = {
    x: cities,
    y: values,
    type: "bar",
    marker: { color: colors },
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 480,
    showlegend: false,
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, title: `${pollutant} Mean Concentration (µg/m³)` },
  };

  Plotly.newPlot("explore-main-chart", [trace], layout, PLOTLY_CONFIG);
}

// ── 2. Time Trend Over Multi-Year Timeline ───────────────────────────────────
async function renderExploreTimeTrend(pollutant) {
  const cities = ["Delhi", "Mumbai", "Bengaluru", "Kolkata", "Chennai"];
  const traces = [];
  const palette = ["#ef4444", "#38bdf8", "#10b981", "#f59e0b", "#a855f7"];

  for (let i = 0; i < cities.length; i++) {
    const c = cities[i];
    const res = await apiGet(`/api/trends?city=${encodeURIComponent(c)}&pollutant=${encodeURIComponent(pollutant)}`);
    if (res && res.monthly_trend) {
      traces.push({
        x: res.monthly_trend.map((d) => d.period),
        y: res.monthly_trend.map((d) => {
          if (pollutant === "PM10") return d.pm10;
          if (pollutant === "NO2") return d.no2;
          return d.pm25_mean;
        }),
        type: "scatter",
        mode: "lines",
        name: c,
        line: { color: palette[i % palette.length], width: 2 },
        hovertemplate: `${c} %{x}: <b>%{y:.1f} µg/m³</b><extra></extra>`,
      });
    }
  }

  const layout = {
    ...PLOTLY_DARK,
    height: 480,
    showlegend: true,
    legend: { orientation: "h", y: 1.1, font: { color: "#94a3b8" } },
    yaxis: { ...PLOTLY_DARK.yaxis, title: `${pollutant} (µg/m³)` },
  };

  Plotly.newPlot("explore-main-chart", traces, layout, PLOTLY_CONFIG);
}

// ── 3. Correlation Heatmap ───────────────────────────────────────────────────
async function renderExploreCorrelations() {
  const data = await apiGet("/api/comparison");
  if (!data || !data.correlations) return;

  const corr = data.correlations;
  const trace = {
    z: corr.matrix,
    x: corr.labels,
    y: corr.labels,
    type: "heatmap",
    colorscale: [
      [0.0, "#08306b"],
      [0.25, "#2171b5"],
      [0.5, "#0b162c"],
      [0.75, "#f16913"],
      [1.0, "#d94801"],
    ],
    zmin: -0.5,
    zmax: 1.0,
    hovertemplate: "%{x} × %{y}: <b>r = %{z:.2f}</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 480,
    margin: { l: 80, r: 40, t: 40, b: 80 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, type: "category" },
  };

  Plotly.newPlot("explore-main-chart", [trace], layout, PLOTLY_CONFIG);
}

// ── 4. City x Pollutant Heatmap ──────────────────────────────────────────────
async function renderExploreCityPollutantMatrix() {
  const data = await apiGet("/api/comparison");
  if (!data || !data.city_pollutant_matrix) return;

  const cp = data.city_pollutant_matrix;
  const trace = {
    z: cp.values,
    x: cp.pollutants,
    y: cp.cities,
    type: "heatmap",
    colorscale: "Viridis",
    hovertemplate: "%{y} • %{x}: <b>%{z:.1f}</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 480,
    margin: { l: 100, r: 40, t: 40, b: 60 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, type: "category" },
  };

  Plotly.newPlot("explore-main-chart", [trace], layout, PLOTLY_CONFIG);
}

// ── 5. Seasonal Patterns Heatmap ─────────────────────────────────────────────
async function renderExploreSeasonalMatrix() {
  const data = await apiGet("/api/comparison");
  if (!data || !data.seasonal_patterns) return;

  const sp = data.seasonal_patterns;
  const trace = {
    z: sp.matrix,
    x: sp.cities,
    y: sp.seasons,
    type: "heatmap",
    colorscale: "Magma",
    hovertemplate: "%{y} in %{x}: <b>%{z:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 480,
    margin: { l: 140, r: 40, t: 40, b: 80 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, type: "category" },
  };

  Plotly.newPlot("explore-main-chart", [trace], layout, PLOTLY_CONFIG);
}

// ── Secondary Visualizations (Seasonal & Correlation Snippets) ───────────────
async function loadSecondaryExploreCharts() {
  const data = await apiGet("/api/comparison");
  if (!data) return;

  // 1. Seasonal bar comparison for top cities
  if (data.seasonal_patterns) {
    const sp = data.seasonal_patterns;
    const citiesToShow = ["Delhi", "Mumbai", "Bengaluru", "Kolkata"];
    const seasons = sp.seasons;

    const traces = seasons.map((seasonName, sIdx) => {
      return {
        name: seasonName.split(" ")[0],
        x: citiesToShow,
        y: citiesToShow.map((c) => {
          const cIdx = sp.cities.indexOf(c);
          return cIdx !== -1 ? sp.matrix[sIdx][cIdx] : 0;
        }),
        type: "bar",
      };
    });

    const layout = {
      ...PLOTLY_DARK,
      height: 280,
      barmode: "group",
      showlegend: true,
      legend: { orientation: "h", y: 1.15, font: { color: "#94a3b8", size: 10 } },
      xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
      yaxis: { ...PLOTLY_DARK.yaxis, title: "PM2.5 (µg/m³)" },
    };

    Plotly.newPlot("explore-seasonal-chart", traces, layout, PLOTLY_CONFIG);
  }

  // 2. Correlation snippet
  if (data.correlations) {
    const corr = data.correlations;
    const pollSubset = ["PM2.5", "PM10", "NO2", "SO2", "CO"];
    const indices = pollSubset.map((p) => corr.labels.indexOf(p));
    const subMatrix = indices.map((i) => indices.map((j) => corr.matrix[i][j]));

    const trace = {
      z: subMatrix,
      x: pollSubset,
      y: pollSubset,
      type: "heatmap",
      colorscale: "Tealrose",
      zmin: 0,
      zmax: 1,
      hovertemplate: "%{x} × %{y}: <b>r = %{z:.2f}</b><extra></extra>",
    };

    const layout = {
      ...PLOTLY_DARK,
      height: 280,
      margin: { l: 60, r: 20, t: 20, b: 40 },
      xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
      yaxis: { ...PLOTLY_DARK.yaxis, type: "category" },
    };

    Plotly.newPlot("explore-corr-chart", [trace], layout, PLOTLY_CONFIG);
  }
}
