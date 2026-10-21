"""ABS Labour Force explorer: official observations only; no synthetic data."""
import io
import re
import pandas as pd
import plotly.express as px
import streamlit as st
import requests

API = 'https://data.api.abs.gov.au/rest/data/ABS,LF,all/all'
HEADERS = {'Accept': 'application/vnd.sdmx.data+csv;urn=true;file=true;labels=both', 'User-Agent': 'AustralianMacroTracker/1.0'}

@st.cache_data(ttl=3600, show_spinner=False)
def load_labour_force(start_year, end_year):
    response = requests.get(API, params={'startPeriod':str(start_year),'endPeriod':str(end_year),'format':'csv','dimensionAtObservation':'AllDimensions'}, headers=HEADERS, timeout=(15, 120))
    response.raise_for_status()
    if response.text.lstrip().startswith('<'):
        raise ValueError('ABS returned XML rather than observation CSV.')
    data = pd.read_csv(io.StringIO(response.text), dtype=str, low_memory=False)
    if data.empty:
        raise ValueError('No Labour Force observations returned.')
    return data, response.url

def find_col(df, names):
    for name in names:
        for c in df.columns:
            if c.upper() == name or c.upper().startswith(name + ':'):
                return c
    return None

def series_name(row, cols):
    return ' · '.join(str(row[c]).split(':',1)[-1].strip() for c in cols)

def show_unemployment_dashboard(start_year, end_year):
    st.header('Unemployment & Labour Market')
    st.caption('Source: Australian Bureau of Statistics — Labour Force, Australia (LF). Official series only; seasonal adjustment and population scope are shown explicitly.')
    st.info('The Labour Force dataflow is large. The first request may be slow. Subsequent requests are cached for one hour.')
    try:
        with st.spinner('Loading ABS Labour Force observations…'):
            raw, url = load_labour_force(start_year, end_year)
    except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
        st.error(f'Could not load the ABS Labour Force data: {exc}')
        st.caption('If the ABS changes its dataflow or limits large requests, the query may need a dimension-specific series key.')
        return
    time_col = find_col(raw, ['TIME_PERIOD'])
    value_col = find_col(raw, ['OBS_VALUE'])
    if not time_col or not value_col:
        st.error('ABS response lacks TIME_PERIOD or OBS_VALUE columns.')
        st.write('Returned columns:', list(raw.columns))
        return
    raw['_date'] = pd.to_datetime(raw[time_col].astype(str), errors='coerce')
    raw['_value'] = pd.to_numeric(raw[value_col], errors='coerce')
    raw = raw.dropna(subset=['_date','_value']).copy()
    if raw.empty:
        st.warning('No numeric dated observations found.')
        return
    meta = [c for c in raw.columns if c not in {time_col, value_col, '_date', '_value'} and not c.upper().startswith(('OBS_', 'TIME_', 'UNIT_', 'DECIMALS', 'CONF_', 'OBS '))]
    # Exclude non-dimensional attributes from grouping where possible.
    meta = [c for c in meta if raw[c].nunique(dropna=False) > 1 and raw[c].nunique(dropna=False) < 300]
    with st.expander('ABS series filters', expanded=True):
        st.caption('Choose a consistent geography, adjustment, population group and measure. Do not compare counts with percentages.')
        filter_cols = st.columns(2)
        selected = raw
        for i, col in enumerate(meta):
            values = sorted(selected[col].dropna().astype(str).unique().tolist())
            if len(values) < 2 or len(values) > 150:
                continue
            choice = filter_cols[i % 2].selectbox(col, ['All'] + values, key=f'lf_{i}_{col}')
            if choice != 'All':
                selected = selected[selected[col].astype(str) == choice]
    if selected.empty:
        st.warning('No observations match these filters.')
        return
    # Preserve the actual SDMX dimension combination to avoid silently mixing distinct series.
    group_cols = [c for c in meta if selected[c].nunique(dropna=False) > 1]
    if group_cols:
        series = selected[group_cols].fillna('Unspecified').astype(str).agg(' · '.join, axis=1)
    else:
        series = pd.Series('Selected ABS series', index=selected.index)
    selected = selected.assign(_series=series)
    options = selected['_series'].value_counts().index.tolist()
    st.caption(f'{len(selected):,} observations across {len(options):,} distinct series; {selected["_date"].min():%b %Y}–{selected["_date"].max():%b %Y}')
    if len(options) > 1:
        chosen = st.selectbox('Series to chart', options, key='lf_chart_series')
        selected = selected[selected['_series'] == chosen].copy()
    selected = selected.sort_values('_date').drop_duplicates('_date', keep='last')
    latest = selected.iloc[-1]
    previous = selected.iloc[-2] if len(selected) > 1 else None
    a,b,c = st.columns(3)
    a.metric('Latest observation', f'{latest["_value"]:,.2f}', help='Units depend on the selected official ABS series.')
    b.metric('Observation date', latest['_date'].strftime('%b %Y'))
    c.metric('Change from prior observation', f'{latest["_value"]-previous["_value"]:+,.2f}' if previous is not None else '—', help='Change in the series native units; percentage rates change in percentage points.')
    st.subheader('Historical trend')
    fig = px.line(selected, x='_date', y='_value', template='plotly_dark', labels={'_date':'Date','_value':'Official ABS value'}, title='Selected Labour Force series')
    fig.update_layout(paper_bgcolor='#090F1A', plot_bgcolor='#142235', font_color='#F1F5F9', hovermode='x unified', hoverlabel=dict(bgcolor='#1E293B',font_color='#F8FAFC'))
    fig.update_traces(hovertemplate='%{x|%b %Y}<br>%{y:,.2f}<extra></extra>')
    st.plotly_chart(fig, use_container_width=True)
    st.subheader('Labour market momentum')
    selected['_change'] = selected['_value'].diff()
    selected['_annual_change'] = selected['_value'] - selected.set_index('_date')['_value'].reindex(selected['_date'] - pd.DateOffset(years=1)).to_numpy()
    fig2 = px.bar(selected.dropna(subset=['_change']), x='_date', y='_change', template='plotly_dark', labels={'_date':'Date','_change':'Change (native units)'}, title='Change since previous observation')
    fig2.update_layout(paper_bgcolor='#090F1A', plot_bgcolor='#142235', font_color='#F1F5F9')
    st.plotly_chart(fig2, use_container_width=True)
    st.subheader('Observations & download')
    output = selected[['_date','_value','_change']].rename(columns={'_date':'Date','_value':'ABS value','_change':'Change from previous'})
    st.dataframe(output.sort_values('Date',ascending=False), hide_index=True, use_container_width=True)
    st.download_button('Download selected official series (CSV)', output.to_csv(index=False).encode('utf-8'), file_name='abs_labour_force_selected.csv', mime='text/csv')
    with st.expander('Source and methodology'):
        st.markdown(f'[ABS API request]({url})')
        st.write('The dashboard does not automatically label an arbitrary selected series as unemployment. Select the appropriate unemployment-rate, seasonally adjusted, Australia, persons series using the ABS dimensions above. Counts and rates have different units; change for a rate is in percentage points.')
