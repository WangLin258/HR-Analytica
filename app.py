# -*- coding: utf-8 -*-
"""HR Analytica - main entry point."""

import streamlit as st

from auth import require_access
from analysis_engine import CONFIG, init_db, cleanup_old_history, load_user_pref
from ui_components import (
    load_css,
    render_mobile_hint,
    render_nav,
    render_home,
    render_analysis_page,
    render_recruit_page,
    render_report_page,
    render_footer,
)


st.set_page_config(page_title="HR Analytica", layout="wide")
load_css()
try:
    init_db()
    cleanup_old_history()
except Exception as e:
    st.warning(f"历史数据库初始化失败：{e}")


# Session state defaults
for key, default in {
    "splash_done": False,
    "page": "home",
    "df": None,
    "df_filtered": None,
    "src": "",
    "sheets": [],
    "cat_cols": [],
    "num_cols": [],
    "date_cols": [],
    "col_types": {},
    "gc": [],
    "vc": "",
    "cc": "",
    "history": [],
    "id_cols": [],
    "last_stats": None,
    "last_bar_fig": None,
    "last_hist_fig": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = load_user_pref("dark_mode", "false") == "true"


# Splash screen: full-screen brand intro, click anywhere to enter
if not st.session_state.splash_done:
    st.markdown("""
    <style>
    .splash-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 9999;
        background: linear-gradient(135deg, #ECFDF5 0%, #A7F3D0 100%);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        pointer-events: none;
        overflow: hidden;
    }
    .splash-deco-circle {
        position: absolute;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(5,150,105,0.12) 0%, transparent 70%);
    }
    .splash-deco-1 { width: 340px; height: 340px; top: -80px; right: -60px; }
    .splash-deco-2 { width: 220px; height: 220px; bottom: -60px; left: -40px; }
    .splash-grid {
        position: absolute;
        inset: 0;
        background-image:
            linear-gradient(rgba(5,150,105,0.05) 1px, transparent 1px),
            linear-gradient(90deg, rgba(5,150,105,0.05) 1px, transparent 1px);
        background-size: 48px 48px;
    }
    .splash-title {
        font-size: 3.6rem;
        font-weight: 800;
        color: #111827;
        letter-spacing: -1px;
        line-height: 1.1;
        margin-bottom: 18px;
        animation: splashFadeIn 1s ease;
    }
    .splash-slogan {
        font-size: 1.2rem;
        color: #6B7280;
        animation: splashFadeIn 1s ease 0.3s backwards;
    }
    .splash-hint {
        position: absolute;
        bottom: 72px;
        font-size: 14px;
        color: rgba(107,114,128,0.6);
        animation: splashPulse 2s ease-in-out infinite;
    }
    .splash-powered {
        position: absolute;
        bottom: 24px;
        right: 32px;
        font-size: 12px;
        color: #9CA3AF;
    }
    @keyframes splashFadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: none; }
    }
    @keyframes splashPulse {
        0%, 100% { opacity: 0.4; }
        50% { opacity: 1; }
    }
    .stButton > button {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 9998 !important;
        background: transparent !important;
        border: none !important;
        color: transparent !important;
        box-shadow: none !important;
        padding: 0 !important;
        cursor: pointer !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        '<div class="splash-overlay">'
        '<div class="splash-grid"></div>'
        '<div class="splash-deco-circle splash-deco-1"></div>'
        '<div class="splash-deco-circle splash-deco-2"></div>'
        '<div class="splash-title">HR Analytica</div>'
        '<div class="splash-slogan">用数据，发现人力资源的真实价值</div>'
        '<div class="splash-hint">点击任意位置开始</div>'
        '<div class="splash-powered">Powered by 王林</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button("进入", key="splash_btn"):
        st.session_state.splash_done = True
        st.rerun()
    st.stop()


# Fade-in transition when entering the app from splash
if st.session_state.splash_done and "app_faded" not in st.session_state:
    st.markdown("""
    <style>
    .main .block-container {
        animation: appFadeIn 0.5s ease;
    }
    @keyframes appFadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: none; }
    }
    </style>
    """, unsafe_allow_html=True)
    st.session_state.app_faded = True


if st.session_state.get("dark_mode"):
    st.markdown("""
    <style>
    .stApp { background-color:#1E1E1E !important; color:#E0E0E0 !important; }
    .card, .chart-card, .stat-card, .feature-card, .scene-card,
    .clean-report, .summary-card, .upload-area, .placeholder-card,
    .about-card, section[data-testid="stSidebar"] {
        background-color:#2D2D2D !important;
        color:#E0E0E0 !important;
        border-color:#444444 !important;
    }
    .stat-card .value, .card-title, .chart-card .card-title,
    .feature-title, .scene-title, .section-title-inner, .page-title {
        color:#E0E0E0 !important;
    }
    .stat-card .label, .feature-desc, .scene-desc, .step-desc,
    .hero-desc, .page-breadcrumb {
        color:#B0B0B0 !important;
    }
    .stDataFrame thead tr th { background:#333333 !important; color:#E0E0E0 !important; }
    .stButton > button, .stButton button[kind="secondary"] {
        background-color:#3A3A3A !important;
        color:#E0E0E0 !important;
        border-color:#555555 !important;
    }
    </style>
    """, unsafe_allow_html=True)


render_mobile_hint()
render_nav()

page = st.session_state.page

if page == "home":
    render_home()
elif page == "salary":
    render_analysis_page("salary")
elif page == "recruit":
    render_recruit_page()
elif page == "report":
    render_report_page()

render_footer()
