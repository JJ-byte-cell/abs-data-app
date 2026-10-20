import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

# Official dataflow registry keys accepted by the ABS API cluster
FALLBACK_OPTIONS = {
    "CPI - Consumer Price Index": "ABS,CPI,2.0.0",
    "RES_PROP_INDEX - Property Price Indexes": "ABS,RES_PROP_INDEX,1.0.0",
    "LABOUR_TURNOVER - Labour Turnover": "ABS,LABOUR_TURNOVER,1.0.0"
}

st.sidebar.header("1. Choose a Dataset")
selected_flow_name = st.sidebar.selectbox("Select Dataflow:", options=list(FALLBACK_OPTIONS.keys()))
selected_flow_ref = FALLBACK_OPTIONS[selected_flow_name]

st.sidebar.header("2. Data Filters")
start_year = st.sidebar.number_input("Start Year:", min_value=2010, max_value=2026, value=2018)

if selected_flow_ref:
    # Official endpoint route mapping to the correct API server domain
    api_url = f"https://abs.gov.au{selected_flow_ref}/all?dimensionAtObservation=AllDimensions&startPeriod={start_year}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Connecting to live ABS API gateways..."):
            try:
                # The ABS API strictly requires the explicit SDMX CSV application header to allow external scripts through
                headers = {
                    "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
                    "User-Agent": "Mozilla/5.0 Streamlit Cloud Data Downloader"
                }
                
                response = requests.get(api_url, headers=headers, timeout=20)
                
                if response.status_code == 200:
                    # Convert response bytes directly into a pandas dataframe
                    df_data = pd.read_csv(io.StringIO(response.text))
                    
                    if df_data.empty:
                        st.warning("The ABS API returned an empty dataset for this selection.")
                    else:
                        st.success(f"Successfully loaded {len(df_data)} live rows!")
                        
                        # CRITICAL FIX: Aggressively strip whitespaces from column names to fix the Time Period error
                        df_data.columns = df_data.columns.str.strip()
                        
                        # If a column specifically named "Time Period" exists, rename it cleanly to get rid of plotting confusion
                        if "Time Period" in df_data.columns:
                            df_data = df_data.rename(columns={"Time Period": "TIME_PERIOD"})
                        
                        with st.expander("🔍 View Raw Extracted Data Table", expanded=False):
                            st.dataframe(df_data, use_container_width=True)
                        
                        # --- Data Visualisation ---
                        st.subheader("📈 Visualise Data Trends")
                        
                        # Find the appropriate data structure columns based on standard ABS labels
                        time_col = next((col for col in df_data.columns if 'TIME' in col.upper() or 'PERIOD' in col.upper()), None)
                        value_col = next((col for col in df_data.columns if 'VALUE' in col.upper() or 'OBS_VALUE' in col.upper()), None)
                        group_col = next((col for col in df_data.columns if 'MEASURE' in col.upper() or 'INDEX' in col.upper() or 'DATA_ITEM' in col.upper()), None)
                        
                        if time_col and value_col:
                            df_data[value_col] = pd.to_numeric(df_data[value_col], errors='coerce')
                            df_data = df_data.dropna(subset=[value_col])
                            
                            if group_col and group_col in df_data.columns:
                                unique_groups = df_data[group_col].unique().tolist()
                                selected_groups = st.multiselect(
                                    f"Filter chart lines by {group_col}:", 
                                    options=unique_groups, 
                                    default=unique_groups[:3]
                                )
                                
                                chart_filtered_df = df_data[df_data[group_col].isin(selected_groups)]
                                pivot_df = chart_filtered_df.pivot_table(index=time_col, columns=group_col, values=value_col, aggfunc='mean')
                                st.line_chart(pivot_df, use_container_width=True)
                            else:
                                st.line_chart(df_data.set_index(time_col)[value_col], use_container_width=True)
                        else:
                            st.warning("Could not map layout axes automatically. Explore raw grid details above.")
                else:
                    st.error(f"ABS API Connection Refused. Server status code: {response.status_code}")
                    
            except Exception as e:
                st.error(f"Data stream error: {e}")
