"""Financial-terminal visual theme. Does not modify ABS data or calculations."""
import streamlit as st

CSS = """
<style>
:root {color-scheme:dark;}
.stApp,[data-testid="stAppViewContainer"]{background:#090f1a!important;color:#e2e8f0!important;}
[data-testid="stHeader"]{background:#090f1a!important;}
[data-testid="stSidebar"],[data-testid="stSidebarContent"]{background:#101a2a!important;border-color:#26364a!important;}
.block-container{max-width:1580px!important;padding-top:1.25rem!important;}
h1,h2,h3,h4,h5,h6{color:#f1f5f9!important;letter-spacing:-.02em;}
[data-testid="stCaptionContainer"]{color:#9eb3c9!important;}
[data-testid="stWidgetLabel"] label,[data-testid="stWidgetLabel"] p{color:#cbd5e1!important;}
/* Force BaseWeb select background AND its internal input and display layers. */
[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"]>div,
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"]>div,
[data-baseweb="select"] [data-baseweb="input"],
[data-baseweb="select"] [data-baseweb="input"]>div{
 background:#162438!important;background-color:#162438!important;
 border-color:#34475f!important;color:#f1f5f9!important;}
[data-baseweb="select"] input,[data-baseweb="select"] span,
[data-baseweb="select"] svg,[data-baseweb="select"] [role="button"]{
 color:#f1f5f9!important;-webkit-text-fill-color:#f1f5f9!important;}
[data-baseweb="select"] input::placeholder{color:#9eb3c9!important;-webkit-text-fill-color:#9eb3c9!important;}
/* Portaled menus: target both menu options and nested content. */
[data-baseweb="popover"],[data-baseweb="popover"]>div,
[data-baseweb="menu"],[role="listbox"]{background:#101d2e!important;color:#f1f5f9!important;}
[role="option"],[role="option"] *,[data-baseweb="menu"] li,[data-baseweb="menu"] li *{
 color:#f1f5f9!important;-webkit-text-fill-color:#f1f5f9!important;}
[role="option"]:hover,[role="option"][aria-selected="true"]{background:#234564!important;}
/* Number/text/date widgets */
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"]>div,
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stTextArea"] textarea{
 background:#162438!important;border-color:#34475f!important;color:#f1f5f9!important;}
[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,[data-testid="stTextArea"] textarea{
 background:#162438!important;color:#f1f5f9!important;-webkit-text-fill-color:#f1f5f9!important;}
[data-testid="stNumberInput"] button{background:#1b3048!important;color:#f1f5f9!important;border-color:#34475f!important;}
[data-testid="stNumberInput"] button svg{color:#f1f5f9!important;stroke:#f1f5f9!important;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,
[data-testid="stFormSubmitButton"] button{background:#1b3048!important;color:#f1f5f9!important;border:1px solid #395b7e!important;border-radius:6px!important;}
[data-testid="stButton"] button:hover,[data-testid="stDownloadButton"] button:hover{background:#234564!important;}
[data-testid="stMetric"]{background:#142235!important;border:1px solid #2b4059!important;border-radius:7px!important;padding:14px 16px!important;}
[data-testid="stMetricLabel"]{color:#9eb3c9!important;}
[data-testid="stMetricValue"]{color:#f8fafc!important;}
[data-testid="stExpander"]{background:#111d2e!important;border-color:#2b4059!important;}
[data-testid="stAlert"]{background:#15263a!important;border:1px solid #375572!important;color:#e2e8f0!important;}
[data-testid="stAlert"] p{color:#dceafa!important;}
[data-testid="stFileUploader"] section{background:#142235!important;border-color:#3a516b!important;}
[data-testid="stTabs"] [data-baseweb="tab-list"]{background:#101b2b!important;border-color:#34475f!important;}
[data-testid="stTabs"] [data-baseweb="tab"]{color:#cbd5e1!important;}
[data-testid="stTabs"] [aria-selected="true"]{color:#63c5ff!important;}
[data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid #26384d!important;border-radius:7px!important;overflow:hidden;}
/* HTML table used for the overview and other short tables. */
.terminal-table-scroll{width:100%;overflow-x:auto;border:1px solid #34475f;border-radius:7px;background:#111d2e;}
.terminal-table{width:100%;border-collapse:collapse;font-size:.88rem;font-variant-numeric:tabular-nums;}
.terminal-table th{position:sticky;top:0;text-align:left;background:#1b3048;color:#dcecff;padding:11px 13px;border-bottom:1px solid #395b7e;white-space:nowrap;}
.terminal-table td{padding:10px 13px;color:#e2e8f0;background:#111d2e;border-bottom:1px solid #26384d;}
.terminal-table tbody tr:nth-child(even) td{background:#142235;}
.terminal-table tbody tr:hover td{background:#234564;}
a{color:#66bfff!important;} code{background:#1c2d43!important;color:#f8c572!important;}
hr{border-color:#29394e!important;}
</style>
"""

def install():
    st.markdown(CSS, unsafe_allow_html=True)

# Backward compatibility for other modules importing the old helpers.
def apply_dropdown_contrast():
    pass

def apply_dark_ui():
    pass

def fix_light_controls():
    pass
