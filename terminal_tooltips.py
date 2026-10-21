"""Shared financial-terminal hover styling for all Streamlit Plotly charts."""
import datetime as dt
import re
import pandas as pd
import streamlit as st

_ORIGINAL = st.plotly_chart


def _date_axis(values):
    if values is None:
        return False
    try:
        first = next((v for v in values if v is not None and not pd.isna(v)), None)
    except (TypeError, ValueError):
        return False
    return isinstance(first, (dt.date, dt.datetime, pd.Timestamp)) or (
        hasattr(first, 'dtype') and 'datetime' in str(first.dtype)
    )


def _unit(trace, fig):
    name = str(getattr(trace, 'name', '') or '')
    axis = str(getattr(trace, 'yaxis', '') or 'y')
    ax = fig.layout.yaxis2 if axis == 'y2' else fig.layout.yaxis
    label = str(getattr(getattr(ax, 'title', None), 'text', '') or '')
    title = str(getattr(getattr(fig.layout, 'title', None), 'text', '') or '')
    context = ' '.join((name, label, title)).lower()
    if re.search(r'\b(pp|percentage points?|contribution pp)\b', context):
        return 'pp'
    if '%' in context or re.search(r'\b(inflation|cash rate|interest rate|growth|annual change|unemployment|yield|wages less cpi|share)\b', context):
        return '%'
    if re.search(r'\b(index|indexed|base\s*=\s*100)\b', context):
        return 'index'
    return ''


def apply_terminal_tooltips(fig):
    """Mutate a figure's hover presentation without changing its underlying observations."""
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#101a2a',
        plot_bgcolor='#101a2a',
        font=dict(family='Arial, sans-serif', color='#cbd5e1', size=12),
        colorway=['#55b8ff','#f7b955','#42d9b3','#b59aff','#fa7f84','#9bd15b'],
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='#1E293B',
            bordercolor='#334155',
            font=dict(family='Arial, sans-serif', size=13, color='#F8FAFC'),
            namelength=-1,
            align='left',
        ),
    )
    fig.update_xaxes(hoverformat='%b %Y', gridcolor='#26384d', zerolinecolor='#34475f', linecolor='#34475f')
    fig.update_yaxes(gridcolor='#26384d', zerolinecolor='#34475f', linecolor='#34475f')
    fig.update_layout(legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#cbd5e1'))) 
    for trace in fig.data:
        kind = getattr(trace, 'type', '')
        if kind not in ('scatter', 'bar', 'scattergl', 'histogram', 'heatmap'):
            continue
        # Heatmaps need z and categorical labels; never format their values as y.
        if kind == 'heatmap':
            trace.hovertemplate = '<b>%{y}</b><br>%{x}<br><b>%{z:.2f}</b><extra></extra>'
            continue
        horizontal = kind == 'bar' and getattr(trace, 'orientation', None) == 'h'
        values = getattr(trace, 'y' if horizontal else 'x', None)
        period = '%{y}' if horizontal else ('%{x|%b %Y}' if _date_axis(values) else '%{x}')
        value = '%{x:,.2f}' if horizontal else '%{y:,.2f}'
        unit = _unit(trace, fig)
        suffix = '%' if unit == '%' else (' pp' if unit == 'pp' else '')
        series_name = str(getattr(trace, 'name', '') or '')
        if not series_name or series_name.lower() in ('_value', '_plot_value', 'wide_variable', 'trace 0'):
            series_name = str(getattr(getattr(fig.layout, 'title', None), 'text', '') or 'Observation')
        # Plotly's unified hover displays the series name separately, so keep only
        # the formatted observation in each row to avoid duplicate labels.
        trace.hovertemplate = f'<b>{value}{suffix}</b><extra>{series_name}</extra>'
        # Unified hover header is the observation period, controlled by xaxis.hoverformat.
        if horizontal:
            trace.hovertemplate = f'<b>{period}</b> · {value}{suffix}<extra>{series_name}</extra>'
    return fig


def plotly_chart(fig, *args, **kwargs):
    return _ORIGINAL(apply_terminal_tooltips(fig), *args, **kwargs)


def install():
    """Install once so both app.py and macro_research.py share identical tooltips."""
    if st.plotly_chart is not plotly_chart:
        st.plotly_chart = plotly_chart
