"""Australian money-market tracker using free RBA F1 daily data.

Public API: show_money_market_dashboard(start_year=None, end_year=None)
The dashboard never relabels generic bank bill yields as official BBSW/BBSY.
"""
import csv
import io
import re
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

F1_URL = 'https://www.rba.gov.au/statistics/tables/csv/f1-data.csv'
TABLES_URL = 'https://www.rba.gov.au/statistics/tables/'
BG, GRID, TEXT = '#111d2e', '#29394e', '#f1f5f9'
BLUE, CYAN, GREEN, RED, GOLD = '#53b8ff', '#38bdf8', '#22c55e', '#ef5350', '#fbbf24'


def _date(value):
    s = str(value).strip().strip('"')
    for fmt in ('%d-%b-%Y', '%d/%m/%Y', '%Y-%m-%d', '%d %b %Y', '%d-%b-%y'):
        try:
            return pd.Timestamp(datetime.strptime(s, fmt))
        except ValueError:
            continue
    return pd.NaT


def _clean(s):
    return re.sub(r'\s+', ' ', str(s)).strip()


def _metadata_label(rows, header_idx, col):
    labels = []
    for row in rows[:header_idx]:
        if col < len(row):
            cell = _clean(row[col])
            if cell and cell.lower() not in ('series id', 'series', 'frequency', 'units', 'unit', 'source', 'publication date', 'title'):
                labels.append(cell)
    return ' | '.join(dict.fromkeys(labels[-8:]))


def _parse_f1(content):
    rows = list(csv.reader(io.StringIO(content.decode('utf-8-sig', errors='replace'))))
    if not rows:
        raise ValueError('The RBA F1 CSV is empty.')
    # Locate the observation date column from actual rows, independent of metadata width.
    candidates = []
    for idx, row in enumerate(rows[:100]):
        for col, value in enumerate(row[:4]):
            if pd.notna(_date(value)):
                candidates.append((idx, col))
    if not candidates:
        raise ValueError('Could not identify dated observations in RBA F1.')
    date_col = max(set(col for _, col in candidates), key=lambda c: sum(x[1] == c for x in candidates))
    first_data_row = next(i for i, c in candidates if c == date_col)
    width = max(len(row) for row in rows[first_data_row:first_data_row + 15])
    # Metadata often has a row of series identifiers; retain it for auditability.
    id_row = next((row for row in rows[:first_data_row] if any(re.fullmatch(r'F[A-Z0-9]{5,}', _clean(c), re.I) for c in row)), None)
    records = []
    for row in rows[first_data_row:]:
        if len(row) <= date_col:
            continue
        date = _date(row[date_col])
        if pd.isna(date):
            continue
        record = {'Date': date}
        for col in range(width):
            if col == date_col or col >= len(row):
                continue
            raw = _clean(row[col]).replace(',', '')
            try:
                record[col] = float(raw)
            except ValueError:
                continue
        records.append(record)
    if not records:
        raise ValueError('No numeric dated observations were found in RBA F1.')
    frame = pd.DataFrame(records).drop_duplicates('Date', keep='last').sort_values('Date')
    series = []
    for col in frame.columns:
        if col == 'Date' or frame[col].notna().sum() < 10:
            continue
        meta = _metadata_label(rows, first_data_row, col)
        sid = _clean(id_row[col]) if id_row is not None and col < len(id_row) else ''
        series.append({'col': col, 'id': sid, 'label': meta, 'search': (meta + ' ' + sid).lower()})
    return frame, series


@st.cache_data(ttl=3600, show_spinner=False)
def load_money_market_data():
    response = requests.get(F1_URL, timeout=(10, 60), headers={'User-Agent': 'Mozilla/5.0 (AustralianMacroTracker/1.0)'})
    response.raise_for_status()
    return _parse_f1(response.content)


def _kind(s):
    t = s['search']
    if 'bbsy' in t:
        return 'BBSY'
    if 'bbsw' in t or 'bank bill swap' in t:
        return 'BBSW'
    if 'bank' in t and ('bill' in t or 'accepted' in t):
        return 'Bank bill yield'
    if 'cash rate target' in t:
        return 'Cash rate target'
    if ('cash rate' in t or 'interbank overnight' in t) and 'target' not in t:
        return 'Cash rate'
    return None


def _tenor(s):
    t = s['search']
    for n in (1, 2, 3, 4, 5, 6):
        if re.search(rf'(?<!\d){n}\s*[- ]?\s*(?:month|mth|mths|mo)(?!\w)', t):
            return n
    if re.search(r'90\s*[- ]?\s*day', t):
        return 3
    if re.search(r'180\s*[- ]?\s*day', t):
        return 6
    return None


def _style(fig, ytitle='Rate (%)'):
    fig.update_layout(template='plotly_dark', paper_bgcolor=BG, plot_bgcolor=BG,
                      font_color=TEXT, hovermode='x unified',
                      hoverlabel=dict(bgcolor='#162438', font_color=TEXT),
                      margin=dict(l=25, r=20, t=55, b=25),
                      xaxis_title='Date', yaxis_title=ytitle,
                      legend=dict(orientation='h', y=1.13, x=0))
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def show_money_market_dashboard(start_year=None, end_year=None):
    st.header('Australian Money Markets — BBSW & Bank Bill Rates')
    st.caption('Source: Reserve Bank of Australia, Statistical Table F1 (daily). Rates are identified using published source labels.')
    try:
        with st.spinner('Loading official RBA money-market data…'):
            raw, all_series = load_money_market_data()
    except (requests.RequestException, ValueError, csv.Error, UnicodeError) as exc:
        st.error(f'Unable to load RBA Table F1: {exc}')
        st.markdown(f'[View RBA statistical tables]({TABLES_URL})')
        return

    classified = [{**s, 'kind': _kind(s), 'tenor': _tenor(s)} for s in all_series]
    eligible = [s for s in classified if s['kind']]
    if not eligible:
        st.warning('No clearly labelled bank bill, BBSW or cash rate series could be identified in the current F1 CSV. The source layout may have changed.')
        with st.expander('Inspect detected series metadata'):
            st.dataframe(pd.DataFrame(all_series), hide_index=True, use_container_width=True)
        return

    start = int(start_year) if start_year is not None else int(raw['Date'].dt.year.min())
    end = int(end_year) if end_year is not None else int(raw['Date'].dt.year.max())
    df = raw.loc[raw['Date'].dt.year.between(start, end)].copy()
    if df.empty:
        st.warning('No observations in the selected year range.')
        return

    def description(s):
        label = s['label'] or s['id'] or f'RBA column {s["col"]}'
        return f'{s["kind"]} · {s["tenor"]}M · {label}' if s['tenor'] else f'{s["kind"]} · {label}'

    bank = [s for s in eligible if s['kind'] in ('BBSW', 'Bank bill yield', 'BBSY')]
    bank.sort(key=lambda s: (0 if s['kind'] == 'BBSW' else 1 if s['kind'] == 'Bank bill yield' else 2,
                             0 if s['tenor'] == 3 else 1 if s['tenor'] == 6 else 2))
    cash = [s for s in eligible if s['kind'] in ('Cash rate target', 'Cash rate')]
    cash.sort(key=lambda s: 0 if s['kind'] == 'Cash rate target' else 1)
    if not bank:
        st.warning('No bank bill or BBSW series was unambiguously identified. Inspect RBA metadata below before using any series.')
        with st.expander('Inspect detected series metadata'):
            st.dataframe(pd.DataFrame(all_series), hide_index=True, use_container_width=True)
        return

    choices = {f'{description(s)} [{s["id"] or s["col"]}]': s for s in bank}
    selected = st.selectbox('Money-market series', list(choices), key='money_market_series')
    chosen = choices[selected]
    compare_options = {'None': None}
    compare_options.update({f'{description(s)} [{s["id"] or s["col"]}]': s for s in bank if s['col'] != chosen['col']})
    if cash:
        s = cash[0]
        compare_options[f'{description(s)} [{s["id"] or s["col"]}]'] = s
    comparison_default = next((i for i, (k, s) in enumerate(compare_options.items()) if s is not None and s['kind'].startswith('Cash rate')), 0)
    comparison = st.selectbox('Compare against', list(compare_options), index=comparison_default, key='money_market_comparison')
    second = compare_options[comparison]
    frequency = st.selectbox('Chart frequency', ['Daily', 'Monthly average', 'Quarterly average'], key='money_market_frequency')

    columns = ['Date', chosen['col']] + ([second['col']] if second is not None else [])
    plot = df[columns].copy().rename(columns={chosen['col']: 'Primary', **({second['col']: 'Comparison'} if second else {})})
    plot = plot.dropna(subset=['Primary'])
    if plot.empty:
        st.warning('The selected series has no observations in this date range.')
        return
    latest = plot.iloc[-1]
    previous = plot.iloc[-2] if len(plot) > 1 else None
    delta = (latest['Primary'] - previous['Primary']) * 100 if previous is not None else None
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Latest rate', f'{latest["Primary"]:.3f}%')
    c2.metric('Observation date', latest['Date'].strftime('%d %b %Y'))
    c3.metric('Change from previous', f'{delta:+.1f} bp' if delta is not None else '—')
    c4.metric('Period high / low', f'{plot["Primary"].max():.2f}% / {plot["Primary"].min():.2f}%')

    st.info(f'**Series classification:** {chosen["kind"]}. ' +
            ('This is identified as BBSW in the RBA metadata.' if chosen['kind'] == 'BBSW' else
             'This is not labelled as an official BBSW fixing. Do not use it as a contractual BBSW/BBSY rate.'), icon='ℹ️')
    chart = plot.set_index('Date')
    if frequency == 'Monthly average':
        chart = chart.resample('MS').mean()
    elif frequency == 'Quarterly average':
        chart = chart.resample('QS').mean()
    chart = chart.reset_index()

    st.subheader('Historical money-market rates')
    trend = go.Figure()
    trend.add_trace(go.Scatter(x=chart['Date'], y=chart['Primary'], mode='lines', name=chosen['kind'], line=dict(color=BLUE, width=2.5)))
    if second is not None:
        trend.add_trace(go.Scatter(x=chart['Date'], y=chart['Comparison'], mode='lines', name=second['kind'], line=dict(color=GOLD, width=2)))
    trend.update_layout(title='Short-term interest rates')
    st.plotly_chart(_style(trend), use_container_width=True)

    st.subheader('Rate momentum')
    movement = chart[['Date', 'Primary']].copy()
    movement['Change (bp)'] = movement['Primary'].diff() * 100
    movement = movement.dropna()
    bars = go.Figure(go.Bar(x=movement['Date'], y=movement['Change (bp)'],
                            marker_color=[GREEN if x >= 0 else RED for x in movement['Change (bp)']],
                            hovertemplate='%{x|%d %b %Y}<br>%{y:+.2f} bp<extra></extra>'))
    bars.update_layout(title='Change between displayed observations', showlegend=False)
    st.plotly_chart(_style(bars, 'Change (bp)'), use_container_width=True)

    if second is not None:
        spread = chart[['Date', 'Primary', 'Comparison']].dropna().copy()
        if not spread.empty:
            spread['Spread (bp)'] = (spread['Primary'] - spread['Comparison']) * 100
            st.subheader('Interest-rate spread')
            fig = go.Figure(go.Scatter(x=spread['Date'], y=spread['Spread (bp)'], mode='lines',
                                       line=dict(color=CYAN, width=2.3), name='Spread'))
            fig.update_layout(title='Selected rate minus comparison rate')
            st.plotly_chart(_style(fig, 'Spread (bp)'), use_container_width=True)

    st.subheader('Macroeconomic interpretation')
    st.markdown('Bank bill rates reflect short-term wholesale funding conditions and are influenced by cash-rate expectations, bank credit and liquidity premia. A widening bank bill–cash rate spread may indicate changes in funding premia, but the spread alone does not identify a cause. **BBSY is not inferred from BBSW or bank bill yields.**')
    with st.expander('View official RBA observations', expanded=False):
        display = plot.copy().sort_values('Date', ascending=False)
        display['Date'] = display['Date'].dt.strftime('%d %b %Y')
        st.dataframe(display, hide_index=True, use_container_width=True)
    st.download_button('Download selected RBA money-market observations',
                       data=plot.to_csv(index=False).encode('utf-8'),
                       file_name='rba_money_market_rates.csv', mime='text/csv')
    with st.expander('Source and methodology'):
        st.markdown(f'[Official RBA F1 CSV]({F1_URL}) · [RBA statistical tables]({TABLES_URL})')
        st.write('Primary source label:', chosen['label'])
        st.write('Primary series identifier:', chosen['id'] or 'Not identified')
        st.write('Monthly and quarterly rates are arithmetic averages of available daily values. Spreads and changes are shown in basis points.')
        st.write('BBSW and BBSY are not interchangeable. The dashboard does not calculate or estimate BBSY.')
        with st.expander('Inspect detected source series'):
            st.dataframe(pd.DataFrame(eligible)[['id', 'kind', 'tenor', 'label']], hide_index=True, use_container_width=True)
