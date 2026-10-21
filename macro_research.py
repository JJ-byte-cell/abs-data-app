"""On-demand macro research views for Australian Macro Tracker.
Data is sourced from ABS SDMX CSV, or user-uploaded official CSV extracts.
No unavailable metric is silently estimated or substituted.
"""
import io
import re
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API = 'https://data.api.abs.gov.au/rest'
FLOW_HINTS = {
    'Labour & Wages': [('Labour Force','LABOUR_FORCE'), ('Wage Price Index','WPI'), ('Job Vacancies','JOB_VACANCIES')],
    'Property': [('Building Approvals','BUILDING_APPROVALS'), ('Building Activity','BUILDING_ACTIVITY'), ('Residential Property Prices (historical)','RES_PROP_INDEX')],
    'Economic Growth': [('National Accounts / GDP','ANA_AGG'), ('Household Spending','MHS')],
    'Monetary Policy': [('Consumer Price Index','CPI')],
    'Inflation Research': [('Consumer Price Index','CPI')],
    'ASX Insights': [('Household Spending','MHS'), ('Consumer Price Index','CPI')],
    'Macro Overview': [('Consumer Price Index','CPI'), ('Labour Force','LABOUR_FORCE')],
}

@st.cache_data(ttl=3600, show_spinner=False, max_entries=18)
def get_abs(flow, start, end):
    r = requests.get(f'{API}/data/ABS,{flow},all/all', params={'startPeriod':str(start),'endPeriod':str(end),'format':'csv','dimensionAtObservation':'AllDimensions'}, headers={'Accept':'application/vnd.sdmx.data+csv;urn=true;file=true;labels=both','User-Agent':'AustralianMacroTracker/2.0'},timeout=(8,45))
    r.raise_for_status()
    if r.text.lstrip().startswith('<'):
        raise ValueError('ABS returned XML instead of CSV')
    df = pd.read_csv(io.BytesIO(r.content),low_memory=False)
    if df.empty: raise ValueError('No observations returned')
    return df

def match(df, key):
    return next((c for c in df if c.upper().split(':')[0].strip()==key), None)

def parse_dates(s):
    x=s.astype(str).str.strip().str.replace(r'^(\d{4})-Q([1-4])$',lambda m: f'{m.group(1)}-{int(m.group(2))*3:02d}-01',regex=True)
    x=x.str.replace(r'^(\d{4})-(\d{2})$',r'\1-\2-01',regex=True)
    return pd.to_datetime(x,errors='coerce')

def tidy(df):
    tc=match(df,'TIME_PERIOD'); vc=match(df,'OBS_VALUE')
    if not tc or not vc: raise ValueError('TIME_PERIOD or OBS_VALUE not present')
    out=df.copy()
    out['_date']=parse_dates(out[tc]);out['_value']=pd.to_numeric(out[vc],errors='coerce')
    out=out.dropna(subset=['_date','_value'])
    return out,tc,vc

def dimension_columns(df,tc,vc):
    exclude={tc,vc,'DATAFLOW','OBS_STATUS','OBS_COMMENT','UNIT_MEASURE','UNIT_MULT','DECIMALS','TIME_FORMAT','OBS_CONF','OBS_PRE_BREAK','OBS_COM','OBS_REV','OBS_FLAG'}
    return [c for c in df if c not in exclude and not c.startswith('_') and df[c].nunique(dropna=True)>1 and df[c].nunique(dropna=True)<3000]

def choose_series(df,tc,vc,namespace):
    """Require one observation per period, with explicit user-controlled dimensions."""
    cols=dimension_columns(df,tc,vc)
    with st.expander('Series selection — choose a consistent ABS series',expanded=True):
        st.caption('ABS dataflows contain multiple measures, regions, frequencies and adjustments. Select one value for each dimension before charting. Do not average incompatible series.')
        for col in cols:
            options=sorted(df[col].dropna().astype(str).unique().tolist())
            if not options:continue
            default=0
            for preferred in ['Australia','Original','Index number','Seasonally adjusted','Quarterly']:
                found=next((i for i,v in enumerate(options) if preferred.lower() in v.lower()),None)
                if found is not None:default=found;break
            chosen=st.selectbox(col,options,index=default,key=f'{namespace}_{col}')
            df=df[df[col].astype(str)==chosen]
    duplicates=df.duplicated('_date',keep=False)
    if duplicates.any():
        distinct=df.groupby('_date')['_value'].nunique()
        if (distinct>1).any():
            st.error('Conflicting observations exist for the same date. Narrow the series selection; no chart has been produced.')
            return None
        df=df.drop_duplicates('_date')
    return df.sort_values('_date')[['_date','_value']]

def chart(s,title,kind='line',unit='ABS-reported value'):
    if s is None or s.empty:
        st.info('No matching observations. Change the selected ABS series or upload a compatible CSV.')
        return
    f=px.bar(s,x='_date',y='_value',title=title) if kind=='bar' else px.line(s,x='_date',y='_value',title=title)
    f.update_layout(template='plotly_white',height=390,margin=dict(l=15,r=15,t=55,b=20),xaxis_title='',yaxis_title=unit,hovermode='x unified')
    f.update_xaxes(range=[s['_date'].min(),s['_date'].max()])
    st.plotly_chart(f,use_container_width=True)
    st.caption(f'Coverage: {s._date.min():%b %Y} – {s._date.max():%b %Y} · {len(s):,} observations · Source: ABS API')

def uploaded_series(key):
    upload=st.file_uploader('Optional official CSV (date and value columns)',type=['csv'],key=key)
    if upload is None:return None
    try:
        d=pd.read_csv(upload)
        dc=st.selectbox('Date column',list(d),key=key+'date')
        vc=st.selectbox('Value column',list(d),index=min(1,len(d.columns)-1),key=key+'value')
        d=d.assign(_date=parse_dates(d[dc]),_value=pd.to_numeric(d[vc],errors='coerce')).dropna(subset=['_date','_value']).sort_values('_date')
        return d[['_date','_value']]
    except Exception as e:
        st.error(f'Could not read uploaded CSV: {e}');return None

def comparison(a,b,name_a,name_b,title,secondary=False):
    if a is None or b is None or a.empty or b.empty:
        st.info('Provide both compatible series to enable this comparison.');return
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=a._date,y=a._value,name=name_a,mode='lines'))
    fig.add_trace(go.Scatter(x=b._date,y=b._value,name=name_b,mode='lines',yaxis='y2' if secondary else 'y'))
    fig.update_layout(title=title,template='plotly_white',height=420,hovermode='x unified',yaxis2=dict(overlaying='y',side='right',showgrid=False) if secondary else None,margin=dict(l=15,r=15,t=55,b=20))
    st.plotly_chart(fig,use_container_width=True)

def research(view):
    st.subheader(view)
    st.caption('Investment research · Official source series where available · No synthetic market data')
    if view=='Macro Overview':
        st.markdown('**Economic dashboard:** Select a source series to examine its trend. A cycle classification requires consistently defined inflation and growth inputs; it is not inferred from missing data.')
    elif view=='Inflation Research':
        st.markdown('**Headline vs trimmed mean · 3m/6m annualised momentum · CPI contributions**')
        st.info('Trimmed-mean inflation and weighted CPI contributions require their respective official measures. Do not calculate contribution by treating category inflation rates as weights.')
    elif view=='Monetary Policy':
        st.markdown('**RBA cash rate vs CPI · ex-post real policy rate**')
        st.caption('The cash rate is an RBA series, not an ABS dataflow. Upload an official RBA CSV and a comparable CPI annual-inflation series below.')
        a=uploaded_series('rba_cash');b=uploaded_series('policy_cpi')
        comparison(a,b,'Cash rate (%)','Annual CPI (%)','Cash rate vs headline CPI')
        if a is not None and b is not None:
            merged=pd.merge_asof(a.sort_values('_date'),b.sort_values('_date'),on='_date',direction='backward',suffixes=('_cash','_cpi'),tolerance=pd.Timedelta(days=100)).dropna()
            if not merged.empty:
                real=merged.assign(_value=merged._value_cash-merged._value_cpi)[['_date','_value']]
                chart(real,'Ex-post real cash rate (cash rate minus annual CPI)',unit='Percentage points')
        return
    elif view=='Property':
        st.markdown('**Housing supply · nominal/real prices · mortgage affordability**')
        st.caption('Building approvals and completions are distinct measures. Select their official series separately; historical ABS property price indexes may be discontinued.')
        with st.expander('Real property price comparison (uploaded index series)'):
            p=uploaded_series('property_price');c=uploaded_series('property_cpi')
            if p is not None and c is not None:
                m=pd.merge_asof(p.sort_values('_date'),c.sort_values('_date'),on='_date',direction='backward',suffixes=('_property','_cpi'),tolerance=pd.Timedelta(days=110)).dropna()
                if len(m)>1 and m._value_cpi.iloc[0] and m._value_property.iloc[0]:
                    real=m.assign(_value=100*(m._value_property/m._value_cpi)/(m._value_property.iloc[0]/m._value_cpi.iloc[0]))[['_date','_value']]
                    chart(real,'Real property price index (first matched period = 100)',unit='Real index')
        with st.expander('Mortgage affordability scenario'):
            price=st.number_input('Property price (AUD)',min_value=10000.,value=800000.,step=10000.)
            deposit=st.slider('Deposit (%)',0,80,20)
            rate=st.slider('Mortgage rate (%)',0.,15.,6.,0.25)
            income=st.number_input('Gross annual household income (AUD)',min_value=1.,value=150000.,step=5000.)
            years=st.slider('Loan term (years)',5,40,30)
            principal=price*(1-deposit/100);r=rate/1200;n=years*12
            payment=principal/n if r==0 else principal*r/(1-(1+r)**(-n))
            st.metric('Estimated monthly principal + interest',f'${payment:,.0f}')
            st.metric('Repayment / gross monthly income',f'{payment/(income/12)*100:.1f}%')
            st.caption('Illustrative only: excludes fees, taxes, insurance, maintenance and household expenses.')
    elif view=='Labour & Wages':
        st.markdown('**Unemployment vs vacancies · real wage growth**')
        with st.expander('Real wages (upload annual WPI and annual CPI inflation series)'):
            w=uploaded_series('wpi_growth');c=uploaded_series('wpi_cpi')
            if w is not None and c is not None:
                m=pd.merge_asof(w.sort_values('_date'),c.sort_values('_date'),on='_date',direction='backward',suffixes=('_wage','_cpi'),tolerance=pd.Timedelta(days=110)).dropna()
                if not m.empty:chart(m.assign(_value=m._value_wage-m._value_cpi)[['_date','_value']],'Approximate real wage growth (WPI annual % minus CPI annual %)',unit='Percentage points')
    elif view=='Economic Growth':
        st.markdown('**GDP growth decomposition · household demand**')
        st.info('GDP contributions should use published ABS percentage-point contribution series, not independently summed growth rates.')
    elif view=='ASX Insights':
        st.markdown('**Retail spending vs sentiment · AUD vs commodities · economic cycle quadrant**')
        st.caption('Sentiment, AUD and commodity prices require additional non-ABS sources. Upload verified series for comparison; charts are descriptive, not investment recommendations.')
        with st.expander('Compare two macro series'):
            a=uploaded_series('asx_macro_a');b=uploaded_series('asx_macro_b')
            comparison(a,b,'Series A','Series B','Macroeconomic comparison',secondary=True)
    choices=FLOW_HINTS[view]
    st.divider()
    st.markdown('#### Explore official ABS data')
    names=[x[0] for x in choices]
    choice=st.selectbox('ABS dataset',names,key='dataset_'+view)
    default_flow=dict(choices)[choice]
    flow=st.text_input('ABS dataflow code (editable if ABS changes identifiers)',value=default_flow,key='flow_'+view)
    c1,c2=st.columns(2)
    with c1:start=st.number_input('From year',min_value=1960,max_value=2100,value=2015,key='start_'+view)
    with c2:end=st.number_input('To year',min_value=1960,max_value=2100,value=2026,key='end_'+view)
    if st.button('Load ABS series',key='load_'+view):st.session_state['loaded_'+view]=(flow,int(start),int(end))
    selection=st.session_state.get('loaded_'+view)
    if selection:
        try:
            with st.spinner('Retrieving ABS observations...'):
                raw=get_abs(*selection)
            st.caption(f'{len(raw):,} rows returned · ABS dataflow: {selection[0]}')
            df,tc,vc=tidy(raw)
            if df.empty:st.warning('No valid numeric observations');return
            s=choose_series(df,tc,vc,view)
            chart(s,choice)
            if s is not None:
                st.download_button('Download selected observations',s.to_csv(index=False).encode(),file_name=f'{selection[0]}_series.csv',mime='text/csv',key='download_'+view)
        except Exception as e:
            st.error(f'ABS request/series selection failed: {e}')
            st.caption('The dataset may have been renamed or its SDMX dimensions may have changed. Check the ABS dataflow identifier; the rest of the dashboard remains available.')
