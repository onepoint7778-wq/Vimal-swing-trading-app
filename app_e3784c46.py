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

# Tablet-friendly page config
st.set_page_config(page_title="GTF Eye Dashboard", page_icon="📊", layout="wide")

CONFIG_FILE = "config.json"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "fyers_app_id": "",
        "fyers_secret_key": "",
        "fyers_token": "",
        "fyers_redirect_uri": "https://vimal-swing-trading-app-st43utvpyng3zswmkaqot2.streamlit.app/",
        "chartink_url": "",
        "manual_stocks": "",
        "rr_ratio": "1:2",
    }


def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f)
    except:
        pass


config = load_config()

for key, default in {
    "fyers_app_id": "",
    "fyers_secret_key": "",
    "fyers_token": "",
    "fyers_redirect_uri": "https://vimal-swing-trading-app-st43utvpyng3zswmkaqot2.streamlit.app/",
    "chartink_url": "",
    "manual_stocks": "",
    "rr_ratio": "1:2",
}.items():
    if key not in st.session_state:
        st.session_state[key] = config.get(key, default)

# Auto Fyers auth code detection
auth_code = st.query_params.get("auth_code")
if auth_code:
    app_id = config.get("fyers_app_id", "")
    secret_key = config.get("fyers_secret_key", "")
    if app_id and secret_key:
        with st.spinner("🔑 Generating Fyers Access Token..."):
            try:
                hash_input = f"{app_id}:{secret_key}"
                app_id_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                val_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
                payload = {
                    "grant_type": "authorization_code",
                    "appIdHash": app_id_hash,
                    "code": auth_code,
                }
                res = requests.post(
                    val_url, json=payload, headers={"Content-Type": "application/json"}
                )
                if res.status_code == 200:
                    res_data = res.json()
                    if res_data.get("s") == "ok" and "access_token" in res_data:
                        token = res_data["access_token"]
                        st.session_state.fyers_token = token
                        config["fyers_token"] = token
                        save_config(config)
                        st.success("✅ Fyers login successful! Token saved securely.")
                        st.balloons()
                        time.sleep(2)
                    else:
                        st.error(
                            f"Auth failed: {res_data.get('message', 'Unknown error')}"
                        )
                else:
                    st.error(f"Server error {res.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
        st.query_params.clear()
        st.rerun()

# Sidebar - Optimized for clarity
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.markdown("### 🔌 Fyers API Connection")
    st.markdown("*(Your credentials are saved locally and securely)*")

    fyers_app_id = st.text_input(
        "App ID (Client ID):", value=st.session_state.fyers_app_id
    )
    fyers_secret_key = st.text_input(
        "Secret Key:", value=st.session_state.fyers_secret_key, type="password"
    )
    fyers_redirect_uri = st.text_input(
        "Redirect URI:", value=st.session_state.fyers_redirect_uri
    )

    if st.session_state.fyers_token:
        st.success("✅ Logged In")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.fyers_token = ""
            config["fyers_token"] = ""
            save_config(config)
            st.rerun()
    else:
        st.text_input("Access Token:", value="Not generated yet", disabled=True)

    if fyers_app_id and fyers_secret_key and fyers_redirect_uri:
        login_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={fyers_app_id}&redirect_uri={fyers_redirect_uri}&response_type=code&state=sample_state"
        st.markdown(
            f'<a href="{login_url}" target="_blank"><button style="width:100%; background:#1A73E8; color:white; padding:12px; border:none; border-radius:8px; cursor:pointer; font-weight:bold; font-size:16px; margin:10px 0;">🔑 Login with Fyers</button></a>',
            unsafe_allow_html=True,
        )
        st.caption(
            "1. Click Save Settings below first.\n2. Click 'Login with Fyers'.\n3. Approve on Fyers site. Token will auto-set!"
        )

    st.markdown("---")
    st.markdown("### 📊 Scan Settings")
    timeframe_label = st.selectbox(
        "Lookback Timeframe:", ["1 Week (5 Days)", "1 Month (20 Days)"], index=0
    )
    lookback_days = 5 if "1 Week" in timeframe_label else 20

    st.markdown("#### 📋 Stock Input")
    manual_stocks = st.text_area(
        "Paste Stocks (comma separated):",
        value=st.session_state.manual_stocks,
        help="e.g. RELIANCE, TCS, HDFCBANK, TITAN",
        height=120,
    )

    rr_options = ["1:2", "1:2.5", "1:3"]
    rr_label = st.selectbox(
        "Risk-Reward Ratio:",
        rr_options,
        index=rr_options.index(st.session_state.rr_ratio)
        if st.session_state.rr_ratio in rr_options
        else 0,
    )

    if st.button("💾 Save Settings", use_container_width=True, type="primary"):
        for k, v in {
            "fyers_app_id": fyers_app_id,
            "fyers_secret_key": fyers_secret_key,
            "fyers_redirect_uri": fyers_redirect_uri,
            "fyers_token": st.session_state.fyers_token,
            "manual_stocks": manual_stocks,
            "rr_ratio": rr_label,
        }.items():
            st.session_state[k] = v
        save_config(
            {
                "fyers_app_id": fyers_app_id,
                "fyers_secret_key": fyers_secret_key,
                "fyers_redirect_uri": fyers_redirect_uri,
                "fyers_token": st.session_state.fyers_token,
                "chartink_url": "",
                "manual_stocks": manual_stocks,
                "rr_ratio": rr_label,
            }
        )
        st.success("✅ Settings Saved Successfully!")
        st.rerun()

# App Styling - Tablet Optimized (Larger fonts, clear contrasts)
st.markdown(
    """
<style>
    .stApp { background-color: #F8F9FA; }
    h1, h2, h3 { color: #1A1A2E !important; font-weight: 700; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; font-size: 18px !important; padding: 12px 24px !important; }
    .stTabs [aria-selected="true"] { color: #1A73E8 !important; border-bottom: 4px solid #1A73E8 !important; }
    .big-metric { font-size: 2rem !important; font-weight: bold !important; color: #1A73E8 !important; }
    div[data-testid="stDataframe"] { font-size: 16px !important; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    "<h1 style='color:#1A73E8; text-align:center;'>📊 GTF Eye — Swing Trading Dashboard</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#666; font-size:18px;'>Find stocks outperforming Nifty & their Sectors with high Momentum.</p>",
    unsafe_allow_html=True,
)

tab_dash, tab_rrg, tab_back = st.tabs(
    ["🎯 Top Momentum Picks", "📈 Sector RRG", "⏳ Backtest"]
)


@st.cache_data(ttl=3600)
def fetch_data(fyers_app_id, fyers_token, lookback, rr_ratio, manual_stocks):
    agents = SwingTradingAgents(
        use_fyers=True,
        fyers_app_id=fyers_app_id,
        fyers_token=fyers_token,
        chartink_url="",
    )
    sector_rrg, stocks_df, dynamic_risk, logs, df_pipeline = agents.run_pipeline(
        lookback_days=lookback,
        rr_ratio=float(rr_ratio.split(":")[1]),
        manual_stocks=manual_stocks,
    )
    return sector_rrg, stocks_df, df_pipeline, logs


# ============ TAB 1: TOP MOMENTUM PICKS ============
with tab_dash:
    if not st.session_state.fyers_app_id or not st.session_state.fyers_token:
        st.warning(
            "🔑 Please enter Fyers App ID and Secret Key in the sidebar, click 'Save Settings', and then 'Login with Fyers'."
        )
    else:
        with st.spinner("🚀 Fetching market data & scanning stocks..."):
            try:
                sector_rrg, stocks_df, df_pipeline, logs = fetch_data(
                    st.session_state.fyers_app_id,
                    st.session_state.fyers_token,
                    lookback_days,
                    st.session_state.rr_ratio,
                    st.session_state.manual_stocks,
                )
            except Exception as e:
                sector_rrg, stocks_df, df_pipeline, logs = (
                    {},
                    pd.DataFrame(),
                    pd.DataFrame(),
                    {},
                )
                st.error(f"Error fetching data: {e}")

        if stocks_df is not None and not stocks_df.empty:
            st.markdown("### 🏆 Top Ranked Stocks (Sorted by Momentum)")
            st.markdown(
                "These stocks are outperforming BOTH Nifty 50 and their respective Sectors, with strong price action."
            )

            # Enhance the dataframe display for tablets
            display_df = stocks_df.copy()

            # Color code the momentum score for better visual parsing
            def color_momentum(val):
                try:
                    score = float(str(val).split("/")[0])
                    if score >= 8.0:
                        return "background-color: #d4edda; color: #155724; font-weight: bold;"  # Green
                    elif score >= 6.0:
                        return "background-color: #fff3cd; color: #856404; font-weight: bold;"  # Yellow
                    else:
                        return "background-color: #f8d7da; color: #721c24;"  # Red
                except:
                    return ""

            styled_df = display_df.style.applymap(
                color_momentum, subset=["Momentum Score"]
            )
            st.dataframe(
                styled_df, use_container_width=True, hide_index=True, height=400
            )

            st.info(
                "💡 **Tip:** Focus on stocks with a Momentum Score of **8.0/10 or higher** for the best risk-reward setups."
            )
        else:
            st.warning(
                "⚠️ No stocks passed all strict filters today. Try adding more stocks in the 'Paste Stocks' box in the sidebar, or check the 'Full Scan Pipeline Report' below."
            )

        with st.expander(
            "🔍 View Full Scan Pipeline Report (Including Filtered Stocks)"
        ):
            if df_pipeline is not None and not df_pipeline.empty:
                passed = df_pipeline[df_pipeline["Status"] == "✅ Passed"]
                filtered = df_pipeline[df_pipeline["Status"] == "❌ Filtered"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Scanned", len(df_pipeline))
                c2.metric("✅ Passed", len(passed))
                c3.metric("❌ Filtered", len(filtered))
                st.dataframe(df_pipeline, use_container_width=True, hide_index=True)
            else:
                st.info("No stocks scanned yet. Enter stocks in the sidebar.")

# ============ TAB 2: SECTOR RRG ============
with tab_rrg:
    if not st.session_state.fyers_app_id or not st.session_state.fyers_token:
        st.warning("🔑 Please configure Fyers API in sidebar first.")
    else:
        with st.spinner("📈 Loading Sector RRG..."):
            try:
                sector_rrg, stocks_df, df_pipeline, logs = fetch_data(
                    st.session_state.fyers_app_id,
                    st.session_state.fyers_token,
                    lookback_days,
                    st.session_state.rr_ratio,
                    st.session_state.manual_stocks,
                )
            except Exception as e:
                sector_rrg = {}
                st.error(f"Error: {e}")

        if sector_rrg:
            quadrant_colors = {
                "Leading": "#00C853",
                "Improving": "#2979FF",
                "Weakening": "#FF6D00",
                "Lagging": "#D50000",
            }

            fig = go.Figure()

            # Background quadrants
            fig.add_shape(
                type="rect",
                x0=100,
                x1=110,
                y0=100,
                y1=110,
                fillcolor="rgba(0,200,83,0.08)",
                line_width=0,
            )
            fig.add_shape(
                type="rect",
                x0=90,
                x1=100,
                y0=100,
                y1=110,
                fillcolor="rgba(41,121,255,0.08)",
                line_width=0,
            )
            fig.add_shape(
                type="rect",
                x0=100,
                x1=110,
                y0=90,
                y1=100,
                fillcolor="rgba(255,109,0,0.08)",
                line_width=0,
            )
            fig.add_shape(
                type="rect",
                x0=90,
                x1=100,
                y0=90,
                y1=100,
                fillcolor="rgba(213,0,0,0.08)",
                line_width=0,
            )

            # Center lines
            fig.add_hline(y=100, line_dash="dash", line_color="gray", line_width=1)
            fig.add_vline(x=100, line_dash="dash", line_color="gray", line_width=1)

            # Sector dots + tails
            for sector, data in sector_rrg.items():
                quad = data["Quadrant"]
                color = quadrant_colors.get(quad, "gray")
                ratios = data["Ratios"]
                moms = data["Momentums"]

                # Tail line
                fig.add_trace(
                    go.Scatter(
                        x=ratios,
                        y=moms,
                        mode="lines",
                        line=dict(color=color, width=2, dash="dot"),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
                # Current dot
                fig.add_trace(
                    go.Scatter(
                        x=[ratios[-1]],
                        y=[moms[-1]],
                        mode="markers+text",
                        marker=dict(
                            size=16, color=color, line=dict(width=2, color="white")
                        ),
                        text=[sector],
                        textposition="top center",
                        textfont=dict(size=13, color="#333", weight="bold"),
                        name=f"{sector} ({quad})",
                        hovertemplate=f"<b>{sector}</b><br>Quadrant: {quad}<br>RS-Ratio: {ratios[-1]:.2f}<br>RS-Momentum: {moms[-1]:.2f}",
                    )
                )

            # Quadrant labels
            for label, x, y, color in [
                ("🟢 LEADING", 107, 109, "#00C853"),
                ("🔵 IMPROVING", 93, 109, "#2979FF"),
                ("🟠 WEAKENING", 107, 91, "#FF6D00"),
                ("🔴 LAGGING", 93, 91, "#D50000"),
            ]:
                fig.add_annotation(
                    x=x,
                    y=y,
                    text=f"<b>{label}</b>",
                    showarrow=False,
                    font=dict(size=14, color=color),
                )

            fig.update_layout(
                title="Sector Relative Rotation Graph (RRG) vs Nifty 50",
                xaxis_title="JdK RS-Ratio →",
                yaxis_title="JdK RS-Momentum →",
                xaxis=dict(range=[90, 110], showgrid=True, gridcolor="#EEEEEE"),
                yaxis=dict(range=[90, 110], showgrid=True, gridcolor="#EEEEEE"),
                plot_bgcolor="white",
                paper_bgcolor="white",
                height=600,
                legend=dict(orientation="v", x=1.01, y=1, font=dict(size=12)),
                margin=dict(l=60, r=200, t=60, b=60),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Sector table
            with st.container(border=True):
                st.subheader("📋 Sector Summary")
                sector_table = []
                for sec, data in sector_rrg.items():
                    sector_table.append(
                        {
                            "Sector": sec,
                            "Quadrant": data["Quadrant"],
                            "RS-Ratio": data.get("RS_Ratio", "-"),
                            "RS-Momentum": data.get("RS_Momentum", "-"),
                        }
                    )
                df_sec = pd.DataFrame(sector_table).sort_values(
                    "RS-Ratio", ascending=False
                )
                st.dataframe(df_sec, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ No RRG data loaded. Check Fyers token and try again.")

# ============ TAB 3: BACKTEST ============
with tab_back:
    st.subheader("⏳ Historical Backtest")
    if not st.session_state.fyers_app_id or not st.session_state.fyers_token:
        st.warning("🔑 Fyers API required. Configure in sidebar.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            bt_start = st.date_input("Start Date", value=datetime(2024, 1, 1))
        with col2:
            bt_end = st.date_input("End Date", value=datetime.now())

        if st.button("▶️ Run Backtest", use_container_width=True, type="primary"):
            with st.spinner("Crunching historical data..."):
                agents = SwingTradingAgents(
                    use_fyers=True,
                    fyers_app_id=st.session_state.fyers_app_id,
                    fyers_token=st.session_state.fyers_token,
                    chartink_url="",
                )
                bt_df, metrics = agents.run_backtest(
                    start_date=bt_start.strftime("%Y-%m-%d"),
                    end_date=bt_end.strftime("%Y-%m-%d"),
                    lookback_days=lookback_days,
                    rr_ratio=float(st.session_state.rr_ratio.split(":")[1]),
                )

                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total Trades", metrics["Total Trades"])
                    c2.metric("Win Rate", metrics["Win Rate"])
                    c3.metric(
                        "Wins / Losses", f"{metrics['Wins']} / {metrics['Losses']}"
                    )
                    c4.metric("Net Profit", metrics["Net Profit"])

                    c5, c6, c7, c8 = st.columns(4)
                    c5.metric("Avg Return", metrics["Average Return"])
                    c6.metric("Avg Holding", metrics["Average Holding Days"])
                    c7.metric("Best Trade", metrics["Best Trade"])
                    c8.metric("Worst Trade", metrics["Worst Trade"])

                if not bt_df.empty:
                    # Capital growth curve
                    cap_data = [
                        {"Date": bt_start.strftime("%Y-%m-%d"), "Capital (₹)": 50000.0}
                    ]
                    running_cap = 50000.0
                    for _, row in bt_df.iterrows():
                        running_cap += float(row["P&L"])
                        cap_data.append(
                            {"Date": row["Exit Date"], "Capital (₹)": running_cap}
                        )
                    df_cap = pd.DataFrame(cap_data)
                    fig_cap = px.line(
                        df_cap,
                        x="Date",
                        y="Capital (₹)",
                        title="Capital Growth Curve (Starting ₹50,000)",
                        markers=True,
                        color_discrete_sequence=["#1A73E8"],
                    )
                    fig_cap.update_layout(
                        plot_bgcolor="white", paper_bgcolor="white", height=350
                    )
                    st.plotly_chart(fig_cap, use_container_width=True)

                    # Trade log
                    st.subheader("📋 Trade Log")
                    st.dataframe(
                        bt_df[
                            [
                                "Entry Date",
                                "Exit Date",
                                "Stock",
                                "Entry",
                                "Stop Loss",
                                "Target",
                                "Status",
                                "P&L",
                                "Return %",
                                "Holding Days",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No trades executed in this date range.")
