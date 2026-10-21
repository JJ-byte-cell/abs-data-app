
import io
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Australian Macro Tracker",
    page_icon="📊",
    layout="wide",
)

from terminal_tooltips import install as install_terminal_tooltips
install_terminal_tooltips()


from terminal_theme import install as install_terminal_theme
install_terminal_theme()

# Default all Plotly Express charts to the financial-terminal palette.
px.defaults.template = "plotly_dark"

def terminal_table(data, *, max_html_rows=250, height=None):
    """Dark, accessible HTML for small tables; native grid for large data."""
    from html import escape
    if len(data) > max_html_rows:
        st.dataframe(data, hide_index=True, use_container_width=True, height=height)
        return
    shown = data.copy()
    for col in shown.columns:
        if pd.api.types.is_datetime64_any_dtype(shown[col]):
            shown[col] = pd.to_datetime(shown[col], errors="coerce").dt.strftime("%d %b %Y")
        elif pd.api.types.is_numeric_dtype(shown[col]):
            shown[col] = shown[col].map(lambda v: f"{v:,.3f}" if pd.notna(v) else "—")
    headers = "".join(f"<th scope='col'>{escape(str(c))}</th>" for c in shown.columns)
    rows = []
    for record in shown.itertuples(index=False, name=None):
        cells = "".join(f"<td>{escape(str(v)) if pd.notna(v) else '—'}</td>" for v in record)
        rows.append(f"<tr>{cells}</tr>")
    markup = ("<div class='terminal-table-scroll'><table class='terminal-table'>"
              f"<thead><tr>{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    st.markdown(markup, unsafe_allow_html=True)


def apply_terminal_plotly(fig):
    """Style Plotly charts consistently without altering plotted data."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#111d2e", plot_bgcolor="#111d2e",
        font=dict(color="#e2e8f0"),
        title_font=dict(color="#f1f5f9"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#162438", bordercolor="#3b638a", font_color="#f8fafc"),
    )
    fig.update_xaxes(gridcolor="#29394e", zerolinecolor="#34475f")
    fig.update_yaxes(gridcolor="#29394e", zerolinecolor="#34475f")
    return fig

# Apply styling to every chart without changing individual chart calculations.
_original_plotly_chart = st.plotly_chart

def _terminal_plotly_chart(fig, *args, **kwargs):
    return _original_plotly_chart(apply_terminal_plotly(fig), *args, **kwargs)

st.plotly_chart = _terminal_plotly_chart

st.title("🇦🇺 Australian Macroeconomic Tracker")
st.caption("Interactive economic dashboard powered by ABS data")

BASE_URL = "https://data.api.abs.gov.au/rest"

HEADERS = {
    "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
    "User-Agent": "AustralianMacroTracker/1.0",
}

DATASETS = {
    "Consumer Price Index (CPI)": {
        "flow": "ABS,CPI,all",
        "category": "Inflation",
    },
    "Residential Property Price Indexes": {
        "flow": "ABS,RES_PROP_INDEX,all",
        "category": "Housing",
    },
    "Unemployment & Labour Market": {"flow": "ABS,LF,all", "category": "Labour Market"},
    "Labour Turnover": {
        "flow": "ABS,LABOUR_TURNOVER,all",
        "category": "Labour Market",
    },
}


# =========================================================
# 2. API CONNECTION
# =========================================================

def create_session():
    session = requests.Session()

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )

    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


# Resolve ABS dimension positions and codes from the live SDMX structure.
# Do not assume the order of CPI dimensions or hardcode codes across releases.
def _local(tag):
    return tag.rsplit("}", 1)[-1]


@st.cache_data(ttl=86400, show_spinner=False)
def get_cpi_structure():
    url = f"{BASE_URL}/dataflow/ABS/CPI"
    response = create_session().get(
        url, params={"references": "all"},
        headers={"Accept": "application/vnd.sdmx.structure+xml;version=2.1"},
        timeout=(10, 35),
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    codelists = {}
    for el in root.iter():
        if _local(el.tag) != "Codelist":
            continue
        codes = {}
        for code in el:
            if _local(code.tag) != "Code":
                continue
            labels = [n.text.strip() for n in code.iter()
                      if _local(n.tag) == "Name" and n.text]
            if labels:
                codes[code.get("id")] = labels[0]
        codelists[el.get("id")] = codes

    candidates = []
    for node in root.iter():
        if _local(node.tag) != "DataStructure":
            continue
        dimensions = []
        for dim in node.iter():
            if _local(dim.tag) not in ("Dimension", "TimeDimension"):
                continue
            if _local(dim.tag) == "TimeDimension":
                continue
            enumerations = [e for e in dim.iter() if _local(e.tag) == "Enumeration"]
            refs = [e for enum in enumerations for e in enum.iter()
                    if _local(e.tag) == "Ref" and e.get("id")]
            cl = refs[0].get("id") if refs else None
            dimensions.append((int(dim.get("position", len(dimensions) + 1)),
                               dim.get("id", ""), cl))
        if dimensions:
            candidates.append(sorted(dimensions))
    if not candidates:
        raise ValueError("ABS CPI data structure dimensions were not found")
    dims = max(candidates, key=len)
    return dims, codelists


def _choose_codes(codes, patterns, multiple=False):
    matched = [code for code, label in codes.items()
               if any(re.search(p, label, re.I) for p in patterns)]
    return matched if multiple else matched[:1]


def build_cpi_key(frequency="Auto"):
    dims, codelists = get_cpi_structure()
    parts = []
    decisions = []
    essential = {"MEASURE", "INDEX", "REGION", "FREQ"}
    found = set()
    for _, name, cl in dims:
        upper = name.upper()
        codes = codelists.get(cl, {})
        if "MEASURE" in upper:
            patterns = [r"^Index numbers?$", r"^Index number"]
            field = "MEASURE"
        elif upper == "INDEX" or "EXPENDITURE" in upper:
            patterns = [r"^All groups CPI$", r"^All groups$", r"^Food and non-alcoholic beverages$",
                        r"^Alcohol and tobacco$", r"^Clothing and footwear$", r"^Housing$",
                        r"^Furnishings, household equipment and services$", r"^Health$",
                        r"^Transport$", r"^Communication$", r"^Recreation and culture$",
                        r"^Education$", r"^Insurance and financial services$"]
            field = "INDEX"
        elif "REGION" in upper:
            patterns = [r"^Australia$"]
            field = "REGION"
        elif upper == "FREQ" or "FREQUENCY" in upper:
            patterns = ([r"^Quarterly$"] if frequency == "Quarterly" else
                        [r"^Monthly$"] if frequency == "Monthly" else
                        [r"^Monthly$", r"^Quarterly$"])
            field = "FREQ"
        elif "TSEST" in upper or "ADJUST" in upper:
            patterns = [r"^Original$"]
            field = "TSEST"
        else:
            parts.append("")
            continue
        found.add(field)
        matches = _choose_codes(codes, patterns, multiple=(field == "INDEX" or (field == "FREQ" and frequency == "Auto")))
        if not matches:
            raise ValueError(f"No matching {name} codes in CPI metadata (codelist: {cl}).")
        # Request BOTH monthly and quarterly series; choose one for display later.
        # A monthly-only request cannot supply the long quarterly CPI history.
        parts.append("+".join(matches))
        decisions.append(f"{name}: {', '.join(matches)}")
    missing = essential - found
    if missing:
        raise ValueError(f"CPI metadata is missing expected dimensions: {', '.join(sorted(missing))}")
    return ".".join(parts), decisions


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_targeted_cpi(start_year, end_year, frequency="Auto"):
    key, decisions = build_cpi_key(frequency)
    # ABS accepts SDMX positional keys in the data endpoint.
    url = f"{BASE_URL}/data/ABS,CPI,all/{key}"
    params = {"startPeriod": str(start_year), "endPeriod": str(end_year),
              "dimensionAtObservation": "AllDimensions", "format": "csv"}
    response = create_session().get(url, params=params, headers=HEADERS,
                                    timeout=(10, 60))
    if not response.ok:
        raise ValueError(f"Targeted ABS CPI query returned HTTP {response.status_code}: {response.text[:400]}")
    if not response.content or response.text.lstrip().startswith("<"):
        raise ValueError("Targeted CPI response was empty or not CSV")
    data = pd.read_csv(io.BytesIO(response.content), dtype=str, low_memory=False)
    if data.empty:
        raise ValueError("Targeted CPI query returned no observations")
    data.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in data.columns]
    return data, response.url, decisions


@st.cache_data(ttl=3600, show_spinner=False)

def fetch_abs_data(flow, start_year, end_year):
    url = f"{BASE_URL}/data/{flow}/all"

    params = {
        "startPeriod": str(start_year),
        "endPeriod": str(end_year),
        "dimensionAtObservation": "AllDimensions",
        "format": "csv",
    }

    response = create_session().get(
        url,
        params=params,
        headers=HEADERS,
        timeout=(10, 60),
    )

    if not response.ok:
        raise ValueError(
            f"ABS API returned HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    if not response.text.strip():
        raise ValueError("The ABS API returned an empty response.")

    if response.text.lstrip().startswith("<"):
        raise ValueError(
            "The API returned XML/HTML instead of CSV. "
            "Check the dataflow identifier and API response."
        )

    df = pd.read_csv(
        io.StringIO(response.text),
        dtype=str,
        low_memory=False,
    )

    if df.empty:
        raise ValueError("No observations were returned.")

    df.columns = [
        re.sub(r"\s+", " ", str(col)).strip()
        for col in df.columns
    ]

    return df, response.url



# =========================================================
# 3. DATA CLEANING FUNCTIONS
# =========================================================

def find_column(df, candidates):
    """Find SDMX columns by code or descriptive label."""

    for candidate in candidates:
        for col in df.columns:
            if col.upper() == candidate.upper():
                return col

    for candidate in candidates:
        for col in df.columns:
            if col.upper().startswith(candidate.upper() + ":"):
                return col

    return None


def clean_label(series):
    """Remove SDMX dimension codes from display labels."""

    return (
        series.astype("string")
        .str.replace(r"^[^:]+:\s*", "", regex=True)
        .str.strip()
    )


def parse_period(value):
    """Parse common ABS annual, quarterly, monthly and daily periods."""

    if pd.isna(value):
        return pd.NaT

    value = str(value).strip()

    try:
        if re.fullmatch(r"\d{4}-Q[1-4]", value):
            return pd.Period(value, freq="Q").start_time

        if re.fullmatch(r"\d{4}-\d{2}", value):
            return pd.Period(value, freq="M").start_time

        if re.fullmatch(r"\d{4}", value):
            return pd.Timestamp(int(value), 1, 1)

        return pd.to_datetime(value, errors="coerce")

    except (ValueError, TypeError, OverflowError):
        return pd.NaT


def infer_frequency(periods):
    """Infer frequency from the original time-period labels."""

    values = periods.dropna().astype(str)

    if values.empty:
        return "Unknown"

    sample = values.iloc[0]

    if re.fullmatch(r"\d{4}-Q[1-4]", sample):
        return "Quarterly"

    if re.fullmatch(r"\d{4}-\d{2}", sample):
        return "Monthly"

    if re.fullmatch(r"\d{4}", sample):
        return "Annual"

    if re.fullmatch(r"\d{4}-\d{3}", sample):
        return "Weekly"

    return "Daily / other"


# =========================================================
# 4. SIDEBAR
# =========================================================

st.sidebar.header("Dashboard Controls")

dataset_name = st.sidebar.selectbox(
    "Select economic indicator",
    list(DATASETS.keys()),
)

dataset = DATASETS[dataset_name]

current_year = datetime.now().year

start_year = st.sidebar.number_input(
    "Start year",
    min_value=1960,
    max_value=current_year,
    value=max(2010, current_year - 10),
)

end_year = st.sidebar.number_input(
    "End year",
    min_value=int(start_year),
    max_value=current_year,
    value=current_year,
)

# History control is declared BEFORE the API request so it can drive retrieval.
cpi_history_years = 5
if dataset_name == "Consumer Price Index (CPI)":
    cpi_history_years = st.sidebar.select_slider(
        "CPI history (years)",
        options=[2, 3, 5, 10, 15, 20, "All available"],
        value=5,
        key="cpi_history_years",
        help="Controls both the ABS data request and the historical CPI graphs.",
    )
    cpi_frequency_choice = st.sidebar.radio(
        "CPI chart frequency", ["Auto", "Quarterly", "Monthly"],
        index=1, horizontal=True, key="cpi_frequency_selector",
        help="Quarterly requests historical quarterly observations directly from the ABS. Monthly may have shorter coverage."
    )
    # Request one extra year to compute the first year-on-year observation.
    requested_start = (1960 if cpi_history_years == "All available"
                       else max(1960, int(end_year) - int(cpi_history_years) - 1))
    effective_start_year = min(int(start_year), requested_start)
    st.sidebar.caption(f"CPI data requested from {effective_start_year} (includes annual-change lookback).")
else:
    effective_start_year = int(start_year)

if st.sidebar.button("🔄 Refresh live data", type="primary"):
    fetch_abs_data.clear()
    fetch_targeted_cpi.clear()
    get_cpi_structure.clear()
    st.rerun()

cpi_fast = False
if dataset_name == "Consumer Price Index (CPI)":
    cpi_fast = st.sidebar.toggle("Fast CPI mode (targeted ABS request)", value=True,
                                 help="Downloads selected CPI series rather than the entire CPI dataflow.")
st.sidebar.caption("Observation cache: 1 hour · CPI structure cache: 24 hours")
st.sidebar.markdown(
    "[ABS Data API documentation](https://www.abs.gov.au/"
    "statistics/application-programming-interfaces-apis/"
    "data-api-user-guide)"
)


# Dedicated labour-force dashboard: avoid loading the generic ABS dataflow twice.
if dataset_name == "Unemployment & Labour Market":
    from unemployment_dashboard import show_unemployment_dashboard, load_labour_force
    if st.sidebar.button("Refresh labour force cache", key="refresh_lf"):
        load_labour_force.clear()
        st.rerun()
    show_unemployment_dashboard(int(start_year), int(end_year))
    st.stop()

# =========================================================
# 5. FETCH DATA
# =========================================================

try:
    with st.spinner("Connecting to the ABS Data API..."):
        if cpi_fast:
            try:
                raw_df, request_url, cpi_decisions = fetch_targeted_cpi(
                    effective_start_year, int(end_year), cpi_frequency_choice
                )
            except (requests.RequestException, ValueError, pd.errors.ParserError, ET.ParseError) as fast_error:
                st.warning(
                    "Fast CPI request could not be completed. "
                    "Using the original ABS CPI data request instead. "
                    f"Technical detail: {str(fast_error)[:350]}"
                )
                raw_df, request_url = fetch_abs_data(
                    dataset["flow"], effective_start_year, int(end_year)
                )
                cpi_decisions = ["Fallback: original full CPI request"]
        else:
            raw_df, request_url = fetch_abs_data(
                dataset["flow"], effective_start_year, int(end_year)
            )

except (requests.RequestException, ValueError, pd.errors.ParserError, ET.ParseError) as exc:
    st.error(f"ABS API request failed: {exc}")
    st.info("The ABS API may be unavailable or the dataset structure may have changed.")
    st.stop()


# =========================================================
# 6. STANDARDISE THE DATA
# =========================================================

@st.cache_data(show_spinner=False)
def standardise_abs_data(raw_df):
    """Standardise ABS data and cache the result."""

    time_col = find_column(raw_df, ["TIME_PERIOD", "TIME PERIOD"])
    value_col = find_column(raw_df, ["OBS_VALUE", "OBS VALUE"])

    if time_col is None or value_col is None:
        raise ValueError(
            "Could not identify the time and observation value columns."
        )

    df = raw_df.copy()

    # Vectorised parsing is substantially faster than Python row-by-row map.
    periods = df[time_col].astype("string").str.strip()
    quarterly = periods.str.fullmatch(r"\d{4}-Q[1-4]").fillna(False)
    monthly = periods.str.fullmatch(r"\d{4}-\d{2}").fillna(False)
    annual = periods.str.fullmatch(r"\d{4}").fillna(False)
    df["_DATE"] = pd.NaT
    df.loc[quarterly, "_DATE"] = pd.to_datetime(
        periods.loc[quarterly].str[:4] + "-" +
        ((periods.loc[quarterly].str[-1].astype(int) - 1) * 3 + 1).astype(str).str.zfill(2) + "-01",
        errors="coerce",
    )
    df.loc[monthly, "_DATE"] = pd.to_datetime(periods.loc[monthly] + "-01", errors="coerce")
    df.loc[annual, "_DATE"] = pd.to_datetime(periods.loc[annual] + "-01-01", errors="coerce")
    other = ~(quarterly | monthly | annual)
    if other.any():
        df.loc[other, "_DATE"] = pd.to_datetime(periods.loc[other], errors="coerce")
    df["_DATE"] = pd.to_datetime(df["_DATE"], errors="coerce")
    df["_VALUE"] = pd.to_numeric(df[value_col], errors="coerce")

    excluded = {
        time_col,
        value_col,
        "_DATE",
        "_VALUE",
        "DATAFLOW",
        "OBS_STATUS",
        "OBS_COMMENT",
        "UNIT_MEASURE",
        "UNIT_MULT",
    }

    dimension_cols = [
        col for col in df.columns
        if col not in excluded and not col.startswith("Unnamed:")
    ]

    label_cols = []

    for col in dimension_cols:
        label_col = col + " [label]"
        # Map unique codes once instead of running a regex on every observation.
        unique_values = df[col].dropna().unique()
        mapping = dict(zip(unique_values, clean_label(pd.Series(unique_values)).tolist()))
        df[label_col] = df[col].map(mapping).astype("category")
        label_cols.append(label_col)

    df = df.dropna(subset=["_DATE"])

    return df, time_col, value_col, dimension_cols, label_cols


try:
    (
        df,
        time_col,
        value_col,
        dimension_cols,
        label_cols,
    ) = standardise_abs_data(raw_df)

except ValueError as exc:
    st.error(str(exc))

    with st.expander("Inspect raw API response", expanded=True):
        st.code(request_url)
        st.dataframe(raw_df, use_container_width=True)

    st.stop()


# =========================================================
# 7. DATASET HEADER
# =========================================================

st.subheader(dataset_name)

with st.expander("API request details"):
    st.write("**Dataflow:**", dataset["flow"])
    if cpi_fast:
        st.write("**Fast CPI key selection:**", "; ".join(cpi_decisions))
    st.write("**Request URL:**")
    st.code(request_url)
    st.write(f"**Rows received:** {len(df):,}")


# =========================================================
# 8. INTERACTIVE DIMENSION FILTERS
# =========================================================

st.markdown("### Filter your data")

selected_dimensions = {}

filterable_cols = [
    col for col in label_cols
    if df[col].nunique(dropna=True) > 1
]

if filterable_cols:
    filter_columns = st.columns(min(3, len(filterable_cols)))

    for i, col in enumerate(filterable_cols):
        options = sorted(
            df[col].dropna().astype(str).unique().tolist()
        )

        with filter_columns[i % len(filter_columns)]:
            selected = st.selectbox(
                col.replace(" [label]", ""),
                ["All"] + options,
                key=f"filter_{col}",
            )

        if selected != "All":
            selected_dimensions[col] = selected

mask = pd.Series(True, index=df.index)
for col, selected in selected_dimensions.items():
    mask &= df[col].eq(selected)
filtered_df = df.loc[mask].copy()

if filtered_df.empty:
    st.warning("No observations match your selected filters.")
    st.stop()

# Build a series identifier from the remaining dimensions.
series_identity = [
    col for col in label_cols
    if col in filtered_df.columns
    and filtered_df[col].nunique(dropna=False) > 1
]

if series_identity:
    # Encode combinations first: avoid expensive Python row-wise string joins.
    keys = pd.MultiIndex.from_frame(filtered_df[series_identity].astype("string").fillna("Unknown"))
    ids, uniques = pd.factorize(keys, sort=False)
    names = [" | ".join(map(str, item)) for item in uniques]
    filtered_df["_SERIES"] = pd.Categorical.from_codes(ids, categories=names)
else:
    filtered_df["_SERIES"] = dataset_name


# =========================================================
# 9. DASHBOARD TABS
# =========================================================

# Unlike st.tabs, this executes ONLY the selected view. Streamlit tabs eagerly
# compute every chart, table and quality check on every widget interaction.
VIEWS = ["📊 Overview", "📉 CPI Deep Dive", "📈 Trends & Analysis", "🗃️ Data Explorer", "🩺 Data Quality"]
RESEARCH_VIEWS = ["Macro Overview", "Inflation Research", "Monetary Policy", "Property", "Labour & Wages", "Economic Growth", "ASX Insights"]
VIEWS += RESEARCH_VIEWS
active_view = st.selectbox("Dashboard view", VIEWS, label_visibility="collapsed")
if active_view in RESEARCH_VIEWS:
    from macro_research import research
    research(active_view)
    st.stop()


# =========================================================
# 10. OVERVIEW
# =========================================================

if active_view == VIEWS[0]:

    valid = filtered_df.dropna(subset=["_VALUE"]).copy()

    if valid.empty:
        st.warning("No numeric observations are available.")

    else:
        latest_date = valid["_DATE"].max()

        if valid["_SERIES"].nunique() == 1:

            series = (
                valid.sort_values("_DATE")
                .drop_duplicates("_DATE")
            )

            latest_value = series["_VALUE"].iloc[-1]

            previous_value = (
                series["_VALUE"].iloc[-2]
                if len(series) >= 2
                else None
            )

            change = (
                latest_value - previous_value
                if previous_value is not None
                else None
            )

            pct_change = (
                change / abs(previous_value) * 100
                if previous_value not in (None, 0)
                else None
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Latest observation",
                f"{latest_value:,.3f}",
            )

            c2.metric(
                "Previous-period change",
                f"{change:+,.3f}" if change is not None else "N/A",
            )

            c3.metric(
                "Percentage change",
                f"{pct_change:+.2f}%" if pct_change is not None else "N/A",
            )

            c4.metric(
                "Observation date",
                latest_date.strftime("%d %b %Y"),
            )

        else:
            c1, c2, c3 = st.columns(3)

            c1.metric("Observations", f"{len(valid):,}")
            c2.metric(
                "Distinct series",
                valid["_SERIES"].nunique(),
            )
            c3.metric(
                "Latest observation",
                latest_date.strftime("%d %b %Y"),
            )

            st.info(
                "Apply filters to isolate one series for headline "
                "metrics. Different economic series may use different "
                "units and must not be compared as raw levels."
            )

        # CPI visuals are rendered in their own tab to avoid repeated work.

        st.markdown("### Latest available values")

        latest_table = (
            valid.sort_values("_DATE")
            .groupby("_SERIES", dropna=False)
            .tail(1)
            .sort_values("_DATE", ascending=False)
        )

        latest_display = latest_table[
            ["_SERIES", "_DATE", "_VALUE"]
        ].rename(
            columns={
                "_SERIES": "Series",
                "_DATE": "Observation date",
                "_VALUE": "Value",
            }
        )

        terminal_table(latest_display)


# =========================================================
# 10B. CPI DEEP DIVE — MATCHED SERIES ONLY
# =========================================================

CPI_GROUPS = {
    "Food and non-alcoholic beverages", "Alcohol and tobacco",
    "Clothing and footwear", "Housing", "Furnishings, household equipment and services",
    "Health", "Transport", "Communication", "Recreation and culture",
    "Education", "Insurance and financial services",
}

@st.cache_data(show_spinner=False, max_entries=8)
def prepare_cpi_visuals(source, time_column, labels, preferred_frequency="Auto"):

    """Select a comparable CPI index family, never aggregate mixed series."""
    data = source.dropna(subset=["_DATE", "_VALUE"]).copy()
    if data.empty:
        return pd.DataFrame(), "No numeric CPI observations"

    # Find the dimension that contains ABS expenditure groups.
    group_col = None
    for col in labels:
        if col not in data:
            continue
        values = data[col].dropna().astype(str).str.strip()
        if len(set(values.unique()) & CPI_GROUPS) >= 5:
            group_col = col
            break
    if group_col is None:
        return pd.DataFrame(), "Could not identify an ABS expenditure-group dimension"

    # Use an index-number measure, not an existing percentage-change series.
    measure_cols = [c for c in labels if c != group_col and
                    any(w in c.lower() for w in ("measure", "data type", "unit", "series type"))]
    for col in measure_cols:
        vals = data[col].astype(str)
        index_mask = vals.str.contains(r"index number|index numbers|index,?\s*\(?20", case=False, regex=True, na=False)
        if index_mask.any():
            data = data.loc[index_mask].copy()
            break
    # Select frequency BEFORE identifying series, without mixing observations.
    periods = data[time_column].astype(str)
    monthly = periods.str.fullmatch(r"\d{4}-\d{2}")
    quarterly = periods.str.fullmatch(r"\d{4}-Q[1-4]")
    if preferred_frequency == "Quarterly":
        if not quarterly.any():
            return pd.DataFrame(), "Quarterly selected, but ABS returned no quarterly CPI observations. Open CPI data coverage diagnostics and inspect the API request."
        use_monthly = False
    elif preferred_frequency == "Monthly":
        if not monthly.any():
            return pd.DataFrame(), "Monthly selected, but ABS returned no monthly CPI observations."
        use_monthly = True
    elif preferred_frequency == "Auto":
        # Prefer quarterly if it covers meaningfully more history.
        monthly_start = data.loc[monthly, "_DATE"].min() if monthly.any() else pd.NaT
        quarterly_start = data.loc[quarterly, "_DATE"].min() if quarterly.any() else pd.NaT
        use_monthly = bool(monthly.any() and (
            not quarterly.any() or monthly_start <= quarterly_start + pd.DateOffset(months=6)
        ))
    else:
        use_monthly = bool(monthly.any())
    if use_monthly:
        data = data.loc[monthly].copy()
        lag, frequency = 12, "Monthly"
    elif quarterly.any():
        data = data.loc[quarterly].copy()
        lag, frequency = 4, "Quarterly"
    else:
        return pd.DataFrame(), "No monthly or quarterly CPI series detected"

    # Select a coherent series family using all SDMX dimensions. In ABS CSV,
    # ancillary columns such as OBS_COMMENT can produce repeated group/date rows.
    # First choose a preferred dimension slice, then validate numeric conflicts.
    data["Group"] = data[group_col].astype(str).str.strip()
    data = data.loc[data["Group"].isin(CPI_GROUPS | {"All groups CPI", "All groups"})].copy()
    if data.empty:
        return pd.DataFrame(), "No comparable CPI expenditure groups found"

    other_cols = [c for c in labels if c != group_col and c in data]
    for col in other_cols:
        choices = data[col].dropna().astype(str).unique().tolist()
        if len(choices) <= 1:
            continue
        name = col.upper()
        preferences = (
            [r"^Australia$"] if "REGION" in name else
            [r"^Original$"] if "TSEST" in name or "ADJUST" in name else
            [r"^Index numbers?$", r"^Index number"] if "MEASURE" in name else
            []
        )
        selected = next((v for pat in preferences for v in choices
                         if re.search(pat, v, re.I)), None)
        if selected is None:
            # Prefer the slice with the widest time/category coverage.
            coverage = data.groupby(col, observed=True).agg(
                dates=("_DATE", "nunique"), rows=("_VALUE", "size")
            ).sort_values(["dates", "rows"], ascending=False)
            selected = str(coverage.index[0])
        data = data.loc[data[col].astype(str) == selected].copy()
        if data.empty:
            return pd.DataFrame(), f"No CPI observations after selecting {col}"

    # The API may repeat an identical value due to observation metadata.
    # Collapse ONLY equal values; conflicting values must not be averaged.
    conflicts = data.groupby(["Group", "_DATE"], observed=True)["_VALUE"].nunique()
    conflicting = conflicts[conflicts > 1]
    if not conflicting.empty:
        example = conflicting.index[0]
        return pd.DataFrame(), (
            f"Conflicting CPI observations for {example[0]} on "
            f"{example[1]:%Y-%m-%d}. Select a specific CPI index, "
            "region, adjustment and frequency in the filters."
        )
    data = data.drop_duplicates(subset=["Group", "_DATE"], keep="first")
    data = data.sort_values(["Group", "_DATE"])
    # Match exact calendar periods to avoid incorrect shifts if a month is missing.
    data["_PERIOD"] = data["_DATE"].dt.to_period("M" if lag == 12 else "Q")
    data["_PREV_PERIOD"] = data["_PERIOD"] - lag
    previous = data[["Group", "_PERIOD", "_VALUE"]].rename(columns={"_PERIOD": "_PREV_PERIOD", "_VALUE": "_YEAR_AGO"})
    data = data.merge(previous, on=["Group", "_PREV_PERIOD"], how="left", validate="one_to_one")
    data["Annual %"] = (data["_VALUE"] / data["_YEAR_AGO"] - 1) * 100
    prev_period = data.groupby("Group")["_PERIOD"].shift(1)
    prev_value = data.groupby("Group")["_VALUE"].shift(1)
    data["Period %"] = ((data["_VALUE"] / prev_value) - 1).mul(100).where(
        (prev_period == data["_PERIOD"] - 1) & (prev_value > 0)
    )
    data.loc[data["_YEAR_AGO"] <= 0, "Annual %"] = float("nan")
    data.attrs["frequency"] = frequency
    return data, ""

if active_view == VIEWS[1]:
    if dataset_name != "Consumer Price Index (CPI)":
        st.info("Choose Consumer Price Index (CPI) in the sidebar to see the CPI analysis.")
    else:
        st.subheader("Inflation monitor")
        st.caption("ABS-inspired visuals · CPI expenditure groups · Annual percentage change is not weighted contribution to headline CPI")
        st.caption(f"Selected CPI frequency: **{cpi_frequency_choice}**")
        with st.expander("CPI data coverage diagnostics", expanded=False):
            period_values = df[time_col].astype(str)
            for freq_name, pattern in [("Monthly", r"\d{4}-\d{2}"), ("Quarterly", r"\d{4}-Q[1-4]")]:
                match = period_values.str.fullmatch(pattern)
                dates = df.loc[match, "_DATE"]
                st.write(f"{freq_name}: {int(match.sum()):,} observations; " +
                         (f"{dates.min():%b %Y} to {dates.max():%b %Y}" if not dates.empty else "none returned"))
            st.caption("If Quarterly is selected but no quarterly observations were returned, the API request or available CPI series must be checked.")
        cpi, cpi_error = prepare_cpi_visuals(
            df[["_DATE", "_VALUE", time_col] + label_cols],
            time_col, label_cols, cpi_frequency_choice
        )
        if cpi_error:
            st.warning(cpi_error)
            st.caption("The CPI view selects a consistent index-number family independently of the general filters. If no chart appears, inspect the CPI series and ABS dimension labels in Data Explorer.")
        else:
            available = cpi.dropna(subset=["Annual %"])
            if available.empty:
                st.info("Not enough history to calculate annual inflation. Expand the start year.")
            else:
                last_period = available["_DATE"].max()
                st.markdown("#### Historical CPI analysis")
                history_years = cpi_history_years
                if history_years == "All available":
                    history = available
                else:
                    cutoff = last_period - pd.DateOffset(years=history_years)
                    history = available.loc[available["_DATE"] >= cutoff].copy()
                st.caption(f"Showing {history['_DATE'].min():%b %Y} to {last_period:%b %Y} · {cpi.attrs.get('frequency', 'Unknown')} CPI · ABS data requested from {effective_start_year}.")
                if history["_DATE"].min() > last_period - pd.DateOffset(years=history_years if isinstance(history_years, int) else 100):
                    st.info("The selected ABS CPI series has less history than requested. Monthly CPI coverage may be shorter than quarterly CPI coverage; consider a quarterly series for longer-term comparisons.")
                latest = available.loc[available["_DATE"] == last_period].copy()
                groups = latest[latest["Group"].isin(CPI_GROUPS)].sort_values("Annual %")
                headline = history[history["Group"].isin(["All groups CPI", "All groups"])].sort_values("_DATE")
                if not headline.empty:
                    recent = headline.iloc[-1]
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Headline CPI · annual", f"{recent['Annual %']:.2f}%")
                    k2.metric("Headline CPI · period", f"{recent['Period %']:.2f}%" if pd.notna(recent["Period %"]) else "N/A")
                    k3.metric("Latest CPI period", recent["_DATE"].strftime("%b %Y"))
                    fig = go.Figure()
                    fig.add_hrect(y0=2, y1=3, fillcolor="#10b981", opacity=.12, line_width=0,
                                  annotation_text="RBA target band", annotation_position="top left")
                    fig.add_trace(go.Scatter(x=headline["_DATE"], y=headline["Annual %"],
                                             mode="lines", name="Headline CPI", line=dict(color="#1677c8", width=3)))
                    fig.update_layout(title="Headline inflation — annual change", yaxis_title="Annual change (%)",
                                      xaxis_title="", template="plotly_dark", height=390,
                                      margin=dict(l=20,r=20,t=60,b=20), hovermode="x unified")
                    fig.update_xaxes(range=[headline["_DATE"].min(), headline["_DATE"].max() + pd.DateOffset(months=1)], autorange=False)
                    st.plotly_chart(fig, use_container_width=True, key="headline_cpi")
                else:
                    st.info("Headline CPI series not present in this matched ABS slice.")
                if not groups.empty:
                    fig = px.bar(groups, x="Annual %", y="Group", orientation="h", text="Annual %",
                                 color="Annual %", color_continuous_scale=["#bd5549", "#e9edf2", "#1677c8"],
                                 color_continuous_midpoint=0, title="Annual inflation by expenditure group")
                    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
                    fig.update_layout(template="plotly_dark", height=520, coloraxis_showscale=False,
                                      yaxis_title="", xaxis_title="Annual change (%)", margin=dict(l=20,r=65,t=55,b=20))
                    fig.add_vline(x=0, line_color="gray", line_width=1)
                    st.plotly_chart(fig, use_container_width=True, key="cpi_groups")
                    st.caption(f"Expenditure-group observations: {last_period:%b %Y}. Rates are NOT contributions to overall CPI.")
                else:
                    st.info("No expenditure groups share the latest available period.")
                st.markdown("#### Inflation momentum")
                if not headline.empty:
                    momentum = headline
                    momentum_fig = go.Figure()
                    momentum_fig.add_trace(go.Bar(x=momentum["_DATE"], y=momentum["Period %"], name="Period-on-period %"))
                    momentum_fig.add_trace(go.Scatter(x=momentum["_DATE"], y=momentum["Annual %"],
                                                      name="Annual %", mode="lines+markers", yaxis="y2"))
                    momentum_fig.update_layout(template="plotly_dark", height=360,
                                               yaxis=dict(title="Period change (%)"),
                                               yaxis2=dict(title="Annual change (%)", overlaying="y", side="right"),
                                               legend=dict(orientation="h", y=1.15), margin=dict(l=20,r=20,t=55,b=20))
                    st.plotly_chart(momentum_fig, use_container_width=True, key="cpi_momentum")
                st.markdown("#### Inflation persistence heatmap")
                heat = history[history["Group"].isin(CPI_GROUPS)].copy()
                if not heat.empty:
                    periods = sorted(heat["_DATE"].unique())
                    heat = heat[heat["_DATE"].isin(periods)]
                    heat["Period"] = heat["_DATE"].dt.strftime("%b %y")
                    matrix = heat.pivot(index="Group", columns="Period", values="Annual %")
                    order = heat[["_DATE", "Period"]].drop_duplicates().sort_values("_DATE")["Period"]
                    matrix = matrix.reindex(columns=order)
                    hfig = px.imshow(matrix, aspect="auto", color_continuous_scale="RdBu_r",
                                     color_continuous_midpoint=0, labels=dict(color="Annual %"))
                    hfig.update_layout(template="plotly_dark", height=440, margin=dict(l=20,r=20,t=20,b=20))
                    st.plotly_chart(hfig, use_container_width=True, key="cpi_heatmap")
                st.markdown("#### Expenditure group trends")
                history_groups = history[history["Group"].isin(CPI_GROUPS)].copy()
                if not history_groups.empty:
                    group_options = sorted(history_groups["Group"].unique().tolist())
                    default_groups = [g for g in ["Housing", "Food and non-alcoholic beverages", "Transport"] if g in group_options]
                    chosen_groups = st.multiselect("Compare expenditure groups", group_options, default=default_groups, key="cpi_group_trend_selection")
                    if chosen_groups:
                        trend_data = history_groups[history_groups["Group"].isin(chosen_groups)]
                        group_fig = px.line(trend_data, x="_DATE", y="Annual %", color="Group", title="Annual inflation by expenditure group over time", labels={"_DATE":"", "Annual %":"Annual change (%)"}, template="plotly_dark")
                        group_fig.update_layout(height=420, hovermode="x unified", margin=dict(l=20,r=20,t=55,b=20))
                        group_fig.add_hline(y=0, line_dash="dot", line_color="gray")
                        st.plotly_chart(group_fig, use_container_width=True, key="cpi_group_history")
                st.caption("Source: ABS Data API. CPI index levels converted to annual changes using matched calendar periods. Compare ABS published rates before making investment decisions.")

                st.divider()
                st.markdown("### Investment research — additional CPI insights")
                st.caption("Historical series are matched by date. Optional ABS/RBA data uploads unlock indicators that are not included in the selected CPI API slice.")
                research_tabs = st.tabs(["Inflation breadth", "Housing components", "Underlying inflation", "CPI contributions", "Wages & cash rate"])
                with research_tabs[0]:
                    broad = history[history["Group"].isin(CPI_GROUPS)].dropna(subset=["Annual %"])
                    if not broad.empty:
                        breadth = broad.groupby("_DATE").agg(
                            groups=("Group", "nunique"),
                            above_3=("Annual %", lambda x: int((x > 3).sum())),
                            above_2=("Annual %", lambda x: int((x > 2).sum())),
                            median_inflation=("Annual %", "median"),
                        ).reset_index()
                        breadth["Above 3% share"] = 100 * breadth["above_3"] / breadth["groups"]
                        breadth["Above 2% share"] = 100 * breadth["above_2"] / breadth["groups"]
                        fig = px.line(breadth, x="_DATE", y=["Above 3% share", "Above 2% share"],
                                      title="Share of CPI expenditure groups above inflation thresholds",
                                      labels={"_DATE": "", "value": "Share of groups (%)", "variable": "Threshold"},
                                      template="plotly_dark")
                        fig.update_yaxes(range=[0, 100]); fig.update_layout(hovermode="x unified")
                        st.plotly_chart(fig, use_container_width=True, key="breadth_plot")
                        st.caption("Equal-weighted group breadth, not expenditure-weighted inflation. A group is counted only when its annual rate is available.")
                        terminal_table(breadth.tail(12))
                    else:
                        st.info("No expenditure-group inflation rates are available for breadth analysis.")
                with research_tabs[1]:
                    st.markdown("#### Housing inflation")
                    housing = history[history["Group"].str.contains("Housing|Rent|dwelling", case=False, na=False)]
                    if not housing.empty:
                        st.plotly_chart(px.line(housing, x="_DATE", y="Annual %", color="Group",
                                                title="Housing CPI annual inflation", template="plotly_dark"),
                                        use_container_width=True, key="housing_plot")
                    st.caption("The targeted top-level CPI query may only contain Housing, not rents and new-dwelling subgroups. Upload a dated ABS subgroup export to inspect components.")
                    housing_upload = st.file_uploader("Optional ABS housing subgroup CSV (Date, Component, Annual %)", type="csv", key="housing_upload")
                    if housing_upload is not None:
                        try:
                            h = pd.read_csv(housing_upload)
                            if not {"Date", "Component", "Annual %"}.issubset(h.columns):
                                st.warning("CSV must contain Date, Component, Annual % columns.")
                            else:
                                h["Date"] = pd.to_datetime(h["Date"], errors="coerce")
                                h["Annual %"] = pd.to_numeric(h["Annual %"], errors="coerce")
                                h = h.dropna(subset=["Date", "Annual %", "Component"])
                                st.plotly_chart(px.line(h, x="Date", y="Annual %", color="Component",
                                                        title="Housing CPI subgroups — uploaded ABS data", template="plotly_dark"),
                                                use_container_width=True, key="housing_subgroups")
                        except Exception as exc:
                            st.warning(f"Could not read housing CSV: {exc}")
                with research_tabs[2]:
                    st.markdown("#### Headline vs trimmed-mean inflation")
                    st.caption("Trimmed mean is a separate underlying-inflation measure. It must not be inferred from a simple median or average of expenditure groups.")
                    underlying_upload = st.file_uploader("ABS trimmed-mean CSV (Date, Trimmed mean annual %)", type="csv", key="trimmed_upload")
                    if underlying_upload is not None:
                        try:
                            u = pd.read_csv(underlying_upload)
                            if not {"Date", "Trimmed mean annual %"}.issubset(u.columns):
                                st.warning("CSV must contain Date and Trimmed mean annual % columns.")
                            else:
                                u["Date"] = pd.to_datetime(u["Date"], errors="coerce")
                                u["Trimmed mean annual %"] = pd.to_numeric(u["Trimmed mean annual %"], errors="coerce")
                                u = u.dropna(subset=["Date", "Trimmed mean annual %"])
                                base = headline[["_DATE", "Annual %"]].rename(columns={"_DATE": "Date", "Annual %": "Headline annual %"})
                                compare = pd.merge(base, u[["Date", "Trimmed mean annual %"]], on="Date", how="inner")
                                if compare.empty:
                                    st.warning("No matching CPI dates. Use dates aligned to the CPI observation periods and frequency.")
                                else:
                                    st.plotly_chart(px.line(compare, x="Date", y=["Headline annual %", "Trimmed mean annual %"],
                                                            title="Headline vs trimmed-mean CPI (matched periods)", template="plotly_dark"),
                                                    use_container_width=True, key="trimmed_chart")
                        except Exception as exc:
                            st.warning(f"Could not read trimmed-mean CSV: {exc}")
                    else:
                        st.info("Upload the official ABS trimmed-mean time series to enable a valid comparison.")
                with research_tabs[3]:
                    st.markdown("#### Contributions to headline inflation")
                    st.caption("Annual group inflation rates are NOT contributions. The chart below requires externally supplied ABS-compatible contribution values in percentage points.")
                    contrib_upload = st.file_uploader("Contribution CSV (Date, Group, Contribution pp)", type="csv", key="contrib_upload")
                    if contrib_upload is not None:
                        try:
                            co = pd.read_csv(contrib_upload)
                            if not {"Date", "Group", "Contribution pp"}.issubset(co.columns):
                                st.warning("CSV must contain Date, Group, Contribution pp columns.")
                            else:
                                co["Date"] = pd.to_datetime(co["Date"], errors="coerce")
                                co["Contribution pp"] = pd.to_numeric(co["Contribution pp"], errors="coerce")
                                co = co.dropna(subset=["Date", "Group", "Contribution pp"])
                                co = co[co["Date"] >= history["_DATE"].min()]
                                if not co.empty:
                                    fig = px.bar(co, x="Date", y="Contribution pp", color="Group",
                                                 title="CPI contributions (percentage points) — supplied series",
                                                 template="plotly_dark")
                                    fig.update_layout(barmode="relative", hovermode="x unified")
                                    st.plotly_chart(fig, use_container_width=True, key="contribution_chart")
                                    st.caption("Validate that contribution methodology and group coverage match the ABS headline CPI definition.")
                        except Exception as exc:
                            st.warning(f"Could not read contribution CSV: {exc}")
                    else:
                        st.info("Upload published contribution data. The app will not estimate contributions from unweighted inflation rates.")
                with research_tabs[4]:
                    st.markdown("#### Inflation, wages and monetary policy")
                    st.caption("Supply official wage-growth and RBA cash-rate series. Charts use actual observation dates and do not interpolate missing periods.")
                    macro_upload = st.file_uploader("Macro CSV (Date, Wages annual %, Cash rate %)", type="csv", key="macro_upload")
                    if macro_upload is not None:
                        try:
                            m = pd.read_csv(macro_upload)
                            if "Date" not in m or not any(c in m for c in ["Wages annual %", "Cash rate %"]):
                                st.warning("CSV requires Date and at least one of Wages annual % or Cash rate %.")
                            else:
                                m["Date"] = pd.to_datetime(m["Date"], errors="coerce")
                                cols = [c for c in ["Wages annual %", "Cash rate %"] if c in m]
                                for c in cols: m[c] = pd.to_numeric(m[c], errors="coerce")
                                m = m.dropna(subset=["Date"])
                                base = headline[["_DATE", "Annual %"]].rename(columns={"_DATE": "Date", "Annual %": "CPI annual %"})
                                aligned = pd.merge(base, m[["Date"] + cols], on="Date", how="inner")
                                if aligned.empty:
                                    st.warning("No exact matching dates. Align the supplied dates with CPI release observation periods.")
                                else:
                                    st.plotly_chart(px.line(aligned, x="Date", y=["CPI annual %"] + cols,
                                                            title="CPI vs wages growth and cash rate — matched dates", template="plotly_dark"),
                                                    use_container_width=True, key="macro_comparison")
                                    if "Wages annual %" in cols:
                                        aligned["Wages less CPI (pp)"] = aligned["Wages annual %"] - aligned["CPI annual %"]
                                        st.plotly_chart(px.bar(aligned, x="Date", y="Wages less CPI (pp)",
                                                               title="Nominal wage growth less CPI inflation (percentage points)", template="plotly_dark"),
                                                        use_container_width=True, key="real_wages_proxy")
                                        st.caption("Wage growth minus CPI is a purchasing-power indicator, not an exact real-wage growth calculation.")
                        except Exception as exc:
                            st.warning(f"Could not read macro CSV: {exc}")
                    else:
                        st.info("Upload ABS Wage Price Index and RBA cash-rate observations to unlock comparisons.")



# =========================================================
# 11. INTERACTIVE CHARTS
# =========================================================

if active_view == VIEWS[2]:

    c1, c2 = st.columns(2)

    with c1:
        chart_type = st.selectbox(
            "Chart type",
            ["Line", "Area", "Scatter"],
        )

    with c2:
        transform = st.selectbox(
            "Transformation",
            [
                "Original values",
                "Period-on-period % change",
                "Year-on-year % change",
                "Indexed to 100 at start",
            ],
        )

    plot_df = (
        filtered_df.dropna(subset=["_VALUE"])
        .copy()
        .sort_values(["_SERIES", "_DATE"])
    )

    frequency = infer_frequency(plot_df[time_col])

    lag_map = {
        "Monthly": 12,
        "Quarterly": 4,
        "Weekly": 52,
        "Annual": 1,
        "Daily / other": 365,
        "Unknown": 1,
    }

    if transform == "Period-on-period % change":

        previous = plot_df.groupby("_SERIES", observed=True)["_VALUE"].shift(1)
        plot_df["_PLOT_VALUE"] = ((plot_df["_VALUE"] / previous) - 1).mul(100).where(previous != 0)

    elif transform == "Year-on-year % change":

        lag = lag_map[frequency]

        # Compare exact calendar periods, never the Nth prior row if data has gaps.
        period_freq = {"Monthly": "M", "Quarterly": "Q", "Annual": "Y"}.get(frequency)
        if period_freq:
            plot_df["_CAL_PERIOD"] = plot_df["_DATE"].dt.to_period(period_freq)
            lookback = plot_df[["_SERIES", "_CAL_PERIOD", "_VALUE"]].copy()
            lookback["_CAL_PERIOD"] = lookback["_CAL_PERIOD"] + lag
            lookback = lookback.drop_duplicates(["_SERIES", "_CAL_PERIOD"])
            lookback = lookback.rename(columns={"_VALUE": "_YEAR_AGO"})
            plot_df = plot_df.merge(lookback, on=["_SERIES", "_CAL_PERIOD"], how="left")
            plot_df["_PLOT_VALUE"] = ((plot_df["_VALUE"] / plot_df["_YEAR_AGO"]) - 1).mul(100).where(plot_df["_YEAR_AGO"] > 0)
        else:
            plot_df["_PLOT_VALUE"] = float("nan")
            st.info("Exact year-on-year comparisons are supported for monthly, quarterly and annual series.")

    elif transform == "Indexed to 100 at start":

        base = (
            plot_df.groupby("_SERIES")["_VALUE"]
            .transform("first")
        )

        plot_df["_PLOT_VALUE"] = (
            plot_df["_VALUE"] / base * 100
        ).where(base != 0)

    else:
        plot_df["_PLOT_VALUE"] = plot_df["_VALUE"]

    plot_df = plot_df.dropna(subset=["_PLOT_VALUE"])

    # Keep full transformed data for accurate summary statistics.
    stats_df = plot_df.copy()

    # Limit chart rendering to the 20 largest series.
    MAX_SERIES = 20
    MAX_POINTS_PER_SERIES = 500

    series_sizes = (
        plot_df.groupby("_SERIES")
        .size()
        .sort_values(ascending=False)
    )

    if len(series_sizes) > MAX_SERIES:
        keep_series = series_sizes.head(MAX_SERIES).index

        plot_df = plot_df[
            plot_df["_SERIES"].isin(keep_series)
        ].copy()

        st.warning(
            f"Showing {MAX_SERIES} series with the most observations "
            f"out of {len(series_sizes)} total series. "
            "Apply dimension filters to explore other series."
        )

    # Reduce plotted points while preserving time order and each series' last point.
    sampled_groups = []

    for _, group in plot_df.groupby("_SERIES", sort=False):
        if len(group) > MAX_POINTS_PER_SERIES:
            step = (
                len(group) + MAX_POINTS_PER_SERIES - 1
            ) // MAX_POINTS_PER_SERIES

            group = pd.concat([
                group.iloc[::step],
                group.iloc[[-1]],
            ]).drop_duplicates()

        sampled_groups.append(group)

    if sampled_groups:
        plot_df = pd.concat(sampled_groups, ignore_index=True)

    y_titles = {
        "Original values": "ABS-reported value",
        "Period-on-period % change": "Change (%)",
        "Year-on-year % change": "Change (%)",
        "Indexed to 100 at start": "Index (start = 100)",
    }

    if plot_df.empty:
        st.warning(
            "There are not enough observations for this transformation. "
            "Select a longer date range."
        )

    else:
        chart_functions = {
            "Line": px.line,
            "Area": px.area,
            "Scatter": px.scatter,
        }

        fig = chart_functions[chart_type](
            plot_df,
            x="_DATE",
            y="_PLOT_VALUE",
            color="_SERIES",
            labels={
                "_DATE": "Observation date",
                "_PLOT_VALUE": y_titles[transform],
                "_SERIES": "Economic series",
            },
            title=f"{dataset_name}: {transform}",
            template="plotly_dark",
        )

        fig.update_layout(
            hovermode="x unified",
            margin=dict(l=20, r=20, t=65, b=20),
            legend_title_text="Economic series",
        )

        fig.update_xaxes(
            rangeslider_visible=True,
            showgrid=True,
        )

        fig.update_yaxes(showgrid=True)

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        st.caption(
            f"Detected frequency: {frequency}. "
            "Year-on-year calculations use matched calendar periods. "
            "Verify the series frequency before interpreting results."
        )

        st.markdown("### Summary statistics")

        stats = (
            stats_df.groupby("_SERIES")["_PLOT_VALUE"]
            .agg(["count", "mean", "median", "min", "max", "std"])
            .reset_index()
        )

        stats.columns = [
            "Series",
            "Observations",
            "Mean",
            "Median",
            "Minimum",
            "Maximum",
            "Standard deviation",
        ]

        terminal_table(stats)


# =========================================================
# 12. DATA EXPLORER AND EXPORTS
# =========================================================

if active_view == VIEWS[3]:

    st.markdown("### Filtered observations")

    display_cols = [
        col for col in filtered_df.columns
        if not col.startswith("_")
    ]

    # Large Streamlit tables are expensive to render on every rerun.
    # Show a preview here, while keeping the full filtered dataset downloadable.
    PREVIEW_ROWS = 5000
    preview_df = filtered_df[display_cols].head(PREVIEW_ROWS)

    st.caption(
        f"Showing the first {len(preview_df):,} of {len(filtered_df):,} "
        "matching rows. Download the CSV for the full dataset."
    )

    if st.checkbox("Show observation preview (up to 5,000 rows)", value=False):
        st.dataframe(preview_df, hide_index=True, use_container_width=True)

    # Invalidate previously prepared downloads when dataset/date/filter choices change.
    download_signature = (
        dataset_name,
        int(start_year),
        int(end_year),
        tuple(sorted(selected_dimensions.items())),
    )
    if st.session_state.get("download_signature") != download_signature:
        st.session_state.pop("filtered_csv_bytes", None)
        st.session_state.pop("cleaned_csv_bytes", None)
        st.session_state["download_signature"] = download_signature

    # Build downloads only when the user asks for them, rather than serialising
    # 100k+ rows on every ordinary dashboard rerun.
    with st.expander("Download data", expanded=False):
        if st.button("Prepare filtered CSV", key="prepare_filtered_csv"):
            st.session_state["filtered_csv_bytes"] = filtered_df[display_cols].to_csv(
                index=False
            ).encode("utf-8")

        if "filtered_csv_bytes" in st.session_state:
            st.download_button(
                label="⬇️ Download filtered data as CSV",
                data=st.session_state["filtered_csv_bytes"],
                file_name="abs_filtered_data.csv",
                mime="text/csv",
                key="download_filtered_csv",
            )

        if st.button("Prepare cleaned CSV", key="prepare_cleaned_csv"):
            cleaned = filtered_df.copy()
            cleaned["PARSED_DATE"] = cleaned["_DATE"]
            cleaned["NUMERIC_VALUE"] = cleaned["_VALUE"]
            st.session_state["cleaned_csv_bytes"] = cleaned.to_csv(
                index=False
            ).encode("utf-8")

        if "cleaned_csv_bytes" in st.session_state:
            st.download_button(
                label="⬇️ Download cleaned data as CSV",
                data=st.session_state["cleaned_csv_bytes"],
                file_name="abs_cleaned_data.csv",
                mime="text/csv",
                key="download_cleaned_csv",
            )


# =========================================================
# 13. DATA QUALITY CHECKS
# =========================================================

if active_view == VIEWS[4]:

    st.markdown("### Automated data-quality report")

    numeric_values = pd.to_numeric(
        filtered_df["_VALUE"],
        errors="coerce",
    )

    dates = filtered_df["_DATE"]

    duplicate_keys = series_identity + [time_col]
    duplicate_keys = [
        col for col in duplicate_keys
        if col in filtered_df.columns
    ]

    duplicate_count = (
        filtered_df.duplicated(subset=duplicate_keys).sum()
        if duplicate_keys
        else filtered_df.duplicated().sum()
    )

    report = {
        "Total rows": len(filtered_df),
        "Numeric observations": int(numeric_values.notna().sum()),
        "Missing / non-numeric values": int(numeric_values.isna().sum()),
        "Duplicate observations": int(duplicate_count),
        "Unparseable dates": int(dates.isna().sum()),
        "Latest observation date": (
            dates.max().strftime("%Y-%m-%d")
            if dates.notna().any()
            else "Unavailable"
        ),
    }

    c1, c2, c3 = st.columns(3)

    c1.metric("Rows", f"{report['Total rows']:,}")
    c2.metric(
        "Missing values",
        f"{report['Missing / non-numeric values']:,}",
    )
    c3.metric(
        "Duplicate observations",
        f"{report['Duplicate observations']:,}",
    )

    with st.expander("Detailed quality checks"):
        terminal_table(pd.DataFrame([{"Check": key, "Result": value} for key, value in report.items()]))

    # Basic anomaly screening within each individual series.
    ordered = filtered_df.sort_values(["_SERIES", "_DATE"]).copy()

    ordered["_CHANGE_PCT"] = (
        ordered.groupby("_SERIES")["_VALUE"]
        .pct_change(fill_method=None) * 100
    )

    extreme = ordered[
        ordered["_CHANGE_PCT"].abs() > 50
    ]

    if len(extreme):
        st.warning(
            f"{len(extreme)} sequential changes exceed 50%. "
            "Investigate these observations; they may be genuine "
            "movements, revisions, or data issues."
        )

        st.dataframe(
            extreme[["_SERIES", "_DATE", "_VALUE", "_CHANGE_PCT"]],
            hide_index=True,
            use_container_width=True,
        )

    else:
        st.success(
            "No sequential changes exceeding 50% were identified "
            "by this screening rule."
        )

    st.info(
        "These are preliminary screening checks. They do not replace "
        "verification of units, seasonal adjustment, observation status, "
        "revision history, or statistical methodology."
    )


# =========================================================
# 14. FOOTER
# =========================================================

st.divider()

st.caption(
    "Source: Australian Bureau of Statistics Data API. "
    "Data is cached for one hour. Views render on demand. Latest observation dates depend "
    "on the publication schedule of each dataset."
)
