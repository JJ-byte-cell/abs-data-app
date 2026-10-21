"""Australian 10-year nominal Commonwealth Government bond yield dashboard.

RBA Statistical Table F2. Public API for app.py:
    load_bond_yield() -> (DataFrame, description)
    show_bond_dashboard(start_year, end_year) -> None
"""
import csv
import io
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

RBA_F2 = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"
RBA_TABLE = "https://www.rba.gov.au/statistics/tables/"
SERIES_ID = "FCMYGBAG10D"

# Colours consistent with the existing dark terminal theme.
BACKGROUND = "#111d2e"
GRID = "#29394e"
TEXT = "#f1f5f9"
BLUE = "#53b8ff"
CYAN = "#38bdf8"
GREEN = "#22c55e"
RED = "#ef5350"


def _date(value):
    text = str(value).strip().strip('"')
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%b-%Y", "%b %Y"):
        try:
            return pd.Timestamp(datetime.strptime(text, fmt))
        except ValueError:
            pass
    return pd.NaT


def _parse_rba_f2(content):
    """Locate the 10-year yield by official series ID in RBA's metadata CSV."""
    decoded = content.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(decoded)))
    if not rows:
        raise ValueError("The RBA CSV is empty.")

    positions = [
        (i, j)
        for i, row in enumerate(rows[:40])
        for j, cell in enumerate(row)
        if cell.strip().upper() == SERIES_ID
    ]
    if not positions:
        raise ValueError(f"RBA F2 did not contain series {SERIES_ID}.")
    header_row, series_col = positions[0]

    candidate_dates = []
    for row in rows[header_row + 1:header_row + 60]:
        for j, cell in enumerate(row[:4]):
            if pd.notna(_date(cell)):
                candidate_dates.append(j)
    if not candidate_dates:
        raise ValueError("Could not identify the date column in RBA F2.")
    date_col = max(set(candidate_dates), key=candidate_dates.count)

    observations = []
    for row in rows[header_row + 1:]:
        if len(row) <= max(series_col, date_col):
            continue
        date = _date(row[date_col])
        if pd.isna(date):
            continue
        raw = row[series_col].strip().replace(",", "")
        if not raw or raw.lower() in ("-", "..", "n.a.", "na"):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        observations.append((date, value))

    if not observations:
        raise ValueError(f"Found RBA series {SERIES_ID}, but no numeric observations.")
    df = pd.DataFrame(observations, columns=["Date", "Yield (%)"])
    df = df.drop_duplicates("Date", keep="last").sort_values("Date").reset_index(drop=True)
    return df, "Australian Government 10-year nominal bond yield (RBA F2; FCMYGBAG10D)"


@st.cache_data(ttl=3600, show_spinner=False)
def load_bond_yield():
    """Fetch and cache official RBA F2 observations."""
    response = requests.get(
        RBA_F2,
        timeout=(10, 60),
        headers={"User-Agent": "Mozilla/5.0 (compatible; AustralianMacroTracker/1.0)"},
    )
    response.raise_for_status()
    return _parse_rba_f2(response.content)


def _style(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        font_color=TEXT,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#162438", font_color="#f8fafc"),
        margin=dict(l=25, r=20, t=55, b=25),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#8295aa")
    return fig


def show_bond_dashboard(start_year=None, end_year=None):
    """Render the bond macro tracker, compatible with existing app.py calls."""
    st.header("Australian 10-Year Government Bond Yield")
    st.caption(
        "Source: Reserve Bank of Australia, Statistical Table F2. "
        "Nominal Commonwealth Government 10-year bond yield; daily observations, updated weekly."
    )

    try:
        with st.spinner("Loading official RBA bond yield data…"):
            all_data, description = load_bond_yield()
    except (requests.RequestException, ValueError, UnicodeError, csv.Error) as exc:
        st.error(f"Unable to load RBA 10-year government bond yield: {exc}")
        st.markdown(f"[View the RBA statistical tables]({RBA_TABLE})")
        return

    start = int(start_year) if start_year is not None else int(all_data["Date"].dt.year.min())
    end = int(end_year) if end_year is not None else int(all_data["Date"].dt.year.max())
    df = all_data.loc[all_data["Date"].dt.year.between(start, end)].copy()
    if df.empty:
        st.warning("No published observations in the selected date range. Change the start/end year in the sidebar.")
        return

    frequency = st.selectbox(
        "Chart frequency",
        ["Daily observations", "Monthly average", "Quarterly average"],
        index=0,
        key="bond_chart_frequency",
    )
    if frequency == "Monthly average":
        chart_data = df.set_index("Date").resample("MS")["Yield (%)"].mean().dropna().reset_index()
    elif frequency == "Quarterly average":
        chart_data = df.set_index("Date").resample("QS")["Yield (%)"].mean().dropna().reset_index()
    else:
        chart_data = df.copy()

    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else None
    change_bp = (latest["Yield (%)"] - previous["Yield (%)"]) * 100 if previous is not None else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("10-year bond yield", f"{latest['Yield (%)']:.2f}%")
    c2.metric("Latest observation", latest["Date"].strftime("%d %b %Y"))
    c3.metric("Change from previous", f"{change_bp:+.1f} bp" if change_bp is not None else "—")
    c4.metric("Period high / low", f"{df['Yield (%)'].max():.2f}% / {df['Yield (%)'].min():.2f}%")

    st.subheader("Historical yield trend")
    trend = px.line(chart_data, x="Date", y="Yield (%)", title="Australian Government 10-year nominal yield")
    trend.update_traces(
        line=dict(color=BLUE, width=2.5),
        hovertemplate="%{x|%d %b %Y}: %{y:.2f}%<extra></extra>",
    )
    st.plotly_chart(_style(trend), use_container_width=True)

    st.subheader("Yield momentum")
    changes = chart_data.copy()
    changes["Change (bp)"] = changes["Yield (%)"].diff() * 100
    changes = changes.dropna(subset=["Change (bp)"])
    bars = go.Figure()
    bars.add_trace(go.Bar(
        x=changes["Date"],
        y=changes["Change (bp)"],
        marker=dict(
            color=[GREEN if v >= 0 else RED for v in changes["Change (bp)"]],
            line=dict(width=0),
        ),
        hovertemplate="%{x|%d %b %Y}<br>Change: %{y:+.1f} bp<extra></extra>",
        name="Yield change",
    ))
    bars.update_layout(
        title="Change between displayed observations (basis points)",
        xaxis_title="Date",
        yaxis_title="Change (bp)",
        showlegend=False,
        bargap=0.08,
    )
    bars.update_yaxes(zeroline=True, zerolinewidth=1.5, zerolinecolor="#8295aa")
    st.plotly_chart(_style(bars), use_container_width=True)

    st.subheader("Yield distribution")
    hist = px.histogram(
        df,
        x="Yield (%)",
        nbins=35,
        title="Distribution of yields in the selected period",
        color_discrete_sequence=[CYAN],
    )
    hist.update_traces(
        marker_line_color=BACKGROUND,
        marker_line_width=0.5,
        opacity=0.92,
        hovertemplate="Yield bin: %{x:.2f}%<br>Observations: %{y}<extra></extra>",
    )
    hist.update_layout(
        xaxis_title="Yield (%)",
        yaxis_title="Observations",
        bargap=0.035,
        showlegend=False,
    )
    st.plotly_chart(_style(hist), use_container_width=True)

    st.subheader("Macroeconomic interpretation")
    st.markdown(
        "A higher 10-year yield can reflect expectations of higher future short-term rates, "
        "inflation compensation, or an increased term premium. A lower yield may reflect the reverse. "
        "**Changes in yields alone cannot establish the cause.** Bond prices generally move "
        "inversely to yields. This yield is not the RBA cash rate."
    )

    st.subheader("Official observations")
    st.dataframe(df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)
    st.download_button(
        "Download RBA 10-year bond yield CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="rba_australian_10y_bond_yield.csv",
        mime="text/csv",
    )
    with st.expander("Source and methodology"):
        st.markdown(f"[Official RBA F2 CSV]({RBA_F2}) · [RBA statistical tables]({RBA_TABLE})")
        st.write("Selected series:", description)
        st.write(
            "Monthly and quarterly charts use arithmetic averages of available daily observations. "
            "Yield changes are expressed in basis points (100 bp = 1 percentage point)."
        )
