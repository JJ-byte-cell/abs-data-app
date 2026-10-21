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

# ============================================
# FINANCIAL TERMINAL - DARK UI CONSISTENCY
# ============================================

def apply_dark_ui():
    st.markdown("""
    <style>

    /* General dashboard backgrounds */
    .stApp,
    [data-testid="stAppViewContainer"] {
        background-color: #090F1A !important;
        color: #E2E8F0 !important;
    }

    /* Input fields */
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"],
    [data-baseweb="textarea"] > div,
    [data-baseweb="select"] > div {
        background-color: #162438 !important;
        border-color: #34475F !important;
        color: #F1F5F9 !important;
    }

    /* Input text */
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {
        background-color: transparent !important;
        color: #F1F5F9 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    /* Dropdown popup and options */
    [data-baseweb="popover"],
    [data-baseweb="popover"] [data-baseweb="menu"],
    [role="listbox"],
    [role="listbox"] [role="option"] {
        background-color: #101D2E !important;
        color: #F1F5F9 !important;
    }

    [role="listbox"] [role="option"] *,
    [data-baseweb="menu"] [role="option"] * {
        color: #F1F5F9 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    [role="option"]:hover,
    [role="option"][aria-selected="true"] {
        background-color: #075BC4 !important;
    }

    /* Buttons */
    .stButton button,
    .stDownloadButton button,
    .stFormSubmitButton button {
        background-color: #1B3048 !important;
        border: 1px solid #395B7E !important;
        color: #F1F5F9 !important;
    }

    /* File upload areas */
    [data-testid="stFileUploader"] section,
    [data-testid="stFileUploaderDropzone"] {
        background-color: #142235 !important;
        border-color: #3A516B !important;
    }

    /* Expanders and bordered containers */
    [data-testid="stExpander"],
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #111D2E !important;
        border-color: #2B4059 !important;
    }

    /* Tables */
    [data-testid="stTable"] table,
    [data-testid="stTable"] th,
    [data-testid="stTable"] td {
        background-color: #111D2E !important;
        color: #E2E8F0 !important;
        border-color: #2B4059 !important;
    }

    /* Dataframe containers */
    [data-testid="stDataFrame"] {
        background-color: #111D2E !important;
        border-color: #2B4059 !important;
    }

    /* Tabs */
    [data-baseweb="tab-list"] {
        background-color: #101B2B !important;
    }

    /* Popovers, tooltips and menus */
    [data-baseweb="tooltip"],
    [data-baseweb="popover"] > div {
        background-color: #142235 !important;
        color: #F1F5F9 !important;
    }

    /* Alerts */
    [data-testid="stAlert"] {
        background-color: #15263A !important;
        border-color: #375572 !important;
        color: #E2E8F0 !important;
    }

    </style>
    """, unsafe_allow_html=True)
  
# ============================================
# FINANCIAL TERMINAL - LIGHT CONTROL FIX
# ============================================

def fix_light_controls():
    import streamlit as st

    st.markdown("""
    <style>
    /* Colour palette
       Main background: #090F1A
       Control background: #162438
       Popup background: #101D2E
       Border: #34475F
       Text: #F1F5F9
    */

    /* All select boxes and multiselects */
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    [data-testid="stSelectbox"] [data-baseweb="select"],
    [data-testid="stMultiSelect"] [data-baseweb="select"] {
        background-color: #162438 !important;
        border-color: #34475F !important;
        color: #F1F5F9 !important;
    }

    /* Text inside select boxes */
    [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stMultiSelect"] [data-baseweb="select"] * {
        color: #F1F5F9 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    /* Number input outer container */
    [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stNumberInput"] [data-baseweb="input"] > div {
        background-color: #162438 !important;
        border-color: #34475F !important;
    }

    /* Number input text */
    [data-testid="stNumberInput"] input {
        background-color: #162438 !important;
        color: #F1F5F9 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    /* Plus and minus buttons */
    [data-testid="stNumberInput"] button,
    [data-testid="stNumberInput"] [data-baseweb="button"] {
        background-color: #1B3048 !important;
        color: #F1F5F9 !important;
        border-color: #34475F !important;
    }

    /* Icons inside number buttons */
    [data-testid="stNumberInput"] button svg {
        color: #F1F5F9 !important;
        fill: none !important;
        stroke: #F1F5F9 !important;
    }

    /* Radio button group containers */
    [data-testid="stRadio"] [role="radiogroup"] {
        background-color: #162438 !important;
        border-radius: 6px !important;
    }

    /* Segmented control outer container */
    [data-testid="stSegmentedControl"] [data-baseweb="button-group"],
    [data-testid="stSegmentedControl"] > div {
        background-color: #162438 !important;
        color: #F1F5F9 !important;
    }

    /* Segmented control buttons */
    [data-testid="stSegmentedControl"] button {
        background-color: #162438 !important;
        color: #F1F5F9 !important;
        border: 1px solid #34475F !important;
    }

    /* Active segmented option */
    [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
        background-color: #075BC4 !important;
        color: #FFFFFF !important;
    }

    /* Dropdown popups */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [role="listbox"] {
        background-color: #101D2E !important;
        color: #F1F5F9 !important;
    }

    /* Dropdown menu option text */
    [role="option"],
    [role="option"] *,
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] li * {
        color: #F1F5F9 !important;
        -webkit-text-fill-color: #F1F5F9 !important;
    }

    /* Selected dropdown option */
    [role="option"][aria-selected="true"] {
        background-color: #075BC4 !important;
    }

    /* Tabs */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        background-color: #101B2B !important;
    }

    [data-testid="stTabs"] [data-baseweb="tab"] {
        background-color: #162438 !important;
        color: #CBD5E1 !important;
    }

    [data-testid="stTabs"] [aria-selected="true"] {
        background-color: #1B3048 !important;
        color: #63C5FF !important;
    }

    /* General buttons */
    [data-testid="stButton"] button,
    [data-testid="stDownloadButton"] button {
        background-color: #1B3048 !important;
        color: #F1F5F9 !important;
        border-color: #395B7E !important;
    }

    /* Prevent white hover backgrounds */
    [data-testid="stButton"] button:hover,
    [data-testid="stNumberInput"] button:hover,
    [data-testid="stSegmentedControl"] button:hover {
        background-color: #234564 !important;
        color: #FFFFFF !important;
    }

    </style>
    """, unsafe_allow_html=True)

