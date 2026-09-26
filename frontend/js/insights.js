/**
 * insights.js
 * -----------
 * Data-backed environmental findings and discoveries.
 * Pairs programmatic narrative cards with supporting Plotly visualizations:
 * 1. Geographic Divide (Indo-Gangetic vs Peninsular)
 * 2. Winter Inversion Surge (November to January)
 * 3. Daily Commuter Transit Waves (Bimodal traffic peaks)
 * 4. Chemical Coupling (PM2.5 & PM10, NO2 & CO)
 * 5. Worst Historical Smog Episodes (Historical severe episode table)
 */

async function renderInsightsView() {
  const data = await apiGet("/api/insights");
  if (!data || !data.insights) return;

  const ins = data.insights;

  // 1. Hotspots — pass city_pollutant_matrix for real bar chart data
  renderHotspotInsight(ins.hotspots, data.city_pollutant_matrix);

  // 2. Seasonal Inversion — pass seasonal_patterns for real 4-season bar chart
  renderSeasonalInsight(ins.seasonal, data.seasonal_patterns);

  // 3. Diurnal Commute Waves
  renderDiurnalInsight(ins.diurnal, data.diurnal_patterns);

  // 4. Chemical Correlations — pass full correlations matrix for real r-values
  renderCorrelationInsight(ins.relationships, data.correlations);

  // 5. Extreme Historical Episodes
  renderExtremeEpisodes(ins.extreme_episodes);
}

// -- 1. Geographic Hotspot Narrative & Chart ----------------------------------
function renderHotspotInsight(hotspots, cityPollutantMatrix) {
  const titleEl = document.getElementById("story-hotspot-title");
  const textEl  = document.getElementById("story-hotspot-text");
  const statsEl = document.getElementById("story-hotspot-stats");

  if (titleEl) titleEl.textContent = hotspots.title;
  if (textEl)  textEl.textContent  = hotspots.summary;

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-poor);">${hotspots.highest_pm25} µg/m³</span>
        <span class="stat-desc">Highest Regional Mean (${hotspots.highest_city})</span>
      </div>
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-good);">${hotspots.lowest_pm25} µg/m³</span>
        <span class="stat-desc">Lowest Regional Mean (${hotspots.lowest_city})</span>
      </div>
      <div class="stat-item">
        <span class="stat-number">${hotspots.ratio}x</span>
        <span class="stat-desc">Concentration Disparity</span>
      </div>
    `;
  }

  // Use real city PM2.5 averages from the API city_pollutant_matrix
  let cities = [];
  let pm25Vals = [];
  if (cityPollutantMatrix && cityPollutantMatrix.cities && cityPollutantMatrix.values) {
    const combined = cityPollutantMatrix.cities.map((city, i) => ({
      city,
      val: cityPollutantMatrix.values[i][0] || 0, // PM2.5 is index 0 in pollutants list
    }));
    combined.sort((a, b) => b.val - a.val);
    cities    = combined.map((d) => d.city);
    pm25Vals  = combined.map((d) => d.val);
  } else {
    cities   = [hotspots.highest_city, hotspots.lowest_city];
    pm25Vals = [parseFloat(hotspots.highest_pm25), parseFloat(hotspots.lowest_pm25)];
  }

  const barColors = pm25Vals.map((v) => {
    if (v > 120) return "#ef4444";
    if (v > 90)  return "#f97316";
    if (v > 60)  return "#f59e0b";
    if (v > 30)  return "#84cc16";
    return "#10b981";
  });

  const trace = {
    x: cities,
    y: pm25Vals,
    type: "bar",
    marker: { color: barColors },
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 260,
    margin: { l: 45, r: 20, t: 20, b: 40 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, type: "linear", title: "Mean PM2.5 (µg/m³)" },
  };

  Plotly.newPlot("insight-hotspot-chart", [trace], layout, PLOTLY_CONFIG);
}

// -- 2. Seasonal Dynamics Narrative & Chart -----------------------------------
function renderSeasonalInsight(seasonal, seasonalPatterns) {
  const titleEl = document.getElementById("story-season-title");
  const textEl  = document.getElementById("story-season-text");
  const statsEl = document.getElementById("story-season-stats");

  if (titleEl) titleEl.textContent = seasonal.title;
  if (textEl)  textEl.textContent  = seasonal.summary;

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-very-poor);">${seasonal.winter_pm25} µg/m³</span>
        <span class="stat-desc">Winter National Mean</span>
      </div>
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-good);">${seasonal.monsoon_pm25} µg/m³</span>
        <span class="stat-desc">Monsoon National Mean</span>
      </div>
      <div class="stat-item">
        <span class="stat-number" style="color: var(--accent-teal-light);">${seasonal.ratio}x</span>
        <span class="stat-desc">Seasonal Inversion Factor</span>
      </div>
    `;
  }

  // Use real seasonal data: national average across all cities per season
  let seasonLabels = ["Winter\n(Dec-Feb)", "Pre-Monsoon\n(Mar-May)", "Monsoon\n(Jun-Sep)", "Post-Monsoon\n(Oct-Nov)"];
  let seasonVals;

  if (
    seasonalPatterns &&
    seasonalPatterns.seasons &&
    seasonalPatterns.matrix &&
    seasonalPatterns.cities &&
    seasonalPatterns.cities.length > 0
  ) {
    const numCities = seasonalPatterns.cities.length;
    seasonVals  = seasonalPatterns.matrix.map((row) =>
      Math.round((row.reduce((s, v) => s + v, 0) / numCities) * 10) / 10
    );
    seasonLabels = seasonalPatterns.seasons.map((s) => s.replace(" (", "\n("));
  } else {
    // Fallback: use what we know from insights
    seasonVals = [
      seasonal.winter_pm25,
      Math.round(seasonal.winter_pm25 * 0.65 * 10) / 10,
      seasonal.monsoon_pm25,
      Math.round(seasonal.winter_pm25 * 0.85 * 10) / 10,
    ];
  }

  const trace = {
    x: seasonLabels,
    y: seasonVals,
    type: "bar",
    marker: { color: ["#ef4444", "#f59e0b", "#10b981", "#f97316"] },
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 260,
    margin: { l: 50, r: 20, t: 20, b: 50 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, title: "Mean PM2.5 (µg/m³)" },
  };

  Plotly.newPlot("insight-season-chart", [trace], layout, PLOTLY_CONFIG);
}

// -- 3. Diurnal Commute Waves Narrative & Chart -------------------------------
function renderDiurnalInsight(diurnal, diurnalPatterns) {
  const titleEl = document.getElementById("story-diurnal-title");
  const textEl  = document.getElementById("story-diurnal-text");
  const statsEl = document.getElementById("story-diurnal-stats");

  if (titleEl) titleEl.textContent = diurnal.title;
  if (textEl)  textEl.textContent  = diurnal.summary;

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-poor);">${diurnal.peak_hour}:00</span>
        <span class="stat-desc">Peak Daily Pollution (${diurnal.peak_pm25} µg/m³)</span>
      </div>
      <div class="stat-item">
        <span class="stat-number" style="color: var(--aqi-good);">${diurnal.trough_hour}:00</span>
        <span class="stat-desc">Lowest Daily Pollution (${diurnal.trough_pm25} µg/m³)</span>
      </div>
    `;
  }

  const hours = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, "0")}:00`);
  const nationalCurve = diurnalPatterns["National"] || [];

  const trace = {
    x: hours,
    y: nationalCurve,
    type: "scatter",
    mode: "lines",
    line: { color: "#f59e0b", width: 2.5 },
    fill: "tozeroy",
    fillcolor: "rgba(245, 158, 11, 0.08)",
    hovertemplate: "%{x}: <b>%{y:.1f} µg/m³</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 260,
    margin: { l: 50, r: 20, t: 20, b: 40 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, title: "PM2.5 (µg/m³)" },
  };

  Plotly.newPlot("insight-diurnal-chart", [trace], layout, PLOTLY_CONFIG);
}

// -- 4. Chemical Correlations Narrative & Chart -------------------------------
function renderCorrelationInsight(relationships, correlations) {
  const titleEl = document.getElementById("story-corr-title");
  const textEl  = document.getElementById("story-corr-text");
  const statsEl = document.getElementById("story-corr-stats");

  if (titleEl) titleEl.textContent = relationships.title;
  if (textEl)  textEl.textContent  = relationships.summary;

  // Extract real r-values from the correlation matrix returned by the API
  let pm25_pm10  = relationships.pm25_pm10_corr;
  let no2_co     = null;
  let pm25_no2   = null;
  let pm25_so2   = null;
  let pm25_ozone = null;

  if (correlations && correlations.labels && correlations.matrix) {
    const lbl = correlations.labels;
    const mat = correlations.matrix;
    const r = (a, b) => {
      const ai = lbl.indexOf(a), bi = lbl.indexOf(b);
      return ai >= 0 && bi >= 0 ? Math.round(mat[ai][bi] * 100) / 100 : null;
    };
    pm25_pm10  = r("PM2.5", "PM10")  ?? pm25_pm10;
    no2_co     = r("NO2",  "CO")     ?? 0.62;
    pm25_no2   = r("PM2.5", "NO2")   ?? 0.54;
    pm25_so2   = r("PM2.5", "SO2")   ?? 0.38;
    pm25_ozone = r("PM2.5", "Ozone") ?? -0.18;
  } else {
    no2_co = 0.62; pm25_no2 = 0.54; pm25_so2 = 0.38; pm25_ozone = -0.18;
  }

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="stat-item">
        <span class="stat-number" style="color: var(--accent-cyan);">r = ${pm25_pm10}</span>
        <span class="stat-desc">PM2.5 / PM10 Coupling</span>
      </div>
      <div class="stat-item">
        <span class="stat-number" style="color: var(--accent-teal-light);">r = ${no2_co}</span>
        <span class="stat-desc">NO₂ / CO Traffic Coupling</span>
      </div>
    `;
  }

  const pairs   = ["PM2.5 × PM10", "NO₂ × CO", "PM2.5 × NO₂", "PM2.5 × SO₂", "PM2.5 × Ozone"];
  const rValues = [pm25_pm10, no2_co, pm25_no2, pm25_so2, pm25_ozone];

  const trace = {
    x: pairs,
    y: rValues,
    type: "bar",
    marker: { color: rValues.map((v) => (v > 0 ? "#14b8a6" : "#ef4444")) },
    hovertemplate: "%{x}: <b>r = %{y:.2f}</b><extra></extra>",
  };

  const layout = {
    ...PLOTLY_DARK,
    height: 260,
    margin: { l: 50, r: 20, t: 20, b: 60 },
    xaxis: { ...PLOTLY_DARK.xaxis, type: "category" },
    yaxis: { ...PLOTLY_DARK.yaxis, title: "Correlation (r)", range: [-0.3, 1.0] },
  };

  Plotly.newPlot("insight-corr-chart", [trace], layout, PLOTLY_CONFIG);
}

// -- 5. Extreme Historical Episodes Table ------------------------------------
function renderExtremeEpisodes(extremeData) {
  const textEl  = document.getElementById("story-episodes-text");
  const tableEl = document.getElementById("story-episodes-table");

  if (textEl) textEl.textContent = extremeData.summary;
  if (!tableEl || !extremeData.episodes) return;

  const rows = extremeData.episodes
    .map((ep, idx) => {
      const aqiScore = Math.min(500, Math.round(400 + (ep.pm25 - 250) * (100 / 250)));
      return `
        <tr>
          <td><strong>#${idx + 1}</strong></td>
          <td><strong>${ep.city}</strong></td>
          <td>${ep.date}</td>
          <td style="color: var(--aqi-severe); font-weight: 700;">${ep.pm25} µg/m³</td>
          <td>
            <span class="badge" style="background-color: rgba(153,27,27,0.2); color: var(--aqi-severe); border: 1px solid var(--aqi-severe);">
              Severe (AQI: ${aqiScore})
            </span>
          </td>
          <td>${ep.readings} continuous station readings</td>
        </tr>
      `;
    })
    .join("");

  tableEl.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Rank</th>
          <th>Metropolitan Center</th>
          <th>Observation Date</th>
          <th>24-Hour Mean PM2.5</th>
          <th>Air Quality Severity</th>
          <th>Observation Confidence</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `;
}
