"""
app/pages_analysis.py
─────────────────────
Page 2: Air Quality Pattern Analysis & Exploration.
Provides interactive environmental intelligence:
  - Multi-pollutant temporal trends
  - Correlation heatmaps across co-pollutants and meteorology
  - City × Pollutant intensity matrix
  - Diurnal (hourly) bimodal commuting patterns
  - Seasonal & monthly variation heatmaps
"""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from app.styles import PLOTLY_DARK_LAYOUT
from src.preprocessor import load_processed
from src.config import POLLUTANT_COLS, MET_COLS, TARGET_COL

POLLUTANT_OPTIONS = {
    "PM2.5 (ug/m3)": "PM2.5 — Fine Respirable Particulates",
    "PM10 (ug/m3)":  "PM10 — Coarse Inhalable Particulates",
    "NO2 (ug/m3)":   "NO2 — Nitrogen Dioxide (Vehicular/Industrial)",
    "CO (mg/m3)":    "CO — Carbon Monoxide (Incomplete Combustion)",
    "SO2 (ug/m3)":   "SO2 — Sulfur Dioxide (Thermal/Refinery)",
    "Ozone (ug/m3)": "Ozone — Ground-level Photochemical Smog",
}


@st.cache_data(show_spinner=False)
def get_sample_processed_data():
    """Load cached processed data sample for rapid interactive filtering."""
    df = load_processed()
    return df


def render_analysis_page():
    st.markdown(
        """
        <div class="hero-header">
            <div class="hero-title">Air Quality Pattern Analysis & Exploration</div>
            <div class="hero-subtitle">
                Interactive multivariate exploration of diurnal cycles, seasonal smog episodes,
                meteorological dispersion mechanisms, and inter-pollutant chemical correlations.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        df = get_sample_processed_data()
        cities_available = sorted(df["city"].unique().tolist())
    except Exception:
        cities_available = [
            "All Cities", "Delhi", "Mumbai", "Bengaluru", "Chennai",
            "Kolkata", "Hyderabad", "Lucknow", "Ahmedabad", "Jaipur", "Patna"
        ]
        df = None

    # ── Interactive Filter Controls ───────────────────────────────────────────
    st.markdown(
        """
        <div class="glass-panel" style="padding: 16px 20px; margin-bottom: 20px;">
            <div style="font-size: 13px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
                ⚙️ Dynamic Filter Controls
            </div>
        """,
        unsafe_allow_html=True,
    )

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sel_city = st.selectbox(
            "Select Urban Center",
            options=["All Cities"] + [c for c in cities_available if c != "All Cities"],
            index=0,
        )
    with fc2:
        sel_pollutant = st.selectbox(
            "Primary Pollutant Parameter",
            options=list(POLLUTANT_OPTIONS.keys()),
            format_func=lambda k: POLLUTANT_OPTIONS[k],
            index=0,
        )
    with fc3:
        sel_year_range = st.slider(
            "Observation Years",
            min_value=2015,
            max_value=2023,
            value=(2017, 2023),
            step=1,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Filter Data ───────────────────────────────────────────────────────────
    if df is not None:
        sub = df[(df["year"] >= sel_year_range[0]) & (df["year"] <= sel_year_range[1])]
        if sel_city != "All Cities":
            sub = sub[sub["city"] == sel_city]
    else:
        sub = None

    tab_trends, tab_heatmaps, tab_diurnal, tab_distributions = st.tabs([
        "📈 Temporal Trends & Seasonality",
        "🔥 Multivariate Heatmaps",
        "⏰ Diurnal & Hourly Cycles",
        "📊 Pollutant Distributions",
    ])

    # ── TAB 1: Temporal Trends ────────────────────────────────────────────────
    with tab_trends:
        st.markdown("##### Monthly Mean Concentration Trajectory")
        if sub is not None and sel_pollutant in sub.columns:
            monthly = (
                sub.groupby(["year", "month"], observed=True)[sel_pollutant]
                .mean()
                .reset_index()
            )
            monthly["date_str"] = monthly.apply(
                lambda r: f"{int(r['year'])}-{int(r['month']):02d}", axis=1
            )
            monthly = monthly.sort_values("date_str")

            fig_trend = px.line(
                monthly,
                x="date_str",
                y=sel_pollutant,
                labels={"date_str": "Year-Month", sel_pollutant: f"{sel_pollutant}"},
                title=f"Monthly Average {sel_pollutant.split(' ')[0]} ({sel_city})",
            )
            fig_trend.update_traces(
                line=dict(color="#38bdf8", width=2.5),
                mode="lines+markers",
                marker=dict(size=5, color="#0284c7"),
            )
            if "PM2.5" in sel_pollutant:
                fig_trend.add_hline(
                    y=60.0,
                    line_dash="dash",
                    line_color="#f59e0b",
                    annotation_text="NAAQS 24-hr Standard (60 µg/m³)",
                    annotation_position="top right",
                )
            fig_trend.update_layout(**PLOTLY_DARK_LAYOUT, height=420)
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Loading temporal trends visualization...")

    # ── TAB 2: Heatmaps ───────────────────────────────────────────────────────
    with tab_heatmaps:
        hm_col1, hm_col2 = st.columns(2, gap="medium")

        with hm_col1:
            st.markdown("##### Inter-Pollutant & Met Correlation")
            if sub is not None:
                numeric_poll = [c for c in POLLUTANT_COLS + ["RH (%)", "WS (m/s)", "AT (degree C)"] if c in sub.columns]
                corr = sub[numeric_poll].corr().round(2)
                short_labels = [c.split(" ")[0] for c in corr.columns]

                fig_corr = px.imshow(
                    corr.values,
                    x=short_labels,
                    y=short_labels,
                    color_continuous_scale="Viridis",
                    aspect="auto",
                    zmin=-0.5,
                    zmax=1.0,
                    title="Correlation Matrix (Pearson r)",
                )
                fig_corr.update_layout(**PLOTLY_DARK_LAYOUT, height=440)
                st.plotly_chart(fig_corr, use_container_width=True)

        with hm_col2:
            st.markdown("##### Seasonal PM2.5 Load by City")
            if df is not None:
                season_order = ["Winter", "Summer", "Monsoon", "Post-Monsoon"]
                pivot_season = (
                    df.groupby(["city", "season"], observed=True)[TARGET_COL]
                    .mean()
                    .unstack("season")
                    .reindex(columns=season_order)
                    .dropna()
                )
                fig_season = px.imshow(
                    pivot_season.values,
                    x=season_order,
                    y=pivot_season.index.tolist(),
                    color_continuous_scale="YlOrRd",
                    aspect="auto",
                    title="Mean PM2.5 (µg/m³) by City & Season",
                )
                fig_season.update_layout(**PLOTLY_DARK_LAYOUT, height=440)
                st.plotly_chart(fig_season, use_container_width=True)

    # ── TAB 3: Diurnal Patterns ───────────────────────────────────────────────
    with tab_diurnal:
        st.markdown("##### Diurnal (Hourly) Cycle: Bimodal Commuter Spike")
        if sub is not None and sel_pollutant in sub.columns:
            hourly = (
                sub.groupby("hour", observed=True)[sel_pollutant]
                .mean()
                .reset_index()
            )
            fig_hour = px.area(
                hourly,
                x="hour",
                y=sel_pollutant,
                labels={"hour": "Hour of Day (00:00 to 23:00)", sel_pollutant: f"{sel_pollutant}"},
                title=f"Average Hourly Profile for {sel_pollutant.split(' ')[0]} ({sel_city})",
            )
            fig_hour.update_traces(
                line_color="#10b981",
                fillcolor="rgba(16, 185, 129, 0.15)",
            )
            fig_hour.update_layout(
                **PLOTLY_DARK_LAYOUT,
                height=420,
                xaxis=dict(tickmode="linear", tick0=0, dtick=2),
            )
            st.plotly_chart(fig_hour, use_container_width=True)

            st.caption(
                "Noticeable bimodal distribution: Morning peak (08:00–10:00) during vehicular rush hours, "
                "followed by midday solar heating dispersion, and a second intense evening crest (20:00–23:00) "
                "caused by nighttime boundary layer subsidence and heavy transit traffic."
            )

    # ── TAB 4: Distributions ──────────────────────────────────────────────────
    with tab_distributions:
        st.markdown("##### Concentration Spread & Statistical Outliers")
        if sub is not None and sel_pollutant in sub.columns:
            sample_sub = sub.sample(min(15000, len(sub)), random_state=42)
            fig_box = px.box(
                sample_sub,
                x="city" if sel_city == "All Cities" else "season",
                y=sel_pollutant,
                color="city" if sel_city == "All Cities" else "season",
                title=f"{sel_pollutant.split(' ')[0]} Concentration Distribution (Box & Whisker)",
            )
            fig_box.update_layout(**PLOTLY_DARK_LAYOUT, height=440)
            st.plotly_chart(fig_box, use_container_width=True)
