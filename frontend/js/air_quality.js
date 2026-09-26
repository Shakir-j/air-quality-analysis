/**
 * air_quality.js
 * ──────────────
 * Location-specific air quality inspection:
 * - City & Station selectors
 * - Large official AQI gauge indicator
 * - Pollutant metric cards (PM2.5, PM10, NO2, SO2, CO, O3)
 * - 48-Hour recent trend line chart
 * - Daily diurnal commuter cycle breakdown
 * - Historical monthly/yearly time-series exploration
 */

let currentHistViewMode = "monthly";
let currentAQData = null;

async function renderAirQualityView() {
  const city = AppState.selectedCity || "Delhi";
  await loadAirQualityData(city);
}

function onAirQualityCityChange() {
  const select = document.getElementById("aq-city-select");
  if (select && select.value) {
    AppState.selectedCity = select.value;
    loadAirQualityData(select.value);
  }
}

function onAirQualityStationChange() {
  const select = document.getElementById("aq-station-select");
  if (select) {
    AppState.selectedStation = select.value;
    loadAirQualityData(AppState.selectedCity);
  }
}

function onAirQualityPollutantChange() {
  const select = document.getElementById("aq-pollutant-select");
  if (select) {
    AppState.selectedPollutant = select.value;
    if (currentAQData) {
      renderAQRecentTrendChart(currentAQData);
    }
    loadAirQualityHistorical(AppState.selectedCity, select.value, currentHistViewMode);
  }
}

async function loadAirQualityData(cityName) {
  const data = await apiGet(`/api/air-quality?city=${encodeURIComponent(cityName)}`);
  if (!data) return;
  currentAQData = data;

  // 1. Populate Stations dropdown
  const stnSelect = document.getElementById("aq-station-select");
  if (stnSelect && data.stations) {
    const prevVal = stnSelect.value;
    stnSelect.innerHTML = `<option value="all">All Stations (${data.station_count} Active Monitoring Stations)</option>`;
    data.stations.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.station_id;
      opt.textContent = `${s.station_location} (${s.mean_pm25} µg/m³ avg)`;
      if (s.station_id === prevVal) opt.selected = true;
      stnSelect.appendChild(opt);
    });
  }

  // 2. Render Main Gauge / Status Indicator
  renderAQMainIndicator(data);

  // 3. Render Pollutant Cards (PM2.5, PM10, NO2, SO2, CO, O3)
  renderPollutantCards(data);

  // 4. Render 48-hour Recent Trend
  renderAQRecentTrendChart(data);

  // 5. Render Diurnal Breakdown
  renderAQDiurnalChart(data);
  renderAQBreakdownBar(data);

  // 6. Render Historical
  loadAirQualityHistorical(cityName, AppState.selectedPollutant, currentHistViewMode);
}

function renderAQMainIndicator(data) {
  const container = document.getElementById("aq-main-indicator");
  if (!container) return;

  const lat = data.latest_recorded;
  const health = getHealthGuidance(lat.category);

  container.innerHTML = `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <span class="aqi-label-eyebrow">National Air Quality Index</span>
        <span class="badge" style="background-color: ${lat.color}22; color: ${lat.color}; border: 1px solid ${lat.color}66;">
          ${lat.category}
        </span>
      </div>

      <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
        <span style="font-size: 52px; font-weight: 800; color: ${lat.color}; line-height: 1;">
          ${Math.round(lat.aqi)}
        </span>
        <span style="font-size: 15px; color: var(--text-muted); font-weight: 500;">NAQI Score</span>
      </div>

      <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 20px;">
        Primary pollutant: <strong>Fine Particulate Matter (PM2.5)</strong>
      </p>

      <div style="background-color: var(--bg-surface); border-radius: var(--radius-sm); padding: 14px; border: 1px solid var(--border-subtle); margin-bottom: 16px;">
        <div style="font-size: 12px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">Health Advisory:</div>
        <div style="font-size: 13px; color: var(--text-secondary); line-height: 1.5;">${health.advisory}</div>
      </div>
    </div>

    <div style="font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px;">
      Recorded at: ${lat.timestamp.split(" ")[0]} • Station: ${lat.station_location || data.city}
    </div>
  `;
}

function renderPollutantCards(data) {
  const container = document.getElementById("aq-pollutant-cards");
  if (!container) return;

  const avgs = data.pollutant_averages || {};
  const lat = data.latest_recorded || {};

  const pollutantsConfig = [
    { key: "PM2.5", name: "PM2.5", unit: "µg/m³", standard: 60, val: lat.pm25, avg: avgs["PM2.5"] },
    { key: "PM10", name: "PM10", unit: "µg/m³", standard: 100, val: lat.pm10, avg: avgs["PM10"] },
    { key: "NO2", name: "NO₂", unit: "µg/m³", standard: 80, val: lat.no2, avg: avgs["NO2"] },
    { key: "SO2", name: "SO₂", unit: "µg/m³", standard: 80, val: lat.so2, avg: avgs["SO2"] },
    { key: "CO", name: "CO", unit: "mg/m³", standard: 2.0, val: lat.co, avg: avgs["CO"] },
    { key: "Ozone", name: "Ozone (O₃)", unit: "µg/m³", standard: 100, val: lat.ozone, avg: avgs["Ozone"] },
  ];

  container.innerHTML = pollutantsConfig
    .map((p) => {
      const displayVal = p.val !== null && p.val !== undefined ? p.val : (p.avg !== null ? p.avg : "—");
      const isNum = typeof displayVal === "number";
      const ratio = isNum ? Math.min(100, Math.round((displayVal / p.standard) * 100)) : 0;
      
      let barColor = "var(--aqi-good)";
      if (ratio >= 75) barColor = "var(--aqi-moderate)";
      if (ratio >= 100) barColor = "var(--aqi-poor)";
      if (ratio >= 150) barColor = "var(--aqi-very-poor)";
      if (ratio >= 200) barColor = "var(--aqi-severe)";

      return `
        <div class="pollutant-card">
          <div>
            <div class="pollutant-header">
              <span class="pollutant-name">${p.name}</span>
              <span class="pollutant-standard">Std: ${p.standard} ${p.unit}</span>
            </div>
            <div class="pollutant-reading">
              <span class="pollutant-val">${displayVal}</span>
              <span class="pollutant-unit">${p.unit}</span>
            </div>
          </div>
          <div>
            <div class="pollutant-bar-bg">
              <div class="pollutant-bar-fill" style="width: ${ratio}%; background-color: ${barColor};"></div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 6px; font-size: 11px; color: var(--text-muted);">
              <span>${ratio}% of 24h standard</span>
              <span>Hist. Avg: ${p.avg || "—"}</span>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderAQRecentTrendChart(data) {
  const chartEl = document.getElementById("aq-recent-trend-chart");
  if (!chartEl || !data.recent_trend || data.recent_trend.length === 0) return;

  const trend = data.recent_trend;
  const times = trend.map((t) => t.time);
  const activePoll = AppState.selectedPollutant || "PM2.5";
  
  const pollKeyMap = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "NO2": "no2",
    "SO2": "so2",
    "CO": "co",
    "Ozone": "ozone",
  };
  const activeKey = pollKeyMap[activePoll] || "pm25";
  const activeVals = trend.map((t) => t[activeKey]);

  const traces = [
    {
      x: times,
      y: activeVals,
      name: `${activePoll} (Active Focus)`,
      type: "scatter",
      mode: "lines+markers",
      line: { color: "#14b8a6", width: 2.5 },
      marker: { size: 4, color: "#14b8a6" },
      hovertemplate: `%{x}<br>${activePoll}: <b>%{y:.1f}</b><extra></extra>`,
    },
  ];

  if (activePoll !== "PM2.5") {
    traces.push({
      x: times,
      y: trend.map((t) => t.pm25),
      name: "PM2.5 Reference",
      type: "scatter",
      mode: "lines",
      line: { color: "#64748b", width: 1.5, dash: "dot" },
      hovertemplate: "%{x}<br>PM2.5: <b>%{y:.1f}</b><extra></extra>",
    });
  }

  const layout = {
    ...PLOTLY_DARK,
    height: 340,
    showlegend: true,
    legend: { x: 0.02, y: 0.98, bgcolor: "rgba(0,0,0,0)", font: { color: "#94a3b8" } },
    yaxis: { ...PLOTLY_DARK.yaxis, title: `${activePoll} Concentration` },
  };

  Plotly.newPlot("aq-recent-trend-chart", traces, layout, PLOTLY_CONFIG);
}

function renderAQDiurnalChart(data) {
  const chartEl = document.getElementById("aq-diurnal-chart");
  if (!chartEl || !data.diurnal_pattern) return;

  const hours = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);
  const cityVals = data.diurnal_pattern;
  const natVals = data.national_diurnal || [];

  const traceCity = {
    x: hours,
    y: cityVals,
    name: `${data.city} Average`,
    type: "scatter",
    mode: "lines+markers",
    line: { color: "#f59e0b", width: 2.2 },
    marker: { size: 5, color: "#f59e0b" },
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const traceNat = {
    x: hours,
    y: natVals,
    name: "National Average",
    type: "scatter",
    mode: "lines",
    line: { color: "#64748b", width: 1.5, dash: "dash" },
    hovertemplate: "National: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 280,
    showlegend: true,
    legend: { x: 0.02, y: 0.98, bgcolor: "rgba(0,0,0,0)", font: { color: "#94a3b8" } },
    yaxis: { ...PLOTLY_DARK.yaxis, title: "PM2.5 (µg/m³)" },
  };

  Plotly.newPlot("aq-diurnal-chart", [traceCity, traceNat], layout, PLOTLY_CONFIG);
}

function renderAQBreakdownBar(data) {
  const chartEl = document.getElementById("aq-breakdown-bar");
  if (!chartEl || !data.pollutant_averages) return;

  const avgs = data.pollutant_averages;
  const labels = ["PM2.5", "PM10", "NO₂", "SO₂", "Ozone"];
  const values = [
    avgs["PM2.5"] || 0,
    avgs["PM10"] || 0,
    avgs["NO2"] || 0,
    avgs["SO2"] || 0,
    avgs["Ozone"] || 0,
  ];

  const trace = {
    x: labels,
    y: values,
    type: "bar",
    marker: {
      color: ["#14b8a6", "#38bdf8", "#f59e0b", "#f97316", "#a855f7"],
    },
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 280,
    showlegend: false,
    yaxis: { ...PLOTLY_DARK.yaxis, title: "Historical Mean (µg/m³)" },
  };

  Plotly.newPlot("aq-breakdown-bar", [trace], layout, PLOTLY_CONFIG);
}

async function loadAirQualityHistorical(cityName, pollutant, mode) {
  const chartEl = document.getElementById("aq-historical-chart");
  if (!chartEl) return;

  const res = await apiGet(`/api/trends?city=${encodeURIComponent(cityName)}&pollutant=${encodeURIComponent(pollutant)}`);
  if (!res) return;

  if (mode === "monthly" && res.monthly_trend) {
    const x = res.monthly_trend.map((m) => m.period);
    const y = res.monthly_trend.map((m) => {
      if (pollutant === "PM10") return m.pm10;
      if (pollutant === "NO2") return m.no2;
      if (pollutant === "SO2") return m.so2;
      return m.pm25_mean;
    });

    const trace = {
      x,
      y,
      type: "scatter",
      mode: "lines",
      line: { color: "#38bdf8", width: 2 },
      fill: "tozeroy",
      fillcolor: "rgba(56, 189, 248, 0.08)",
      hovertemplate: "%{x}<br><b>%{y:.1f} µg/m³</b><extra></extra>",
    };

    const layout = {
      ...PLOTLY_DARK,
      height: 380,
      showlegend: false,
      yaxis: { ...PLOTLY_DARK.yaxis, title: `${pollutant} (µg/m³)` },
    };

    Plotly.newPlot("aq-historical-chart", [trace], layout, PLOTLY_CONFIG);
  } else if (mode === "yearly" && res.yearly_trend) {
    const x = res.yearly_trend.map((d) => d.year.toString());
    const pollKeyMap = {
      "PM2.5": "pm25_mean",
      "PM10": "pm10_mean",
      "NO2": "no2",
      "SO2": "so2",
    };
    const activeKey = pollKeyMap[pollutant] || "pm25_mean";
    const y = res.yearly_trend.map((d) => d[activeKey] ?? d.pm25_mean);

    const trace = {
      x,
      y,
      type: "bar",
      marker: { color: "#14b8a6" },
      hovertemplate: "Year %{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
    };

    const layout = {
      ...PLOTLY_DARK,
      height: 380,
      showlegend: false,
      yaxis: { ...PLOTLY_DARK.yaxis, title: `Annual Mean ${pollutant} (µg/m³)` },
    };

    Plotly.newPlot("aq-historical-chart", [trace], layout, PLOTLY_CONFIG);
  }
}

function switchHistoricalView(mode) {
  currentHistViewMode = mode;
  document.getElementById("btn-hist-monthly")?.classList.toggle("active", mode === "monthly");
  document.getElementById("btn-hist-yearly")?.classList.toggle("active", mode === "yearly");
  loadAirQualityHistorical(AppState.selectedCity, AppState.selectedPollutant, mode);
}
