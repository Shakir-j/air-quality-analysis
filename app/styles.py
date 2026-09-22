"""
app/styles.py
─────────────
Design system and styling tokens for the Air Quality Analysis & Prediction Dashboard.
Implements a dark, professional environmental intelligence aesthetic.
"""

# Custom CSS for Streamlit
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Global Styles ─────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #e2e8f0;
}

/* Background */
.stApp {
    background-color: #0b0f19;
    background-image: 
        radial-gradient(circle at 15% 15%, rgba(16, 185, 129, 0.04) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(59, 130, 246, 0.04) 0%, transparent 40%);
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #080c14 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #94a3b8;
}

/* Top App Header / Title Banner */
.hero-header {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(30, 41, 59, 0.5) 100%);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 14px;
    padding: 24px 30px;
    margin-bottom: 24px;
    backdrop-filter: blur(10px);
}

.hero-title {
    font-size: 26px;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: linear-gradient(90deg, #34d399 0%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 6px;
}

.hero-subtitle {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 0;
}

/* KPI Card Component */
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.kpi-card {
    background: rgba(17, 24, 39, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 18px 20px;
    backdrop-filter: blur(8px);
    transition: transform 0.2s ease, border-color 0.2s ease;
}

.kpi-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.3);
}

.kpi-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 6px;
}

.kpi-val {
    font-size: 26px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.5px;
    margin-bottom: 4px;
}

.kpi-badge {
    display: inline-flex;
    align-items: center;
    font-size: 11px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 9999px;
}

/* Glass Section Container */
.glass-panel {
    background: rgba(17, 24, 39, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 14px;
    padding: 22px 24px;
    margin-bottom: 20px;
    backdrop-filter: blur(8px);
}

.panel-title {
    font-size: 16px;
    font-weight: 700;
    color: #f1f5f9;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Prediction Output Card */
.prediction-result-card {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.6) 100%);
    border-radius: 16px;
    padding: 26px;
    border-left: 6px solid;
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    margin: 16px 0;
}

.pred-val-display {
    font-size: 44px;
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1;
}

.aqi-badge-large {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 10px;
}

/* Advisory Box */
.advisory-box {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px 18px;
    margin-top: 16px;
}

/* Clean tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 4px;
}

.stTabs [data-baseweb="tab"] {
    height: 40px;
    background-color: transparent;
    border-radius: 8px;
    color: #94a3b8;
    font-weight: 500;
    font-size: 13px;
    padding: 0 16px;
    border: 1px solid transparent;
}

.stTabs [aria-selected="true"] {
    background-color: rgba(30, 41, 59, 0.8) !important;
    color: #38bdf8 !important;
    border: 1px solid rgba(56, 189, 248, 0.3) !important;
}

/* Input widgets styling */
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
    background-color: #0f172a !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
    color: #f1f5f9 !important;
}

/* Streamlit button customisation */
.stButton > button {
    background: linear-gradient(135deg, #059669 0%, #0d9488 100%) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3) !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(5, 150, 105, 0.45) !important;
}
</style>
"""

# Plotly dark template layout defaults
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(15, 23, 42, 0.4)",
    font=dict(family="Plus Jakarta Sans, sans-serif", color="#94a3b8", size=11),
    title_font=dict(family="Plus Jakarta Sans, sans-serif", color="#f1f5f9", size=14),
    xaxis=dict(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.08)",
        tickfont=dict(color="#94a3b8"),
    ),
    yaxis=dict(
        gridcolor="rgba(255, 255, 255, 0.05)",
        zerolinecolor="rgba(255, 255, 255, 0.08)",
        tickfont=dict(color="#94a3b8"),
    ),
    legend=dict(
        bgcolor="rgba(15, 23, 42, 0.6)",
        bordercolor="rgba(255, 255, 255, 0.08)",
        borderwidth=1,
        font=dict(color="#94a3b8", size=10),
    ),
)
