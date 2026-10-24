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
    AppState.selectedStation = "all";
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
  const requestedStation = AppState.selectedStation || "all";
  const stationParam = requestedStation !== "all"
    ? `&station=${encodeURIComponent(requestedStation)}`
    : "";
  const data = await apiGet(
    `/api/air-quality?city=${encodeURIComponent(cityName)}${stationParam}`
  );
  if (!data) return;
  currentAQData = data;

  // 1. Populate Stations dropdown
  const stnSelect = document.getElementById("aq-station-select");
  if (stnSelect && data.stations) {
    const selectedStationId = data.selected_station
      ? data.selected_station.station_id
      : "all";

    stnSelect.innerHTML =
      `<option value="all">City-wide aggregate (${data.station_count} stations in historical archive)</option>`;

    data.stations.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.station_id;
      opt.textContent =
        `${s.station_location} (historical PM2.5 mean: ${s.mean_pm25} ug/m3)`;
      stnSelect.appendChild(opt);
    });

    stnSelect.value = selectedStationId;
    AppState.selectedStation = selectedStationId;
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

  const lat = data.latest_recorded || {};
  const live = data.current_live;
  const isLive = live && live.is_live;

  const displayData = isLive ? live : lat;
  const historicalCompositeAvailable =
    !isLive &&
    lat.composite_aqi !== null &&
    lat.composite_aqi !== undefined &&
    Number.isFinite(Number(lat.composite_aqi));

  const displayColor = isLive
    ? (live.color || live.aqi_color || "#94a3b8")
    : historicalCompositeAvailable
      ? (lat.composite_color || lat.color || "#94a3b8")
      : (lat.pm25_color || "#94a3b8");

  const displayCategory = isLive
    ? (live.category || "Unavailable")
    : historicalCompositeAvailable
      ? (lat.composite_category || lat.category || "Unavailable")
      : (lat.pm25_category || lat.category || "Unavailable");

  const displayAQIRaw = isLive
    ? live.aqi
    : historicalCompositeAvailable
      ? lat.composite_aqi
      : (lat.pm25_subindex !== null && lat.pm25_subindex !== undefined
          ? lat.pm25_subindex
          : lat.aqi);

  const displayAQI =
    displayAQIRaw !== null &&
    displayAQIRaw !== undefined &&
    Number.isFinite(Number(displayAQIRaw))
      ? Math.round(Number(displayAQIRaw))
      : "?";

  const health = getHealthGuidance(displayCategory);
  const avgs = data.pollutant_averages || {};

  const pollutantDisplayNames = {
    "PM2.5": "Fine Particulate Matter (PM2.5)",
    "PM10": "Particulate Matter (PM10)",
    "NO2": "Nitrogen Dioxide (NO2)",
    "SO2": "Sulfur Dioxide (SO2)",
    "CO": "Carbon Monoxide (CO)",
    "O3": "Ozone (O3)",
    "Ozone": "Ozone (O3)"
  };

  const dominantPollutant =
    lat.main_pollutant && lat.main_pollutant !== "Unavailable"
      ? lat.main_pollutant
      : (lat.dominant_pollutant || null);

  const dominantPollutantLabel = dominantPollutant
    ? (pollutantDisplayNames[dominantPollutant] || dominantPollutant)
    : "Unavailable";

  const historicalScopeLabel = data.data_scope === "station"
    ? "selected-station rolling averages"
    : "city-wide rolling averages";

  const pollutantSummaryHtml = isLive
    ? `<p style="font-size:14px; color:var(--text-secondary); margin-bottom:20px;">
         Index basis: <strong>PM2.5 sub-index</strong>
       </p>`
    : historicalCompositeAvailable
      ? `<p style="font-size:14px; color:var(--text-secondary); margin-bottom:20px;">
           Dominant pollutant: <strong>${dominantPollutantLabel}</strong>
         </p>`
      : `<p style="font-size:14px; color:var(--text-secondary); margin-bottom:20px;">
           Dominant pollutant: <strong>Unavailable (composite AQI not calculated)</strong>
         </p>`;

  const aqiTypeLabel = isLive
    ? (live.aqi_type || "PM2.5 Sub-Index")
    : historicalCompositeAvailable
      ? `AIRWISE Historical Composite AQI Estimate (${historicalScopeLabel})`
      : "Historical PM2.5 Sub-Index (composite AQI unavailable)";

  const badgeHtml = isLive
    ? `<span class="live-badge-pill"><span class="live-pulse-dot"></span> Live CPCB Telemetry</span>`
    : `<span class="badge" style="background-color: ${displayColor}22; color: ${displayColor}; border: 1px solid ${displayColor}66;">${displayCategory}</span>`;

  const metaFooterHtml = isLive
    ? `<div style="font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px; margin-top: 16px; line-height: 1.5;">
        <div>📡 <strong>Live Station:</strong> ${live.station_name || data.city}</div>
        <div><strong>Observed:</strong> ${live.observation_time} • <strong>Ingested:</strong> ${live.retrieval_time}</div>
        <div style="font-size: 11px; margin-top: 2px;"><strong>Source:</strong> ${live.source_name || "CPCB CAAQMS via data.gov.in"}</div>
      </div>`
    : `<div style="font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px; margin-top: 16px; line-height: 1.5;">
        <div>⚠️ <strong>Historical Baseline:</strong> Recorded at ${lat.timestamp ? lat.timestamp.split(" ")[0] : "Archive"}</div>
        <div><strong>Historical scope:</strong> ${data.data_scope === "station"
          ? (lat.station_location || "Selected monitoring station")
          : "City-wide archive; stations contributing observations at this timestamp"}</div>
      </div>`;

  container.innerHTML = `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <span class="aqi-label-eyebrow">${aqiTypeLabel}</span>
        ${badgeHtml}
      </div>

      <div style="display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px;">
        <span style="font-size: 52px; font-weight: 800; color: ${displayColor}; line-height: 1;">
          ${displayAQI}
        </span>
        <span style="font-size: 15px; color: var(--text-muted); font-weight: 500;">${isLive ? "PM2.5 Sub-Index" : (historicalCompositeAvailable ? "Historical Composite AQI Estimate" : "PM2.5 Sub-Index ? composite unavailable")}</span>
      </div>

      <p style="font-size: 14px; color: var(--text-secondary); margin-bottom: 20px;">
        ${pollutantSummaryHtml}
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

    ${metaFooterHtml}
  `;

  // Store current values for the send-to-prediction button
  window._aqCurrentData = {
    city: data.city,
    pm25: (isLive && live.pm25 !== null && live.pm25 !== undefined) ? live.pm25 : (lat.pm25 ?? avgs["PM2.5"] ?? null),
    no2:  (isLive && live.no2 !== null && live.no2 !== undefined)  ? live.no2  : (lat.no2  ?? avgs["NO2"]  ?? null),
    so2:  (isLive && live.so2 !== null && live.so2 !== undefined)  ? live.so2  : (lat.so2  ?? avgs["SO2"]  ?? null),
    co:   (isLive && live.co !== null && live.co !== undefined)   ? live.co   : (lat.co   ?? avgs["CO"]   ?? null),
    ozone: (isLive && live.ozone !== null && live.ozone !== undefined) ? live.ozone : (lat.ozone ?? avgs["Ozone"] ?? null),
  };
}

function renderPollutantCards(data) {
  const container = document.getElementById("aq-pollutant-cards");
  if (!container) return;

  const historicalMeans = data.pollutant_averages || {};
  const latest = data.latest_recorded || {};
  const live = data.current_live || {};
  const isLive = Boolean(live.is_live);
  const subIndices = latest.aqi_sub_indices || {};
  const coverage = data.archive_coverage || {};

  const specs = [
    { mean: "PM2.5", latest: "pm25", live: "pm25", aqi: "PM2.5",
      name: "PM2.5", unit: "\u00b5g/m\u00b3", reference: 60, window: 24, digits: 1 },
    { mean: "PM10", latest: "pm10", live: "pm10", aqi: "PM10",
      name: "PM10", unit: "\u00b5g/m\u00b3", reference: 100, window: 24, digits: 1 },
    { mean: "NO2", latest: "no2", live: "no2", aqi: "NO2",
      name: "NO\u2082", unit: "\u00b5g/m\u00b3", reference: 80, window: 24, digits: 1 },
    { mean: "SO2", latest: "so2", live: "so2", aqi: "SO2",
      name: "SO\u2082", unit: "\u00b5g/m\u00b3", reference: 80, window: 24, digits: 1 },
    { mean: "CO", latest: "co", live: "co", aqi: "CO",
      name: "CO", unit: "mg/m\u00b3", reference: 2, window: 8, digits: 2 },
    { mean: "Ozone", latest: "ozone", live: "ozone", aqi: "O3",
      name: "Ozone (O\u2083)", unit: "\u00b5g/m\u00b3", reference: 100, window: 8, digits: 1 }
  ];

  const valid = (v) =>
    v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));

  const scope = data.data_scope === "station"
    ? "selected station"
    : "city-wide station-weighted archive";

  const cards = specs.map((p) => {
    const historicalMean = valid(historicalMeans[p.mean])
      ? Number(historicalMeans[p.mean])
      : null;
    const meanText = historicalMean === null ? "\u2014" : historicalMean.toFixed(p.digits);

    const latestRaw = isLive ? live[p.live] : latest[p.latest];
    const latestValue = valid(latestRaw) ? Number(latestRaw) : null;
    const latestText = latestValue === null
      ? "\u2014"
      : `${latestValue.toFixed(p.digits)} ${p.unit}`;

    const observedAt = isLive
      ? (live.observation_time || "")
      : (latest.timestamp || "");

    const sub = isLive ? null : subIndices[p.aqi];
    const concentration = sub && valid(sub.concentration)
      ? Number(sub.concentration)
      : null;
    const validHours = sub && valid(sub.valid_hours) ? Number(sub.valid_hours) : 0;
    const requiredHours = sub && valid(sub.required_hours)
      ? Number(sub.required_hours)
      : (p.window === 24 ? 16 : 8);
    const actualWindow = sub && valid(sub.window_hours) ? Number(sub.window_hours) : null;

    const comparisonAvailable =
      !isLive &&
      concentration !== null &&
      actualWindow === p.window &&
      validHours >= requiredHours;

    const percentage = comparisonAvailable
      ? Math.max(0, concentration / p.reference * 100)
      : null;

    const barWidth = percentage === null ? 0 : Math.min(100, percentage);

    // The colour shows magnitude relative to the reference, not an official AQI category.
    let barColor = "var(--accent-teal)";
    if (percentage !== null && percentage >= 100) barColor = "var(--aqi-poor)";

    const comparisonText = percentage !== null
      ? `Recent ${p.window}h mean: ${Math.round(percentage)}% of reference (${validHours} valid hours)`
      : isLive
        ? "Rolling comparison unavailable from an hourly live reading"
        : "Rolling comparison unavailable (insufficient valid observations)";

    return `
      <div class="pollutant-card">
        <div>
          <div class="pollutant-header">
            <span class="pollutant-name">${p.name}</span>
            <span class="pollutant-standard">
              Reference: ${p.reference} ${p.unit} (${p.window}h)
            </span>
          </div>

          <div style="font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--text-muted);margin:6px 0 2px;">
            Historical mean
          </div>
          <div class="pollutant-reading">
            <span class="pollutant-val">${meanText}</span>
            <span class="pollutant-unit">${p.unit}</span>
          </div>

          <div style="font-size:11px;color:var(--text-muted);margin-top:6px;line-height:1.45;">
            ${isLive ? "Latest live reading" : "Last archived hourly reading"}:
            <strong>${latestText}</strong>
            ${observedAt ? `<br>Observed: ${observedAt}` : ""}
            ${isLive && p.name === "CO" && latestValue !== null && latestValue > 50
              ? `<div role="note" style="font-size:11px;color:var(--aqi-poor, #f59e0b);margin-top:6px;line-height:1.4;">Outside AIRWISE's accepted prediction input range; excluded from model inputs.</div>`
              : ""}
          </div>
        </div>

        <div style="margin-top:12px;">
          <div class="pollutant-bar-bg">
            <div class="pollutant-bar-fill"
                 style="width:${barWidth}%;background-color:${barColor};"></div>
          </div>
          <div style="margin-top:6px;font-size:11px;color:var(--text-muted);line-height:1.4;">
            ${comparisonText}
          </div>
        </div>
      </div>
    `;
  }).join("");

  const start = coverage.start ? String(coverage.start).slice(0, 10) : "";
  const end = coverage.end ? String(coverage.end).slice(0, 10) : "";
  const coverageText = start && end ? ` Archive coverage: ${start} to ${end}.` : "";

  container.innerHTML = `${cards}
    <p style="grid-column:1/-1;font-size:11px;line-height:1.5;color:var(--text-muted);margin:4px 2px 0;">
      Historical means use available valid observations for the ${scope}.${coverageText}
      Recent-window percentages are indicative comparisons, not compliance determinations.
      Missing observations are not treated as zero.
    </p>`;
}


function renderAQRecentTrendChart(data) {
  const chartEl = document.getElementById("aq-recent-trend-chart");
  if (!chartEl || !Array.isArray(data.recent_trend) || data.recent_trend.length === 0) return;

  const trend = data.recent_trend;
  const times = trend.map((t) => t.time);
  const activePoll = AppState.selectedPollutant || "PM2.5";
  const keyMap = {
    "PM2.5": "pm25", "PM10": "pm10", "NO2": "no2",
    "SO2": "so2", "CO": "co", "Ozone": "ozone"
  };
  const key = keyMap[activePoll] || "pm25";
  const unit = activePoll === "CO" ? "mg/m\u00b3" : "\u00b5g/m\u00b3";
  const digits = activePoll === "CO" ? 2 : 1;

  const trace = {
    x: times,
    y: trend.map((t) => t[key] ?? null),
    name: activePoll,
    type: "scatter",
    mode: "lines+markers",
    connectgaps: false,
    line: { color: "#14b8a6", width: 2.5 },
    marker: { size: 4, color: "#14b8a6" },
    hovertemplate: `%{x}<br>${activePoll}: <b>%{y:.${digits}f} ${unit}</b><extra></extra>`
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 340,
    showlegend: false,
    yaxis: { ...PLOTLY_DARK.yaxis, title: `${activePoll} concentration (${unit})` }
  };

  Plotly.newPlot("aq-recent-trend-chart", [trace], layout, PLOTLY_CONFIG);
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
    name: data.data_scope === "station"
      ? (data.selected_station?.station_location || "Selected station")
      : `${data.city} city-wide average`,
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
  if (!chartEl) return;

  const avgs = data.pollutant_averages || {};
  const keys = ["PM2.5", "PM10", "NO2", "SO2", "Ozone"];
  const labels = ["PM2.5", "PM10", "NO\u2082", "SO\u2082", "O\u2083"];
  const valid = (v) =>
    v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));
  const values = keys.map((k) => valid(avgs[k]) ? Number(avgs[k]) : null);

  const trace = {
    x: keys,
    y: values,
    type: "bar",
    marker: { color: ["#14b8a6", "#38bdf8", "#f59e0b", "#f97316", "#a855f7"] },
    hovertemplate: "%{x}: <b>%{y:.1f} \u00b5g/m\u00b3</b><extra></extra>"
  };

  const layout = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", color: "#94a3b8", size: 12 },
    margin: { l: 55, r: 25, t: 20, b: 50 },
    height: 280,
    showlegend: false,
    xaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      type: "category",
      tickvals: keys,
      ticktext: labels
    },
    yaxis: {
      gridcolor: "rgba(255,255,255,0.06)",
      zerolinecolor: "rgba(255,255,255,0.1)",
      tickfont: { color: "#94a3b8" },
      title: { text: "Historical mean concentration (\u00b5g/m\u00b3)", font: { color: "#94a3b8" } }
    }
  };

  Plotly.newPlot("aq-breakdown-bar", [trace], layout, PLOTLY_CONFIG);

  let note = document.getElementById("aq-breakdown-note");
  if (!note) {
    note = document.createElement("p");
    note.id = "aq-breakdown-note";
    note.style.cssText = "font-size:12px;line-height:1.5;color:var(--text-muted);margin:8px 2px 0;";
    chartEl.insertAdjacentElement("afterend", note);
  }
  const co = valid(avgs["CO"]) ? Number(avgs["CO"]).toFixed(2) : "\u2014";
  note.textContent =
    `CO historical mean: ${co} mg/m3. CO is reported separately because it uses a different unit. ` +
    "Bars show historical mean concentrations, not pollutant proportions.";
}


async function loadAirQualityHistorical(cityName, pollutant, mode) {
  const chartEl = document.getElementById("aq-historical-chart");
  if (!chartEl) return;

  const res = await apiGet(
    `/api/trends?city=${encodeURIComponent(cityName)}&pollutant=${encodeURIComponent(pollutant)}`
  );
  if (!res) return;

  const specs = {
    "PM2.5": {
      monthly: "pm25_mean", yearly: "pm25_mean",
      count: "pm25_readings", unit: "\u00b5g/m\u00b3", digits: 1
    },
    "PM10": {
      monthly: "pm10", yearly: "pm10_mean",
      count: "pm10_readings", unit: "\u00b5g/m\u00b3", digits: 1
    },
    "NO2": {
      monthly: "no2", yearly: "no2_mean",
      count: "no2_readings", unit: "\u00b5g/m\u00b3", digits: 1
    },
    "SO2": {
      monthly: "so2", yearly: "so2_mean",
      count: "so2_readings", unit: "\u00b5g/m\u00b3", digits: 1
    },
    "CO": {
      monthly: "co", yearly: "co_mean",
      count: "co_readings", unit: "mg/m\u00b3", digits: 2
    },
    "Ozone": {
      monthly: "ozone", yearly: "ozone_mean",
      count: "ozone_readings", unit: "\u00b5g/m\u00b3", digits: 1
    }
  };

  const spec = specs[pollutant] || specs["PM2.5"];
  const isMonthly = mode === "monthly";
  const rows = isMonthly
    ? (res.monthly_trend || [])
    : (res.yearly_trend || []);

  const numericOrNull = (value) =>
    value !== null &&
    value !== undefined &&
    value !== "" &&
    Number.isFinite(Number(value))
      ? Number(value)
      : null;

  // Monthly observations are real dates, shown with yearly tick labels.
  // Annual observations are categorical labels, so 2023* is never parsed as a date.
  const x = isMonthly
    ? rows.map((row) => `${row.period}-01`)
    : rows.map((row) => `${row.year}${row.is_partial_year ? "*" : ""}`);

  const valueKey = isMonthly ? spec.monthly : spec.yearly;
  const y = rows.map((row) => numericOrNull(row[valueKey]));

  if (!y.some((value) => value !== null)) {
    chartEl.innerHTML =
      `<div style="padding:24px;color:var(--text-muted);font-size:13px;">` +
      `Historical ${pollutant} data is unavailable for ${cityName}. ` +
      "No substitute pollutant has been displayed.</div>";
    return;
  }

  const customdata = isMonthly
    ? rows.map((row) => [row.period])
    : rows.map((row) => [
        row[spec.count] ?? 0,
        row.stations ?? 0,
        row.period_start || "",
        row.period_end || "",
        row.is_partial_year ? "Yes" : "No"
      ]);

  const trace = {
    x,
    y,
    customdata,
    type: isMonthly ? "scatter" : "bar",
    connectgaps: false,
    ...(isMonthly ? {
      mode: "lines",
      line: { color: "#0d9488", width: 2.5 },
      fill: "tozeroy",
      fillcolor: "rgba(13,148,136,0.10)"
    } : {
      marker: {
        color: "#40916c",
        line: { color: "rgba(255,255,255,0.18)", width: 1 }
      }
    }),
    hovertemplate: isMonthly
      ? `%{customdata[0]}<br><b>${pollutant}: %{y:.${spec.digits}f} ${spec.unit}</b><extra></extra>`
      : `Year %{x}<br><b>${pollutant}: %{y:.${spec.digits}f} ${spec.unit}</b>` +
        `<br>Valid readings: %{customdata[0]}` +
        `<br>Stations represented: %{customdata[1]}` +
        `<br>Observed span: %{customdata[2]} to %{customdata[3]}` +
        `<br>Partial year: %{customdata[4]}<extra></extra>`
  };

  let xaxis;

  if (isMonthly) {
    const firstYear = String(rows[0].period).slice(0, 4);

    xaxis = {
      ...PLOTLY_DARK.xaxis,
      type: "date",
      tickformat: "%Y",
      dtick: "M12",
      tick0: `${firstYear}-01-01`,
      tickangle: 0,
      automargin: true,
      title: "Year (monthly observations)",
      showgrid: false
    };
  } else {
    xaxis = {
      ...PLOTLY_DARK.xaxis,
      type: "category",
      categoryorder: "array",
      categoryarray: x,
      tickangle: 0,
      automargin: true,
      title: "Year",
      showgrid: false
    };
  }

  const layout = {
    ...PLOTLY_DARK,
    height: 380,
    autosize: true,
    showlegend: false,
    margin: { l: 65, r: 28, t: 26, b: 58 },
    hovermode: "closest",
    xaxis,
    yaxis: {
      ...PLOTLY_DARK.yaxis,
      automargin: true,
      rangemode: "tozero",
      title: isMonthly
        ? `Monthly mean ${pollutant} (${spec.unit})`
        : `Annual mean ${pollutant} (${spec.unit})`,
      gridcolor: "rgba(148,163,184,0.18)",
      zerolinecolor: "rgba(148,163,184,0.25)"
    }
  };

  Plotly.react("aq-historical-chart", [trace], layout, PLOTLY_CONFIG);

  let note = document.getElementById("aq-historical-note");
  if (!note) {
    note = document.createElement("p");
    note.id = "aq-historical-note";
    note.style.cssText =
      "font-size:11px;line-height:1.6;color:var(--text-muted);margin:8px 2px 0;";
    chartEl.insertAdjacentElement("afterend", note);
  }

  note.textContent = isMonthly
    ? `Monthly mean ${pollutant} for ${cityName}, calculated from available historical observations across stations. ` +
      "The x-axis shows years to keep the monthly timeline readable. Gaps are not filled with invented data."
    : `Annual mean ${pollutant} for ${cityName}, calculated from available historical observations across stations. ` +
      "Hover over a bar for the number of valid readings and observed date range. * marks an incomplete year.";
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
  if (!d) {
    console.error("AIRWISE: No Air Quality data is available to transfer.");
    return;
  }

  if (typeof navigateTo === "function") {
    navigateTo("prediction");
  }

  window.setTimeout(async () => {
    const citySelect = document.getElementById("pred-city");
    if (citySelect && d.city) {
      citySelect.value = d.city;
    }

    if (typeof loadLivePredictionInputs !== "function") {
      console.error("AIRWISE: Telemetry loader is unavailable.");
      alert("Could not load station telemetry. Please refresh AIRWISE and try again.");
      return;
    }

    try {
      await loadLivePredictionInputs();
    } catch (error) {
      console.error("AIRWISE: Failed to transfer station telemetry.", error);
      alert("Could not load station telemetry. Please check the server and try again.");
    }
  }, 150);
}
