"""Cash-rate research suite. No future-data leakage: external macro observations need release dates."""
import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

RATE = 'Cash rate target (%)'
FEATURES = ['Trimmed CPI (%)', 'Headline CPI (%)', 'Unemployment (%)', 'Wages growth (%)', 'GDP growth (%)', '90-day bank bill (%)', '10-year bond yield (%)']

def monthly_rates(decisions):
    s = decisions.set_index('Date')[RATE].sort_index()
    end = pd.Timestamp.now(tz='Australia/Brisbane').tz_localize(None).to_period('M').to_timestamp('M')
    idx = pd.date_range(s.index.min().to_period('M').to_timestamp('M'), end, freq='ME')
    # As-of lookup: a policy decision in a month only affects month-end after its effective date.
    values = s.reindex(s.index.union(idx)).sort_index().ffill().reindex(idx)
    return values.dropna().rename('rate')

def read_macro(file):
    if file is None: return pd.DataFrame(columns=['Release date','Observation date']+FEATURES)
    df = pd.read_csv(file)
    if not {'Release date','Observation date'}.issubset(df.columns):
        raise ValueError('Macro CSV must contain Release date and Observation date columns.')
    cols = [c for c in FEATURES if c in df.columns]
    if not cols: raise ValueError('Macro CSV must include at least one recognised indicator column.')
    for c in ['Release date','Observation date']: df[c] = pd.to_datetime(df[c], errors='coerce', dayfirst=False)
    for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['Release date','Observation date']).sort_values('Release date')
    df = df.loc[df['Observation date'] <= df['Release date']]
    return df[['Release date','Observation date']+cols].copy()

def asof_features(origin, macro):
    out = {}
    eligible = macro.loc[macro['Release date'] <= origin] if not macro.empty else macro
    for col in FEATURES:
        if col not in eligible: continue
        rows = eligible.dropna(subset=[col]).sort_values(['Observation date','Release date'])
        if not rows.empty:
            # Latest observation available as of origin; latest release wins on revisions.
            obs = rows['Observation date'].max()
            out[col] = float(rows.loc[rows['Observation date'] == obs].iloc[-1][col])
    return out

def make_features(rates, macro):
    records = []
    for i in range(12, len(rates)):
        date = rates.index[i]
        row = {'Date': date, 'rate': float(rates.iloc[i]), 'lag1':float(rates.iloc[i-1]),
               'lag3':float(rates.iloc[i-3]), 'lag6':float(rates.iloc[i-6]),
               'lag12':float(rates.iloc[i-12]), 'change3':float(rates.iloc[i]-rates.iloc[i-3]),
               'change12':float(rates.iloc[i]-rates.iloc[i-12])}
        row.update(asof_features(date, macro))
        records.append(row)
    return pd.DataFrame(records).set_index('Date')

def xgb_predict(frame, rates, origin, horizon, min_train=60):
    """Direct horizon model; training labels are strictly observable by origin."""
    target = rates.shift(-horizon).rename('target')
    joined = frame.join(target).loc[lambda x: x.index <= origin - pd.offsets.MonthEnd(horizon)]
    cols = [c for c in frame.columns if c != 'rate' and frame[c].notna().sum() >= 36]
    joined = joined.dropna(subset=['target'])
    if len(joined) < min_train or not cols: return np.nan
    model = XGBRegressor(n_estimators=110, max_depth=2, learning_rate=0.045,
                         subsample=0.9, colsample_bytree=0.9, objective='reg:squarederror',
                         random_state=42, n_jobs=1)
    model.fit(joined[cols], joined['target'])
    if origin not in frame.index: return np.nan
    return max(0., float(model.predict(frame.loc[[origin], cols])[0]))

def taylor_rule(origin, macro):
    x = asof_features(origin, macro)
    pi = x.get('Trimmed CPI (%)', x.get('Headline CPI (%)'))
    u = x.get('Unemployment (%)')
    if pi is None or u is None: return np.nan
    # Illustrative policy-rule benchmark, not an RBA reaction-function estimate.
    return max(0., 2.5 + pi + .5*(pi-2.5) - 1.0*(u-4.5))

def arima_prediction(history, horizon):
    if len(history) < 36: return np.nan
    try:
        fit = ARIMA(history.to_numpy(), order=(1,1,0), trend='n').fit()
        return max(0., float(fit.forecast(horizon)[-1]))
    except (ValueError, np.linalg.LinAlgError): return np.nan

def backtest(rates, macro, horizon, n_origins, stride):
    frame = make_features(rates, macro)
    candidates = frame.index[(frame.index >= rates.index[0] + pd.DateOffset(years=6)) &
                             (frame.index <= rates.index[-1] - pd.offsets.MonthEnd(horizon))]
    origins = list(candidates[::stride])[-n_origins:]
    rows = []
    for date in origins:
        actual = float(rates.loc[date + pd.offsets.MonthEnd(horizon)])
        history = rates.loc[:date]
        vals = {'Origin':date, 'Target date':date + pd.offsets.MonthEnd(horizon), 'Actual':actual,
                'Unchanged rate':float(history.iloc[-1]),
                'ARIMA':arima_prediction(history, horizon),
                'XGBoost':xgb_predict(frame, rates, date, horizon),
                'Taylor rule':taylor_rule(date, macro)}
        rows.append(vals)
    return pd.DataFrame(rows)

def professional_csv(file):
    if file is None: return pd.DataFrame()
    df = pd.read_csv(file)
    required = {'Firm','Forecast issued','Target date','Forecast rate (%)'}
    if not required.issubset(df): raise ValueError('Professional CSV requires: '+', '.join(sorted(required)))
    for c in ['Forecast issued','Target date']: df[c] = pd.to_datetime(df[c], errors='coerce')
    df['Forecast rate (%)'] = pd.to_numeric(df['Forecast rate (%)'], errors='coerce')
    df = df.dropna(subset=['Firm','Forecast issued','Target date','Forecast rate (%)'])
    return df.loc[df['Target date'] > df['Forecast issued']].copy()

def show_suite(decisions):
    st.divider()
    st.header('Monetary policy forecasting suite')
    st.caption('Research models, not RBA forecasts. Historical macro backtests require release-dated vintages; current revised observations must not be backfilled into earlier forecasts.')
    with st.expander('Data inputs and methodology', expanded=False):
        st.markdown('**Macro CSV:** `Release date,Observation date,Trimmed CPI (%),Headline CPI (%),Unemployment (%),Wages growth (%),GDP growth (%),90-day bank bill (%),10-year bond yield (%)`. Each row may populate one or several indicators. Record the publication date for each observation/revision. Missing data stays missing; no fabricated macro history.')
        st.markdown('**Professional forecasts CSV:** `Firm,Forecast issued,Target date,Forecast rate (%)`. Use forecasts actually published on their issue dates (e.g. bank research or RBA J1). We do not manufacture bank forecasts.')
        st.markdown('XGBoost uses direct horizon-specific targets and lagged cash rates. The Taylor rule uses assumed neutral real rate 2.5%, inflation target 2.5%, unemployment reference 4.5%; these are adjustable research assumptions, **not** an estimated RBA rule. Macro inputs are selected only when their release date is at or before the forecast origin. Monthly backtests use month-end origins, not RBA meeting decisions.')
    a,b = st.columns(2)
    with a: macro_file = st.file_uploader('Release-dated macroeconomic history (CSV)', type='csv', key='suite_macro')
    with b: pro_file = st.file_uploader('Dated professional forecasts (CSV)', type='csv', key='suite_pro')
    try:
        macro = read_macro(macro_file)
        pro = professional_csv(pro_file)
    except (ValueError, pd.errors.ParserError) as e:
        st.error(str(e)); return
    rates = monthly_rates(decisions)
    if len(rates) < 84: st.warning('At least seven years of historical rates are required.'); return
    horizon = st.select_slider('Comparison horizon (months)', options=[3,6,9,12], value=6, key='suite_horizon')
    frame = make_features(rates, macro)
    origin = rates.index[-1]
    with st.spinner('Calculating forecast comparisons...'):
        now = {'Unchanged rate':float(rates.iloc[-1]), 'ARIMA':arima_prediction(rates,horizon),
               'XGBoost':xgb_predict(frame,rates,origin,horizon), 'Taylor rule':taylor_rule(origin,macro)}
    future_date = origin + pd.offsets.MonthEnd(horizon)
    st.subheader('1. Model and professional forecast comparison')
    fig = go.Figure()
    history = rates.tail(36)
    fig.add_trace(go.Scatter(x=history.index,y=history.values,name='Official target',line=dict(color='#38bdf8',width=3)))
    palette = {'Unchanged rate':'#94a3b8','ARIMA':'#fbbf24','XGBoost':'#34d399','Taylor rule':'#f472b6'}
    for name, value in now.items():
        if np.isfinite(value):
            fig.add_trace(go.Scatter(x=[origin,future_date],y=[rates.iloc[-1],value],mode='lines+markers',name=name,
                                     line=dict(color=palette[name],dash='dash')))
    if not pro.empty:
        recent = pro.loc[(pro['Forecast issued'] <= pd.Timestamp.now()) &
                         (pro['Forecast issued'] >= pd.Timestamp.now()-pd.DateOffset(months=9))]
        for firm, rows in recent.groupby('Firm'):
            rows = rows.sort_values(['Target date','Forecast issued']).drop_duplicates('Target date',keep='last')
            fig.add_trace(go.Scatter(x=rows['Target date'],y=rows['Forecast rate (%)'],mode='lines+markers',name=str(firm)))
    fig.update_layout(height=450,title='Historical rate and forward forecasts (issue dates must be verified)',yaxis_title='Cash rate target (%)',hovermode='x unified')
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(pd.DataFrame([{'Model':k,'Forecast month':future_date.strftime('%Y-%m'),'Rate (%)':round(v,3) if np.isfinite(v) else None} for k,v in now.items()]),hide_index=True,use_container_width=True)
    if macro.empty: st.info('No release-dated macro CSV: XGBoost uses only cash-rate lags; Taylor rule is unavailable. Upload macro vintages to enable macro-enhanced comparisons.')
    if pro.empty: st.info('No verified professional forecast CSV uploaded. Bank forecasts are intentionally not invented.')
    st.subheader('2. Walk-forward out-of-sample backtest')
    col1,col2,col3=st.columns(3)
    with col1: count=st.select_slider('Maximum forecast origins',options=[12,24,36,48],value=24,key='suite_count')
    with col2: stride=st.select_slider('Origin spacing (months)',options=[1,2,3,6],value=3,key='suite_stride')
    with col3: run=st.button('Run backtest',type='primary',key='suite_run')
    if run:
        with st.spinner('Running expanding-window backtest; this may take a minute...'):
            st.session_state['suite_bt'] = backtest(rates,macro,horizon,count,stride)
            st.session_state['suite_bt_config'] = (horizon,count,stride,hash(macro.to_csv(index=False)))
    cfg=(horizon,count,stride,hash(macro.to_csv(index=False)))
    bt=st.session_state.get('suite_bt') if st.session_state.get('suite_bt_config')==cfg else None
    if bt is None:
        st.caption('Click Run backtest. Computation is on demand to keep your existing dashboards fast.')
        return
    if bt.empty: st.warning('Not enough history for the selected backtest.'); return
    long=bt.melt(id_vars=['Origin','Target date','Actual'],var_name='Model',value_name='Prediction').dropna(subset=['Prediction'])
    long['Absolute error (pp)']=(long['Prediction']-long['Actual']).abs()
    score=long.groupby('Model').agg(**{'MAE (pp)':('Absolute error (pp)','mean'),'Origins':('Absolute error (pp)','size')}).reset_index().sort_values('MAE (pp)')
    st.caption('Same-origin comparison: models with unavailable predictions are excluded from those origins. Compare common-origin subsets before declaring a winner.')
    fig=go.Figure()
    for name,g in long.groupby('Model'):
        fig.add_trace(go.Scatter(x=g['Target date'],y=g['Absolute error (pp)'],mode='lines+markers',name=name))
    fig.update_layout(title='Out-of-sample absolute forecast error',yaxis_title='Percentage points',height=370)
    st.plotly_chart(fig,use_container_width=True)
    st.subheader('3. Model ranking and backtest audit')
    fig=go.Figure(go.Bar(x=score['Model'],y=score['MAE (pp)'],text=score['MAE (pp)'].round(3),textposition='outside'))
    fig.update_layout(title='Mean absolute error (lower is better)',yaxis_title='Percentage points',height=350)
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(score,hide_index=True,use_container_width=True)
    st.download_button('Download backtest predictions CSV',bt.to_csv(index=False),file_name='cash_rate_backtest.csv',mime='text/csv')
    if not pro.empty:
        # Evaluate professional forecasts only against a target date at/before latest available rate.
        observed=rates.rename('Actual').rename_axis('Target month').reset_index()
        p=pro.copy();p['Target month']=p['Target date'].dt.to_period('M').dt.to_timestamp('M')
        joined=p.merge(observed,on='Target month',how='inner')
        joined=joined.loc[joined['Forecast issued'] < joined['Target month']]
        if not joined.empty:
            joined['Absolute error (pp)']=(joined['Forecast rate (%)']-joined['Actual']).abs()
            st.subheader('4. Archived professional forecast accuracy')
            st.dataframe(joined.groupby('Firm')['Absolute error (pp)'].agg(['mean','count']).rename(columns={'mean':'MAE (pp)','count':'Forecasts'}),use_container_width=True)
            st.caption('Professional forecasts have varying horizons and dates; these scores are descriptive and not directly comparable with the fixed-horizon model backtest.')
