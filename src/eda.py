"""
src/eda.py
──────────
Exploratory Data Analysis — chart generation functions.

Each function:
  - Accepts a clean DataFrame (output of preprocessor.load_processed())
  - Returns a Plotly figure (interactive) or a Matplotlib figure (static)
  - Is self-contained and importable by both scripts and the Streamlit app

Chart catalogue:
  1.  plot_pm25_distribution()        — PM2.5 histogram + KDE
  2.  plot_pollutant_boxplots()        — Boxplot per pollutant
  3.  plot_city_comparison()           — Mean PM2.5 by city (bar)
  4.  plot_monthly_trend()             — Monthly avg PM2.5 line (multi-city)
  5.  plot_seasonal_pattern()          — Season × city PM2.5 heatmap  [HEATMAP A]
  6.  plot_correlation_heatmap()       — Pollutant correlation matrix   [HEATMAP B]
  7.  plot_city_pollutant_heatmap()    — City × pollutant mean          [HEATMAP C]
  8.  plot_yearly_trend()              — Yearly PM2.5 trend (line)
  9.  plot_hourly_pattern()            — Hour-of-day PM2.5 pattern
  10. plot_aqi_distribution()          — AQI category pie/donut
  11. plot_actual_vs_predicted()       — For model evaluation page
  12. plot_residuals()                 — Residual distribution
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
import matplotlib.pyplot as plt
import seaborn as sns

from src.config import TARGET_COL, POLLUTANT_DISPLAY

# ── Colour palette ────────────────────────────────────────────────────────────
CITY_COLORS = px.colors.qualitative.Bold
AQI_COLORS = {
    "Good":         "#00b050",
    "Satisfactory": "#92d050",
    "Moderate":     "#ffff00",
    "Poor":         "#ff7c00",
    "Very Poor":    "#ff0000",
    "Severe":       "#7030a0",
}
DARK_BG   = "#0e1117"
CARD_BG   = "#1a1f2e"
ACCENT    = "#4fc3f7"
TEMPLATE  = "plotly_dark"


# ── Helper ────────────────────────────────────────────────────────────────────
def _short_name(col: str) -> str:
    return POLLUTANT_DISPLAY.get(col, col)


def _apply_dark_layout(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        template=TEMPLATE,
        paper_bgcolor=DARK_BG,
        plot_bgcolor=CARD_BG,
        font=dict(family="Inter, sans-serif", color="#e0e0e0"),
        title=dict(text=title, font=dict(size=16), x=0.5),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 1. PM2.5 Distribution
# ─────────────────────────────────────────────────────────────────────────────
def plot_pm25_distribution(df: pd.DataFrame) -> go.Figure:
    """PM2.5 histogram with CPCB AQI threshold bands."""
    vals = df[TARGET_COL].dropna()
    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=vals,
        nbinsx=80,
        name="PM2.5",
        marker_color=ACCENT,
        opacity=0.75,
        hovertemplate="PM2.5: %{x:.1f}<br>Count: %{y:,}<extra></extra>",
    ))

    # AQI threshold vertical lines
    thresholds = [
        (30,  "Good / Satisfactory",  "#92d050"),
        (60,  "Moderate",             "#ffff00"),
        (90,  "Poor",                 "#ff7c00"),
        (120, "Very Poor",            "#ff0000"),
        (250, "Severe",               "#7030a0"),
    ]
    for x_val, label, color in thresholds:
        fig.add_vline(x=x_val, line_dash="dash", line_color=color,
                      annotation_text=label, annotation_font_size=10,
                      annotation_font_color=color)

    _apply_dark_layout(fig, "PM2.5 Distribution — All Stations")
    fig.update_xaxes(title_text="PM2.5 (µg/m³)", range=[0, 400])
    fig.update_yaxes(title_text="Count")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 2. Pollutant Boxplots
# ─────────────────────────────────────────────────────────────────────────────
def plot_pollutant_boxplots(df: pd.DataFrame) -> go.Figure:
    """Box plots of all major pollutants, normalised for visual comparison."""
    poll_cols = [c for c in [
        "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)",
        "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)"
    ] if c in df.columns]

    fig = go.Figure()
    palette = px.colors.qualitative.Pastel
    for i, col in enumerate(poll_cols):
        vals = df[col].dropna()
        fig.add_trace(go.Box(
            y=vals,
            name=_short_name(col),
            marker_color=palette[i % len(palette)],
            boxmean="sd",
            hoverinfo="y",
        ))

    _apply_dark_layout(fig, "Pollutant Distribution (Box Plots)")
    fig.update_yaxes(title_text="Concentration")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 3. City Comparison — Mean PM2.5
# ─────────────────────────────────────────────────────────────────────────────
def plot_city_comparison(df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Horizontal bar chart: mean PM2.5 by city, sorted descending."""
    city_pm25 = (
        df.groupby("city", observed=True)[TARGET_COL]
        .mean()
        .sort_values(ascending=True)
        .tail(top_n)
    )
    naaqs_limit = 40  # India's annual NAAQS standard for PM2.5

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=city_pm25.index.tolist(),
        x=city_pm25.values,
        orientation="h",
        marker=dict(
            color=city_pm25.values,
            colorscale="RdYlGn_r",
            cmin=0, cmax=150,
            showscale=True,
            colorbar=dict(title="µg/m³"),
        ),
        hovertemplate="%{y}: %{x:.1f} µg/m³<extra></extra>",
    ))
    fig.add_vline(x=naaqs_limit, line_dash="dash", line_color="#ffff00",
                  annotation_text="NAAQS Limit (40)", annotation_font_size=11)

    _apply_dark_layout(fig, f"Mean PM2.5 by City (Top {top_n})")
    fig.update_xaxes(title_text="Mean PM2.5 (µg/m³)")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 4. Monthly Trend
# ─────────────────────────────────────────────────────────────────────────────
def plot_monthly_trend(
    df: pd.DataFrame,
    cities: list[str] | None = None,
    pollutant: str = TARGET_COL,
) -> go.Figure:
    """Line chart: monthly average pollutant level, one line per city."""
    if pollutant not in df.columns:
        pollutant = TARGET_COL

    sub = df.copy()
    if cities:
        sub = sub[sub["city"].isin(cities)]

    monthly = (
        sub.groupby(["city", "year", "month"], observed=True)[pollutant]
        .mean()
        .reset_index()
    )
    monthly["date"] = pd.to_datetime(
        monthly[["year", "month"]].assign(day=1)
    )
    monthly = monthly.sort_values("date")

    fig = px.line(
        monthly, x="date", y=pollutant, color="city",
        color_discrete_sequence=CITY_COLORS,
        labels={"date": "Month", pollutant: _short_name(pollutant) + " (µg/m³)"},
        hover_data={"year": False, "month": False},
    )
    _apply_dark_layout(fig, f"Monthly {_short_name(pollutant)} Trend by City")
    fig.update_traces(line=dict(width=1.5))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Seasonal Pattern Heatmap — HEATMAP A
# ─────────────────────────────────────────────────────────────────────────────
def plot_seasonal_heatmap(
    df: pd.DataFrame,
    pollutant: str = TARGET_COL,
) -> go.Figure:
    """
    Heatmap: Season × City mean pollutant concentration.
    Rows = seasons (Winter, Pre-Monsoon, Monsoon, Post-Monsoon)
    Columns = cities
    """
    if pollutant not in df.columns:
        pollutant = TARGET_COL

    season_order = ["Winter", "Pre-Monsoon", "Monsoon", "Post-Monsoon"]
    pivot = (
        df.groupby(["season", "city"], observed=True)[pollutant]
        .mean()
        .reset_index()
        .pivot(index="season", columns="city", values=pollutant)
        .reindex(season_order)
    )

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="RdYlGn_r",
        hovertemplate="Season: %{y}<br>City: %{x}<br>%{z:.1f} µg/m³<extra></extra>",
        colorbar=dict(title="µg/m³"),
        text=np.round(pivot.values, 1),
        texttemplate="%{text}",
        textfont=dict(size=10),
    ))
    _apply_dark_layout(fig, f"Seasonal {_short_name(pollutant)} by City")
    fig.update_xaxes(title_text="City", tickangle=-30)
    fig.update_yaxes(title_text="Season")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. Pollutant Correlation Heatmap — HEATMAP B
# ─────────────────────────────────────────────────────────────────────────────
def plot_correlation_heatmap(df: pd.DataFrame) -> go.Figure:
    """Pearson correlation matrix of all numeric pollutant + met columns."""
    numeric_cols = [c for c in [
        "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)", "NOx (ppb)",
        "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)", "NH3 (ug/m3)",
        "Benzene (ug/m3)", "RH (%)", "WS (m/s)", "AT (degree C)", "AQI",
    ] if c in df.columns]

    sample = df[numeric_cols].dropna(thresh=len(numeric_cols) // 2)
    corr = sample[numeric_cols].corr()
    short_labels = [_short_name(c) for c in numeric_cols]

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=short_labels,
        y=short_labels,
        colorscale="RdBu",
        zmid=0,
        zmin=-1, zmax=1,
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Pearson r"),
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=9),
    ))
    _apply_dark_layout(fig, "Pollutant & Meteorological Correlation Matrix")
    fig.update_layout(width=700, height=650)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 7. City × Pollutant Heatmap — HEATMAP C
# ─────────────────────────────────────────────────────────────────────────────
def plot_city_pollutant_heatmap(df: pd.DataFrame) -> go.Figure:
    """
    Heatmap: City (rows) × Pollutant (columns) mean concentration.
    Values are normalised within each pollutant column (0–1 scale)
    so that different units don't dominate colour.
    """
    poll_cols = [c for c in [
        "PM2.5 (ug/m3)", "PM10 (ug/m3)", "NO2 (ug/m3)",
        "SO2 (ug/m3)", "CO (mg/m3)", "Ozone (ug/m3)",
    ] if c in df.columns]

    pivot = (
        df.groupby("city", observed=True)[poll_cols]
        .mean()
        .round(1)
    )
    # Normalise per column
    pivot_norm = (pivot - pivot.min()) / (pivot.max() - pivot.min() + 1e-9)
    short_poll = [_short_name(c) for c in poll_cols]

    fig = go.Figure(data=go.Heatmap(
        z=pivot_norm.values,
        x=short_poll,
        y=pivot.index.tolist(),
        colorscale="YlOrRd",
        hovertemplate="City: %{y}<br>Pollutant: %{x}<br>Norm. value: %{z:.2f}<extra></extra>",
        colorbar=dict(title="Normalised\nConcentration"),
        text=pivot.values,
        texttemplate="%{text}",
        textfont=dict(size=9),
    ))
    _apply_dark_layout(fig, "City × Pollutant Mean Concentration (Normalised)")
    fig.update_xaxes(title_text="Pollutant")
    fig.update_yaxes(title_text="City")
    fig.update_layout(height=500)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 8. Yearly Trend
# ─────────────────────────────────────────────────────────────────────────────
def plot_yearly_trend(
    df: pd.DataFrame,
    cities: list[str] | None = None,
    pollutant: str = TARGET_COL,
) -> go.Figure:
    """Annual mean pollutant level, one line per city."""
    if pollutant not in df.columns:
        pollutant = TARGET_COL
    sub = df.copy()
    if cities:
        sub = sub[sub["city"].isin(cities)]

    yearly = sub.groupby(["city", "year"], observed=True)[pollutant].mean().reset_index()

    fig = px.line(
        yearly, x="year", y=pollutant, color="city",
        markers=True,
        color_discrete_sequence=CITY_COLORS,
        labels={"year": "Year", pollutant: _short_name(pollutant) + " (µg/m³)"},
    )
    _apply_dark_layout(fig, f"Yearly {_short_name(pollutant)} Trend by City")
    fig.update_traces(line=dict(width=2))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 9. Hourly Pattern
# ─────────────────────────────────────────────────────────────────────────────
def plot_hourly_pattern(
    df: pd.DataFrame,
    city: str | None = None,
    pollutant: str = TARGET_COL,
) -> go.Figure:
    """Mean pollutant by hour of day — shows traffic/industrial patterns."""
    if pollutant not in df.columns:
        pollutant = TARGET_COL
    sub = df.copy()
    if city:
        sub = sub[sub["city"] == city]

    hourly = sub.groupby("hour")[pollutant].mean().reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly["hour"], y=hourly[pollutant],
        mode="lines+markers",
        line=dict(color=ACCENT, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(79,195,247,0.12)",
        hovertemplate="Hour %{x}:00 — %{y:.1f} µg/m³<extra></extra>",
    ))
    title = f"Diurnal {_short_name(pollutant)} Pattern"
    if city:
        title += f" — {city}"
    _apply_dark_layout(fig, title)
    fig.update_xaxes(title_text="Hour of Day", tickvals=list(range(0, 24, 3)))
    fig.update_yaxes(title_text=f"{_short_name(pollutant)} (µg/m³)")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 10. AQI Distribution
# ─────────────────────────────────────────────────────────────────────────────
def plot_aqi_distribution(df: pd.DataFrame) -> go.Figure:
    """Donut chart of AQI category distribution across all observations."""
    valid_cats = ["Good", "Satisfactory", "Moderate", "Poor", "Very Poor", "Severe"]
    counts = (
        df["AQI_Category"]
        .value_counts()
        .reindex(valid_cats)
        .dropna()
    )
    colors = [AQI_COLORS.get(c, "#888") for c in counts.index]

    fig = go.Figure(go.Pie(
        labels=counts.index.tolist(),
        values=counts.values,
        hole=0.5,
        marker_colors=colors,
        hovertemplate="%{label}: %{value:,} observations (%{percent})<extra></extra>",
        textinfo="percent+label",
    ))
    _apply_dark_layout(fig, "AQI Category Distribution")
    fig.update_layout(showlegend=True)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 11. Actual vs Predicted
# ─────────────────────────────────────────────────────────────────────────────
def plot_actual_vs_predicted(
    y_actual: np.ndarray,
    y_pred: np.ndarray,
    title: str = "Actual vs Predicted PM2.5",
    max_points: int = 5000,
) -> go.Figure:
    """Scatter: actual vs predicted PM2.5. Samples if dataset is large."""
    if len(y_actual) > max_points:
        idx = np.random.choice(len(y_actual), max_points, replace=False)
        y_actual = y_actual[idx]
        y_pred   = y_pred[idx]

    perfect_line = [float(min(y_actual.min(), y_pred.min())),
                    float(max(y_actual.max(), y_pred.max()))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=y_actual, y=y_pred,
        mode="markers",
        marker=dict(color=ACCENT, size=4, opacity=0.5),
        name="Predictions",
        hovertemplate="Actual: %{x:.1f}<br>Predicted: %{y:.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=perfect_line, y=perfect_line,
        mode="lines",
        line=dict(color="#ff4444", dash="dash", width=1.5),
        name="Perfect fit",
    ))
    _apply_dark_layout(fig, title)
    fig.update_xaxes(title_text="Actual PM2.5 (µg/m³)")
    fig.update_yaxes(title_text="Predicted PM2.5 (µg/m³)")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 12. Residuals
# ─────────────────────────────────────────────────────────────────────────────
def plot_residuals(
    y_actual: np.ndarray,
    y_pred: np.ndarray,
    title: str = "Residual Distribution",
) -> go.Figure:
    """Histogram of residuals (actual − predicted)."""
    residuals = y_actual - y_pred
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=residuals,
        nbinsx=60,
        marker_color=ACCENT,
        opacity=0.8,
        name="Residuals",
        hovertemplate="Residual: %{x:.1f}<br>Count: %{y:,}<extra></extra>",
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="#ff4444",
                  annotation_text="Zero error")
    _apply_dark_layout(fig, title)
    fig.update_xaxes(title_text="Residual (µg/m³)")
    fig.update_yaxes(title_text="Count")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 13. Month × Year Heatmap
# ─────────────────────────────────────────────────────────────────────────────
def plot_month_year_heatmap(
    df: pd.DataFrame,
    city: str | None = None,
    pollutant: str = TARGET_COL,
) -> go.Figure:
    """
    Heatmap: Year (rows) × Month (columns) mean pollutant.
    Shows temporal patterns over the full 2010–2023 span.
    """
    if pollutant not in df.columns:
        pollutant = TARGET_COL
    sub = df.copy()
    if city:
        sub = sub[sub["city"] == city]

    pivot = (
        sub.groupby(["year", "month"])[pollutant]
        .mean()
        .reset_index()
        .pivot(index="year", columns="month", values=pollutant)
    )
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    pivot.columns = [month_names[m - 1] for m in pivot.columns]

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale="RdYlGn_r",
        hovertemplate="Year: %{y}<br>Month: %{x}<br>%{z:.1f} µg/m³<extra></extra>",
        colorbar=dict(title="µg/m³"),
        text=np.where(np.isnan(pivot.values), "", np.round(pivot.values, 0).astype("Int64").astype(str)),
        texttemplate="%{text}",
        textfont=dict(size=8),
    ))
    title = f"Year × Month {_short_name(pollutant)} Pattern"
    if city:
        title += f" — {city}"
    _apply_dark_layout(fig, title)
    fig.update_xaxes(title_text="Month")
    fig.update_yaxes(title_text="Year", autorange="reversed")
    fig.update_layout(height=500)
    return fig
