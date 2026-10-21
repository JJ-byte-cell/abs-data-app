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

@st.cache_data(ttl=3600, show_spinner=False)
def rba_cash_history():
    """RBA published cash-rate target decision table (effective dates)."""
    url='https://www.rba.gov.au/statistics/cash-rate/'
    r=requests.get(url,timeout=(8,30),headers={'User-Agent':'Mozilla/5.0 (compatible; MacroResearch/1.0)'})
    r.raise_for_status()
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(r.text,'html.parser')
    records=[]
    for table in soup.find_all('table'):
        heads=' '.join(t.get_text(' ',strip=True) for t in table.find_all('th')).lower()
        if 'cash rate target' not in heads or 'effective date' not in heads:continue
        for tr in table.find_all('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
            if len(cells)<3:continue
            date=pd.to_datetime(cells[0],dayfirst=True,errors='coerce')
            value=pd.to_numeric(re.sub(r'[^0-9.\-]','',cells[2]),errors='coerce')
            if pd.notna(date) and pd.notna(value):records.append((date,float(value)))
    if not records:raise ValueError('RBA table structure not recognised; no cash rate data plotted')
    return pd.DataFrame(records,columns=['_date','_value']).drop_duplicates('_date').sort_values('_date')

@st.cache_data(ttl=3600, show_spinner=False)
def abs_headline_index(freq,start,end):
    """Specific CPI series key published in ABS API examples; fail closed on changed schema."""
    key=f'1.10001.10.50.{freq}'
    url=f'{API}/data/ABS,CPI,all/{key}'
    r=requests.get(url,params={'startPeriod':str(start),'endPeriod':str(end),'format':'csv','dimensionAtObservation':'AllDimensions'},headers={'Accept':'application/vnd.sdmx.data+csv;labels=both','User-Agent':'AustralianMacroTracker/2.1'},timeout=(8,45))
    r.raise_for_status()
    df=pd.read_csv(io.BytesIO(r.content),low_memory=False)
    df,tc,vc=tidy(df)
    # Reject conflicting or non-index data, including schema changes.
    if df.empty:raise ValueError('ABS CPI series is empty')
    freq_col=match(df,'FREQ')
    if freq_col is not None and not df[freq_col].astype(str).str.split(':').str[0].eq(freq).all():
        raise ValueError('Returned ABS frequency differs from requested frequency')
    for col in df.columns:
        if col.startswith('_') or col in [tc,vc,'DATAFLOW','OBS_STATUS','OBS_COMMENT','UNIT_MEASURE','UNIT_MULT']:continue
        if df[col].nunique(dropna=True)>1:raise ValueError(f'ABS CPI key returned multiple values for {col}')
    if df.groupby('_date')['_value'].nunique().max()>1:raise ValueError('Conflicting CPI values per date')
    return df.drop_duplicates('_date').sort_values('_date')[['_date','_value']]

def annual_change(index,periods):
    s=index.sort_values('_date').copy()
    s['_value']=s['_value'].pct_change(periods=periods,fill_method=None)*100
    return s.dropna()

def auto_abs_view(flow,title,start,end):
    st.markdown(f'#### {title}')
    if st.button(f'Fetch official {title} data',key=f'fetch_{flow}_{title}'):
        st.session_state[f'auto_{flow}_{title}']=True
    if not st.session_state.get(f'auto_{flow}_{title}'):return
    try:
        raw=get_abs(flow,start,end)
        st.caption(f'{len(raw):,} ABS observations downloaded. Select a consistent series below.')
        df,tc,vc=tidy(raw)
        s=choose_series(df,tc,vc,f'auto_{flow}_{title}')
        chart(s,title)
    except Exception as e:
        st.warning(f'Could not load {title}: {e}')
        st.caption('This ABS flow may have changed, or its response may be too large. No substitute observations have been generated.')

def research(view):
    st.subheader(view)
    st.caption('Official ABS and RBA sources · Data loaded on demand · No required CSV uploads')
    years=st.select_slider('Research history (years)',options=[2,3,5,10,15,20],value=10,key='research_years_'+view)
    end=pd.Timestamp.today().year
    start=end-years-2
    if view in ['Monetary Policy','Inflation Research','Macro Overview','ASX Insights']:
        st.markdown('#### Official headline CPI')
        freq=st.radio('CPI frequency',['Quarterly','Monthly'],horizontal=True,key='freq_'+view)
        try:
            ix=abs_headline_index('Q' if freq=='Quarterly' else 'M',start,end)
            inflation=annual_change(ix,4 if freq=='Quarterly' else 12)
            if inflation.empty:raise ValueError('Insufficient CPI observations for annual changes')
            inflation=inflation[inflation['_date']>=pd.Timestamp(end-years,1,1)]
            chart(inflation,'Headline CPI: annual change',unit='Annual %')
            st.caption('ABS CPI index converted to year-ended percentage change. Annual change uses 4 quarters or 12 months.')
        except Exception as e:
            inflation=None
            st.warning(f'Official CPI series unavailable: {e}')
            st.caption('The specific CPI SDMX series key may need updating to match the current ABS release.')
    else:inflation=None
    if view=='Monetary Policy':
        st.markdown('#### RBA cash rate target')
        try:
            cash=rba_cash_history()
            cash=cash[cash['_date']>=pd.Timestamp(end-years,1,1)]
            chart(cash,'RBA cash rate target — decision dates',unit='Cash rate (%)')
            st.caption('Source: https://www.rba.gov.au/statistics/cash-rate/ · rate target effective dates')
            if inflation is not None and not cash.empty:
                # Rates are step functions; inflation is observed at monthly/quarterly period dates.
                aligned=pd.merge_asof(inflation.sort_values('_date'),cash.sort_values('_date'),on='_date',direction='backward',suffixes=('_cpi','_cash')).dropna()
                if not aligned.empty:
                    comparison(aligned[['_date','_value_cash']].rename(columns={'_value_cash':'_value'}),aligned[['_date','_value_cpi']].rename(columns={'_value_cpi':'_value'}),'Cash rate target','Annual CPI','RBA cash rate target vs headline inflation')
                    real=aligned.assign(_value=aligned['_value_cash']-aligned['_value_cpi'])[['_date','_value']]
                    chart(real,'Ex-post real cash rate (simple difference)',unit='Percentage points')
        except Exception as e:st.warning(f'RBA automatic retrieval unavailable: {e}')
    elif view=='Inflation Research':
        st.info('Trimmed mean, expenditure contributions and inflation breadth require validated official series and weights. They are not inferred from headline CPI alone.')
        auto_abs_view('CPI','CPI measure explorer',start,end)
    elif view=='Property':
        auto_abs_view('BUILDING_APPROVALS','Building approvals',start,end)
        auto_abs_view('BUILDING_ACTIVITY','Building activity / completions',start,end)
        auto_abs_view('RES_PROP_INDEX','Historical property prices',start,end)
        st.markdown('#### Mortgage affordability scenario')
        price=st.number_input('Property price (AUD)',min_value=10000.,value=800000.,step=10000.,key='prop_price')
        deposit=st.slider('Deposit (%)',0,80,20,key='prop_deposit')
        rate=st.slider('Mortgage rate (%)',0.,15.,6.,0.25,key='prop_rate')
        income=st.number_input('Gross household income (AUD/year)',min_value=1.,value=150000.,step=5000.,key='prop_income')
        term=st.slider('Loan term (years)',5,40,30,key='prop_term')
        principal=price*(1-deposit/100);r=rate/1200;n=term*12
        payment=principal/n if r==0 else principal*r/(1-(1+r)**(-n))
        st.metric('Monthly repayment',f'${payment:,.0f}')
        st.metric('Repayment / gross monthly income',f'{payment/(income/12)*100:.1f}%')
        st.caption('Scenario, not a current mortgage quote. Excludes transaction costs and other expenses.')
    elif view=='Labour & Wages':
        auto_abs_view('LABOUR_FORCE','Labour force',start,end)
        auto_abs_view('JOB_VACANCIES','Job vacancies',start,end)
        auto_abs_view('WPI','Wage Price Index',start,end)
        st.caption('Real wages require consistent annual WPI and CPI measures. Do not subtract index levels.')
    elif view=='Economic Growth':
        auto_abs_view('ANA_AGG','GDP and national accounts',start,end)
        auto_abs_view('MHS','Household spending',start,end)
        st.caption('GDP contributions must use published contribution series; component growth rates cannot simply be summed.')
    elif view=='ASX Insights':
        auto_abs_view('MHS','Household spending / consumer demand',start,end)
        st.info('Sector investment signals need additional validated market series. No unverified buy/sell recommendations are generated.')
    elif view=='Macro Overview':
        auto_abs_view('LABOUR_FORCE','Labour force / unemployment',start,end)
        st.info('Economic cycle classification remains disabled until comparable growth and inflation measures are validated.')
    st.caption('If an official series is unavailable, the dashboard reports the error instead of displaying fabricated data.')
