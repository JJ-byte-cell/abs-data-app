import streamlit as st
import pandas as pd
import requests
import io

st.set_page_config(page_title="ABS Data API Explorer", layout="wide", page_icon="📊")
st.title("🇦🇺 Australian Bureau of Statistics (ABS) Live Data Explorer")

# FIXED: Updating dataflow registry references to match the active production versions (2.0.0 / 1.0.0)
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
    # Constructing standard SDMX RESTful API query link matching ABS specifications
    base_domain = "https://data.api.abs.gov.au"
    endpoint_path = f"/rest/data/{selected_flow_id}/all"
    query_params = f"?dimensionAtObservation=AllDimensions&startPeriod={start_year}"
    api_url = f"{base_domain}{endpoint_path}{query_params}"
    
    st.subheader(f"Dataset: {selected_flow_name}")
    st.markdown(f"**Target API Endpath:** `{api_url}`")
    
    if st.button("🚀 Fetch Live Data", type="primary"):
        with st.spinner("Connecting to live ABS API gateways..."):
            try:
                # Request layout forcing CSV return array blocks with both codes and names
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
                        df_data.columns = df_data.columns.astype(str).str.strip()
                        
                        # Clean whitespace errors out of cell data rows themselves
                        for col in df_data.select_dtypes(include=['object']).columns:
                            df_data[col] = df_data[col].astype(str).str.strip()
                        
                        # --- EXPLICIT AXIS CORRECTION ---
                        rename_dict = {}
                        for col in df_data.columns:
                            col_upper = col.upper()
                            if "TIME" in col_upper or "PERIOD" in col_upper:
                                rename_dict[col] = "TIME_PERIOD"
                            elif "OBS_VALUE" in col_upper or "OBS VALUE" in col_upper or "VALUE" in col_upper:
                                rename_dict[col] = "OBS_VALUE"
                            elif "MEASURE" in col_upper or "HEADING" in col_upper or "ITEM" in col_upper or "INDEX" in col_upper:
                                if "LABEL" in col_upper or "NAME" in col_upper or col_upper in ["DATA ITEM", "INDEX", "MEASURE"]:
                                    rename_dict[col] = "DATA_GROUP"
                        
                        if rename_dict:
                            df_data = df_data.rename(columns=rename_dict)
                        
                        with st.expander("🔍 View Raw Extracted Data Table", expanded=False):
                            st.dataframe(df_data, use_container_width=True)
                        
                        # --- Data Visualisation ---
                        st.subheader("📈 Visualise Data Trends")
                        
                        time_col = "TIME_PERIOD" if "TIME_PERIOD" in df_data.columns else None
                        value_col = "OBS_VALUE" if "OBS_VALUE" in df_data.columns else None
                        group_col = "DATA_GROUP" if "DATA_GROUP" in df_data.columns else None
                        
                        if time_col and value_col:
                            df_data[value_col] = pd.to_numeric(df_data[value_col], errors='coerce')
                            df_data = df_data.dropna(subset=[value_col])
                            
                            if group_col and group_col in df_data.columns:
                                unique_groups = df_data[group_col].unique().tolist()
                                selected_groups = st.multiselect(
                                    "Filter chart lines:", 
                                    options=unique_groups, 
                                    default=unique_groups[:3]
                                )
                                
                                chart_filtered_df = df_data[df_data[group_col].isin(selected_groups)]
                                pivot_df = chart_filtered_df.pivot_table(index=time_col, columns=group_col, values=value_col, aggfunc='mean')
                                st.line_chart(pivot_df, use_container_width=True)
                            else:
                                st.line_chart(df_data.set_index(time_col)[value_col], use_container_width=True)
                        else:
                            st.warning("Could not automatically align chart axes. View the raw grid expanded above.")
                else:
                    st.error(f"ABS API Connection Refused. Server status code: {response.status_code}")
                    st.info(f"Verify request structure against current documentation protocols.")
                    
            except Exception as e:
                st.error(f"Data stream error: {e}")
