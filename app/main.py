"""
app/main.py
───────────
Main Entry Point for the Air Quality Analysis & Prediction Web Application.
Built with Streamlit and Plotly for high-performance environmental intelligence.

Official Problem Statement:
"Develop a data science and machine learning solution that analyzes environmental data
to identify air quality patterns and predict air quality levels."

Usage:
    streamlit run app/main.py
"""

import sys
from pathlib import Path

# Ensure project root is in Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st

# Page Configuration — must be the very first Streamlit call
st.set_page_config(
    page_title="Air Quality Analysis & Prediction | India",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Import custom styles and page modules
from app.styles import CUSTOM_CSS
from app.pages_overview import render_overview_page
from app.pages_analysis import render_analysis_page
from app.pages_prediction import render_prediction_page
from app.pages_models import render_models_page
from app.pages_methodology import render_methodology_page

# Inject design system CSS inside main


def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    # ── Sidebar Navigation ───────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 10px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 16px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 22px;">🌍</span>
                    <div>
                        <div style="font-weight: 800; font-size: 15px; color: #f1f5f9; letter-spacing: -0.3px;">Air Quality Platform</div>
                        <div style="font-size: 11px; color: #38bdf8; font-weight: 600;">Environmental Intelligence</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #64748b; font-weight: 700; margin-bottom: 8px;">
                Navigation
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav_choice = st.radio(
            label="Navigation Sections",
            options=[
                "🏠 1. Executive Dashboard",
                "📈 2. Pattern Analysis & EDA",
                "🔮 3. Real-Time Predictor",
                "🧠 4. ML Models & Evaluation",
                "📖 5. Methodology & SDGs",
            ],
            label_visibility="collapsed",
        )

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        # Dataset & Model Quick Badge
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 14px 16px; margin-bottom: 16px;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #94a3b8; font-weight: 600; margin-bottom: 6px;">
                    Project Metadata
                </div>
                <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                    • <strong>Dataset:</strong> CPCB / Kaggle (2010–2023)<br>
                    • <strong>Scope:</strong> 133 Stations, 10 Major Hubs<br>
                    • <strong>Primary Target:</strong> PM2.5 (1h Ahead)<br>
                    • <strong>Framework:</strong> XGBoost & Ensemble ML
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Academic credit footer
        st.markdown(
            """
            <div style="font-size: 11px; color: #64748b; line-height: 1.5; padding: 0 4px;">
                B.E. Computer Science Semester Project<br>
                <em>Air Quality Analysis and Prediction</em>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Route to Active Page ─────────────────────────────────────────────────
    if "1. Executive Dashboard" in nav_choice:
        render_overview_page()
    elif "2. Pattern Analysis" in nav_choice:
        render_analysis_page()
    elif "3. Real-Time Predictor" in nav_choice:
        render_prediction_page()
    elif "4. ML Models" in nav_choice:
        render_models_page()
    elif "5. Methodology" in nav_choice:
        render_methodology_page()


if __name__ == "__main__":
    main()
