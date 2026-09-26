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
  if (timeBadge) {
    timeBadge.textContent = `Recorded: ${lat.timestamp.split(" ")[0]} at ${lat.station_location || "Monitoring Network"}`;
  }

  const health = getHealthGuidance(lat.category);

  container.innerHTML = `
    <div class="aqi-summary-layout">
      <!-- Left: Big AQI Badge -->
      <div class="aqi-badge-hero" style="border-left-color: ${lat.color};">
        <span class="aqi-label-eyebrow">CPCB Air Quality Index</span>
        <div class="aqi-category-title" style="color: ${lat.color};">${lat.category}</div>
        <div class="aqi-subindex-display">
          <span class="aqi-num-val" style="color: ${lat.color};">${Math.round(lat.aqi)}</span>
          <span class="aqi-num-unit">NAQI Sub-Index</span>
        </div>
        <div class="aqi-primary-pollutant">
          <strong>Dominant Pollutant:</strong> Fine Particulates (PM2.5)
        </div>
      </div>

      <!-- Right: Pollutants & Health Advisory -->
      <div class="aqi-pollutants-and-advisory">
        <div class="pollutants-mini-row">
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">PM2.5</div>
            <div class="mini-poll-val">${lat.pm25 !== null ? lat.pm25 : "—"}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 60)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">PM10</div>
            <div class="mini-poll-val">${lat.pm10 !== null ? lat.pm10 : "—"}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 100)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">NO₂</div>
            <div class="mini-poll-val">${lat.no2 !== null ? lat.no2 : "—"}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 80)</div>
          </div>
          <div class="mini-pollutant-card">
            <div class="mini-poll-name">SO₂</div>
            <div class="mini-poll-val">${lat.so2 !== null ? lat.so2 : "—"}</div>
            <div class="mini-poll-unit">µg/m³ (Std: 80)</div>
          </div>
        </div>

        <div class="aqi-health-interpretation">
          <span class="health-callout-bold">Health Impact:</span> ${health.advisory}
          <div style="margin-top: 6px; color: var(--text-muted); font-size: 12px;">
            ⚠️ <em>Historical recorded data from CPCB network. Not a real-time sensor stream.</em>
          </div>
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

    marker.bindTooltip(`<strong>${c.city}</strong><br>Mean PM2.5: ${c.overall_pm25_mean} µg/m³ (${c.overall_category})`, {
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
    <div class="panel-state-name">${cityObj.state} • ${cityObj.station_count} Active Stations</div>
    <div class="panel-aqi-pill" style="background-color: ${cityObj.overall_color}22; color: ${cityObj.overall_color}; border: 1px solid ${cityObj.overall_color}55;">
      Overall: ${cityObj.overall_category} (Avg: ${cityObj.overall_pm25_mean} µg/m³)
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
        <span class="stat-label">Latest Recorded PM2.5</span>
        <span class="stat-val-bold">${cityObj.latest_recorded.pm25} µg/m³</span>
      </div>
      <div class="panel-stat-item">
        <span class="stat-label">Latest Recorded AQI</span>
        <span class="stat-val-bold">${Math.round(cityObj.latest_recorded.aqi)} (${cityObj.latest_recorded.category})</span>
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
    subtitle.textContent = `Historical monthly ${pollutant} trajectory for ${cityName} (2010–2023).`;
  }

  const res = await apiGet(`/api/trends?city=${encodeURIComponent(cityName)}&pollutant=${encodeURIComponent(pollutant)}`);
  if (!res || !res.monthly_trend || res.monthly_trend.length === 0) {
    chartEl.innerHTML = `<div class="aqi-loading-placeholder">No trend data available for ${cityName}.</div>`;
    return;
  }

  const periods = res.monthly_trend.map((d) => d.period);
  const values = res.monthly_trend.map((d) => {
    if (pollutant === "PM10") return d.pm10;
    if (pollutant === "NO2") return d.no2;
    return d.pm25_mean;
  });

  const trace = {
    x: periods,
    y: values,
    type: "scatter",
    mode: "lines",
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
    name: "CPCB 24h Standard",
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
        Indo-Gangetic cities record up to <strong>${ins.hotspots.ratio}x higher</strong> particulate pollution than coastal southern cities, shaped by landlocked stagnation.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Seasonal Meteorology</span>
      <h3 class="insight-card-title">${ins.seasonal.ratio}x Winter Surge</h3>
      <p class="insight-card-body">
        National average PM2.5 jumps from <strong>${ins.seasonal.monsoon_pm25} µg/m³</strong> in monsoon to <strong>${ins.seasonal.winter_pm25} µg/m³</strong> in winter due to thermal inversion.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Diurnal Rhythms</span>
      <h3 class="insight-card-title">Peak Commute at ${ins.diurnal.peak_hour}:00</h3>
      <p class="insight-card-body">
        Daily particulate levels peak at night and during early rush hours (${ins.diurnal.peak_pm25} µg/m³), dropping to their trough in mid-afternoon.
      </p>
    </div>

    <div class="insight-card">
      <span class="insight-tag">Chemical Coupling</span>
      <h3 class="insight-card-title">PM2.5 & PM10 Correlation</h3>
      <p class="insight-card-body">
        Fine and coarse particulates display an extremely strong correlation (<strong>r = ${ins.relationships.pm25_pm10_corr}</strong>), reflecting mutual combustion origins.
      </p>
    </div>
  `;
}
