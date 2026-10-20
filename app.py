
import io
import re
from datetime import datetime

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

st.markdown("""<style>
.block-container {padding-top: 1.5rem; max-width: 1500px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.07); padding: 14px 18px; border-radius: 12px; border: 1px solid rgba(128,128,128,.12);}
[data-testid="stMetricLabel"] {font-weight: 600;}
</style>""", unsafe_allow_html=True)
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

if st.sidebar.button("🔄 Refresh live data", type="primary"):
    fetch_abs_data.clear()
    st.rerun()

st.sidebar.caption("Data cache: 1 hour")
st.sidebar.markdown(
    "[ABS Data API documentation](https://www.abs.gov.au/"
    "statistics/application-programming-interfaces-apis/"
    "data-api-user-guide)"
)


# =========================================================
# 5. FETCH DATA
# =========================================================

try:
    with st.spinner("Connecting to the ABS Data API..."):
        raw_df, request_url = fetch_abs_data(
            dataset["flow"],
            int(start_year),
            int(end_year),
        )

except requests.RequestException as exc:
    st.error(f"ABS API connection failed: {exc}")
    st.info(
        "Check your internet connection and the dataflow ID. "
        "The API may also be temporarily unavailable."
    )
    st.stop()

except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"Unable to process the ABS response: {exc}")
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

    df["_DATE"] = df[time_col].map(parse_period)
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
        df[label_col] = clean_label(df[col])
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

filtered_df = df.copy()

for col, selected in selected_dimensions.items():
    filtered_df = filtered_df[
        filtered_df[col].astype(str) == selected
    ]

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
    filtered_df["_SERIES"] = (
        filtered_df[series_identity]
        .astype("string")
        .fillna("Unknown")
        .agg(" | ".join, axis=1)
    )
else:
    filtered_df["_SERIES"] = dataset_name


# =========================================================
# 9. DASHBOARD TABS
# =========================================================

overview_tab, cpi_tab, trends_tab, data_tab, quality_tab = st.tabs(
    [
        "📊 Overview",
        "📉 CPI Deep Dive",
        "📈 Trends & Analysis",
        "🗃️ Data Explorer",
        "🩺 Data Quality",
    ]
)


# =========================================================
# 10. OVERVIEW
# =========================================================

with overview_tab:

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

        st.dataframe(
            latest_display,
            hide_index=True,
            use_container_width=True,
        )


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
def prepare_cpi_visuals(source, time_column, labels):
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
    # Avoid mixing quarterly and monthly observations.
    periods = data[time_column].astype(str)
    monthly = periods.str.fullmatch(r"\d{4}-\d{2}")
    quarterly = periods.str.fullmatch(r"\d{4}-Q[1-4]")
    if monthly.any():
        data = data.loc[monthly].copy()
        lag = 12
        frequency = "Monthly"
    elif quarterly.any():
        data = data.loc[quarterly].copy()
        lag = 4
        frequency = "Quarterly"
    else:
        return pd.DataFrame(), "No monthly or quarterly CPI series detected"

    # Select a single coherent slice across all other SDMX dimensions.
    # Prefer Australia, original (not seasonally adjusted) and index number.
    other_cols = [c for c in labels if c != group_col and c in data]
    for col in other_cols:
        choices = data[col].dropna().astype(str).unique().tolist()
        if len(choices) <= 1:
            continue
        preferences = [r"^Australia$", r"^Original$", r"^Index number", r"^Index Numbers"]
        selected = next((v for pat in preferences for v in choices if re.search(pat, v, re.I)), None)
        if selected is None:
            # Select the most common slice rather than mixing incompatible series.
            selected = data[col].astype(str).value_counts().index[0]
        data = data.loc[data[col].astype(str) == selected].copy()

    data["Group"] = data[group_col].astype(str).str.strip()
    data = data.loc[data["Group"].isin(CPI_GROUPS | {"All groups CPI", "All groups"})].copy()
    if data.empty:
        return pd.DataFrame(), "No comparable CPI expenditure groups found"
    # Require unique observation per group and date: duplicates mean ambiguity.
    if data.duplicated(["Group", "_DATE"]).any():
        return pd.DataFrame(), "Multiple CPI series remain per group/date; select a single measure and geography"
    data = data.sort_values(["Group", "_DATE"])
    # Match exact calendar periods to avoid incorrect shifts if a month is missing.
    data["_PERIOD"] = data["_DATE"].dt.to_period("M" if lag == 12 else "Q")
    data["_PREV_PERIOD"] = data["_PERIOD"] - lag
    previous = data[["Group", "_PERIOD", "_VALUE"]].rename(columns={"_PERIOD": "_PREV_PERIOD", "_VALUE": "_YEAR_AGO"})
    data = data.merge(previous, on=["Group", "_PREV_PERIOD"], how="left", validate="one_to_one")
    data["Annual %"] = (data["_VALUE"] / data["_YEAR_AGO"] - 1) * 100
    data["Period %"] = data.groupby("Group")["_VALUE"].pct_change(fill_method=None) * 100
    data.loc[data["_YEAR_AGO"] <= 0, "Annual %"] = float("nan")
    data.attrs["frequency"] = frequency
    return data, ""

with cpi_tab:
    if dataset_name != "Consumer Price Index (CPI)":
        st.info("Choose Consumer Price Index (CPI) in the sidebar to see the CPI analysis.")
    else:
        st.subheader("Inflation monitor")
        st.caption("ABS-inspired visuals · CPI expenditure groups · Annual percentage change is not weighted contribution to headline CPI")
        cpi, cpi_error = prepare_cpi_visuals(df, time_col, label_cols)
        if cpi_error:
            st.warning(cpi_error)
            st.caption("The API's dimensions may differ across ABS releases. Inspect the Data Explorer to identify a consistent index-number series.")
        else:
            available = cpi.dropna(subset=["Annual %"])
            if available.empty:
                st.info("Not enough history to calculate annual inflation. Expand the start year.")
            else:
                last_period = available["_DATE"].max()
                latest = available.loc[available["_DATE"] == last_period].copy()
                groups = latest[latest["Group"].isin(CPI_GROUPS)].sort_values("Annual %")
                headline = available[available["Group"].isin(["All groups CPI", "All groups"])].sort_values("_DATE")
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
                                      xaxis_title="", template="plotly_white", height=390,
                                      margin=dict(l=20,r=20,t=60,b=20), hovermode="x unified")
                    st.plotly_chart(fig, use_container_width=True, key="headline_cpi")
                else:
                    st.info("Headline CPI series not present in this matched ABS slice.")
                if not groups.empty:
                    fig = px.bar(groups, x="Annual %", y="Group", orientation="h", text="Annual %",
                                 color="Annual %", color_continuous_scale=["#bd5549", "#e9edf2", "#1677c8"],
                                 color_continuous_midpoint=0, title="Annual inflation by expenditure group")
                    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", cliponaxis=False)
                    fig.update_layout(template="plotly_white", height=520, coloraxis_showscale=False,
                                      yaxis_title="", xaxis_title="Annual change (%)", margin=dict(l=20,r=65,t=55,b=20))
                    fig.add_vline(x=0, line_color="gray", line_width=1)
                    st.plotly_chart(fig, use_container_width=True, key="cpi_groups")
                    st.caption(f"Expenditure-group observations: {last_period:%b %Y}. Rates are NOT contributions to overall CPI.")
                else:
                    st.info("No expenditure groups share the latest available period.")
                st.markdown("#### Inflation momentum")
                if not headline.empty:
                    momentum = headline.tail(24)
                    momentum_fig = go.Figure()
                    momentum_fig.add_trace(go.Bar(x=momentum["_DATE"], y=momentum["Period %"], name="Period-on-period %"))
                    momentum_fig.add_trace(go.Scatter(x=momentum["_DATE"], y=momentum["Annual %"],
                                                      name="Annual %", mode="lines+markers", yaxis="y2"))
                    momentum_fig.update_layout(template="plotly_white", height=360,
                                               yaxis=dict(title="Period change (%)"),
                                               yaxis2=dict(title="Annual change (%)", overlaying="y", side="right"),
                                               legend=dict(orientation="h", y=1.15), margin=dict(l=20,r=20,t=55,b=20))
                    st.plotly_chart(momentum_fig, use_container_width=True, key="cpi_momentum")
                st.markdown("#### Inflation persistence heatmap")
                heat = available[available["Group"].isin(CPI_GROUPS)].copy()
                if not heat.empty:
                    periods = sorted(heat["_DATE"].unique())[-24:]
                    heat = heat[heat["_DATE"].isin(periods)]
                    heat["Period"] = heat["_DATE"].dt.strftime("%b %y")
                    matrix = heat.pivot(index="Group", columns="Period", values="Annual %")
                    order = heat[["_DATE", "Period"]].drop_duplicates().sort_values("_DATE")["Period"]
                    matrix = matrix.reindex(columns=order)
                    hfig = px.imshow(matrix, aspect="auto", color_continuous_scale="RdBu_r",
                                     color_continuous_midpoint=0, labels=dict(color="Annual %"))
                    hfig.update_layout(template="plotly_white", height=440, margin=dict(l=20,r=20,t=20,b=20))
                    st.plotly_chart(hfig, use_container_width=True, key="cpi_heatmap")
                st.caption("Source: ABS Data API. CPI index levels converted to annual changes using matched calendar periods. Compare ABS published rates before making investment decisions.")


# =========================================================
# 11. INTERACTIVE CHARTS
# =========================================================

with trends_tab:

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

        plot_df["_PLOT_VALUE"] = (
            plot_df.groupby("_SERIES")["_VALUE"]
            .pct_change(fill_method=None) * 100
        )

    elif transform == "Year-on-year % change":

        lag = lag_map[frequency]

        plot_df["_PLOT_VALUE"] = (
            plot_df.groupby("_SERIES")["_VALUE"]
            .pct_change(periods=lag, fill_method=None) * 100
        )

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
            template="plotly_white",
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
            "Year-on-year calculations use a frequency-based lag. "
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

        st.dataframe(
            stats,
            hide_index=True,
            use_container_width=True,
        )


# =========================================================
# 12. DATA EXPLORER AND EXPORTS
# =========================================================

with data_tab:

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

    st.dataframe(
        preview_df,
        hide_index=True,
        use_container_width=True,
    )

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

with quality_tab:

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

    st.dataframe(
        pd.DataFrame(
            [
                {"Check": key, "Result": value}
                for key, value in report.items()
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

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
    "Data is cached for one hour. Latest observation dates depend "
    "on the publication schedule of each dataset."
)
