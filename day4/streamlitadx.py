import streamlit as st
import pandas as pd

# Import your analysis logic
from Adxlist import run_analysis  # make sure the file is named Adx_list.py

# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(
    page_title="Stock Momentum Dashboard",
    layout="wide"
)

st.title("📊 Stock Technical & Momentum Dashboard")

# --------------------------------------------------
# Load data (cached)
# --------------------------------------------------
@st.cache_data(ttl=1800)  # cache for 30 minutes
def load_data():
    return run_analysis()

with st.spinner("Fetching market data..."):
    df = load_data()

if df is None or df.empty:
    st.error("No data available")
    st.stop()

# Ensure numeric columns are proper dtype
numeric_cols = ["Close", "RSI", "MACD", "MACD_Signal", "BB_High", "BB_Low", "P/E", "P/B", "ADX"]
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# --------------------------------------------------
# Sidebar filters
# --------------------------------------------------
st.sidebar.header("🔍 Filters")

selected_stocks = st.sidebar.multiselect(
    "Select Stocks",
    options=df["Stock"].unique(),
    default=df["Stock"].unique()
)

adx_filter = st.sidebar.multiselect(
    "ADX Signal",
    options=df["ADX_SIGNAL"].unique(),
    default=df["ADX_SIGNAL"].unique()
)

filtered_df = df[
    (df["Stock"].isin(selected_stocks)) &
    (df["ADX_SIGNAL"].isin(adx_filter))
]

# --------------------------------------------------
# KPIs
# --------------------------------------------------
st.subheader("📈 Market Snapshot")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Stocks", len(filtered_df))
c2.metric("BUY Signals", (filtered_df["Recommendation_MOMENTUM"] == "BUY").sum())
c3.metric("Strong ADX", (filtered_df["ADX"] > 25).sum())
c4.metric("Avg RSI", round(filtered_df["RSI"].mean(skipna=True), 2))

# --------------------------------------------------
# Main table
# --------------------------------------------------
st.subheader("📋 Stock Analysis")

# Format only numeric columns present in DataFrame
format_dict = {col: "{:.2f}" for col in numeric_cols if col in filtered_df.columns}

styled_df = (
    filtered_df.style
    .format(format_dict)
    .applymap(
        lambda x: "background-color: #c6f6d5" if x == "BUY" else "",
        subset=["Recommendation_MOMENTUM"] if "Recommendation_MOMENTUM" in filtered_df.columns else []
    )
    .applymap(
        lambda x: "background-color: #bee3f8" if x == "BUY" else "",
        subset=["ADX_SIGNAL"] if "ADX_SIGNAL" in filtered_df.columns else []
    )
)

st.dataframe(styled_df, use_container_width=True)

# --------------------------------------------------
# Optional drill-down
# --------------------------------------------------
st.subheader("🔎 Stock Drill-Down")

stock = st.selectbox("Select a stock", filtered_df["Stock"].unique())
row = filtered_df[filtered_df["Stock"] == stock].iloc[0]

st.json(row.to_dict())

# --------------------------------------------------
# Footer
# --------------------------------------------------
st.caption("Data source: Yahoo Finance • Indicators: RSI, MACD, Bollinger Bands, ADX")
