import streamlit as st
import pandas as pd
from agents import SwingTradingAgents
from datetime import datetime
import time
import json
import os
import hashlib
import requests

st.set_page_config(page_title="TradeLogic Dashboard", page_icon="📊", layout="wide")

# --- PERSISTENT CONFIGURATION STORAGE ---
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "use_fyers": True,
        "fyers_app_id": "",
        "fyers_secret_key": "",
        "fyers_token": "",
        "fyers_redirect_uri": "https://vimal-swing-trading-app-st43utvpyng3zswmkaqot2.streamlit.app/",
        "chartink_url": "https://chartink.com/screener/richroad-pivot-points-weekly-scan-2028",
        "rr_ratio": "1:2"
    }

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f)
    except:
        pass

# Initialize session state from stored config
config = load_config()
if "use_fyers" not in st.session_state:
    st.session_state.use_fyers = True
if "fyers_app_id" not in st.session_state:
    st.session_state.fyers_app_id = config.get("fyers_app_id", "")
if "fyers_secret_key" not in st.session_state:
    st.session_state.fyers_secret_key = config.get("fyers_secret_key", "")
if "fyers_token" not in st.session_state:
    st.session_state.fyers_token = config.get("fyers_token", "")
if "fyers_redirect_uri" not in st.session_state:
    st.session_state.fyers_redirect_uri = config.get("fyers_redirect_uri", "https://vimal-swing-trading-app-st43utvpyng3zswmkaqot2.streamlit.app/")
if "chartink_url" not in st.session_state:
    st.session_state.chartink_url = config.get("chartink_url", "https://chartink.com/screener/richroad-pivot-points-weekly-scan-2028")
if "rr_ratio" not in st.session_state:
    st.session_state.rr_ratio = config.get("rr_ratio", "1:2")

# --- AUTOMATIC FYERS AUTH CODE DETECTION ---
auth_code = st.query_params.get("auth_code")
if auth_code:
    app_id = config.get("fyers_app_id", "")
    secret_key = config.get("fyers_secret_key", "")
    
    if app_id and secret_key:
        with st.spinner("🔑 Validating Fyers Auth Code & Generating Token..."):
            try:
                hash_input = f"{app_id}:{secret_key}"
                app_id_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                
                val_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
                payload = {
                    "grant_type": "authorization_code",
                    "appIdHash": app_id_hash,
                    "code": auth_code
                }
                headers = {"Content-Type": "application/json"}
                
                res = requests.post(val_url, json=payload, headers=headers)
                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get("s") == "ok" and "access_token" in res_data:
                        token = res_data["access_token"]
                        st.session_state.fyers_token = token
                        config["fyers_token"] = token
                        save_config(config)
                        st.success("🎉 Successfully authenticated with Fyers API!")
                        st.balloons()
                        time.sleep(2)
                    else:
                        st.error(f"Fyers Auth Failed: {res_data.get('message', 'Unknown error')}")
                else:
                    st.error(f"Fyers Server Error (HTTP {res.status_code}): {res.text}")
            except Exception as e:
                st.error(f"Error during authentication: {e}")
            
            st.query_params.clear()
    else:
        st.warning("⚠️ Auth code received, but App ID or Secret Key was not configured/saved.")
        st.query_params.clear()

# --- STREAMLIT SIDEBAR SETTINGS ---
with st.sidebar:
    st.markdown("### 🔌 Fyers API Settings")
    fyers_app_id = st.text_input("Fyers App ID (Client ID):", value=st.session_state.fyers_app_id)
    fyers_secret_key = st.text_input("Fyers Secret Key:", value=st.session_state.fyers_secret_key, type="password")
    fyers_redirect_uri = st.text_input("Redirect URI (Registered in Fyers App):", value=st.session_state.fyers_redirect_uri)
    fyers_token = st.text_input("Fyers Access Token (Auto-generated or Manual):", value=st.session_state.fyers_token, type="password")
    
    if fyers_app_id and fyers_secret_key and fyers_redirect_uri:
        login_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={fyers_app_id}&redirect_uri={fyers_redirect_uri}&response_type=code&state=sample_state"
        st.markdown(f'<a href="{login_url}" target="_blank" style="text-decoration:none;"><button style="width:100%; border:none; background-color:#1A73E8; color:white; padding:10px; border-radius:6px; cursor:pointer; font-weight:bold; margin-bottom:10px;">🔑 Log In & Generate Access Token</button></a>', unsafe_allow_html=True)
        st.caption("💡 Steps: (1) Save Settings first, (2) Click button above to login & authorize, (3) It will redirect back and set token.")
    else:
        st.info("ℹ️ Enter App ID, Secret Key, and Redirect URI, then Save to enable Fyers auto-login.")
        
    st.markdown("### 📊 Strategy Settings")
    timeframe_label = st.selectbox(
        "Select Strength Lookback Timeframe:",
        ["1 Week (5 Trading Days)", "1 Month (20 Trading Days)"],
        index=0
    )
    lookback_days = 5 if "1 Week" in timeframe_label else 20
    
    chartink_url = st.text_input("Chartink Scanner URL:", value=st.session_state.chartink_url)
    
    st.markdown("#### ⚙️ Controls")
    rr_options = ["1:2", "1:2.5", "1:3"]
    default_idx = rr_options.index(st.session_state.rr_ratio) if st.session_state.rr_ratio in rr_options else 0
    rr_label = st.selectbox("Risk-Reward Ratio:", rr_options, index=default_idx)
    
    if st.button("💾 Save & Apply Settings"):
        st.session_state.fyers_app_id = fyers_app_id
        st.session_state.fyers_secret_key = fyers_secret_key
        st.session_state.fyers_redirect_uri = fyers_redirect_uri
        st.session_state.fyers_token = fyers_token
        st.session_state.chartink_url = chartink_url
        st.session_state.rr_ratio = rr_label
        
        save_config({
            "use_fyers": True,
            "fyers_app_id": fyers_app_id,
            "fyers_secret_key": fyers_secret_key,
            "fyers_redirect_uri": fyers_redirect_uri,
            "fyers_token": fyers_token,
            "chartink_url": chartink_url,
            "rr_ratio": rr_label
        })
        st.success("Settings saved successfully!")
        st.rerun()

# --- TRADELOGIC UI THEME ---
st.markdown("""
    <style>
        .stApp { background-color: #F8F9FA; color: #1E1E1E; }
        h1, h2, h3 { color: #000000 !important; font-weight: 700; font-family: 'Inter', sans-serif; }
        h4, h5 { color: #5F6368 !important; font-weight: 600; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            background-color: #FFFFFF;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            border: 1px solid #F1F3F4;
            padding: 24px;
            margin-bottom: 15px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='color: #1A73E8;'>📊 TradeLogic Dashboard</h2>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def fetch_data(use_fyers, fyers_app_id, fyers_token, lookback, chartink_url, rr_ratio):
    agents = SwingTradingAgents(
        use_fyers=use_fyers,
        fyers_app_id=fyers_app_id,
        fyers_token=fyers_token,
        chartink_url=chartink_url
    )
    sector_rrg, stocks_df, dynamic_risk, logs, df_pipeline = agents.run_pipeline(
        lookback_days=lookback,
        rr_ratio=float(rr_ratio.split(":")[1])
    )
    return stocks_df, df_pipeline

if not st.session_state.fyers_app_id or not st.session_state.fyers_token:
    st.warning("🔑 **Fyers API Configuration Required:** Please enter your Fyers App ID and log in using the sidebar button to retrieve live market data from Fyers API.")
else:
    with st.spinner("🚀 Processing Live Market Data..."):
        try:
            stocks_df, df_pipeline = fetch_data(
                True,
                st.session_state.fyers_app_id,
                st.session_state.fyers_token,
                lookback_days,
                st.session_state.chartink_url,
                st.session_state.rr_ratio
            )
        except Exception as e:
            stocks_df, df_pipeline = pd.DataFrame(), pd.DataFrame()
            st.error(f"Error fetching data: {e}")

    # 1. PASSED STOCKS TABLE
    with st.container(border=True):
        st.subheader("🎯 Final Filtered Stock List (Momentum Setup Passed)")
        if stocks_df is not None and not stocks_df.empty:
            st.dataframe(
                stocks_df, 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.warning("⚠️ No stocks passed all filtering criteria today.")

    # 2. SCANNING PIPELINE REPORT
    with st.container(border=True):
        st.subheader("🔍 Complete Stock Scanning Report")
        st.caption("Real-time filtering pipeline based on Nifty return, Sector return, Price structure, Volume, and Weekly Move checks.")
        
        if df_pipeline is not None and not df_pipeline.empty:
            st.info(f"📋 **Chartink Scanned Source:** {st.session_state.chartink_url}\n\nFound **{len(df_pipeline)} raw candidates** from the scan. Below is the multi-level filtration report:")
            st.dataframe(
                df_pipeline,
                column_config={
                    "Stock": st.column_config.TextColumn("Stock name"),
                    "Sector": st.column_config.TextColumn("Sector"),
                    "Current Price (₹)": st.column_config.TextColumn("Current price"),
                    "Return vs Nifty": st.column_config.TextColumn("Return vs Nifty"),
                    "Return vs Sector": st.column_config.TextColumn("Return vs Sector"),
                    "Status": st.column_config.TextColumn("Status"),
                    "Reason": st.column_config.TextColumn("Pass/Fail reason")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No scanning pipeline data generated. Check Fyers API connection or Chartink URL.")
