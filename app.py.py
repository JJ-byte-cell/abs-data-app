import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

FALLBACK_OPTIONS = {
    "CPI - Consumer Price Index": "ABS,CPI,2.0.0",
    "RES_PROP_INDEX - Property Price Indexes": "ABS,RES_PROP_INDEX,1.0.0",
    "LFS - Labour Force Survey": "ABS,LABOUR_FORCE,1.0.0"
}

st.sidebar.header("1. Choose a Dataset")
selected_flow_name = st.sidebar.selectbox("Select Dataflow:", options=list(FALLBACK_OPTIONS.keys()))
selected_flow_ref = FALLBACK_OPTIONS[selected_flow_name]

start_year = st.sidebar.number_input("Start Year:", min_value=2010, max_value=2026, value=2018)

if selected_flow_ref:
    api_url = f"https://abs.gov.au{selected_flow_ref}/all?format=csvfilewithlabels&startPeriod={start_year}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Fetching live data from ABS servers..."):
            try:
                df_data = pd.read_csv(api_url)
                if df_data.empty:
                    st.warning("No data found.")
                else:
                    st.success(f"Loaded {len(df_data)} live rows!")
                    
                    with st.expander("View Raw Data"):
                        st.dataframe(df_data, use_container_width=True)
                        
                    time_col = next((col for col in df_data.columns if 'TIME' in col.upper()), None)
                    value_col = next((col for col in df_data.columns if 'VALUE' in col.upper() or 'OBS_VALUE' in col.upper()), None)
                    group_col = next((col for col in df_data.columns if 'MEASURE' in col.upper() or 'INDEX' in col.upper()), None)
                    
                    if time_col and value_col:
                        df_data[value_col] = pd.to_numeric(df_data[value_col], errors='coerce')
                        if group_col:
                            pivot_df = df_data.pivot_table(index=time_col, columns=group_col, values=value_col, aggfunc='mean')
                            st.line_chart(pivot_df)
                        else:
                            st.line_chart(df_data.set_index(time_col)[value_col])
            except Exception as e:
                st.error(f"Cloud server error: {e}")
