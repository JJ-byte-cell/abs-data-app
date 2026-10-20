import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

# FIX: Dropping the strict version numbers (e.g. ,2.0.0) so the API automatically grabs the newest table version
FALLBACK_OPTIONS = {
    "CPI - Consumer Price Index": "CPI",
    "RES_PROP_INDEX - Property Price Indexes": "RES_PROP_INDEX",
    "LABOUR_TURNOVER - Labour Turnover": "LABOUR_TURNOVER"
}

st.sidebar.header("1. Choose a Dataset")
selected_flow_name = st.sidebar.selectbox("Select Dataflow:", options=list(FALLBACK_OPTIONS.keys()))
selected_flow_id = FALLBACK_OPTIONS[selected_flow_name]

st.sidebar.header("2. Data Filters")
start_year = st.sidebar.number_input("Start Year:", min_value=2010, max_value=2026, value=2018)

if selected_flow_id:
    # Build clean versionless query path structure
    base_domain = "https://data.api.abs.gov.au"
    endpoint_path = f"/rest/data/{selected_flow_id}/all"
    query_params = f"?dimensionAtObservation=AllDimensions&startPeriod={start_year}"
    api_url = f"{base_domain}{endpoint_path}{query_params}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    st.markdown(f"**Target API Endpath:** `{api_url}`")
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Connecting to live ABS API gateways..."):
            try:
                # Direct structural data payload download via standard SDMX data-frame conversions
                headers = {
                    "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
                    "User-Agent": "Mozilla/5.0 Streamlit Cloud Data Downloader"
                }
                
                response = requests.get(api_url, headers=headers, timeout=20)
                
                if response.status_code == 200:
                    df_data = pd.read_csv(io.StringIO(response.text))
                    
                    if df_data.empty:
                        st.warning("The ABS API returned an empty dataset for this selection.")
                    else:
                        st.success(f"Successfully loaded {len(df_data)} live rows!")
                        
                        # Strip accidental leading or trailing blank spaces from headers
                        df_data.columns = df_data.columns.str.strip()
                        
                        # Map messy "Time Period" keys out of Vega-Altair plotting configurations
                        if "Time Period" in df_data.columns:
                            df_data = df_data.rename(columns={"Time Period": "TIME_PERIOD"})
                        
                        with st.expander("🔍 View Raw Extracted Data Table", expanded=False):
                            st.dataframe(df_data, use_container_width=True)
                        
                        # --- Data Visualisation ---
                        st.subheader("📈 Visualise Data Trends")
                        
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
                    st.info("The path version formatting structure might be rejecting the current automated data key.")
                    
            except Exception as e:
                st.error(f"Data stream error: {e}")
