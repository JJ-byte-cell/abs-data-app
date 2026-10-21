"""Headline Australian CPI forecasting from a single consistent ABS All Groups index series."""
import warnings
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from statsmodels.tsa.statespace.sarimax import SARIMAX

BG = '#111d2e'
BLUE = '#53b8ff'
GREEN = '#22c55e'


def _clean_headline(cpi):
    data = cpi.loc[cpi['Group'].isin(['All groups CPI', 'All groups']), ['_DATE', '_VALUE']].copy()
    data['_DATE'] = pd.to_datetime(data['_DATE'])
    data['_VALUE'] = pd.to_numeric(data['_VALUE'], errors='coerce')
    data = data.dropna().drop_duplicates('_DATE').sort_values('_DATE')
    data = data.loc[data['_VALUE'] > 0]
    freq = cpi.attrs.get('frequency', 'Quarterly')
    period_code = 'M' if freq == 'Monthly' else 'Q'
    periods = data['_DATE'].dt.to_period(period_code)
    if periods.duplicated().any():
        raise ValueError('Multiple headline index values for the same CPI period.')
    values = pd.Series(data['_VALUE'].to_numpy(dtype=float), index=pd.PeriodIndex(periods, freq=period_code))
    values = values.asfreq(period_code)
    if values.isna().any():
        raise ValueError('Missing CPI periods in the index history. Extend or correct the ABS series before forecasting.')
    return values, (12 if period_code == 'M' else 4), freq


def _model(values, horizon):
    # Log index keeps central forecast strictly positive. Lightweight baseline for Streamlit.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        fitted = SARIMAX(np.log(values), order=(1, 1, 1), trend='n',
                         enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=75)
        prediction = fitted.get_forecast(steps=horizon)
    mean = np.exp(prediction.predicted_mean)
    bands = {}
    for level in (0.8, 0.95):
        ci = np.exp(prediction.conf_int(alpha=1-level))
        bands[level] = (ci.iloc[:, 0], ci.iloc[:, 1])
    return mean, bands


@st.cache_data(ttl=3600, show_spinner=False)
def _forecast_cached(values, horizon):
    return _model(values, horizon)


def _yoy(forecast, observed, lag):
    combined = pd.concat([observed, forecast])
    result = []
    for p, value in forecast.items():
        prior = combined.get(p-lag, np.nan)
        result.append((value/prior-1)*100 if pd.notna(prior) and prior > 0 else np.nan)
    return pd.Series(result, index=forecast.index)


def _backtest(values, lag, steps, windows=8):
    # One-step rolling-origin evaluation, no future observations in training.
    results = []
    minimum = max(24, lag*5)
    for end in range(max(minimum, len(values)-windows), len(values)):
        if end >= len(values):
            break
        try:
            forecast, _ = _model(values.iloc[:end], 1)
            prior = values.get(values.index[end]-lag, np.nan)
            if pd.isna(prior):
                continue
            predicted = (float(forecast.iloc[0])/prior-1)*100
            actual = (float(values.iloc[end])/prior-1)*100
            baseline = (float(values.iloc[end-1])/prior-1)*100
            results.append((predicted, actual, baseline))
        except Exception:
            continue
    return results


def show_cpi_forecasting(cpi):
    st.subheader('Headline CPI forecasting laboratory')
    st.caption('Statistical forecasts, not ABS or RBA forecasts. Based on the selected Australian All Groups CPI index.')
    try:
        values, lag, freq = _clean_headline(cpi)
    except ValueError as exc:
        st.warning(str(exc))
        return
    if len(values) < max(30, lag*6):
        st.info('At least 30 consecutive CPI index observations (and six years for monthly data) are required. Increase the start year or choose quarterly CPI.')
        return
    options = {'3 months':3, '6 months':6, '12 months':12} if lag == 12 else {'1 quarter (3 months)':1, '2 quarters (6 months)':2, '4 quarters (12 months)':4}
    horizon_label = st.selectbox('Forecast horizon', list(options), index=1, key='headline_cpi_forecast_horizon')
    horizon = options[horizon_label]
    st.caption(f'Model: ARIMA(1,1,1) on log CPI index · {freq.lower()} observations · {len(values)} data points. Forecast bands are model-based, not guarantees.')
    try:
        with st.spinner('Fitting headline CPI forecast…'):
            predicted, bands = _forecast_cached(values, horizon)
    except Exception as exc:
        st.warning(f'Forecast could not be fitted to this series: {exc}')
        return
    central = _yoy(predicted, values, lag)
    low80 = _yoy(bands[0.8][0], values, lag)
    high80 = _yoy(bands[0.8][1], values, lag)
    low95 = _yoy(bands[0.95][0], values, lag)
    high95 = _yoy(bands[0.95][1], values, lag)
    actual = (values / values.shift(lag)-1)*100
    hist = actual.dropna().tail(50)
    to_date = lambda idx: idx.to_timestamp(how='end').normalize()
    fig = go.Figure()
    xfuture = to_date(predicted.index)
    fig.add_trace(go.Scatter(x=xfuture, y=high95, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=xfuture, y=low95, mode='lines', fill='tonexty', fillcolor='rgba(83,184,255,0.12)', line=dict(width=0), name='95% interval', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=xfuture, y=high80, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=xfuture, y=low80, mode='lines', fill='tonexty', fillcolor='rgba(83,184,255,0.25)', line=dict(width=0), name='80% interval', hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=to_date(hist.index), y=hist, mode='lines', line=dict(color=BLUE, width=2.5), name='Actual annual CPI'))
    fig.add_trace(go.Scatter(x=[to_date(hist.index[-1]), *xfuture], y=[hist.iloc[-1], *central], mode='lines+markers', line=dict(color=GREEN, width=2.5, dash='dash'), name='Forecast annual CPI'))
    fig.update_layout(template='plotly_dark', paper_bgcolor=BG, plot_bgcolor=BG, font_color='#f1f5f9',
                      title='Australian headline CPI — annual inflation (%)', yaxis_title='Annual inflation (%)',
                      xaxis_title='Observation period', hovermode='x unified', margin=dict(l=20,r=20,t=55,b=25))
    fig.update_xaxes(gridcolor='#29394e')
    fig.update_yaxes(gridcolor='#29394e')
    if pd.notna(central.iloc[-1]):
        st.metric(f'Forecast annual CPI · {str(predicted.index[-1])}', f'{central.iloc[-1]:.2f}%')
    st.plotly_chart(fig, use_container_width=True)
    table = pd.DataFrame({'Period':[str(x) for x in predicted.index], 'Forecast CPI index':predicted.values,
                          'Annual CPI forecast (%)':central.values, '80% lower (%)':low80.values,
                          '80% upper (%)':high80.values, '95% lower (%)':low95.values, '95% upper (%)':high95.values})
    with st.expander('Forecast observations and download', expanded=False):
        st.dataframe(table.round(2), use_container_width=True, hide_index=True)
        st.download_button('Download CPI forecast CSV', table.to_csv(index=False).encode('utf-8'),
                           file_name='australian_headline_cpi_forecast.csv', mime='text/csv')
    with st.expander('Historical forecast accuracy', expanded=False):
        if st.button('Run rolling-origin backtest', key='cpi_forecast_backtest'):
            with st.spinner('Testing past one-period forecasts…'):
                errors = _backtest(values, lag, horizon)
            if len(errors) < 3:
                st.info('Insufficient successful historical backtest windows.')
            else:
                test = np.array(errors)
                model_mae = np.mean(np.abs(test[:,0]-test[:,1]))
                baseline_mae = np.mean(np.abs(test[:,2]-test[:,1]))
                a,b = st.columns(2)
                a.metric('Model MAE (percentage points)', f'{model_mae:.2f}')
                b.metric('Simple baseline MAE (percentage points)', f'{baseline_mae:.2f}')
                st.caption(f'{len(errors)} one-period-ahead rolling-origin tests. Baseline assumes next CPI index equals the most recent observed index. Backtest does not validate multi-period intervals.')
    st.caption('Uncertainty intervals are transformed from model CPI-index intervals. CPI revisions, structural breaks and forecast model misspecification can materially affect results.')
