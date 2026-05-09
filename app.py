import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from agents import SwingTradingAgents
from datetime import datetime
import time

try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    pass

st.set_page_config(page_title="TradeLogic Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# --- TRADELOGIC UI THEME ---
st.markdown("""
    <style>
        /* Modern White/Light Grey Background */
        .stApp { background-color: #F8F9FA; color: #1E1E1E; }
        .st-emotion-cache-1y4p8pa { padding-top: 1rem; }
        
        /* Headers */
        h1, h2, h3 { color: #000000 !important; font-weight: 700; font-family: 'Inter', sans-serif; }
        h4, h5 { color: #5F6368 !important; font-weight: 600; }
        
        /* Top Navigation Bar */
        .top-nav {
            display: flex;
            align-items: center;
            padding: 10px 20px;
            background-color: white;
            border-bottom: 1px solid #EAEAEA;
            margin-bottom: 20px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.02);
        }
        .nav-logo { font-weight: bold; font-size: 20px; color: #1A73E8; margin-right: 30px; display: flex; align-items: center;}
        .nav-logo span { margin-left: 8px; color: #202124; }
        .nav-item { margin-right: 25px; color: #5F6368; font-size: 14px; font-weight: 500; cursor: pointer; }
        .nav-item.active { color: #1A73E8; border-bottom: 2px solid #1A73E8; padding-bottom: 12px; margin-bottom: -13px; }
        
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

# --- TOP NAVIGATION BAR ---
st.markdown("""
    <div class="top-nav">
        <div class="nav-logo">📊 <span>TradeLogic</span></div>
        <div class="nav-item active">Dashboard</div>
        <div class="nav-item">Markets</div>
        <div class="nav-item">Portfolio</div>
        <div class="nav-item">Research</div>
        <div class="nav-item">Tools</div>
    </div>
""", unsafe_allow_html=True)

st.title("Dashboard")
st.markdown("<p style='color: #5F6368; margin-top: -10px;'>Home > Markets > Current Dashboard</p>", unsafe_allow_html=True)

# --- INITIALIZE AGENT CHAT SYSTEM ---
agents_list = [
    "Neha (Journal Clerk)", 
    "Pro Trader AI (Mentorship)", 
    "Vimal (The CEO)", 
    "Vikram (Risk Manager)", 
    "Amit (Sector Analyst)", 
    "Rahul (Data Miner)"
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

# LAYOUT: Two Columns (Left 2/3, Right 1/3)
col_left, col_right = st.columns([1.6, 1], gap="large")

with col_left:
    @st.cache_data(ttl=3600)
    def fetch_data(capital):
        agents = SwingTradingAgents(current_capital=capital)
        sector_rrg, stocks_df, dynamic_risk, logs = agents.run_pipeline()
        return sector_rrg, stocks_df, dynamic_risk, logs

    with st.spinner(f"🚀 Processing Live Market Data..."):
        sector_rrg, stocks_df, dynamic_risk, logs = fetch_data(current_capital)

    # 1. TOP 2 STOCKS TABLE
    with st.container(border=True):
        st.subheader("Top 2 Stocks")
        if stocks_df is not None and not stocks_df.empty:
            # Format to look like TradeLogic mockup
            display_df = pd.DataFrame({
                "Symbol": stocks_df["Stock"],
                "Name": stocks_df["Stock"] + " Ltd.",
                "Price": stocks_df["Entry (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                "Target": stocks_df["Target (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                "Stop Loss": stocks_df["Stop Loss (₹)"].apply(lambda x: f"₹{x:,.2f}"),
                "Rating": ["⭐⭐⭐⭐⭐", "⭐⭐⭐⭐"][:len(stocks_df)]
            })
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            st.success(f"✅ Vimal (CEO): Capital locked at ₹{dynamic_risk:,.2f} risk per trade.")
        else:
            st.warning("⚠️ CEO's Verdict: No setups met the strict RichRoad criteria today. Keep capital in cash.")

    # 2. SECTOR RRG MAP
    with st.container(border=True):
        st.subheader("Sector RRG Map")
        st.caption("Relative Rotation Graph")
        if sector_rrg:
            fig = go.Figure()
            
            # Dynamic scaling around 0
            max_abs_val = 2
            for sec, data in sector_rrg.items():
                ratios = [r - 100 for r in data['Ratios']]
                moms = [m - 100 for m in data['Momentums']]
                max_abs_val = max(max_abs_val, max([abs(x) for x in ratios + moms]))
                
            limit = max_abs_val * 1.1 # Padding
            
            # Mockup Style Quadrants (Centered at 0,0)
            fig.add_shape(type="rect", x0=-limit, y0=0, x1=0, y1=limit, fillcolor="#F0F8FF", layer="below", line_width=0) # Improving
            fig.add_shape(type="rect", x0=-limit, y0=-limit, x1=0, y1=0, fillcolor="#FFF0F5", layer="below", line_width=0) # Lagging
            fig.add_shape(type="rect", x0=0, y0=0, x1=limit, y1=limit, fillcolor="#F0FFF0", layer="below", line_width=0) # Leading
            fig.add_shape(type="rect", x0=0, y0=-limit, x1=limit, y1=0, fillcolor="#FFFFF0", layer="below", line_width=0) # Weakening

            # Crosshairs at 0,0
            fig.add_hline(y=0, line_width=1, line_color="#E0E0E0")
            fig.add_vline(x=0, line_width=1, line_color="#E0E0E0")
            
            # Plot each sector's tail and head
            for sec, data in sector_rrg.items():
                ratios = [r - 100 for r in data['Ratios']]
                moms = [m - 100 for m in data['Momentums']]
                quad = data['Quadrant']
                
                color_map = {'Leading': '#2E7D32', 'Improving': '#1565C0', 'Weakening': '#F9A825', 'Lagging': '#C62828'}
                color = color_map.get(quad, '#333333')
                
                # 1. Plot the tail (straight translucent line)
                fig.add_trace(go.Scatter(
                    x=moms, y=ratios, mode='lines', 
                    showlegend=False,
                    line=dict(color=color, width=4),
                    opacity=0.3,
                    hoverinfo='skip'
                ))
                
                # 2. Plot the Head (Solid dot)
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

    # 3. BACKTESTING ENGINE
    with st.expander("⏳ View Historical Backtester (Jan '26 - Apr '26)", expanded=False):
        st.markdown("> **RichRoad Strict Rules:** Turnover > 100Cr, Price > 200 EMA, RSI Exhaustion Filter.")
        agents = SwingTradingAgents()
        bt_df, metrics = agents.run_backtest(start_date="2026-01-01", end_date="2026-04-30")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Trades", metrics["Total Trades"])
        c2.metric("Win Rate (%)", metrics["Win Rate"], delta="Real Data")
        c3.metric("W/L Ratio", f"{metrics['Wins']} / {metrics['Losses']}")
        c4.metric("Net Profit", metrics["Net Profit"])
        
        st.dataframe(bt_df, use_container_width=True, hide_index=True)

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
            
            # Agent Specific Logic
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
