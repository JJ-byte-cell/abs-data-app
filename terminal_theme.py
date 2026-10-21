"""Visual-only financial terminal theme for Streamlit; no data or calculation changes."""
import streamlit as st

CSS = r'''
<style>
:root {color-scheme: dark;}
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], .stApp {
 background: #090f1a !important; color: #e2e8f0 !important;
}
[data-testid="stHeader"] {background: rgba(9,15,26,.92) !important; border-bottom: 1px solid #233247;}
[data-testid="stSidebar"], [data-testid="stSidebarContent"] {background: #101a2a !important; border-right: 1px solid #26364a;}
[data-testid="stSidebar"] * {color: #cbd5e1;}
.block-container {max-width: 1580px !important; padding-top: 1.25rem !important; padding-bottom: 3rem !important;}
h1,h2,h3,h4,h5,h6 {color:#f1f5f9 !important; letter-spacing: -.025em;}
h1 {font-weight: 720 !important; border-bottom: 1px solid #26364a; padding-bottom: .65rem;}
h2,h3 {font-weight: 650 !important;}
p,li,label,span {letter-spacing: .002em;}
[data-testid="stCaptionContainer"], .stCaption {color: #8da2ba !important;}
[data-testid="stMetric"] {background: #142235 !important; border: 1px solid #2b4059 !important; border-radius: 7px !important; padding: 14px 16px !important; box-shadow: none !important;}
[data-testid="stMetricLabel"] {color: #9eb3c9 !important; font-weight: 600 !important;}
[data-testid="stMetricValue"] {color: #f8fafc !important; font-variant-numeric: tabular-nums;}
[data-testid="stMetricDelta"] {font-variant-numeric: tabular-nums;}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] {border-color: #2b4059 !important; border-radius: 7px !important;}
[data-testid="stExpander"] {background: #111d2e !important;}
[data-testid="stSelectbox"] > div > div, [data-testid="stMultiSelect"] > div > div,
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea,
[data-baseweb="select"] > div, [data-baseweb="input"] > div {
 background: #162438 !important; color: #e2e8f0 !important; border-color: #34475f !important; border-radius: 6px !important;
}
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {background: #17263a !important; color: #e2e8f0 !important;}
[data-baseweb="menu"] li {color:#e2e8f0 !important;}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
 background: #1b3048 !important; color: #dcecff !important; border: 1px solid #395b7e !important; border-radius: 6px !important; font-weight: 600 !important;
}
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {background: #234564 !important; border-color:#53a6e8 !important;}
[data-testid="stButton"] button[kind="primary"] {background:#1268a3 !important; color:white !important; border-color:#278dcf !important;}
[data-testid="stTabs"] [data-baseweb="tab-list"] {background:#101b2b; border-bottom:1px solid #34475f; gap:.3rem;}
[data-testid="stTabs"] [data-baseweb="tab"] {color:#a5b9cf; font-weight:600;}
[data-testid="stTabs"] [aria-selected="true"] {color:#63c5ff !important; border-bottom-color:#45a9e7 !important;}
[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"] {border:1px solid #26384d; border-radius:7px; overflow:hidden;}
[data-testid="stAlert"] {background:#15263a !important; border:1px solid #375572 !important; border-radius:6px !important; color:#e2e8f0 !important;}
hr {border-color:#29394e !important;}
[data-testid="stFileUploader"] section {background:#142235 !important; border-color:#3a516b !important;}
[data-testid="stProgressBar"] > div {background:#1b314a;}
a {color:#66bfff !important;}
code {background:#1c2d43 !important; color:#f8c572 !important;}
</style>
'''

def install():
    st.markdown(CSS, unsafe_allow_html=True)

# ============================================
# FINANCIAL TERMINAL - DROPDOWN CONTRAST FIX
# ============================================

import streamlit as st


def apply_dropdown_contrast():
    import streamlit as st

    st.markdown("""
    <style>
    /* Main dropdown field */
    div[data-baseweb="select"] > div {
        background: #102035 !important;
        border: 1px solid #3B638A !important;
    }

    /* Selected value */
    div[data-baseweb="select"] [data-testid="stMarkdownContainer"],
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
    }

    /* Dropdown popup container */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div {
        background-color: #0D1B2A !important;
        color: #F8FAFC !important;
    }

    /* Popup menu */
    div[data-baseweb="menu"],
    ul[role="listbox"] {
        background-color: #0D1B2A !important;
        color: #F8FAFC !important;
    }

    /* Dropdown items */
    div[data-baseweb="menu"] li,
    ul[role="listbox"] li,
    li[role="option"] {
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        background-color: #0D1B2A !important;
    }

    /* Nested option labels */
    div[data-baseweb="menu"] li *,
    ul[role="listbox"] li *,
    li[role="option"] * {
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
    }

    /* Hover and keyboard focus */
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #075BC4 !important;
    }

    /* Filter labels */
    div[data-testid="stWidgetLabel"] * {
        color: #CBD5E1 !important;
    }
    </style>
    """, unsafe_allow_html=True)
