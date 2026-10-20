import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

# FIXED DATAFRAME KEYS: Dropped the version numbers entirely to default securely to the live index (ABS,CPI)
FALLBACK_OPTIONS = {
    "CPI - Consumer Price Index": "ABS,CPI",
    "RES_PROP_INDEX - Property Price Indexes": "ABS,RES_PROP_INDEX",
    "LABOUR_TURNOVER - Labour Turnover": "ABS,LABOUR_TURNOVER"
}

st.sidebar.header("1. Choose a Dataset")
selected_flow_name = st.sidebar.selectbox("Select Dataflow:", options=list(FALLBACK_OPTIONS.keys()))
selected_flow_id = FALLBACK_OPTIONS[selected_flow_name]

st.sidebar.header("2. Data Filters")
start_year = st.sidebar.number_input("Start Year:", min_value=2010, max_value=2026, value=2018)

# --- SYSTEM UPGRADE: INITIALISE MEMORY REPOSITORIES ---
if "abs_dataframe" not in st.session_state:
    st.session_state.abs_dataframe = None
if "current_dataset" not in st.session_state:
    st.session_state.current_dataset = None
if "current_year" not in st.session_state:
    st.session_state.current_year = None

if selected_flow_id:
    # CLEAN URL STRUCTURE: Versionless identifiers combined with /all endpoint pathing
    base_domain = "https://data.api.abs.gov.au"
    endpoint_path = f"/rest/data/{selected_flow_id}/all"
    api_url = f"{base_domain}{endpoint_path}?startPeriod={start_year}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    st.markdown(f"**Target API Endpath:** `{api_url}`")
    
    # Reset internal memory cache if the dataset or year choices shift
    if (st.session_state.current_dataset != selected_flow_id) or (st.session_state.current_year != start_year):
        st.session_state.abs_dataframe = None
        st.session_state.current_dataset = selected_flow_id
        st.session_state.current_year = start_year
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Connecting to live ABS API gateways..."):
            try:
                headers = {
                    "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
                    "User-Agent": "Mozilla/5.0 Streamlit Cloud Data Downloader"
                }
                
                response = requests.get(api_url, headers=headers, timeout=25)
                
                if response.status_code == 200:
                    df_raw = pd.read_csv(io.StringIO(response.text))
                    
                    if df_raw.empty:
                        st.warning("The ABS API returned an empty dataset for this selection.")
                    else:
                        # Clean space formatting from column headers
                        df_raw.columns = df_raw.columns.astype(str).str.strip()
                        
                        # Replace colons to avoid Vega-Altair chart configuration collisions
                        df_raw.columns = df_raw.str.replace(':', ' -')
                        
                        # Clean inner-cell whitespace strings safely
                        for col in df_raw.select_dtypes(include=['object']).columns:
                            df_raw[col] = df_raw[col].astype(str).str.strip()
                        
                        # Lock into session state memory slot
                        st.session_state.abs_dataframe = df_raw
                        st.success(f"Successfully loaded {len(df_raw)} live rows!")
                else:
                    st.error(f"ABS API Connection Refused. Server status code: {response.status_code}")
                    st.info("Check parameters against active statistical repository protocols.")
                    
            except Exception as e:
                st.error(f"Data stream error: {e}")

    # --- RENDER ENGINE: LOCAL CACHE LOOKUP ---
    if st.session_state.abs_dataframe is not None:
        df_data = st.session_state.abs_dataframe
        
        with st.expander("🔍 View Raw Extracted Data Table", expanded=False):
            st.dataframe(df_data, use_container_width=True)
        
        # --- Data Visualisation ---
        st.subheader("📈 Visualise Data Trends")
        
        time_col = next((col for col in df_data.columns if 'TIME_PERIOD' in col or 'TIME PERIOD' in col), None)
        value_col = next((col for col in df_data.columns if 'OBS_VALUE' in col or 'VALUE' in col), None)
        
        # Discover category filtering keys cleanly
        group_col = None
        for target in ['MEASURE - Measure', 'INDEX - Index', 'DATA_ITEM - Data Item', 'REGION - Region']:
            if target in df_data.columns:
                group_col = target
                break
        
        if not group_col:
            group_col = next((col for col in df_data.columns if 'MEASURE' in col.upper() or 'INDEX' in col.upper()), None)
        
        if time_col and value_col:
            df_data[value_col] = pd.to_numeric(df_data[value_col], errors='coerce')
            df_data = df_data.dropna(subset=[value_col])
            
            if group_col:
                unique_groups = df_data[group_col].unique().tolist()
                
                selected_groups = st.multiselect(
                    f"Filter lines ({group_col}):", 
                    options=unique_groups, 
                    default=unique_groups[:3]
                )
                
                chart_filtered_df = df_data[df_data[group_col].isin(selected_groups)]
                pivot_df = chart_filtered_df.pivot_table(index=time_col, columns=group_col, values=value_col, aggfunc='mean')
                
                # Chronologically index variables to avoid messy patch lines
                pivot_df = pivot_df.sort_index()
                st.line_chart(pivot_df, use_container_width=True)
                
                # Export Module
                st.markdown("### 📥 Export Your Filtered Workspace")
                csv_buffer = io.StringIO()
                chart_filtered_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="💾 Download Filtered Data as CSV",
                    data=csv_buffer.getvalue(),
                    file_name=f"filtered_abs_{selected_flow_id.lower().replace(',', '_')}.csv",
                    mime="text/csv"
                )
            else:
                df_sorted = df_data.sort_values(by=time_col)
                st.line_chart(df_sorted.set_index(time_col)[value_col], use_container_width=True)
        else:
            st.warning("Could not automatically align chart axes. View the raw grid expanded above.")
