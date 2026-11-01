"""RBA cash-rate target dashboard. Source: official RBA Statistical Table F1 (daily)."""
import io
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from statsmodels.tsa.arima.model import ARIMA

RBA_F1 = 'https://www.rba.gov.au/statistics/tables/csv/f1-data.csv'
SERIES_ID = 'FIRMMCRTD'  # Official daily cash rate TARGET, not actual overnight cash rate


@st.cache_data(ttl=3600, show_spinner=False)
def load_cash_rate_data():
    """Return daily official cash-rate target and successful fetch timestamp (AEST/AEDT)."""
    response = requests.get(RBA_F1, headers={'User-Agent': 'AustralianMacroTracker/1.0'}, timeout=(10, 40))
    response.raise_for_status()
    content = response.content.decode('utf-8-sig', errors='replace')
    # RBA statistical CSVs include descriptive header rows, with the Series ID row
    # identifying columns. Avoid assuming a fixed column position or header offset.
    raw = pd.read_csv(io.StringIO(content), header=None, dtype=str, on_bad_lines='skip', low_memory=False)
    target_col = None
    for i in range(min(30, len(raw))):
        values = raw.iloc[i].fillna('').astype(str).str.strip()
        matching = values[values.eq(SERIES_ID)]
        if not matching.empty:
            target_col = int(matching.index[0])
            break
    if target_col is None:
        raise ValueError(f'RBA F1 did not contain expected series {SERIES_ID}; source format may have changed.')
    dates = pd.to_datetime(raw.iloc[:, 0].astype(str).str.strip(), format='%d-%b-%Y', errors='coerce')
    # Some releases use ISO dates or dd/mm/yyyy.
    if dates.notna().sum() < 50:
        dates = pd.to_datetime(raw.iloc[:, 0].astype(str).str.strip(), dayfirst=True, errors='coerce')
    values = pd.to_numeric(raw.iloc[:, target_col].astype(str).str.replace(',', '', regex=False).str.strip(), errors='coerce')
    result = pd.DataFrame({'Date': dates, 'Cash rate target (%)': values}).dropna()
    result = result.sort_values('Date').drop_duplicates('Date', keep='last')
    if len(result) < 36:
        raise ValueError('Too few valid RBA cash-rate observations; check F1 file format.')
    checked_at = datetime.now(ZoneInfo('Australia/Brisbane')).strftime('%d %b %Y, %I:%M %p AEST')
    return result.reset_index(drop=True), checked_at


@st.cache_data(ttl=3600, show_spinner=False)
def forecast_cash_rate(monthly_values, horizon):
    """ARIMA baseline fitted to month-end policy target; returns point estimates only."""
    series = pd.Series(monthly_values, dtype=float)
    if len(series) < 36:
        raise ValueError('At least 36 months of data are needed for an ARIMA baseline.')
    # Choose order by AIC on available history; keep search small for Streamlit speed.
    best = None
    for order in [(0, 1, 0), (1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 0)]:
        try:
            fitted = ARIMA(series, order=order, trend='n').fit()
            if best is None or fitted.aic < best.aic:
                best = fitted
        except (ValueError, np.linalg.LinAlgError):
            continue
    if best is None:
        raise ValueError('ARIMA model fitting failed for the available history.')
    prediction = best.get_forecast(steps=horizon)
    means = np.maximum(np.asarray(prediction.predicted_mean, dtype=float), 0)
    ci = np.asarray(prediction.conf_int(alpha=0.2), dtype=float)
    return means, np.maximum(ci[:, 0], 0), np.maximum(ci[:, 1], 0), str(best.model.order)


def show_cash_rate_dashboard(start_year, end_year):
    st.subheader('RBA Cash Rate Target & Forecast')
    st.caption('Official RBA Table F1 · Cash rate TARGET (FIRMMCRTD) · Forecasts are statistical estimates, not RBA projections')
    try:
        data, checked_at = load_cash_rate_data()
    except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
        st.error(f'Unable to load official RBA cash-rate data: {exc}')
        st.markdown(f'[Open the official RBA cash rate page](https://www.rba.gov.au/statistics/cash-rate/)')
        return
    latest = data.iloc[-1]
    changes = data.loc[data['Cash rate target (%)'].diff().fillna(0).ne(0)]
    last_change = changes.iloc[-1] if not changes.empty else None
    a, b, c = st.columns(3)
    a.metric('Latest cash rate target', f"{latest['Cash rate target (%)']:.2f}%")
    b.metric('Latest official observation', latest['Date'].strftime('%d %b %Y'))
    c.metric('Last data checked', checked_at)
    if last_change is not None:
        st.caption(f"Most recent change effective {last_change['Date']:%d %b %Y} · Latest published target is not necessarily a new policy decision.")
    history = data.loc[data['Date'].dt.year.between(int(start_year), int(end_year))]
    if history.empty:
        st.warning('No observations in the selected history range. Adjust the sidebar years.')
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=history['Date'], y=history['Cash rate target (%)'], mode='lines', line_shape='hv', name='RBA target', line=dict(color='#38bdf8', width=2.5)))
        fig.update_layout(title='Official cash rate target history', yaxis_title='Per cent', xaxis_title='', height=410, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('#### Statistical forecast · ARIMA baseline')
    horizon = st.select_slider('Forecast horizon (months)', options=[3, 6, 9, 12, 18, 24], value=12, key='cash_rate_horizon')
    training_years = st.select_slider('Training history (years)', options=[5, 10, 15], value=10, key='cash_rate_training')
    monthly = data.set_index('Date')['Cash rate target (%)'].resample('ME').last().ffill()
    monthly = monthly.loc[monthly.index >= monthly.index.max() - pd.DateOffset(years=training_years)]
    try:
        with st.spinner('Fitting cash rate ARIMA model...'):
            point, low, high, order = forecast_cash_rate(tuple(monthly.to_numpy()), horizon)
        future = pd.date_range(monthly.index[-1] + pd.offsets.MonthEnd(1), periods=horizon, freq='ME')
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=monthly.index, y=monthly.values, name='Observed target', line=dict(color='#38bdf8', width=2.5)))
        fig.add_trace(go.Scatter(x=future, y=high, line=dict(width=0), hoverinfo='skip', showlegend=False))
        fig.add_trace(go.Scatter(x=future, y=low, fill='tonexty', fillcolor='rgba(56,189,248,0.15)', line=dict(width=0), name='80% model interval'))
        fig.add_trace(go.Scatter(x=future, y=point, mode='lines+markers', name='ARIMA forecast', line=dict(color='#fbbf24', dash='dash', width=2.5)))
        fig.update_layout(title=f'Cash rate target · {horizon}-month ARIMA forecast {order}', yaxis_title='Per cent', height=430, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
        out = pd.DataFrame({'Month': future.strftime('%Y-%m'), 'Forecast (%)': np.round(point, 3), '80% lower (%)': np.round(low, 3), '80% upper (%)': np.round(high, 3)})
        st.dataframe(out, hide_index=True, use_container_width=True)
        st.download_button('Download forecast CSV', out.to_csv(index=False), file_name='rba_cash_rate_forecast.csv', mime='text/csv')
        st.info('ARIMA is a univariate benchmark, not a policy-decision model. It does not incorporate CPI, unemployment, meeting dates or market expectations. Monthly forecasts may be between typical 0.25-point policy increments. Intervals are model-based and may understate uncertainty.')
    except (ValueError, np.linalg.LinAlgError) as exc:
        st.warning(f'Forecast unavailable: {exc}')
    st.caption('Source: Reserve Bank of Australia, Statistical Table F1. Observation date is the latest published business-day value; checked time updates only after a successful uncached download.')
