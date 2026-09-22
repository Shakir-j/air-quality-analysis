"""
app/pages_methodology.py
────────────────────────
Page 5: Technical Methodology, System Architecture & UN Sustainable Development Goals (SDGs).
Provides academic and industry documentation of data lineage, mathematical formulations,
system pipelines, and social-environmental impact alignment.
"""

from __future__ import annotations

import streamlit as st


def render_methodology_page():
    st.markdown(
        """
        <div class="hero-header">
            <div class="hero-title">Methodology, Pipeline Architecture & UN SDGs</div>
            <div class="hero-subtitle">
                Systematic documentation of data provenance, rigorous leak-free chronological modeling,
                CPCB mathematical formulations, and formal alignment with United Nations Global Goals.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Pipeline Architecture ─────────────────────────────────────────────────
    st.markdown("##### 🏛️ End-to-End System Pipeline")
    st.markdown(
        """
        <div class="glass-panel" style="padding: 24px; margin-bottom: 24px;">
            <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; text-align: center;">
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 130px;">
                    <div style="font-size: 11px; color: #38bdf8; font-weight: 700;">PHASE 1</div>
                    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 2px;">Raw Data Ingestion</div>
                    <div style="font-size: 11px; color: #64748b;">453 Station CSVs (14.3M Rows)</div>
                </div>
                <div style="color: #64748b; font-size: 18px;">➔</div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 130px;">
                    <div style="font-size: 11px; color: #10b981; font-weight: 700;">PHASE 2</div>
                    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 2px;">CPCB Preprocessing</div>
                    <div style="font-size: 11px; color: #64748b;">Outlier Capping & Parquet Export</div>
                </div>
                <div style="color: #64748b; font-size: 18px;">➔</div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 130px;">
                    <div style="font-size: 11px; color: #f59e0b; font-weight: 700;">PHASE 3</div>
                    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 2px;">Multivariate EDA</div>
                    <div style="font-size: 11px; color: #64748b;">11 Interactive Plotly Visualizations</div>
                </div>
                <div style="color: #64748b; font-size: 18px;">➔</div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 130px;">
                    <div style="font-size: 11px; color: #a855f7; font-weight: 700;">PHASE 4-5</div>
                    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 2px;">Feature Engineering</div>
                    <div style="font-size: 11px; color: #64748b;">Lags, Rolling Stats & Time Split</div>
                </div>
                <div style="color: #64748b; font-size: 18px;">➔</div>
                <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 12px 16px; flex: 1; min-width: 130px;">
                    <div style="font-size: 11px; color: #ef4444; font-weight: 700;">PHASE 6-8</div>
                    <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-top: 2px;">ML & Dashboard</div>
                    <div style="font-size: 11px; color: #64748b;">5 Models & Streamlit Analytics</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_meta1, col_meta2 = st.columns(2, gap="large")

    with col_meta1:
        st.markdown(
            """
            <div class="glass-panel">
                <div class="panel-title">
                    <span>📐</span> CPCB Indian AQI Mathematical Formulation
                </div>
                <div style="font-size: 13px; color: #94a3b8; line-height: 1.6;">
                    The Central Pollution Control Board (CPCB) calculates the National Air Quality Index (NAQI) sub-index for PM2.5 via piecewise linear interpolation:
                    <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); padding: 12px; border-radius: 8px; margin: 10px 0; font-family: monospace; color: #38bdf8; text-align: center;">
                        I_p = [ (I_hi - I_lo) / (B_hi - B_lo) ] * (C_p - B_lo) + I_lo
                    </div>
                    Where:
                    <ul style="margin: 0; padding-left: 18px; font-size: 12px;">
                        <li><strong>C_p:</strong> Observed or predicted particulate concentration (µg/m³)</li>
                        <li><strong>B_hi, B_lo:</strong> Breakpoint concentration band corresponding to C_p</li>
                        <li><strong>I_hi, I_lo:</strong> Sub-index range corresponding to breakpoint band</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="glass-panel">
                <div class="panel-title">
                    <span>⏱️</span> Time-Aware Leakage Prevention Protocol
                </div>
                <div style="font-size: 13px; color: #94a3b8; line-height: 1.6;">
                    Air quality prediction is inherently a time-series problem where future information cannot leak into past estimates:
                    <ul style="margin: 8px 0 0 0; padding-left: 18px;">
                        <li><strong>Strict Temporal Ordering:</strong> Train set spans <code>2010 → 2021-12-31</code>; Validation set spans <code>2022-01-01 → 2022-06-30</code>; untouched Test set spans <code>2022-07-01 → 2023-03-31</code>.</li>
                        <li><strong>Zero Future Contamination:</strong> All lag features strictly use <code>shift(n)</code> on historical indices; rolling metrics use left-closed intervals.</li>
                        <li><strong>No Random K-Fold CV:</strong> Random shuffling would cause autocorrelation leakage; temporal cross-validation is enforced.</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_meta2:
        st.markdown(
            """
            <div class="glass-panel">
                <div class="panel-title">
                    <span>🌍</span> Alignment with UN Sustainable Development Goals (SDGs)
                </div>
                <div style="display: flex; flex-direction: column; gap: 14px;">
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 12px 14px; border-radius: 8px; border-left: 4px solid #4ade80;">
                        <div style="font-weight: 700; color: #f8fafc; font-size: 13px;">SDG 3: Good Health and Well-Being (Target 3.9)</div>
                        <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                            Substantially reduce the number of deaths and illnesses from hazardous airborne chemicals and air pollution by providing early 1-hour warning windows for vulnerable cardiac and asthmatic populations.
                        </div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 12px 14px; border-radius: 8px; border-left: 4px solid #f97316;">
                        <div style="font-weight: 700; color: #f8fafc; font-size: 13px;">SDG 11: Sustainable Cities & Communities (Target 11.6)</div>
                        <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                            Reduce the adverse per capita environmental impact of cities, paying special attention to air quality and municipal environmental management through localized station-level surveillance.
                        </div>
                    </div>
                    <div style="background: rgba(15, 23, 42, 0.6); padding: 12px 14px; border-radius: 8px; border-left: 4px solid #38bdf8;">
                        <div style="font-weight: 700; color: #f8fafc; font-size: 13px;">SDG 13: Climate Action (Target 13.3)</div>
                        <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">
                            Improve education, awareness-raising, and human and institutional capacity on climate change mitigation, impact reduction, and early warning through public air intelligence dashboards.
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="glass-panel">
                <div class="panel-title">
                    <span>💻</span> Technology Stack & Reproducibility
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; color: #94a3b8;">
                    <div>• <strong>Core Runtime:</strong> Python 3.13.11</div>
                    <div>• <strong>Data Engine:</strong> Pandas 2.3 & NumPy 2.3</div>
                    <div>• <strong>ML Framework:</strong> Scikit-Learn 1.7 & XGBoost 3.4</div>
                    <div>• <strong>Serialization:</strong> Joblib 1.5 & PyArrow Parquet</div>
                    <div>• <strong>Visualization:</strong> Plotly 7.1 Dark Theme</div>
                    <div>• <strong>Web Dashboard:</strong> Streamlit 1.47</div>
                    <div>• <strong>Validation Suite:</strong> Pytest 9.1 Unit Testing</div>
                    <div>• <strong>Version Control:</strong> Git (clean semantic commits)</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
