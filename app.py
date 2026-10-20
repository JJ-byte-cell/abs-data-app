import streamlit as st
import pandas as pd
import requests
import io

# 1. Page Configuration & Professional Styling
st.set_page_config(
    page_title="ABS Production Data Dashboard", 
    layout="wide", 
    page_icon="📊",
    initial_sidebar_state="expanded"
)

st.title("🇦🇺 Australian Bureau of Statistics (ABS) Enterprise Explorer")
st.markdown("""
This specialist interface streams live statistical matrices directly from the official **ABS Data REST API Cluster**.
*Data conforms to the global SDMX 2.1 international information exchange standard.*
""")

# FIXED DATAFLOW KEYS: Explicit production versions combined with mandatory sdmx structures
AVAILABLE_DATAFLOWS = {
    "CPI - Consumer Price Index": "ABS,CPI,2.0.0",
    "RES_PROP_INDEX - Property Price Indexes": "ABS,RES_PROP_INDEX,1.0.0",
    "LABOUR_TURNOVER - Labour Turnover Matrix": "ABS,LABOUR_TURNOVER,1.0.0"
}

# 2. Sidebar Navigation Control
st.sidebar.header("🎯 1. Target Data Selection")
selected_name = st.sidebar.selectbox("Select Master Dataflow:", options=list(AVAILABLE_DATAFLOWS.keys()))
target_flow_id = AVAILABLE_DATAFLOWS[selected_name]

st.sidebar.header("⏳ 2. Primary Date Constraints")
start_year = st.sidebar.number_input("Start Period (Year):", min_value=2000, max_value=2026, value=2018)

# 3. Session State Caching Layers (Prevents unwanted auto-refresh loops)
if "master_data_payload" not in st.session_state:
    st.session_state.master_data_payload = None
if "active_dataflow_id" not in st.session_state:
    st.session_state.active_dataflow_id = None
if "active_filter_year" not in st.session_state:
    st.session_state.active_filter_year = None

# FIXED URL PATHWAY: Appending dimensionAtObservation parameter as dictated by ABS CSV specifications
base_gateway = "https://abs.gov.au"
query_endpoint = f"{base_gateway}/{target_flow_id}/all?startPeriod={start_year}&dimensionAtObservation=AllDimensions"

# If sidebar parameters change, invalidate the memory cache to force a clean fetch
if (st.session_state.active_dataflow_id != target_flow_id) or (st.session_state.active_filter_year != start_year):
    st.session_state.master_data_payload = None
    st.session_state.active_dataflow_id = target_flow_id
    st.session_state.active_filter_year = start_year

st.subheader(f"Data Target: {selected_name}")
st.caption(f"Secure Gateway URI: `{query_endpoint}`")

# 4. Data Acquisition Layer
if st.button("🚀 Ingest Live Data Stream", type="primary"):
    with st.spinner("Executing secure handshake with ABS API Gateways..."):
        try:
            # The ABS API cluster demands structural accept tags to parse multi-dimensional metrics
            request_headers = {
                "Accept": "application/vnd.sdmx.data+csv;urn=true;file=true;labels=both",
                "User-Agent": "Mozilla/5.0 Enterprise Analytics Pipeline"
            }
            
            api_response = requests.get(query_endpoint, headers=request_headers, timeout=30)
            
            if api_response.status_code == 200:
                # Direct string stream ingestion to block file system leakages
                df_raw = pd.read_csv(io.StringIO(api_response.text))
                
                if df_raw.empty:
                    st.warning("Gateway Handshake succeeded, but returned an empty structural envelope.")
                else:
                    # --- ENTERPRISE DATA CLEANING PIPELINE ---
                    # Remove trailing whitespaces from headers introduced by transmission padding
                    df_raw.columns = df_raw.columns.astype(str).str.strip()
                    
                    # Vega-Altair chart engine compatibility translation (Eliminates the type syntax errors)
                    df_raw.columns = df_raw.columns.str.replace(':', ' -')
                    
                    # Clean inner-cell whitespace strings across all descriptive categorical objects
                    for text_column in df_raw.select_dtypes(include=['object']).columns:
                        df_raw[text_column] = df_raw[text_column].astype(str).str.strip()
                        
                    # Standardizes time and value dimensions cleanly across volatile structures
                    normalized_headers = {}
                    for column_name in df_raw.columns:
                        normalized_upper = column_name.upper()
                        if "TIME_PERIOD" in normalized_upper and "." not in normalized_upper:
                            normalized_headers[column_name] = "TIME_PERIOD"
                        elif "OBS_VALUE" in normalized_upper and "." not in normalized_upper:
                            normalized_headers[column_name] = "OBS_VALUE"
                    
                    if normalized_headers:
                        df_raw = df_raw.rename(columns=normalized_headers)
                    
                    # Commit sanitized matrix safely to local server session states
                    st.session_state.master_data_payload = df_raw
                    st.success(f"Sanitized Data Matrix Locked: {len(df_raw)} multi-dimensional rows parsed.")
            else:
                st.error(f"ABS API Connection Terminated. Server Status Code: {api_response.status_code}")
                st.info(f"Response Body: {api_response.text}")
                
        except Exception as network_error:
            st.error(f"Inbound Pipeline Crash: {network_error}")

# 5. Advanced Analytical Visualization & Granular Filtering Layer
if st.session_state.master_data_payload is not None:
    working_df = st.session_state.master_data_payload.copy()
    
    st.markdown("---")
    st.subheader("🛠️ Granular Data Filtering & Matrix Controls")
    
    # Isolate key dimensions from the sanitized headers
    time_index = "TIME_PERIOD" if "TIME_PERIOD" in working_df.columns else None
    value_index = "OBS_VALUE" if "OBS_VALUE" in working_df.columns else None
    
    # Establish a reliable segmentation column, prioritizing index labels or region boundaries
    segmentation_target = None
    for priority_label in ['MEASURE - Measure', 'INDEX - Index', 'DATA_ITEM - Data Item', 'REGION - Region']:
        if priority_label in working_df.columns:
            segmentation_target = priority_label
            break
            
    if not segmentation_target:
        segmentation_target = next((c for c in working_df.columns if 'MEASURE' in c.upper() or 'INDEX' in c.upper()), None)
        
    if time_index and value_index:
        # Enforce strict data type integrity for plotting
        working_df[value_index] = pd.to_numeric(working_df[value_index], errors='coerce')
        working_df = working_df.dropna(subset=[value_index])
        
        # Split layout into advanced multi-column filtering layouts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Filter Dimension:** `{segmentation_target}`")
            available_categories = working_df[segmentation_target].unique().tolist() if segmentation_target else []
            
            # Interactive Multi-Select Filter Control (Runs instantly via local memory without page-reload loops)
            target_selection = st.multiselect(
                "Isolate Specific Economic Subgroups:", 
                options=available_categories, 
                default=available_categories[:2] if len(available_categories) > 1 else available_categories
            )
            
        with col2:
            # Secondary contextual cross-filtering: Filter by Region if present in dataset matrix
            region_col = next((c for c in working_df.columns if 'REGION' in c.upper()), None)
            if region_col and region_col != segmentation_target:
                available_regions = working_df[region_col].unique().tolist()
                selected_region = st.selectbox("Cross-Filter by Geographic Boundary:", options=["All Regions"] + available_regions)
                if selected_region != "All Regions":
                    working_df = working_df[working_df[region_col] == selected_region]
                    
        # Apply dimensional data slices instantly in local memory
        if segmentation_target and target_selection:
            filtered_matrix = working_df[working_df[segmentation_target].isin(target_selection)]
        else:
            filtered_matrix = working_df
            
        # 6. Advanced Visualization Layer
        st.subheader("📈 Verified Time Series Trend Analysis")
        
        try:
            if segmentation_target:
                # Construct an analytical pivot grid to isolate continuous paths
                chart_pivot = filtered_matrix.pivot_table(
                    index=time_index, 
                    columns=segmentation_target, 
                    values=value_index, 
                    aggfunc='mean'
                )
                # Strict Chronological Sorting Layer to erase zig-zag visual patchwork flaws
                chart_pivot = chart_pivot.sort_index()
                st.line_chart(chart_pivot, use_container_width=True)
            else:
                flat_timeline = filtered_matrix.sort_values(by=time_index)
                st.line_chart(flat_timeline.set_index(time_index)[value_index], use_container_width=True)
                
        except Exception as charting_anomaly:
            st.warning(f"Visualization warning, grid layout complex: {charting_anomaly}")
            
        # 7. Enterprise Export Engine Block
        st.markdown("### 📥 Extract Filtered Pipeline")
        with st.expander("🔍 Inspect Active Filtered Data Grid", expanded=False):
            st.dataframe(filtered_matrix, use_container_width=True)
            
        csv_io_stream = io.StringIO()
        filtered_matrix.to_csv(csv_io_stream, index=False)
        
        st.download_button(
            label="💾 Export Active Workspace Spreadsheet (CSV)",
