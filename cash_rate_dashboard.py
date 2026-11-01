"""RBA cash-rate target dashboard using the official RBA decision history."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup
from statsmodels.tsa.arima.model import ARIMA

RBA_URL = "https://www.rba.gov.au/statistics/cash-rate/"
HEADERS = {"User-Agent": "AustralianMacroTracker/1.0 (economic data research)"}


@st.cache_data(ttl=3600, show_spinner=False)
def load_cash_rate_data():
    """Read the RBA's official effective-date/target table; return observations and fetch time.

    This is a decision-history series, not a daily observation series. Month-end
    values are filled forward only after the earliest published effective date.
    """
    response = requests.get(RBA_URL, headers=HEADERS, timeout=(10, 40))
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    records = []
    # Identify the specific RBA decision table by its column headings rather than
    # depending on a table position, CSS class, or a CSV's metadata row.
    for table in soup.find_all("table"):
        header = " ".join(table.stripped_strings).lower()[:550]
        if not ("effective date" in header and "cash rate target" in header):
            continue
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 3:
                continue
            date_text = cells[0].get_text(" ", strip=True)
            rate_text = cells[2].get_text(" ", strip=True)
            date = pd.to_datetime(date_text, dayfirst=True, errors="coerce")
            match = re.search(r"(?<!\d)(\d{1,2}(?:\.\d+)?)\s*%?", rate_text)
            if pd.notna(date) and match:
                rate = float(match.group(1))
                if 0 <= rate <= 25:
                    records.append((date, rate))
        if records:
            break
    if len(records) < 36:
        raise ValueError(
            "Could not extract enough cash-rate target decisions from the official "
            "RBA table. Its HTML layout may have changed."
        )
    result = pd.DataFrame(records, columns=["Date", "Cash rate target (%)"])
    result = result.sort_values("Date").drop_duplicates("Date", keep="last")
    result = result.loc[result["Date"] <= pd.Timestamp.now().normalize()]
    if len(result) < 36:
        raise ValueError("Too few valid historical decisions after date validation.")
    checked_at = datetime.now(ZoneInfo("Australia/Brisbane")).strftime("%d %b %Y, %I:%M %p AEST")
    return result.reset_index(drop=True), checked_at


@st.cache_data(ttl=3600, show_spinner=False)
def forecast_cash_rate(monthly_values, horizon):
    """Univariate ARIMA benchmark; confidence intervals are model-based."""
    series = pd.Series(monthly_values, dtype=float)
    if len(series) < 36:
        raise ValueError("At least 36 months of cash-rate history are required.")
    best = None
    for order in [(0, 1, 0), (1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 0)]:
        try:
            fitted = ARIMA(series, order=order, trend="n").fit()
            if best is None or fitted.aic < best.aic:
                best = fitted
        except (ValueError, np.linalg.LinAlgError):
            continue
    if best is None:
        raise ValueError("ARIMA model fitting failed for the available history.")
    pred = best.get_forecast(steps=horizon)
    mean = np.maximum(np.asarray(pred.predicted_mean, dtype=float), 0)
    ci = np.asarray(pred.conf_int(alpha=0.2), dtype=float)
    return mean, np.maximum(ci[:, 0], 0), np.maximum(ci[:, 1], 0), str(best.model.order)


def show_cash_rate_dashboard(start_year, end_year):
    st.subheader("RBA Cash Rate Target & Forecast")
    st.caption("Official RBA cash rate target decision history · Forecasts are statistical estimates, not RBA projections")
    if st.button("🔄 Refresh RBA cash-rate data", key="cash_rate_refresh"):
        load_cash_rate_data.clear()
        forecast_cash_rate.clear()
        st.rerun()
    try:
        data, checked_at = load_cash_rate_data()
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Unable to load official RBA cash-rate data: {exc}")
        st.markdown(f"[Open the official RBA cash rate page]({RBA_URL})")
        return

    latest = data.iloc[-1]
    changes = data.loc[data["Cash rate target (%)"].diff().fillna(0).ne(0)]
    last_change = changes.iloc[-1] if not changes.empty else None
    a, b, c = st.columns(3)
    a.metric("Latest cash rate target", f"{latest['Cash rate target (%)']:.2f}%")
    b.metric("Latest published decision", latest["Date"].strftime("%d %b %Y"))
    c.metric("Last data checked", checked_at)
    if last_change is not None:
        st.caption(f"Most recent rate change effective {last_change['Date']:%d %b %Y}. Decision dates are not daily observation dates.")

    history = data.loc[data["Date"].dt.year.between(int(start_year), int(end_year))]
    if history.empty:
        st.warning("No decisions in the selected history range. Adjust the sidebar years.")
    else:
        # Include the immediately preceding target to show the rate at the start
        # of the selected range, even if no decision occurred during that year.
        start = pd.Timestamp(year=int(start_year), month=1, day=1)
        prior = data.loc[data["Date"] < start].tail(1)
        display = pd.concat([prior, history]).drop_duplicates("Date")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=display["Date"], y=display["Cash rate target (%)"],
                                 mode="lines", line_shape="hv", name="RBA target",
                                 line=dict(color="#38bdf8", width=2.5)))
        fig.update_layout(title="Official cash rate target history", yaxis_title="Per cent",
                          xaxis_title="", height=410, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Statistical forecast · ARIMA baseline")
    horizon = st.select_slider("Forecast horizon (months)", options=[3, 6, 9, 12, 18, 24],
                               value=12, key="cash_rate_horizon")
    training_years = st.select_slider("Training history (years)", options=[5, 10, 15],
                                     value=10, key="cash_rate_training")
    # Include the latest known policy target through the current month; do not
    # mistake the last decision date for the latest available business-day observation.
    current_month = pd.Timestamp.now(tz="Australia/Brisbane").tz_localize(None).to_period("M").to_timestamp("M")
    monthly = data.set_index("Date")["Cash rate target (%)"].resample("ME").last()
    monthly = monthly.reindex(pd.date_range(monthly.index.min(), current_month, freq="ME")).ffill()
    monthly = monthly.loc[monthly.index >= monthly.index.max() - pd.DateOffset(years=training_years)]
    try:
        with st.spinner("Fitting cash rate ARIMA model..."):
            point, low, high, order = forecast_cash_rate(tuple(monthly.to_numpy()), horizon)
        future = pd.date_range(monthly.index[-1] + pd.offsets.MonthEnd(1), periods=horizon, freq="ME")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=monthly.index, y=monthly.values, name="Observed target (month-end)",
                                 line=dict(color="#38bdf8", width=2.5)))
        fig.add_trace(go.Scatter(x=future, y=high, line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=future, y=low, fill="tonexty", fillcolor="rgba(56,189,248,0.15)",
                                 line=dict(width=0), name="80% model interval"))
        fig.add_trace(go.Scatter(x=future, y=point, mode="lines+markers", name="ARIMA forecast",
                                 line=dict(color="#fbbf24", dash="dash", width=2.5)))
        fig.update_layout(title=f"Cash rate target · {horizon}-month ARIMA forecast {order}",
                          yaxis_title="Per cent", height=430, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        out = pd.DataFrame({"Month": future.strftime("%Y-%m"), "Forecast (%)": np.round(point, 3),
                            "80% lower (%)": np.round(low, 3), "80% upper (%)": np.round(high, 3)})
        st.dataframe(out, hide_index=True, use_container_width=True)
        st.download_button("Download forecast CSV", out.to_csv(index=False),
                           file_name="rba_cash_rate_forecast.csv", mime="text/csv")
        st.info("ARIMA is a univariate benchmark, not a policy-decision model. It does not incorporate CPI, unemployment, meeting dates or market expectations. Model intervals may understate uncertainty.")
    except (ValueError, np.linalg.LinAlgError) as exc:
        st.warning(f"Forecast unavailable: {exc}")
    st.caption("Source: Reserve Bank of Australia, Cash Rate Target decisions. Latest published decision and last successful download are distinct timestamps.")
