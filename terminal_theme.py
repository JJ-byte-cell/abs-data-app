
"""Unified financial-terminal theme for Streamlit."""

import streamlit as st


CSS = """
<style>

/* =========================================
   1. GLOBAL COLOURS
========================================= */

:root {
    color-scheme: dark;
    --terminal-bg: #090F1A;
    --terminal-panel: #142235;
    --terminal-input: #162438;
    --terminal-border: #34475F;
    --terminal-text: #F1F5F9;
    --terminal-muted: #A5B9CF;
    --terminal-blue: #53B8FF;
}

html,
body,
.stApp,
[data-testid="stAppViewContainer"] {
    background-color: #090F1A !important;
    color: #F1F5F9 !important;
}

[data-testid="stHeader"] {
    background-color: #090F1A !important;
}

[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {
    background-color: #101A2A !important;
    border-color: #26364A !important;
}

.block-container {
    max-width: 1580px !important;
    padding-top: 1.25rem !important;
}

/* =========================================
   2. TEXT
========================================= */

h1, h2, h3, h4, h5, h6 {
    color: #F1F5F9 !important;
}

[data-testid="stWidgetLabel"] *,
[data-testid="stMarkdownContainer"] p {
    color: #CBD5E1;
}

[data-testid="stCaptionContainer"] {
    color: #94A3B8 !important;
}

/* =========================================
   3. SELECTBOXES AND MULTISELECTS
========================================= */

div[data-baseweb="select"],
div[data-baseweb="select"] > div,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background: #162438 !important;
    background-color: #162438 !important;
    border-color: #34475F !important;
    color: #F1F5F9 !important;
}

div[data-baseweb="select"] input,
div[data-baseweb="select"] span,
div[data-baseweb="select"] svg,
div[data-baseweb="select"] [role="button"] {
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
}

/* Dropdown menus */

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"],
[role="listbox"] {
    background: #101D2E !important;
    background-color: #101D2E !important;
    color: #F1F5F9 !important;
}

[role="option"],
[role="option"] *,
[data-baseweb="menu"] li,
[data-baseweb="menu"] li * {
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
}

[role="option"]:hover,
[role="option"][aria-selected="true"] {
    background-color: #075BC4 !important;
}

/* =========================================
   4. NUMBER INPUTS
========================================= */

[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"] > div,
[data-testid="stNumberInput"] input {
    background-color: #162438 !important;
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
    border-color: #34475F !important;
}

[data-testid="stNumberInput"] button {
    background-color: #1B3048 !important;
    color: #F1F5F9 !important;
    border-color: #34475F !important;
}

[data-testid="stNumberInput"] button svg {
    color: #F1F5F9 !important;
    stroke: #F1F5F9 !important;
}

/* =========================================
   5. TEXT AND DATE INPUTS
========================================= */

[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {
    background-color: #162438 !important;
    color: #F1F5F9 !important;
    -webkit-text-fill-color: #F1F5F9 !important;
    border-color: #34475F !important;
}

/* =========================================
   6. BUTTONS
========================================= */

[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button,
[data-testid="stFormSubmitButton"] button {
    background-color: #1B3048 !important;
    color: #F1F5F9 !important;
    border: 1px solid #395B7E !important;
    border-radius: 6px !important;
}

[data-testid="stButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {
    background-color: #234564 !important;
    border-color: #53B8FF !important;
}

/* =========================================
   7. RADIO AND SEGMENTED CONTROLS
========================================= */

[data-testid="stRadio"] [role="radiogroup"] {
    background-color: #162438 !important;
    border-radius: 6px !important;
}

[data-testid="stSegmentedControl"] button {
    background-color: #162438 !important;
    color: #F1F5F9 !important;
    border-color: #34475F !important;
}

[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
    background-color: #075BC4 !important;
    color: #FFFFFF !important;
}

/* =========================================
   8. METRIC CARDS
========================================= */

[data-testid="stMetric"] {
    background-color: #142235 !important;
    border: 1px solid #2B4059 !important;
    border-radius: 7px !important;
    padding: 14px 16px !important;
}

[data-testid="stMetricLabel"] {
    color: #9EB3C9 !important;
}

[data-testid="stMetricValue"] {
    color: #F8FAFC !important;
}

/* =========================================
   9. TABLES
========================================= */

[data-testid="stTable"],
[data-testid="stTable"] table,
[data-testid="stTable"] thead,
[data-testid="stTable"] tbody,
[data-testid="stTable"] tr,
[data-testid="stTable"] th,
[data-testid="stTable"] td {
    background-color: #142235 !important;
    color: #E2E8F0 !important;
    border-color: #2B4059 !important;
}

[data-testid="stTable"] th {
    background-color: #1B3048 !important;
    color: #F1F5F9 !important;
}

[data-testid="stDataFrame"] {
    background-color: #142235 !important;
    border: 1px solid #2B4059 !important;
    border-radius: 7px !important;
}

/* =========================================
   10. TABS
========================================= */

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background-color: #101B2B !important;
    border-bottom: 1px solid #34475F !important;
}

[data-testid="stTabs"] [data-baseweb="tab"] {
    background-color: #162438 !important;
    color: #CBD5E1 !important;
}

[data-testid="stTabs"] [aria-selected="true"] {
    background-color: #1B3048 !important;
    color: #63C5FF !important;
}

/* =========================================
   11. EXPANDERS AND CONTAINERS
========================================= */

[data-testid="stExpander"],
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #111D2E !important;
    border-color: #2B4059 !important;
    border-radius: 7px !important;
}

/* =========================================
   12. ALERTS
========================================= */

[data-testid="stAlert"] {
    background-color: #15263A !important;
    border: 1px solid #375572 !important;
    color: #E2E8F0 !important;
}

[data-testid="stAlert"] p {
    color: #DCEBFA !important;
}

/* =========================================
   13. FILE UPLOADS
========================================= */

[data-testid="stFileUploader"] section {
    background-color: #142235 !important;
    border-color: #3A516B !important;
}

/* =========================================
   14. CHART AND TABLE CONTAINERS
========================================= */

[data-testid="stPlotlyChart"],
[data-testid="stDataFrame"] {
    border: 1px solid #26384D !important;
    border-radius: 7px !important;
    overflow: hidden;
}

/* =========================================
   15. LINKS AND CODE
========================================= */

a {
    color: #66BFFF !important;
}

code {
    background-color: #1C2D43 !important;
    color: #F8C572 !important;
}

hr {
    border-color: #29394E !important;
}

</style>
"""


def install():
    """Apply the financial terminal theme."""
    st.markdown(CSS, unsafe_allow_html=True)


# Compatibility with existing app.py imports.
# All styling is now consolidated in install().

def apply_dropdown_contrast():
    pass


def apply_dark_ui():
    pass


def fix_light_controls():
    pass
