"""Australian 10-year government bond yield tracker (RBA statistical table F2)."""
import io
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

RBA_F2 = 'https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
RBA_TABLE = 'https://www.rba.gov.au/statistics/tables/'


def _parse_rba_f2(content):
    """Locate the nominal Australian Government 10-year bond column by metadata.

    The RBA CSV contains descriptive rows above the dated observations. Never
    choose a numeric column by position or silently substitute an indexed bond.
    """
    raw = pd.read_csv(io.BytesIO(content), header=None, dtype=str, encoding='utf-8-sig',
                      on_bad_lines='skip', engine='python')
    if raw.empty or raw.shape[1] < 2:
        raise ValueError('RBA F2 CSV has no usable observations.')
    first = raw.iloc[:, 0].fillna('').astype(str).str.strip()
    dates = pd.to_datetime(first, format='%d-%b-%Y', errors='coerce')
    if dates.notna().sum() < 5:
        dates = pd.to_datetime(first, dayfirst=True, errors='coerce')
    date_rows = dates.notna()
    if date_rows.sum() < 5:
        raise ValueError('Could not identify dated observations in RBA F2 CSV.')
    first_date_row = date_rows[date_rows].index[0]
    metadata = raw.iloc[:first_date_row].fillna('').astype(str)
    candidates = []
    for col in range(1, raw.shape[1]):
        labels = [re.sub(r'\s+', ' ', v.strip()).lower() for v in metadata.iloc[:, col].tolist() if v.strip()]
        descriptions = [s for s in labels if ('10 year' in s or '10-year' in s or '10 yr' in s or '10yr' in s)]
        nominal = [s for s in descriptions if ('australian government' in s or 'commonwealth government' in s)]
        nominal = [s for s in nominal if not any(w in s for w in ('indexed', 'inflation', 'real yield', 'semi-government'))]
        if nominal:
            candidates.append((col, nominal[0], labels))
    if len(candidates) != 1:
        raise ValueError(f'Could not uniquely identify the nominal Australian Government 10-year bond yield in RBA F2 (matches: {len(candidates)}).')
    col, description, labels = candidates[0]
    values = pd.to_numeric(raw.iloc[:, col].astype(str).str.replace(',', '', regex=False), errors='coerce')
    out = pd.DataFrame({'Date': dates, 'Yield (%)': values})
    out = out.loc[date_rows].dropna().sort_values('Date').drop_duplicates('Date', keep='last')
    if out.empty:
        raise ValueError('The identified RBA bond yield series has no numeric values.')
    return out.reset_index(drop=True), description


@st.cache_data(ttl=3600, show_spinner=False)
def load_bond_yield():
    response = requests.get(RBA_F2, timeout=(12, 60), headers={'User-Agent': 'AustralianMacroTracker/1.0'})
    response.raise_for_status()
    return _parse_rba_f2(response.content)


def _chart(fig):
    fig.update_layout(template='plotly_dark', paper_bgcolor='#111d2e', plot_bgcolor='#111d2e',
                      font_color='#f1f5f9', hovermode='x unified',
                      hoverlabel=dict(bgcolor='#162438', font_color='#f8fafc'))
    fig.update_xaxes(gridcolor='#29394e')
    fig.update_yaxes(gridcolor='#29394e')
    return fig


def show_bond_dashboard(start_year, end_year):
    st.header('Australian 10-Year Government Bond Yield')
    st.caption('Source: Reserve Bank of Australia (RBA), Statistical Table F2 — nominal Australian Government 10-year bond yield. Daily observations, published weekly.')
    try:
        with st.spinner('Loading official RBA government bond yields…'):
            all_data, description = load_bond_yield()
    except (requests.RequestException, ValueError, pd.errors.ParserError) as exc:
        st.error(f'Unable to load the RBA 10-year government bond yield: {exc}')
        st.markdown(f'[View RBA statistical tables]({RBA_TABLE})')
        return
    df = all_data.loc[all_data['Date'].dt.year.between(int(start_year), int(end_year))].copy()
    if df.empty:
        st.warning('No published observations in the selected year range.')
        return
    frequency = st.selectbox('Chart frequency', ['Daily (published weekly)', 'Monthly average', 'Quarterly average'], index=0, key='bond_frequency')
    if frequency == 'Monthly average':
        plot = df.set_index('Date').resample('MS')['Yield (%)'].mean().dropna().reset_index()
    elif frequency == 'Quarterly average':
        plot = df.set_index('Date').resample('QS')['Yield (%)'].mean().dropna().reset_index()
    else:
        plot = df.copy()
    latest = df.iloc[-1]
    previous = df.iloc[-2] if len(df) > 1 else None
    change_bp = (latest['Yield (%)'] - previous['Yield (%)']) * 100 if previous is not None else None
    m1, m2, m3, m4 = st.columns(4)
    m1.metric('10-year bond yield', f"{latest['Yield (%)']:.2f}%", help='Latest available observation in selected date range')
    m2.metric('Observation date', latest['Date'].strftime('%d %b %Y'))
    m3.metric('Change from previous', f'{change_bp:+.1f} bp' if change_bp is not None else '—', help='Basis points; 100 bp = 1 percentage point')
    m4.metric('Range high / low', f"{df['Yield (%)'].max():.2f}% / {df['Yield (%)'].min():.2f}%")
    st.subheader('Historical yield trend')
    fig = px.line(plot, x='Date', y='Yield (%)', title='Australian Government 10-year nominal yield')
    fig.update_traces(line_color='#53b8ff', hovertemplate='%{x|%d %b %Y}: %{y:.2f}%<extra></extra>')
    st.plotly_chart(_chart(fig), use_container_width=True)
    st.subheader('Bond yield momentum')
    momentum = plot.copy()
    momentum['Change (bp)'] = momentum['Yield (%)'].diff() * 100
    fig2 = px.bar(momentum.dropna(), x='Date', y='Change (bp)', title='Change between displayed observations (basis points)')
    st.plotly_chart(_chart(fig2), use_container_width=True)
    st.subheader('Yield distribution')
    fig3 = px.histogram(df, x='Yield (%)', nbins=35, title='Distribution of published yields in selected period')
    st.plotly_chart(_chart(fig3), use_container_width=True)
    st.subheader('Macro interpretation')
    st.markdown('A rising 10-year yield can reflect higher expected policy rates, inflation expectations or term premia; a falling yield can reflect the reverse. **The yield alone does not identify the cause.** Bond prices generally move inversely to yields, and a 10-year yield is not the same as the RBA cash rate.')
    st.subheader('Official observations')
    st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True, hide_index=True)
    st.download_button('Download RBA bond yield CSV', df.to_csv(index=False).encode('utf-8'),
                       file_name='rba_australian_10y_government_bond_yield.csv', mime='text/csv')
    with st.expander('Source and methodology'):
        st.markdown(f'[RBA F2 CSV data]({RBA_F2}) · [RBA statistical tables]({RBA_TABLE})')
        st.write('Selected official series:', description)
        st.write('Daily yield observations are published in RBA F2 weekly. Monthly and quarterly views are arithmetic averages of available daily observations in the selected window. Changes are in basis points, not percentage changes. RBA may revise or withdraw data.')
