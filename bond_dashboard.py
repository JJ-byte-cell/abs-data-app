import io
import pandas as pd
import requests
import streamlit as st

@st.cache_data(ttl=86400)
def load_bond_yield(*args, **kwargs):
    return load_bond_data()
def load_bond_data():
    url = "https://www.rba.gov.au/statistics/tables/csv/f2-data.csv"

    response = requests.get(
        url,
        headers={"User-Agent": "AustralianMacroDashboard/1.0"},
        timeout=45,
    )
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        skiprows=10,
    )

    df.columns = df.columns.astype(str).str.strip()

    series = "FCMYGBAG10D"
    if series not in df.columns:
        raise ValueError(
            f"10-year series not found. Available columns: {df.columns.tolist()}"
        )

    result = pd.DataFrame({
        "Date": pd.to_datetime(df.iloc[:, 0], dayfirst=True, errors="coerce"),
        "Yield": pd.to_numeric(df[series], errors="coerce"),
    })

    result = result.dropna().sort_values("Date")

    if result.empty:
        raise ValueError("No valid 10-year bond observations found.")

    return result
