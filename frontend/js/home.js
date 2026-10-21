/**
 * home.js
 * ───────
 * Home view logic: Featured air quality snapshot, interactive Leaflet map,
 * historical trend chart, and dynamic data-backed insight highlights.
 */

let homeMapInstance = null;
let currentHomeTrendPollutant = "PM2.5";

async function renderHomeView() {
  const city = AppState.selectedCity || "Delhi";
  await loadFeaturedCityAQ(city);
  initIndiaMap();
  loadHomeTrendChart(city, currentHomeTrendPollutant);
  loadHomeInsightCards();
}

function applyHomeCity() {
  const select = document.getElementById("home-city-select");
  if (select && select.value) {
    AppState.selectedCity = select.value;
    renderHomeView();
  }
}

// ── Featured Air Quality Snapshot ───────────────────────────────────────────
async function loadFeaturedCityAQ(cityName) {
  const container = document.getElementById("featured-aqi-card");
  const heading = document.getElementById("featured-city-heading");
  const timeBadge = document.getElementById("featured-timestamp-badge");

  if (!container) return;
  if (heading) heading.textContent = `${cityName} Air Quality Snapshot`;

  const data = await apiGet(`/api/air-quality?city=${encodeURIComponent(cityName)}`);
  if (!data || !data.latest_recorded) {
    container.innerHTML = `<div class="aqi-loading-placeholder">Failed to load data for ${cityName}.</div>`;
    return;
  }

  const lat = data.latest_recorded;
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

  if (timeBadge) {
    if (isLive) {
      timeBadge.innerHTML = `<span class="live-badge-pill"><span class="live-pulse-dot"></span> LIVE CPCB TELEMETRY</span>`;
    } else {
      timeBadge.innerHTML = `<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-secondary); border: 1px solid var(--border-subtle);">HISTORICAL BASELINE (2010–2023)</span>`;
    }
  }

  const pm25Val = displayData.pm25 !== null && displayData.pm25 !== undefined ? displayData.pm25 : "—";
  const pm10Val = displayData.pm10 !== null && displayData.pm10 !== undefined ? displayData.pm10 : (lat.pm10 !== null ? lat.pm10 : "—");
  const no2Val = displayData.no2 !== null && displayData.no2 !== undefined ? displayData.no2 : (lat.no2 !== null ? lat.no2 : "—");
  const so2Val = displayData.so2 !== null && displayData.so2 !== undefined ? displayData.so2 : (lat.so2 !== null ? lat.so2 : "—");

  const aqiTypeLabel = isLive
    ? (live.aqi_type || "PM2.5 Sub-Index (CPCB Breakpoint Formula)")
    : "Historical CPCB Archive Record";

  const provenanceHtml = isLive
    ? `<div style="margin-top: 10px; padding: 10px 14px; background: rgba(20, 184, 166, 0.08); border-radius: 6px; border: 1px solid rgba(20, 184, 166, 0.25); font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
        <div style="font-weight: 600; color: var(--accent-teal); margin-bottom: 2px;">
          📡 Verified Real-Time Observation: ${live.station_name || cityName}
        </div>
        <div>
          Observed: <strong>${live.observation_time}</strong> | Ingested by AIRWISE: <strong>${live.retrieval_time}</strong>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px;">
          Source: ${live.source_name || "CPCB CAAQMS Network"} (${live.source_attribution || "CPCB / MoEFCC"})
        </div>
      </div>`
    : `<div style="margin-top: 8px; color: var(--text-muted); font-size: 12px;">
        ⚠️ <em>Displaying verified historical baseline from CPCB monitoring network (${lat.timestamp.split(" ")[0]} at ${lat.station_location || cityName}). Real-time live sensor feed is currently offline or rate-limited.</em>
      </div>`;

  container.innerHTML = `
    <div class="aqi-summary-layout">
      <!-- Left: Big AQI Badge -->
      <div class="aqi-badge-hero" style="border-left-color: ${displayColor};">
        <span class="aqi-label-eyebrow">${aqiTypeLabel}</span>
        <div class="aqi-category-title" style="color: ${displayColor};">${displayCategory}</div>
        <div class="aqi-subindex-display">
          <span class="aqi-num-val" style="color: ${displayColor};">${displayAQI}</span>
          <span class="aqi-num-unit">${isLive ? (live.aqi_type || "PM2.5 Sub-Index") : (historicalCompositeAvailable ? "Historical Composite AQI Estimate" : "PM2.5 Sub-Index ? composite unavailable")}</span>
        </div>
        <div class="aqi-primary-pollutant">
          <strong>Dominant Pollutant:</strong> ${isLive ? (live.main_pollutant || "PM2.5") : (historicalCompositeAvailable ? (lat.dominant_pollutant || lat.main_pollutant || "Unavailable") : "PM2.5 (sub-index only)")}
        </div>
      </div>

      <!-- Right: Pollutants & Health Advisory -->
      <div class="aqi-pollutants-and-advisory">
        <div class="pollutants-mini-row">
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">PM2.5</div>
            <div class="mini-poll-val">${pm25Val}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 60)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">PM10</div>
            <div class="mini-poll-val">${pm10Val}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 100)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">NO₂</div>
            <div class="mini-poll-val">${no2Val}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 80)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">SO₂</div>
            <div class="mini-poll-val">${so2Val}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 80)</div>
          </div>
        </div>

        <div class="aqi-health-interpretation">
          <span class="health-callout-bold">Health Impact:</span> ${health.advisory}
          ${provenanceHtml}
        </div>
      </div>
    </div>
  `;
}

// ── Interactive India Map (Leaflet) ──────────────────────────────────────────
function initIndiaMap() {
  const mapElement = document.getElementById("india-map");
  if (!mapElement) return;

  // Cleanly teardown previous map instance if already initialized
  if (homeMapInstance) {
    try {
      homeMapInstance.remove();
    } catch (e) {
      console.warn("Could not remove previous map:", e);
    }
    homeMapInstance = null;
  }

  // Clear container DOM
  mapElement.innerHTML = "";

  homeMapInstance = L.map("india-map", {
    center: [21.5, 79.5],
    zoom: 4.8,
    minZoom: 4,
    maxZoom: 9,
    attributionControl: false,
  });

  // OpenStreetMap standard tiles (100% free, zero API key)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(homeMapInstance);

  // Populate city markers
  AppState.locations.forEach((c) => {
    const lat = c.lat;
    const lon = c.lon;
    if (!lat || !lon) return;

    // Custom circle marker
    const marker = L.circleMarker([lat, lon], {
      radius: 10,
      fillColor: c.overall_color,
      color: "#ffffff",
      weight: 1.5,
      opacity: 0.9,
      fillOpacity: 0.85,
    }).addTo(homeMapInstance);

    const latestAqiValue = c.latest_recorded?.aqi;
    const latestAqiCategory = c.latest_recorded?.category || "Unavailable";
    const latestAqiText = latestAqiValue !== null && latestAqiValue !== undefined && Number.isFinite(Number(latestAqiValue))
      ? `${Math.round(Number(latestAqiValue))} (${latestAqiCategory})`
      : "Unavailable";
        marker.bindTooltip(`<strong>${c.city}</strong><br>Long-term archive mean PM2.5: ${c.overall_pm25_mean ?? "Unavailable"} ug/m3<br>Latest historical composite AQI estimate: ${latestAqiText}`, {
      className: "map-tooltip",
      direction: "top",
    });

    marker.on("click", () => {
      displayMapCityDetail(c);
      loadFeaturedCityAQ(c.city);
    });
  });

  // Display default city in side panel
  const defaultCity = AppState.citiesMap[AppState.selectedCity] || AppState.locations[0];
  if (defaultCity) displayMapCityDetail(defaultCity);
}

function displayMapCityDetail(cityObj) {
  const panel = document.getElementById("map-detail-panel");
  if (!panel) return;

  panel.innerHTML = `
    <div class="panel-city-name">${cityObj.city}</div>
    <div class="panel-state-name">${cityObj.state} ? ${cityObj.station_count} stations in historical archive</div>
    <div class="panel-aqi-pill">
            Long-term archive mean PM2.5: ${cityObj.overall_pm25_mean ?? "Unavailable"} ug/m3
    </div>

    <div class="panel-stats-list">
      <div class="panel-stat-item">
        <span class="stat-label">Total Hourly Readings</span>
        <span class="stat-val-bold">${Number(cityObj.total_records).toLocaleString()}</span>
      </div>
      <div class="panel-stat-item">
        <span class="stat-label">Coverage Window</span>
        <span class="stat-val-bold">${cityObj.date_start.split(" ")[0]} to ${cityObj.date_end.split(" ")[0]}</span>
      </div>
      <div class="panel-stat-item">
        <span class="stat-label">Latest Historical PM2.5</span>
        <span class="stat-val-bold">${cityObj.latest_recorded.pm25} µg/m³</span>
      </div>
      <div class="panel-stat-item">
        <span class="stat-label">Latest Historical Composite AQI Estimate</span>
        <span class="stat-val-bold">${cityObj.latest_recorded.aqi !== null && cityObj.latest_recorded.aqi !== undefined && Number.isFinite(Number(cityObj.latest_recorded.aqi)) ? Math.round(Number(cityObj.latest_recorded.aqi)) + " (" + (cityObj.latest_recorded.category || "Unavailable") + ")" : "Unavailable"}</span>
      </div>
    </div>

    <button class="btn btn-secondary btn-sm" style="width: 100%; margin-top: 8px;" onclick="selectCityAndNavigate('${cityObj.city}')">
      Explore Station Details &rarr;
    </button>
  `;
}

function selectCityAndNavigate(cityName) {
  AppState.selectedCity = cityName;
  const aqSelect = document.getElementById("aq-city-select");
  if (aqSelect) aqSelect.value = cityName;
  navigateTo("air-quality");
}

// ── How is air quality changing? (Trend Line) ────────────────────────────────
async function loadHomeTrendChart(cityName, pollutant) {
  const chartEl = document.getElementById("home-trend-chart");
  const subtitle = document.getElementById("home-trend-subtitle");
  if (!chartEl) return;

  if (subtitle) {
    subtitle.textContent = `Loading historical monthly ${pollutant} data for ${cityName}...`;
  }

  const res = await apiGet(`/api/trends?city=${encodeURIComponent(cityName)}&pollutant=${encodeURIComponent(pollutant)}`);
  if (!res || !res.monthly_trend || res.monthly_trend.length === 0) {
    chartEl.innerHTML = `<div class="aqi-loading-placeholder">No trend data available for ${cityName}.</div>`;
    return;
  }

  const valueForTrend = (row) => {
    if (pollutant === "PM10") return row.pm10;
    if (pollutant === "NO2") return row.no2;
    return row.pm25_mean;
  };
  const hasTrendValue = (row) => {
    const value = valueForTrend(row);
    return value !== null && value !== undefined && Number.isFinite(Number(value));
  };
  const availableFlags = res.monthly_trend.map(hasTrendValue);
  const firstDataIndex = availableFlags.indexOf(true);
  const lastDataIndex = availableFlags.lastIndexOf(true);
  if (firstDataIndex < 0 || lastDataIndex < firstDataIndex) {
    chartEl.innerHTML = `<div class="aqi-loading-placeholder">No valid ${pollutant} trend data available for ${cityName}.</div>`;
    return;
  }
  const chartRows = res.monthly_trend.slice(firstDataIndex, lastDataIndex + 1);
  const periods = chartRows.map((row) => row.period);
  const values = chartRows.map((row) => hasTrendValue(row) ? Number(valueForTrend(row)) : null);
  if (subtitle) {
        subtitle.textContent = `Historical monthly ${pollutant} mean for ${cityName}, ${periods[0]} to ${periods[periods.length - 1]}. Missing months remain blank; a monthly mean cannot establish compliance with a 24-hour standard.`;
  }

  const trace = {
    x: periods,
    y: values,
    type: "scatter",
    mode: "lines",
    connectgaps: false,
    line: { color: "#14b8a6", width: 2.2 },
    fill: "tozeroy",
    fillcolor: "rgba(20, 184, 166, 0.08)",
    name: `${pollutant} Monthly Mean`,
    hovertemplate: "%{x}<br><b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  // Add standard threshold horizontal line
  const thresholdVal = pollutant === "PM2.5" ? 60 : pollutant === "PM10" ? 100 : 80;
  const thresholdLine = {
    x: [periods[0], periods[periods.length - 1]],
    y: [thresholdVal, thresholdVal],
    type: "scatter",
    mode: "lines",
    line: { color: "#ef4444", width: 1.5, dash: "dot" },
    name: "CPCB 24h Standard (reference only)",
    hovertemplate: `CPCB Standard: ${thresholdVal} µg/m³<extra></extra>`,
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 380,
    showlegend: true,
    legend: { x: 0.02, y: 0.98, bgcolor: "rgba(0,0,0,0)", font: { color: "#94a3b8" } },
    yaxis: {
      ...PLOTLY_DARK.yaxis,
      title: `${pollutant} (µg/m³)`,
    },
  };

  Plotly.newPlot("home-trend-chart", [trace, thresholdLine], layout, PLOTLY_CONFIG);
}

function switchHomeTrendPollutant(pollutant, btnEl) {
  currentHomeTrendPollutant = pollutant;
  const parent = btnEl.parentElement;
  if (parent) {
    parent.querySelectorAll(".btn").forEach((b) => b.classList.remove("active"));
    btnEl.classList.add("active");
  }
  loadHomeTrendChart(AppState.selectedCity || "Delhi", pollutant);
}

// ── Explore what the data reveals (4 Insight Cards) ──────────────────────────
async function loadHomeInsightCards() {
  const container = document.getElementById("home-insights-grid");
  if (!container) return;

  const data = await apiGet("/api/insights");
  if (!data || !data.insights) return;

  const ins = data.insights;

  container.innerHTML = `
    <div class="insight-card">
      <span class="insight-tag">Geographic Divide</span>
      <h3 class="insight-card-title">${ins.hotspots.highest_city} vs ${ins.hotspots.lowest_city}</h3>
      <p class="insight-card-body">
        Historical mean PM2.5 differs by up to <strong>${ins.hotspots.ratio}x</strong> between the compared cities. This is a descriptive comparison and does not establish the cause.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Seasonal Meteorology</span>
      <h3 class="insight-card-title">${ins.seasonal.ratio}x Winter-to-Monsoon PM2.5 Ratio</h3>
      <p class="insight-card-body">
        Archive mean PM2.5 is <strong>${ins.seasonal.monsoon_pm25} ?g/m?</strong> in monsoon and <strong>${ins.seasonal.winter_pm25} ?g/m?</strong> in winter. This comparison describes a seasonal difference; it does not establish its cause.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Diurnal Rhythms</span>
      <h3 class="insight-card-title">Observed PM2.5 Peak: ${ins.diurnal.peak_hour}:00</h3>
      <p class="insight-card-body">
        The aggregated hourly profile peaks at <strong>${ins.diurnal.peak_pm25} ?g/m?</strong> at this hour. This identifies a time-of-day pattern, not a source or cause.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Chemical Coupling</span>
      <h3 class="insight-card-title">PM2.5 & PM10 Correlation</h3>
      <p class="insight-card-body">
        PM2.5 and PM10 co-vary in the historical archive (<strong>r = ${ins.relationships.pm25_pm10_corr}</strong>). Correlation alone does not establish a common source.
      </p>
    </div>
  `;
}
