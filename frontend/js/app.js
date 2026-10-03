/**
 * app.js
 * ──────
 * Core application controller, state management, and tab router for AIRWISE.
 */

const AppState = {
  activeTab: "home",
  selectedCity: "Delhi",
  selectedStation: "all",
  selectedPollutant: "PM2.5",
  locations: [],
  citiesMap: {},
  metadata: null,
};

// ── Plotly Dark Styling Helper ───────────────────────────────────────────────
const PLOTLY_DARK = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: {
    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    color: "#94a3b8",
    size: 12,
  },
  margin: { l: 45, r: 25, t: 30, b: 40 },
  xaxis: {
    gridcolor: "rgba(255, 255, 255, 0.06)",
    zerolinecolor: "rgba(255, 255, 255, 0.1)",
    tickfont: { color: "#94a3b8" },
  },
  yaxis: {
    gridcolor: "rgba(255, 255, 255, 0.06)",
    zerolinecolor: "rgba(255, 255, 255, 0.1)",
    tickfont: { color: "#94a3b8" },
  },
};

const PLOTLY_CONFIG = {
  responsive: true,
  displayModeBar: false,
};

// ── API Client ───────────────────────────────────────────────────────────────
async function apiGet(endpoint) {
  try {
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`Failed to fetch from ${endpoint}:`, err);
    return null;
  }
}

async function apiPost(endpoint, body) {
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error(`POST request to ${endpoint} failed:`, err);
    return null;
  }
}

// ── Navigation & View Switching ──────────────────────────────────────────────
function navigateTo(tabName) {
  if (!tabName) tabName = "home";
  tabName = tabName.replace("#", "");

  const validTabs = ["home", "air-quality", "explore", "insights", "prediction"];
  if (!validTabs.includes(tabName)) tabName = "home";

  AppState.activeTab = tabName;

  // Close mobile nav if open
  const mobileNav = document.getElementById("main-nav");
  const hamburger = document.getElementById("nav-hamburger");
  if (mobileNav) mobileNav.classList.remove("mobile-open");
  if (hamburger) hamburger.classList.remove("open");

  // Update navbar links
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.tab === tabName);
  });

  // Switch sections
  document.querySelectorAll(".page-section").forEach((el) => {
    el.classList.remove("active");
  });

  const targetSection = document.getElementById(`section-${tabName}`);
  if (targetSection) {
    targetSection.classList.add("active");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // Trigger view-specific render
  if (tabName === "home" && typeof renderHomeView === "function") {
    renderHomeView();
  } else if (tabName === "air-quality" && typeof renderAirQualityView === "function") {
    renderAirQualityView();
  } else if (tabName === "explore" && typeof renderExploreViews === "function") {
    renderExploreViews();
  } else if (tabName === "insights" && typeof renderInsightsView === "function") {
    renderInsightsView();
  } else if (tabName === "prediction" && typeof initPredictionView === "function") {
    initPredictionView();
  }
}

// ── Global Initializer ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  // Listen for hash changes
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.slice(1);
    if (hash) navigateTo(hash);
  });

  // Fetch initial location data
  const data = await apiGet("/api/locations");
  if (data && data.cities) {
    AppState.locations = data.cities;
    AppState.metadata = data.metadata;
    data.cities.forEach((c) => {
      AppState.citiesMap[c.city] = c;
    });

    populateCityDropdowns();
  }

  // Determine initial view from URL hash or default to home
  const initialHash = window.location.hash.slice(1) || "home";
  navigateTo(initialHash);
});

function populateCityDropdowns() {
  const selects = [
    document.getElementById("home-city-select"),
    document.getElementById("aq-city-select"),
    document.getElementById("pred-city"),
  ];

  selects.forEach((sel) => {
    if (!sel) return;
    sel.innerHTML = "";
    AppState.locations.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.city;
      opt.textContent = `${c.city} (${c.station_count} stations)`;
      if (c.city === AppState.selectedCity) opt.selected = true;
      sel.appendChild(opt);
    });
  });

  // Populate hour selector in prediction form
  const hourSelect = document.getElementById("pred-hour");
  if (hourSelect) {
    hourSelect.innerHTML = "";
    for (let h = 0; h < 24; h++) {
      const opt = document.createElement("option");
      opt.value = h;
      let timeLabel = "Night";
      if (h >= 5 && h < 12) timeLabel = "Morning";
      else if (h >= 12 && h < 17) timeLabel = "Afternoon";
      else if (h >= 17 && h < 21) timeLabel = "Evening";
      
      opt.textContent = `${h.toString().padStart(2, "0")}:00 (${timeLabel})`;
      if (h === 18) opt.selected = true;
      hourSelect.appendChild(opt);
    }
  }
}

// Mobile nav toggle
function toggleMobileNav() {
  const nav = document.getElementById("main-nav");
  const btn = document.getElementById("nav-hamburger");
  if (!nav || !btn) return;
  nav.classList.toggle("mobile-open");
  btn.classList.toggle("open");
}

// Helper: Health Guidance by Category
function getHealthGuidance(category) {
  switch (category) {
    case "Good":
      return {
        advisory: "Air quality is considered satisfactory, and air pollution poses little or no risk.",
        precautions: [
          "Ideal conditions for outdoor activities and exercise.",
          "Open windows for natural indoor ventilation.",
          "No special precautions required for sensitive groups.",
        ],
      };
    case "Satisfactory":
      return {
        advisory: "Air quality is acceptable; however, a very small number of individuals may experience minor discomfort.",
        precautions: [
          "Generally safe for most people to engage in normal outdoor activities.",
          "Individuals with severe respiratory sensitivities should carry prescribed inhalers.",
          "Safe for schools and children's outdoor play.",
        ],
      };
    case "Moderate":
      return {
        advisory: "Breathing discomfort possible to people with lungs, asthma, and heart diseases.",
        precautions: [
          "Sensitive groups should reduce prolonged outdoor exertion.",
          "Keep windows closed during peak commute hours.",
          "Consider wearing an N95 mask if outdoors in heavy traffic.",
        ],
      };
    case "Poor":
      return {
        advisory: "Breathing discomfort to most people on prolonged exposure; significant discomfort to sensitive groups.",
        precautions: [
          "Avoid prolonged or strenuous outdoor activities.",
          "Run indoor HEPA air purifiers if available.",
          "Vulnerable individuals (children, elderly) should stay indoors.",
        ],
      };
    case "Very Poor":
      return {
        advisory: "Respiratory illness on prolonged exposure. Significant risk for individuals with heart/lung disease.",
        precautions: [
          "Avoid outdoor exertion; exercise indoors.",
          "Wear a high-efficiency N95/N99 respirator outdoors.",
          "Keep doors and windows sealed to prevent outdoor infiltration.",
        ],
      };
    case "Severe":
      return {
        advisory: "Affects healthy people and seriously impacts those with existing diseases. Emergency health condition.",
        precautions: [
          "Strictly remain indoors and minimize physical exertion.",
          "Run indoor air purification continuously.",
          "Seek medical advice immediately if experiencing breathing difficulty.",
        ],
      };
    default:
      return {
        advisory: "Moderate pollution levels recorded.",
        precautions: ["Follow standard urban air quality precautions."],
      };
  }
}
