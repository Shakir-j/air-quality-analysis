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
  setVal("pred-weekend", p.weekend);

  // Auto trigger prediction for immediate responsiveness
  submitPredictionForm();
}

async function handlePredictionSubmit(event) {
  event.preventDefault();
  await submitPredictionForm();
}

async function submitPredictionForm() {
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

  const payload = {
    city: document.getElementById("pred-city")?.value || "Delhi",
    pm25_current: getFloat("pred-pm25", 100.0),
    pm25_lag_2h: getFloat("pred-pm25-lag2", null),
    pm25_lag_3h: getFloat("pred-pm25-lag3", null),
    no2: getFloat("pred-no2", null),
    co: getFloat("pred-co", null),
    so2: getFloat("pred-so2", null),
    ozone: getFloat("pred-ozone", null),
    temperature: getFloat("pred-temp", 25.0),
    relative_humidity: getFloat("pred-rh", 60.0),
    wind_speed: getFloat("pred-ws", 1.5),
    month: getInt("pred-month", 11),
    hour: getInt("pred-hour", 18),
    is_weekend: getInt("pred-weekend", 0),
  };

  const res = await apiPost("/api/prediction", payload);

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

  const categoryColor = res.color || "#14b8a6";
  const precautionsHtml = (res.precautions || [])
    .map((p) => `<li class="precaution-item"><span class="precaution-bullet">•</span><span>${p}</span></li>`)
    .join("");

  panel.innerHTML = `
    <div class="prediction-display-card">
      <div class="prediction-badge-bar">
        <span class="pred-provenance-tag">Model Prediction (1-Hour Ahead Forecast)</span>
        <span class="badge" style="background-color: ${res.badge_bg || "rgba(255,255,255,0.06)"}; color: ${categoryColor}; border: 1px solid ${categoryColor};">
          CPCB Category: ${res.aqi_category}
        </span>
      </div>

      <div class="pred-value-section">
        <div class="pred-number-big" style="color: ${categoryColor};">
          ${res.predicted_pm25.toFixed(1)}
        </div>
        <div class="pred-units-box">
          <span class="pred-unit-label">µg/m³ PM2.5</span>
          <span style="font-size: 13px; color: var(--text-muted);">
            Equivalent AQI Sub-Index: <strong>${Math.round(res.predicted_aqi)}</strong>
          </span>
          <div class="pred-category-badge" style="background-color: ${categoryColor}22; color: ${categoryColor}; border: 1px solid ${categoryColor}66;">
            ${res.aqi_category}
          </div>
        </div>
      </div>

      <div class="pred-explanation-card">
        <div class="pred-explanation-title">How to interpret this</div>
        <p class="pred-explanation-body">${res.advisory}</p>
        
        <div style="font-size: 12px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px;">
          Recommended Precautions:
        </div>
        <ul class="precautions-list">
          ${precautionsHtml}
        </ul>
      </div>

      <div style="font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 12px;">
        <em>Notice: This is a statistical model estimate for the upcoming hour based on supplied observations. Not a certified sensor measurement.</em>
      </div>
    </div>
  `;

  if (window.innerWidth < 1024) {
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
}
