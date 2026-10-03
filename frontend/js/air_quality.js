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

  const avgs = data.pollutant_averages || {};

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

      <button
        id="btn-send-to-prediction"
        onclick="sendToPrediction()"
        style="
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 11px 18px;
          background-color: var(--accent-teal);
          color: #fff;
          border: none;
          border-radius: var(--radius-md);
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          font-family: inherit;
          transition: background-color 0.15s ease;
        "
        onmouseover="this.style.backgroundColor='var(--accent-teal-light)'"
        onmouseout="this.style.backgroundColor='var(--accent-teal)'"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
        Predict Next Hour with These Values
      </button>
    </div>

    <div style="font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px; margin-top: 16px;">
      Recorded at: ${lat.timestamp.split(" ")[0]} • Station: ${lat.station_location || data.city}
    </div>
  `;

  // Store current values for the send-to-prediction button
  window._aqCurrentData = {
    city: data.city,
    pm25: lat.pm25 ?? avgs["PM2.5"] ?? null,
    no2:  lat.no2  ?? avgs["NO2"]  ?? null,
    so2:  lat.so2  ?? avgs["SO2"]  ?? null,
    co:   lat.co   ?? avgs["CO"]   ?? null,
    ozone: lat.ozone ?? avgs["Ozone"] ?? null,
  };
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

  // Use integer 0-23 as x values to avoid Plotly date auto-detection on "HH:00" strings
  const hourInts = Array.from({ length: 24 }, (_, i) => i);
  const hourLabels = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);
  const cityVals = data.diurnal_pattern;
  const natVals = data.national_diurnal || [];

  const traceCity = {
    x: hourInts,
    y: cityVals,
    name: `${data.city} Average`,
    type: "scatter",
    mode: "lines+markers",
    line: { color: "#f59e0b", width: 2.2 },
    marker: { size: 5, color: "#f59e0b" },
    hovertemplate: "%{text}: <b>%{y:.1f} µg/m³</b><extra></extra>",
    text: hourLabels,
  };

  const traceNat = {
    x: hourInts,
    y: natVals,
    name: "National Average",
    type: "scatter",
    mode: "lines",
    line: { color: "#64748b", width: 1.5, dash: "dash" },
    hovertemplate: "National %{text}: <b>%{y:.1f} µg/m³</b><extra></extra>",
    text: hourLabels,
  };

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", color: "#94a3b8", size: 12 },
    margin: { l: 50, r: 25, t: 20, b: 50 },
    height: 280,
    showlegend: true,
    legend: { x: 0.02, y: 0.98, bgcolor: "rgba(0,0,0,0)", font: { color: "#94a3b8" } },
    xaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      tickmode: "array",
      tickvals: [0, 3, 6, 9, 12, 15, 18, 21, 23],
      ticktext: ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "23:00"],
      title: { text: "Hour of Day", font: { color: "#94a3b8" } },
    },
    yaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      title: { text: "PM2.5 (µg/m³)", font: { color: "#94a3b8" } },
    },
  };

  Plotly.newPlot("aq-diurnal-chart", [traceCity, traceNat], layout, PLOTLY_CONFIG);
}

function renderAQBreakdownBar(data) {
  const chartEl = document.getElementById("aq-breakdown-bar");
  if (!chartEl || !data.pollutant_averages) return;

  const avgs = data.pollutant_averages;
  // Use ASCII keys for x so Plotly never tries to date-parse them
  const keys = ["PM2.5", "PM10", "NO2", "SO2", "Ozone"];
  const displayLabels = ["PM2.5", "PM10", "NO\u2082", "SO\u2082", "Ozone"];
  const values = [
    avgs["PM2.5"] || 0,
    avgs["PM10"] || 0,
    avgs["NO2"] || 0,
    avgs["SO2"] || 0,
    avgs["Ozone"] || 0,
  ];

  const trace = {
    x: keys,
    y: values,
    type: "bar",
    marker: {
      color: ["#14b8a6", "#38bdf8", "#f59e0b", "#f97316", "#a855f7"],
    },
    hovertemplate: "%{x}: <b>%{y:.1f} \u00b5g/m\u00b3</b><extra></extra>",
  };

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", color: "#94a3b8", size: 12 },
    margin: { l: 50, r: 25, t: 20, b: 50 },
    height: 280,
    showlegend: false,
    xaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      type: "category",
      tickvals: keys,
      ticktext: displayLabels,
    },
    yaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      title: { text: "Historical Mean (\u00b5g/m\u00b3)", font: { color: "#94a3b8" } },
    },
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
      marker: { color: "#40916c" },
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

/**
 * sendToPrediction
 * ────────────────
 * Reads the pollutant values currently displayed on the Air Quality tab,
 * auto-fills the Prediction form with them, then navigates to Prediction.
 * The user only needs to adjust Hour, Month, and Day Type for their target date.
 */
function sendToPrediction() {
  const d = window._aqCurrentData;
  if (!d) return;

  // Navigate to Prediction tab first
  if (typeof navigateTo === "function") navigateTo("prediction");

  // Small delay to let the section render before filling fields
  setTimeout(() => {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el && val !== null && val !== undefined) el.value = val;
    };

    // City
    setVal("pred-city", d.city);

    // PM2.5 — current + reasonable lag estimates (±5% spread)
    if (d.pm25 !== null) {
      setVal("pred-pm25",      parseFloat(d.pm25).toFixed(1));
      setVal("pred-pm25-lag2", (d.pm25 * 1.04).toFixed(1));  // 2h ago ~4% higher
      setVal("pred-pm25-lag3", (d.pm25 * 1.07).toFixed(1));  // 3h ago ~7% higher
    }

    // Pollutant gases
    if (d.no2   !== null) setVal("pred-no2",   parseFloat(d.no2).toFixed(1));
    if (d.co    !== null) setVal("pred-co",    parseFloat(d.co).toFixed(2));
    if (d.so2   !== null) setVal("pred-so2",   parseFloat(d.so2).toFixed(1));
    if (d.ozone !== null) setVal("pred-ozone", parseFloat(d.ozone).toFixed(1));

    // Set month and hour to current real time
    const now = new Date();
    const currentMonth = now.getMonth() + 1; // JS months are 0-indexed
    setVal("pred-month", currentMonth);
    setVal("pred-hour",  now.getHours());
    setVal("pred-weekend", (now.getDay() === 0 || now.getDay() === 6) ? 1 : 0);

    // Auto-fill Temperature, Humidity, and Wind Speed based on City & Season
    const climateLookup = {
      "Delhi": { "winter": { temp: 15, rh: 65, ws: 1.5 }, "summer": { temp: 35, rh: 30, ws: 3.0 }, "monsoon": { temp: 30, rh: 75, ws: 2.5 }, "post_monsoon": { temp: 25, rh: 55, ws: 1.8 } },
      "Mumbai": { "winter": { temp: 26, rh: 60, ws: 3.5 }, "summer": { temp: 30, rh: 65, ws: 4.0 }, "monsoon": { temp: 28, rh: 85, ws: 5.0 }, "post_monsoon": { temp: 29, rh: 70, ws: 3.8 } },
      "Chennai": { "winter": { temp: 25, rh: 70, ws: 3.5 }, "summer": { temp: 32, rh: 65, ws: 4.5 }, "monsoon": { temp: 30, rh: 70, ws: 4.0 }, "post_monsoon": { temp: 28, rh: 75, ws: 3.2 } },
      "Bengaluru": { "winter": { temp: 20, rh: 55, ws: 2.5 }, "summer": { temp: 27, rh: 40, ws: 3.0 }, "monsoon": { temp: 23, rh: 75, ws: 4.5 }, "post_monsoon": { temp: 22, rh: 65, ws: 3.0 } },
      "Kolkata": { "winter": { temp: 18, rh: 60, ws: 1.5 }, "summer": { temp: 32, rh: 55, ws: 3.5 }, "monsoon": { temp: 29, rh: 80, ws: 2.5 }, "post_monsoon": { temp: 26, rh: 70, ws: 1.8 } },
      "Lucknow": { "winter": { temp: 15, rh: 70, ws: 1.2 }, "summer": { temp: 34, rh: 25, ws: 2.5 }, "monsoon": { temp: 29, rh: 80, ws: 2.0 }, "post_monsoon": { temp: 24, rh: 60, ws: 1.5 } },
      "Ahmedabad": { "winter": { temp: 20, rh: 45, ws: 2.0 }, "summer": { temp: 35, rh: 30, ws: 3.5 }, "monsoon": { temp: 30, rh: 75, ws: 4.0 }, "post_monsoon": { temp: 28, rh: 50, ws: 2.5 } },
      "Hyderabad": { "winter": { temp: 22, rh: 50, ws: 2.5 }, "summer": { temp: 33, rh: 35, ws: 3.5 }, "monsoon": { temp: 27, rh: 75, ws: 4.0 }, "post_monsoon": { temp: 25, rh: 60, ws: 3.0 } },
      "Patna": { "winter": { temp: 16, rh: 70, ws: 1.5 }, "summer": { temp: 33, rh: 30, ws: 2.8 }, "monsoon": { temp: 29, rh: 82, ws: 2.2 }, "post_monsoon": { temp: 25, rh: 65, ws: 1.5 } },
      "Pune": { "winter": { temp: 20, rh: 50, ws: 2.0 }, "summer": { temp: 31, rh: 35, ws: 3.5 }, "monsoon": { temp: 25, rh: 80, ws: 4.5 }, "post_monsoon": { temp: 24, rh: 60, ws: 2.5 } }
    };
    
    let season = "winter";
    if (currentMonth >= 3 && currentMonth <= 5) season = "summer";
    else if (currentMonth >= 6 && currentMonth <= 9) season = "monsoon";
    else if (currentMonth >= 10 && currentMonth <= 11) season = "post_monsoon";
    
    const cityClimate = climateLookup[d.city] || climateLookup["Delhi"];
    const weather = cityClimate[season];
    
    setVal("pred-temp", weather.temp);
    setVal("pred-rh", weather.rh);
    setVal("pred-ws", weather.ws);

    // Flash a brief highlight on the form to show it was filled
    const form = document.getElementById("prediction-form");
    if (form) {
      form.style.transition = "box-shadow 0.3s ease";
      form.style.boxShadow = "0 0 0 3px rgba(45, 106, 79, 0.35)";
      setTimeout(() => { form.style.boxShadow = ""; }, 1200);
    }

    // Auto-run the prediction
    if (typeof submitPredictionForm === "function") submitPredictionForm();
  }, 120);
}
