import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

# Dataflow registry references matching active production versions
FALLBACK_OPTIONS = {
    "CPI - Consumer Price Index": "ABS,CPI,2.0.0",
    "RES_PROP_INDEX - Property Price Indexes": "ABS,RES_PROP_INDEX,1.0.0",
    "LABOUR_TURNOVER - Labour Turnover": "ABS,LABOUR_TURNOVER,1.0.0"
}

st.sidebar.header("1. Choose a Dataset")
selected_flow_name = st.sidebar.selectbox("Select Dataflow:", options=list(FALLBACK_OPTIONS.keys()))
selected_flow_id = FALLBACK_OPTIONS[selected_flow_name]

st.sidebar.header("2. Data Filters")
start_year = st.sidebar.number_input("Start Year:", min_value=2010, max_value=2026, value=2018)

if selected_flow_id:
    base_domain = "https://abs.gov.au"
    endpoint_path = f"/rest/data/{selected_flow_id}/all"
    query_params = f"?dimensionAtObservation=AllDimensions&startPeriod={start_year}"
    api_url = f"{base_domain}{endpoint_path}{query_params}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    st.markdown(f"**Target API Endpath:** `{api_url}`")
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Connecting to live ABS API gateways..."):
            try:
                headers = {
                    "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
                    "User-Agent": "Mozilla/5.0 Streamlit Cloud Data Downloader"
                }
                
                response = requests.get(api_url, headers=headers, timeout=20)
                
                if response.status_code == 200:
                    # Let pandas handle the raw layout natively. It automatically appends suffixes (.1, .2) to any matching headers it finds.
                    df_data = pd.read_csv(io.StringIO(response.text))
                    
                    if df_data.empty:
                        st.warning("The ABS API returned an empty dataset for this selection.")
                    else:
                        st.success(f"Successfully loaded {len(df_data)} live rows!")
                        
                        # Strip spacing from column headers
                        df_data.columns = df_data.columns.astype(str).str.strip()
                        
                        # Clean whitespace errors out of cell data rows themselves
                        for col in df_data.select_dtypes(include=['object']).columns:
                            df_data[col] = df_data[col].astype(str).str.strip()
                        
                        with st.expander("🔍 View Raw Extracted Data Table", expanded=False):
                            st.dataframe(df_data, use_container_width=True)
                        
                        # --- Data Visualisation ---
                        st.subheader("📈 Visualise Data Trends")
                        
                        # Dynamically find the primary axis markers by looking at what keys are present
                        time_col = next((col for col in df_data.columns if 'TIME_PERIOD' in col or 'TIME PERIOD' in col), None)
                        value_col = next((col for col in df_data.columns if 'OBS_VALUE' in col or 'VALUE' in col), None)
                        
                        # Pick a single column to slice the chart options by.
                        # For CPI, 'MEASURE: Measure' breaks down individual expenditure groups (Food, Housing, etc.)
                        group_col = None
                        for priority_target in ['MEASURE: Measure', 'INDEX: Index', 'DATA_ITEM: Data Item', 'REGION: Region']:
                            if priority_target in df_data.columns:
                                group_col = priority_target
                                break
                        
                        if not group_col:
                            # Catch-all fallback selector if specific structural strings are modified
                            group_col = next((col for col in df_data.columns if 'MEASURE' in col.upper() or 'INDEX' in col.upper()), None)
                        
                        if time_col and value_col:
                            df_data[value_col] = pd.to_numeric(df_data[value_col], errors='coerce')
                            df_data = df_data.dropna(subset=[value_col])
                            
                            if group_col:
                                unique_groups = df_data[group_col].unique().tolist()
                                selected_groups = st.multiselect(
                                    f"Filter chart lines by ({group_col}):", 
                                    options=unique_groups, 
                                    default=unique_groups[:3] # Displays the first 3 tracking categories by default
                                )
                                
                                chart_filtered_df = df_data[df_data[group_col].isin(selected_groups)]
                                
                                # Use pivot_table to turn different categories into lines on the line chart
                                pivot_df = chart_filtered_df.pivot_table(index=time_col, columns=group_col, values=value_col, aggfunc='mean')
                                st.line_chart(pivot_df, use_container_width=True)
                            else:
                                st.line_chart(df_data.set_index(time_col)[value_col], use_container_width=True)
                        else:
                            st.warning("Could not automatically align chart axes. View the raw grid expanded above.")
                else:
                    st.error(f"ABS API Connection Refused. Server status code: {response.status_code}")
                    
            except Exception as e:
                st.error(f"Data stream error: {e}")
