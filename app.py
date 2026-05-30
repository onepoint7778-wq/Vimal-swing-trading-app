import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from agents import SwingTradingAgents
from datetime import datetime
import time
import json
import os
import hashlib
import requests

try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    pass

st.set_page_config(page_title="TradeLogic Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

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
        "use_fyers": False,
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
    st.session_state.use_fyers = config.get("use_fyers", False)
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
    # Use saved config values to authenticate
    app_id = config.get("fyers_app_id", "")
    secret_key = config.get("fyers_secret_key", "")
    
    if app_id and secret_key:
        with st.spinner("🔑 Validating Fyers Auth Code & Generating Token..."):
            try:
                # 1. Generate appIdHash (SHA-256 of app_id:secret_key)
                hash_input = f"{app_id}:{secret_key}"
                app_id_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                
                # 2. Call validate-authcode endpoint
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
                        st.session_state.use_fyers = True
                        
                        # Save updated config
                        config["fyers_token"] = token
                        config["use_fyers"] = True
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
            
            # Clear query params
            st.query_params.clear()
    else:
        st.warning("⚠️ Auth code received, but App ID or Secret Key was not configured/saved. Please configure them first and retry.")
        st.query_params.clear()

# --- STREAMLIT SIDEBAR SETTINGS ---
with st.sidebar:
    st.markdown("### 🔌 Market Data Settings")
    provider = st.radio(
        "Select Data Feed Source:",
        ["yfinance (Free, Rate-Limited)", "Fyers API (Safe & Fast)"],
        index=1 if st.session_state.use_fyers else 0
    )
    
    use_fyers = (provider == "Fyers API (Safe & Fast)")
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
    
    st.markdown("#### ⚙️ Scanner & Backtest Controls")
    rr_options = ["1:2", "1:2.5", "1:3"]
    default_idx = rr_options.index(st.session_state.rr_ratio) if st.session_state.rr_ratio in rr_options else 0
    rr_label = st.selectbox("Risk-Reward Ratio:", rr_options, index=default_idx)
    
    if st.button("💾 Save & Apply Settings"):
        st.session_state.use_fyers = use_fyers
        st.session_state.fyers_app_id = fyers_app_id
        st.session_state.fyers_secret_key = fyers_secret_key
        st.session_state.fyers_redirect_uri = fyers_redirect_uri
        st.session_state.fyers_token = fyers_token
        st.session_state.chartink_url = chartink_url
        st.session_state.rr_ratio = rr_label
        
        save_config({
            "use_fyers": use_fyers,
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
        /* Modern White/Light Grey Background */
        .stApp { background-color: #F8F9FA; color: #1E1E1E; }
        .st-emotion-cache-1y4p8pa { padding-top: 1rem; }
        
        /* Headers */
        h1, h2, h3 { color: #000000 !important; font-weight: 700; font-family: 'Inter', sans-serif; }
        h4, h5 { color: #5F6368 !important; font-weight: 600; }
        
        /* Tabs Styling (To look like TradeLogic Nav) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            border-bottom: 1px solid #EAEAEA;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            padding: 10px 16px;
            color: #5F6368;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            color: #1A73E8;
            border-bottom: 3px solid #1A73E8;
        }
        
        /* Clean Flat Containers */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            background-color: #FFFFFF;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            border: 1px solid #F1F3F4;
            padding: 24px;
            margin-bottom: 15px;
        }
        
        /* Dataframes & Tables */
        .stDataFrame { border-radius: 8px; }
        
        /* Chat styling */
        .agent-name { font-weight: 600; color: #1A73E8; margin-bottom: 5px; }
        
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='color: #1A73E8;'>📊 TradeLogic</h2>", unsafe_allow_html=True)

# THE 2 TABS
tab_dash, tab_back = st.tabs(["Dashboard", "Backtest"])

# --- INITIALIZE AGENT CHAT SYSTEM ---
agents_list = [
    "Neha (Journal Clerk)", 
    "Pro Trader AI (Mentorship)", 
    "Vimal (The CEO)", 
    "Vikram (Risk Manager)", 
    "Amit (Sector Analyst)", 
    "Rahul (Chartink Screener)"
]

if "chat_histories" not in st.session_state:
    st.session_state.chat_histories = {
        agent: [{"role": "assistant", "content": f"Hello! I am {agent.split(' ')[0]}. How can I assist you today?"}] 
        for agent in agents_list
    }

if "journal" not in st.session_state:
    st.session_state.journal = pd.DataFrame(columns=["Date", "Stock", "Entry", "Quantity", "Status", "P&L"])

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_journal = conn.read(worksheet="Journal")
except:
    df_journal = st.session_state.journal

# Calculate P&L and New Capital
initial_capital = 50000
total_pnl = pd.to_numeric(df_journal['P&L'], errors='coerce').sum() if not df_journal.empty else 0
current_capital = initial_capital + total_pnl

with tab_dash:
    # LAYOUT: Two Columns (Left 2/3, Right 1/3)
    col_left, col_right = st.columns([1.6, 1], gap="large")

    with col_left:
        @st.cache_data(ttl=3600)
        def fetch_data(capital, use_fyers, fyers_app_id, fyers_token, lookback, chartink_url, rr_ratio):
            agents = SwingTradingAgents(
                current_capital=capital,
                use_fyers=use_fyers,
                fyers_app_id=fyers_app_id,
                fyers_token=fyers_token,
                chartink_url=chartink_url
            )
            sector_rrg, stocks_df, dynamic_risk, logs, df_pipeline = agents.run_pipeline(
                lookback_days=lookback,
                rr_ratio=float(rr_ratio.split(":")[1])
            )
            return sector_rrg, stocks_df, dynamic_risk, logs, df_pipeline

        with st.spinner(f"🚀 Processing Live Market Data..."):
            sector_rrg, stocks_df, dynamic_risk, logs, df_pipeline = fetch_data(
                current_capital,
                st.session_state.use_fyers,
                st.session_state.fyers_app_id,
                st.session_state.fyers_token,
                lookback_days,
                st.session_state.chartink_url,
                st.session_state.rr_ratio
            )

        # Check if fetch failed (usually due to rate limits or invalid credentials)
        if df_pipeline is None or df_pipeline.empty:
            st.error("⚠️ **Market Data Connection Error:** Unable to fetch Nifty 50 index data or sector data.\n\n"
                     "* **If using yfinance:** Streamlit Cloud servers are frequently blocked by Yahoo Finance due to rate limits. "
                     "Please switch to **Fyers API** in the sidebar settings for a guaranteed stable and fast data feed.\n"
                     "* **If using Fyers API:** Please make sure you have entered the correct Fyers App ID, Secret Key, and Redirect URI, "
                     "clicked 'Save Settings', and then successfully logged in via the 'Log In & Generate Access Token' button.")

        # 1. TOP 2 STOCKS TABLE
        with st.container(border=True):
            st.subheader("🎯 Top 2 Stocks (Setup Confirmed)")
            if stocks_df is not None and not stocks_df.empty:
                display_df = pd.DataFrame({
                    "Symbol": stocks_df["Stock"],
                    "Name": stocks_df["Stock"] + " Ltd.",
                    "Price": stocks_df["Entry (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                    "Stop Loss": stocks_df["Stop Loss (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                    "Target (1:2)": stocks_df["Target (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                    "Qty": stocks_df["Quantity"],
                    "Max Risk": stocks_df["Max Risk (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                    "Remark": stocks_df["Remark"]
                })
                
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True
                )
                st.success(f"✅ Vimal (CEO): Position Sizing set to 50% Capital (₹{current_capital/2:,.2f} per stock).")
            else:
                st.warning("⚠️ CEO's Verdict: No setups met the strict RichRoad criteria today. Keep capital in cash.")

        # 2. SCANNING PIPELINE REPORT (NEW)
        with st.container(border=True):
            st.subheader("🔍 Complete Stock Scanning Report")
            st.caption("AI Agents real-time multi-level filtering pipeline (Chartink candidates & Nifty heavyweights)")
            if df_pipeline is not None and not df_pipeline.empty:
                st.dataframe(
                    df_pipeline,
                    column_config={
                        "Stock": st.column_config.TextColumn("Ticker", help="Stock Symbol"),
                        "Sector Strong": st.column_config.TextColumn("Sector > Nifty?", help="Is the stock's sector outperforming Nifty 50?"),
                        "RS Status": st.column_config.TextColumn("RS Filter", help="Is the stock outperforming both Nifty and its Sector?"),
                        "Trend (Higher H/L)": st.column_config.TextColumn("Trend Check", help="Is Price structure showing Higher Highs & Higher Lows?"),
                        "Volume Check": st.column_config.TextColumn("Vol Check", help="Is daily volume above the 20-day SMA?"),
                        "Weekly Return": st.column_config.TextColumn("Weekly Return", help="Return this week (must be <= 10% to prevent chasing)"),
                        "Status": st.column_config.TextColumn("Final Status"),
                        "Reason": st.column_config.TextColumn("Filter Reason")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No scanning pipeline data generated. Check market data connections.")

        # 3. SECTOR RRG MAP
        with st.container(border=True):
            st.subheader("Sector RRG Map")
            st.caption("Relative Rotation Graph")
            if sector_rrg:
                fig = go.Figure()
                
                max_abs_val = 2
                for sec, data in sector_rrg.items():
                    ratios = [r - 100 for r in data['Ratios']]
                    moms = [m - 100 for m in data['Momentums']]
                    max_abs_val = max(max_abs_val, max([abs(x) for x in ratios + moms]))
                    
                limit = max_abs_val * 1.1
                
                fig.add_shape(type="rect", x0=-limit, y0=0, x1=0, y1=limit, fillcolor="#F0F8FF", layer="below", line_width=0)
                fig.add_shape(type="rect", x0=-limit, y0=-limit, x1=0, y1=0, fillcolor="#FFF0F5", layer="below", line_width=0)
                fig.add_shape(type="rect", x0=0, y0=0, x1=limit, y1=limit, fillcolor="#F0FFF0", layer="below", line_width=0)
                fig.add_shape(type="rect", x0=0, y0=-limit, x1=limit, y1=0, fillcolor="#FFFFF0", layer="below", line_width=0)

                fig.add_hline(y=0, line_width=1, line_color="#E0E0E0")
                fig.add_vline(x=0, line_width=1, line_color="#E0E0E0")
                
                for sec, data in sector_rrg.items():
                    ratios = [r - 100 for r in data['Ratios']]
                    moms = [m - 100 for m in data['Momentums']]
                    quad = data['Quadrant']
                    
                    color_map = {'Leading': '#2E7D32', 'Improving': '#1565C0', 'Weakening': '#F9A825', 'Lagging': '#C62828'}
                    color = color_map.get(quad, '#333333')
                    
                    fig.add_trace(go.Scatter(
                        x=moms, y=ratios, mode='lines', 
                        showlegend=False,
                        line=dict(color=color, width=4),
                        opacity=0.3,
                        hoverinfo='skip'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[moms[-1]], y=[ratios[-1]], mode='markers+text',
                        name=sec,
                        marker=dict(color=color, size=14),
                        text=[sec],
                        textposition="top center",
                        textfont=dict(color='#1E1E1E', size=11, weight='bold')
                    ))
                
                fig.update_xaxes(range=[-limit, limit], showgrid=True, gridcolor='#F1F3F4', title="Momentum", zeroline=False)
                fig.update_yaxes(range=[-limit, limit], showgrid=True, gridcolor='#F1F3F4', title="Relative Strength", zeroline=False)
                fig.update_layout(plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF', font=dict(color='#5F6368'), height=450, margin=dict(l=20, r=20, t=30, b=20), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # --- MULTI-AGENT CHAT INTERFACE ---
        with st.container(border=True):
            selected_agent = st.selectbox("Select Agent to Chat:", agents_list)
            st.divider()
            
            chat_container = st.container(height=500)
            
            for msg in st.session_state.chat_histories[selected_agent]:
                with chat_container.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_input := st.chat_input(f"Message {selected_agent.split(' ')[0]}..."):
                st.session_state.chat_histories[selected_agent].append({"role": "user", "content": user_input})
                with chat_container.chat_message("user"):
                    st.markdown(user_input)
                    
                ui_lower = user_input.lower()
                
                if "Neha" in selected_agent:
                    if "buy" in ui_lower or "bought" in ui_lower:
                        try:
                            words = ui_lower.split()
                            idx = words.index("buy") + 1 if "buy" in words else words.index("bought") + 1
                            stock = words[idx].upper()
                            new_trade = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Stock": stock, "Entry": 0, "Quantity": 1, "Status": "Open", "P&L": 0}])
                            st.session_state.journal = pd.concat([st.session_state.journal, new_trade], ignore_index=True)
                            reply = f"✅ Noted! Added **{stock}** to your journal."
                        except: reply = "Couldn't parse the stock name. Try 'buy RELIANCE'."
                    elif "hit" in ui_lower or "sold" in ui_lower or "exit" in ui_lower:
                        reply = "🎯 Trade marked as closed in journal. Profit updated."
                    else:
                        reply = "I manage the journal. Tell me if you bought or sold a stock."
                        
                elif "Rahul" in selected_agent:
                    reply = f"I scanned the Top Nifty stocks today. {logs['scraper']}"
                    
                elif "Vikram" in selected_agent:
                    if "reject" in ui_lower or "why" in ui_lower:
                        rej_list = "\n".join([f"- **{r['Stock']}**: {r['Reason']}" for r in logs['risk'][:5]])
                        reply = f"I rejected {len(logs['risk'])} stocks today due to RichRoad rules. Here are some:\n{rej_list}"
                    else:
                        reply = "I am the Risk Manager. I enforce the 100Cr turnover and 200 EMA trend rules."
                        
                elif "Pro Trader AI" in selected_agent:
                    if "richroad" in ui_lower:
                        reply = "The RichRoad strategy focuses on Momentum. We look for stocks above the 200 EMA, with daily turnover > 100Cr, and a tight contraction before breakout."
                    else:
                        reply = "I am a Pro Trader AI. Ask me about technical indicators, RRG mapping, or specific trading strategies."
                        
                else:
                    reply = "I'm monitoring the dashboard. Everything looks solid."

                st.session_state.chat_histories[selected_agent].append({"role": "assistant", "content": reply})
                with chat_container.chat_message("assistant"):
                    st.markdown(reply)
                    st.rerun()

with tab_back:
    # 3. BACKTESTING ENGINE
    st.markdown("<div class='dashboard-header'>⏳ Historical Backtester (Jan '26 - Apr '26)</div>", unsafe_allow_html=True)
    st.markdown("<p style='color: #888;'>FII Institutional Rules: Fast Momentum, Nifty Relative Strength, Silent Accumulation (Low Vol), Target 1:2 RR.</p>", unsafe_allow_html=True)
    
    with st.spinner("Crunching historical market data..."):
        agents = SwingTradingAgents(
            use_fyers=st.session_state.use_fyers,
            fyers_app_id=st.session_state.fyers_app_id,
            fyers_token=st.session_state.fyers_token,
            chartink_url=st.session_state.chartink_url
        )
        bt_df, metrics = agents.run_backtest(
            start_date="2026-01-01", 
            end_date="2026-04-30", 
            lookback_days=lookback_days,
            rr_ratio=float(st.session_state.rr_ratio.split(":")[1])
        )
        
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Trades", metrics["Total Trades"])
        c2.metric("Win Rate", metrics["Win Rate"])
        c3.metric("Wins / Losses", f"{metrics['Wins']} / {metrics['Losses']}")
        c4.metric("Net Profit", metrics["Net Profit"])
        
    with st.container(border=True):
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Avg Return per Trade", metrics["Average Return"])
        c6.metric("Avg Holding Days", metrics["Average Holding Days"])
        c7.metric("Best Trade Return", metrics["Best Trade"])
        c8.metric("Worst Trade Return", metrics["Worst Trade"])
        
    # --- CAPITAL GROWTH CURVE CHART ---
    if not bt_df.empty:
        with st.container(border=True):
            cap_curve_data = [{"Date": "2026-01-01", "Capital (₹)": 50000.0}]
            running_cap = 50000.0
            for idx, row in bt_df.iterrows():
                running_cap += float(row["P&L"])
                cap_curve_data.append({
                    "Date": row["Exit Date"],
                    "Capital (₹)": running_cap
                })
            df_cap_curve = pd.DataFrame(cap_curve_data)
            
            fig_cap = px.line(
                df_cap_curve,
                x="Date",
                y="Capital (₹)",
                title="Capital Growth Curve (Starting: ₹50,000)",
                markers=True
            )
            fig_cap.update_layout(
                plot_bgcolor='#FFFFFF',
                paper_bgcolor='#FFFFFF',
                font=dict(color='#5F6368'),
                height=350,
                margin=dict(l=20, r=20, t=40, b=20),
                xaxis=dict(showgrid=True, gridcolor='#F1F3F4'),
                yaxis=dict(showgrid=True, gridcolor='#F1F3F4')
            )
            st.plotly_chart(fig_cap, use_container_width=True)
        
    st.subheader("Trade Log")
    st.dataframe(bt_df, use_container_width=True, hide_index=True)
