/**
 * prediction.js
 * ─────────────
 * User-facing air quality prediction tool.
 * Evaluates inputs with the backend XGBoost inference engine and returns
 * predicted PM2.5, official CPCB NAQI classification, and health advisories.
 */

const PREDICTION_PRESETS = {
  delhi_winter: {
    city: "Delhi",
    pm25: 185.0,
    pm25_lag2: 172.0,
    pm25_lag3: 160.0,
    no2: 65.0,
    co: 2.1,
    so2: 18.0,
    ozone: 25.0,
    temp: 14.0,
    rh: 78.0,
    ws: 0.8,
    month: 11,
    hour: 20,
    weekend: 0,
  },
  delhi_summer: {
    city: "Delhi",
    pm25: 48.0,
    pm25_lag2: 52.0,
    pm25_lag3: 55.0,
    no2: 24.0,
    co: 0.7,
    so2: 10.0,
    ozone: 42.0,
    temp: 38.0,
    rh: 35.0,
    ws: 3.2,
    month: 5,
    hour: 15,
    weekend: 0,
  },
  mumbai_moderate: {
    city: "Mumbai",
    pm25: 62.0,
    pm25_lag2: 58.0,
    pm25_lag3: 60.0,
    no2: 32.0,
    co: 1.1,
    so2: 12.0,
    ozone: 30.0,
    temp: 29.0,
    rh: 72.0,
    ws: 3.8,
    month: 1,
    hour: 11,
    weekend: 0,
  },
  bengaluru_clean: {
    city: "Bengaluru",
    pm25: 32.0,
    pm25_lag2: 30.0,
    pm25_lag3: 35.0,
    no2: 18.0,
    co: 0.5,
    so2: 6.0,
    ozone: 28.0,
    temp: 24.0,
    rh: 58.0,
    ws: 2.5,
    month: 8,
    hour: 9,
    weekend: 0,
  },
  kolkata_winter: {
    city: "Kolkata",
    pm25: 135.0,
    pm25_lag2: 120.0,
    pm25_lag3: 110.0,
    no2: 52.0,
    co: 1.8,
    so2: 15.0,
    ozone: 22.0,
    temp: 18.0,
    rh: 75.0,
    ws: 1.1,
    month: 12,
    hour: 21,
    weekend: 0,
  },
  lucknow_smog: {
    city: "Lucknow",
    pm25: 210.0,
    pm25_lag2: 195.0,
    pm25_lag3: 180.0,
    no2: 68.0,
    co: 2.4,
    so2: 20.0,
    ozone: 19.0,
    temp: 16.0,
    rh: 80.0,
    ws: 0.6,
    month: 11,
    hour: 22,
    weekend: 0,
  },
};

function initPredictionView() {
  // If city is selected, synchronize it with the form
  const citySelect = document.getElementById("pred-city");
  if (citySelect && AppState.selectedCity) {
    citySelect.value = AppState.selectedCity;
  }
  // Auto-generate initial prediction so user doesn't see an empty state
  const panel = document.getElementById("prediction-result-panel");
  if (panel && panel.querySelector(".result-placeholder")) {
    submitPredictionForm();
  }
}

function loadPredictionPreset(presetKey) {
  const p = PREDICTION_PRESETS[presetKey];
  if (!p) return;

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  };

  setVal("pred-city", p.city);
  setVal("pred-pm25", p.pm25);
  setVal("pred-pm25-lag2", p.pm25_lag2);
  setVal("pred-pm25-lag3", p.pm25_lag3);
  setVal("pred-no2", p.no2);
  setVal("pred-co", p.co);
  setVal("pred-so2", p.so2);
  setVal("pred-ozone", p.ozone);
  setVal("pred-temp", p.temp);
  setVal("pred-rh", p.rh);
  setVal("pred-ws", p.ws);
  setVal("pred-month", p.month);
  setVal("pred-hour", p.hour);
  setVal("pred-weekend", Number.isInteger(p.day_of_week) ? p.day_of_week : (p.weekend ? 5 : 2));

  // Auto trigger prediction for immediate responsiveness
  submitPredictionForm();
}

let lastTelemetryMeta = null;

async function loadLivePredictionInputs() {
  const btn = document.getElementById("btn-fetch-live");
  const citySelect = document.getElementById("pred-city");
  const cityName = (citySelect && citySelect.value) ? citySelect.value : (AppState.selectedCity || "Delhi");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>Loading available station data...</span>`;
  }

  const res = await apiGet(`/api/current?city=${encodeURIComponent(cityName)}`);

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<span>Auto-Fill from Station Telemetry</span>`;
  }

  if (!res || !res.data) {
    alert(`Could not retrieve observation data for ${cityName}.`);
    return;
  }

  const live = res.data;
  const p = live.pollutants || {};
  const w = live.weather || {};

  const pm25Value = Number(p["PM2.5"]);
  if (
    p["PM2.5"] === undefined ||
    p["PM2.5"] === null ||
    p["PM2.5"] === "" ||
    !Number.isFinite(pm25Value) ||
    pm25Value < 0
  ) {
    alert(`Could not retrieve a valid PM2.5 observation for ${cityName}.`);
    return;
  }

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) el.value = val;
  };

  // These values must come from actual observations; never carry stale
  // manual values or manufacture historical PM2.5 lag estimates.
  setVal("pred-pm25-lag2", "");
  setVal("pred-pm25-lag3", "");

  for (const id of [
    "pred-no2",
    "pred-co",
    "pred-so2",
    "pred-ozone",
    "pred-temp",
    "pred-rh",
    "pred-ws"
  ]) {
    setVal(id, "");
  }

  setVal("pred-pm25", pm25Value);

  // These are exact same-station historical readings from the backend.
  // The fields were cleared above, so unavailable readings remain blank.
  if (live.pm25_lag_2h !== undefined && live.pm25_lag_2h !== null) {
    setVal("pred-pm25-lag2", live.pm25_lag_2h);
  }
  if (live.pm25_lag_3h !== undefined && live.pm25_lag_3h !== null) {
    setVal("pred-pm25-lag3", live.pm25_lag_3h);
  }
  if (p["NO2"] !== undefined) setVal("pred-no2", p["NO2"]);
  if (p["CO"] !== undefined) setVal("pred-co", p["CO"]);
  if (p["SO2"] !== undefined) setVal("pred-so2", p["SO2"]);
  if (p["Ozone"] !== undefined) setVal("pred-ozone", p["Ozone"]);

  if (w.temperature !== undefined) setVal("pred-temp", w.temperature);
  if (w.relative_humidity !== undefined) setVal("pred-rh", w.relative_humidity);
  if (w.wind_speed !== undefined) setVal("pred-ws", w.wind_speed);

  // Target the hour after the observation when its timestamp is available.
  const observationDate = live.observation_time
    ? new Date(String(live.observation_time).replace(" ", "T"))
    : null;

  const observationTimeIsValid =
    observationDate && Number.isFinite(observationDate.getTime());

  const targetBase = observationTimeIsValid ? observationDate : new Date();
  const airwiseForecastTargetTime = new Date(targetBase.getTime() + 3600000);
  setVal("pred-month", airwiseForecastTargetTime.getMonth() + 1);
  setVal("pred-hour", airwiseForecastTargetTime.getHours());
  setVal("pred-weekend", (airwiseForecastTargetTime.getDay() + 6) % 7);

  // Update banner display
  const titleEl = document.getElementById("live-banner-title");
  const subEl = document.getElementById("live-banner-sub");
  const pulseEl = document.getElementById("live-banner-pulse");

  if (titleEl) {
    titleEl.textContent = `${cityName}: ${live.station_name || "CPCB Station"}`;
  }
  if (subEl) {
    const badgeType = live.is_live ? "Live CPCB Telemetry" : "Historical Baseline";
    subEl.textContent = `[${badgeType}] Observed: ${live.observation_time} | Source: ${live.data_source}`;
  }
  if (pulseEl) {
    pulseEl.className = live.is_live ? "live-pulse-dot" : "live-pulse-dot offline";
  }

  lastTelemetryMeta = {
    isLive: live.is_live,
    dataSource: live.data_source,
    stationName: live.station_name,
    observationTime: live.observation_time,
    currentMeasured: p["PM2.5"],
  };

  // Automatically submit using the available station data context
  await submitPredictionForm(lastTelemetryMeta);
}

async function handlePredictionSubmit(event) {
  event.preventDefault();
  await submitPredictionForm();
}

async function submitPredictionForm(telemetryContext = null) {
  const btn = document.getElementById("btn-predict");
  const panel = document.getElementById("prediction-result-panel");
  if (!panel) return;

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>Calculating forecast...</span>`;
  }

  const getFloat = (id, def) => {
    const el = document.getElementById(id);
    return el && el.value !== "" ? parseFloat(el.value) : def;
  };

  const getInt = (id, def) => {
    const el = document.getElementById(id);
    return el && el.value !== "" ? parseInt(el.value, 10) : def;
  };

  const cityName = document.getElementById("pred-city")?.value || "Delhi";
  let currentPM25 = getFloat("pred-pm25", 100.0);

  const payload = {
    city: cityName,
    pm25_current: currentPM25,
    pm25_lag_2h: getFloat("pred-pm25-lag2", null),
    pm25_lag_3h: getFloat("pred-pm25-lag3", null),
    no2: getFloat("pred-no2", null),
    co: (() => {
      const coValue = getFloat("pred-co", null);
      return Number.isFinite(coValue) && coValue >= 0 && coValue <= 50
        ? coValue
        : null;
    })(),
    so2: getFloat("pred-so2", null),
    ozone: getFloat("pred-ozone", null),
    temperature: getFloat("pred-temp", null),
    relative_humidity: getFloat("pred-rh", null),
    wind_speed: getFloat("pred-ws", null),
    month: getInt("pred-month", 11),
    hour: getInt("pred-hour", 18),
    day_of_week: getInt("pred-weekend", 2),
    is_weekend: getInt("pred-weekend", 2) >= 5 ? 1 : 0,
  };

  let res;

  if (telemetryContext) {
    // Station-based predictions must use the backend's validated observation
    // pipeline. Manual form submissions retain the ordinary prediction route.
    const liveResponse = await apiPost("/api/prediction/live", {
      city: cityName
    });

    if (liveResponse && liveResponse.forecast) {
      res = {
        ...liveResponse.forecast,
        ...liveResponse,
        model_input_quality_flags: Array.isArray(
          liveResponse.forecast.model_input_quality_flags
        )
          ? liveResponse.forecast.model_input_quality_flags
          : [],
      };

      // Use the observation actually returned by the validated backend.
      const sourceTelemetry = liveResponse.input_telemetry;
      if (sourceTelemetry && typeof sourceTelemetry === "object") {
        const sourcePollutants = sourceTelemetry.pollutants || {};
        const rawPM25 = sourcePollutants["PM2.5"];
        const verifiedPM25 = Number(rawPM25);

        if (
          rawPM25 !== null &&
          rawPM25 !== undefined &&
          rawPM25 !== "" &&
          Number.isFinite(verifiedPM25) &&
          verifiedPM25 >= 0
        ) {
          currentPM25 = verifiedPM25;
          const pm25Input = document.getElementById("pred-pm25");
          if (pm25Input) pm25Input.value = verifiedPM25;
        }

        telemetryContext = {
          isLive: Boolean(sourceTelemetry.is_live),
          dataSource: sourceTelemetry.source_name ||
            sourceTelemetry.data_source || "CPCB Monitoring Network",
          stationName: sourceTelemetry.station_name ||
            sourceTelemetry.city || cityName,
          observationTime: sourceTelemetry.observation_time ||
            res.observation_time || "Unavailable",
          currentMeasured: currentPM25,
        };
        lastTelemetryMeta = telemetryContext;
      }
    } else {
      res = liveResponse;
    }
  } else {
    res = await apiPost("/api/prediction", payload);
  }

  if (btn) {
    btn.disabled = false;
    btn.innerHTML = `<span>Predict Air Quality</span>`;
  }

  if (!res || res.predicted_pm25 === null || res.predicted_pm25 === undefined) {
    panel.innerHTML = `
      <div class="result-placeholder">
        <div class="placeholder-icon">⚠️</div>
        <h3>Prediction Service Unavailable</h3>
        <p>Could not connect to the local inference backend. Please ensure the server is active.</p>
      </div>
    `;
    return;
  }

  const targetHourAlreadyStarted =
    Array.isArray(res.model_input_quality_flags) &&
    res.model_input_quality_flags.some(
      (flag) =>
        typeof flag === "string" &&
        flag.toLowerCase().includes("at or before the data retrieval time")
    );
  const forecastTitle = targetHourAlreadyStarted
    ? "XGBoost Estimate (Target Hour Already Started)"
    : "XGBoost Forecast (1-Hour Ahead Horizon: t+1)";

  const categoryColor = res.color || "#14b8a6";
  const delta = (res.predicted_pm25 - currentPM25).toFixed(1);
  const deltaSign = delta > 0 ? `+${delta}` : delta;
  const deltaColor = delta > 0 ? "#ef4444" : (delta < 0 ? "#10b981" : "var(--text-muted)");

  const precautionsHtml = (res.precautions || [])
    .map((p) => `<li class="precaution-item"><span class="precaution-bullet">•</span><span>${p}</span></li>`)
    .join("");

  const qualityFlags = Array.isArray(res.model_input_quality_flags)
    ? res.model_input_quality_flags.filter(
        (flag) => typeof flag === "string" && flag.trim()
      )
    : [];

  const escapeQualityText = (value) =>
    String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[char]);

  const qualityWarningsHtml = qualityFlags.length
    ? `
      <div role="status" style="
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.45);
        border-radius: var(--radius-sm);
        padding: 12px 14px;
        margin: 12px 0;
        font-size: 12px;
      ">
        <strong style="display:block; margin-bottom:6px;">
          Prediction Input Quality Notes
        </strong>
        <ul style="margin:0; padding-left:18px; line-height:1.6;">
          ${qualityFlags.map((flag) =>
            `<li>${escapeQualityText(flag)}</li>`
          ).join("")}
        </ul>
      </div>
    `
    : "";

  const meta = telemetryContext;
  const sourceLabel = meta ? (meta.isLive ? "🟢 Real-Time CPCB Station Observation" : "⚪ CPCB Historical Archive Baseline") : "Manual Environmental Inputs";
  const obsTimeDisplay = meta ? `Observed: ${meta.observationTime} at ${meta.stationName}` : "Input time configured in form";

  panel.innerHTML = `
    <div class="prediction-display-card">
      <div class="prediction-badge-bar">
        <span class="pred-provenance-tag">${forecastTitle}</span>
        <span class="badge" style="background-color: ${res.badge_bg || "rgba(255,255,255,0.06)"}; color: ${categoryColor}; border: 1px solid ${categoryColor};">
          Predicted: ${res.aqi_category}
        </span>
      </div>

      <div class="pred-value-section">
        <div class="pred-number-big" style="color: ${categoryColor};">
          ${res.predicted_pm25.toFixed(1)}
        </div>
        <div class="pred-units-box">
          <span class="pred-unit-label">µg/m³ PM2.5 Forecast</span>
          <span style="font-size: 13px; color: var(--text-muted);">
            Derived NAQI Sub-Index: <strong>${Math.round(res.predicted_aqi)}</strong>
          </span>
          <div style="font-size: 13px; margin-top: 4px;">
            Change from input: <strong style="color: ${deltaColor};">${deltaSign} µg/m³</strong>
          </div>
        </div>
      </div>

      <!-- Live / Input Data Context -->
      <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 10px 14px; margin: 12px 0; font-size: 12px;">
        <div style="font-weight: 600; color: var(--text-secondary); margin-bottom: 2px;">
          ${sourceLabel}
        </div>
        <div style="color: var(--text-muted);">
          Current Measured PM2.5: <strong>${currentPM25.toFixed(1)} µg/m³</strong> | ${obsTimeDisplay}
        </div>
      </div>

      ${qualityWarningsHtml}

      <div class="pred-explanation-card">
        <div class="pred-explanation-title">Health Impact & CPCB Guidance</div>
        <p class="pred-explanation-body">${res.advisory}</p>

        <div style="font-size: 12px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">
          Actionable Public Precautions:
        </div>
        <ul class="precautions-list">
          ${precautionsHtml}
        </ul>
      </div>

      <div style="font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px;">
        <em>Methodology: 1-hour ahead regression forecast generated by XGBoost Regressor (300 estimators, tree_method='hist'). The AQI figure represents the official CPCB piecewise linear PM2.5 sub-index.</em>
      </div>
    </div>
  `;

  if (window.innerWidth < 1024) {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
