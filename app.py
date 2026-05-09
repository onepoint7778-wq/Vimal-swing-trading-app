import streamlit as st
import pandas as pd
from agents import SwingTradingAgents

st.set_page_config(page_title="TradeLogic Dashboard", layout="wide")
st.markdown("<h2 style='color: #1A73E8;'>📊 TradeLogic Dashboard</h2>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Dashboard", "Backtest"])

with tab1:
    st.write("Live Scanner is running...")

with tab2:
    st.subheader("Institutional Backtester")
    if st.button("Run Backtest Simulation"):
        with st.spinner("Processing..."):
            agent = SwingTradingAgents()
            df, metrics = agent.run_backtest()
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Trades", metrics["Total Trades"])
            c2.metric("Win Rate", metrics["Win Rate"])
            c3.metric("Losses", metrics["Losses"])
            c4.metric("Net Profit", metrics["Net Profit"])
            
            st.dataframe(df, use_container_width=True)