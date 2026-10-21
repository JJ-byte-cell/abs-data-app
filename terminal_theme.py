"""Visual-only financial terminal theme for Streamlit; no data or calculation changes."""
import streamlit as st

CSS = r'''
<style>
:root { color-scheme: dark; }
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], .stApp {
  background: #090f1a !important; color: #e2e8f0 !important;
}
[data-testid="stHeader"] { background: rgba(9,15,26,.92) !important; border-bottom: 1px solid #233247; }
[data-testid="stSidebar"], [data-testid="stSidebarContent"] { background: #101a2a !important; border-right: 1px solid #26364a; }
[data-testid="stSidebar"] * { color: #cbd5e1; }
.block-container { max-width: 1580px !important; padding-top: 1.25rem !important; padding-bottom: 3rem !important; }
h1,h2,h3,h4,h5,h6 { color:#f1f5f9 !important; letter-spacing: -.025em; }
h1 { font-weight: 720 !important; border-bottom: 1px solid #26364a; padding-bottom: .65rem; }
h2,h3 { font-weight: 650 !important; }
p,li,label,span { letter-spacing: .002em; }
[data-testid="stCaptionContainer"], .stCaption { color: #8da2ba !important; }
[data-testid="stMetric"] { background: #142235 !important; border: 1px solid #2b4059 !important; border-radius: 7px !important; padding: 14px 16px !important; box-shadow: none !important; }
[data-testid="stMetricLabel"] { color: #9eb3c9 !important; font-weight: 600 !important; }
[data-testid="stMetricValue"] { color: #f8fafc !important; font-variant-numeric: tabular-nums; }
[data-testid="stMetricDelta"] { font-variant-numeric: tabular-nums; }
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] { border-color: #2b4059 !important; border-radius: 7px !important; }
[data-testid="stExpander"] { background: #111d2e !important; }
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea,
[data-baseweb="input"] > div {
  background: #162438 !important; color: #e2e8f0 !important;
  border-color: #34475f !important; border-radius: 6px !important;
}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
  background: #1b3048 !important; color: #dcecff !important;
  border: 1px solid #395b7e !important; border-radius: 6px !important; font-weight: 600 !important;
}
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover { background: #234564 !important; border-color:#53a6e8 !important; }
[data-testid="stButton"] button[kind="primary"] { background:#1268a3 !important; color:white !important; border-color:#278dcf !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { background:#101b2b; border-bottom:1px solid #34475f; gap:.3rem; }
[data-testid="stTabs"] [data-baseweb="tab"] { color:#a5b9cf; font-weight:600; }
[data-testid="stTabs"] [aria-selected="true"] { color:#63c5ff !important; border-bottom-color:#45a9e7 !important; }
[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"] { border:1px solid #26384d; border-radius:7px; overflow:hidden; }
[data-testid="stAlert"] { background:#15263a !important; border:1px solid #375572 !important; border-radius:6px !important; color:#e2e8f0 !important; }
hr { border-color:#29394e !important; }
[data-testid="stFileUploader"] section { background:#142235 !important; border-color:#3a516b !important; }
[data-testid="stProgressBar"] > div { background:#1b314a; }
a { color:#66bfff !important; }
code { background:#1c2d43 !important; color:#f8c572 !important; }
</style>
'''

DROPDOWN_CSS = r'''
<style>
/* Keep dropdown fields and text readable even when the app has a dark theme. */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-baseweb="select"] > div {
  background-color: #102035 !important;
  border-color: #3b638a !important;
  color: #f8fafc !important;
}
[data-baseweb="select"] input,
[data-baseweb="select"] span,
[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] [data-testid="stMarkdownContainer"] * {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
}
[data-baseweb="select"] svg { fill: #f8fafc !important; color: #f8fafc !important; }
[data-baseweb="select"]:focus-within > div {
  border-color: #2196f3 !important;
  box-shadow: 0 0 0 1px #2196f3 !important;
}
/* BaseWeb often portals the menu outside Streamlit's normal widget subtree. */
[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[data-baseweb="menu"] > div,
[role="listbox"] {
  background: #0d1b2a !important;
  color: #f8fafc !important;
  border-color: #3b638a !important;
}
/* Some Streamlit versions render menu items as divs, not li elements. */
[data-baseweb="menu"] [role="option"],
[data-baseweb="menu"] li,
[role="listbox"] [role="option"],
[role="listbox"] li,
li[role="option"] {
  background: #0d1b2a !important;
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
}
/* Target all descendants, including Streamlit's nested markdown labels. */
[data-baseweb="menu"] [role="option"] *,
[data-baseweb="menu"] li *,
[role="listbox"] [role="option"] *,
[role="listbox"] li *,
li[role="option"] * {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
}
[data-baseweb="menu"] [role="option"]:hover,
[data-baseweb="menu"] li:hover,
[role="listbox"] [role="option"]:hover,
[role="listbox"] li:hover,
[data-baseweb="menu"] [role="option"][aria-selected="true"],
[role="listbox"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] [role="option"][data-highlighted],
[role="listbox"] [role="option"][data-highlighted] {
  background: #075bc4 !important;
}
[data-baseweb="menu"] [role="option"]:hover *,
[role="listbox"] [role="option"]:hover *,
[data-baseweb="menu"] [role="option"][aria-selected="true"] *,
[role="listbox"] [role="option"][aria-selected="true"] * {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}
[data-testid="stWidgetLabel"] *,
[data-testid="stSelectbox"] label *,
[data-testid="stMultiSelect"] label * {
  color: #cbd5e1 !important;
  -webkit-text-fill-color: #cbd5e1 !important;
}
</style>
'''

def install():
    """Install the terminal appearance and dropdown contrast together."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(DROPDOWN_CSS, unsafe_allow_html=True)


def apply_dropdown_contrast():
    """Backward-compatible helper for existing app.py imports."""
    st.markdown(DROPDOWN_CSS, unsafe_allow_html=True)
