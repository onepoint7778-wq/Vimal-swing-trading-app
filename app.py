import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from agents import SwingTradingAgents
from datetime import datetime

try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    pass

st.set_page_config(page_title="Corporate AI Trading System", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

# --- SHARPELY CORPORATE WHITE THEME ---
st.markdown("""
    <style>
        /* Pure White Background */
        .stApp { background-color: #FAFAFA; color: #1E1E1E; }
        .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
        
        /* Headers */
        h1, h2, h3 { color: #0A2540 !important; font-weight: 700; font-family: 'Inter', sans-serif; }
        h4, h5 { color: #425466 !important; font-weight: 600; }
        
        /* Clean Flat Boxes */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px;
            background-color: #FFFFFF;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.04);
            border: 1px solid #EAEAEA;
            padding: 20px;
        }
        
        /* Dataframes & Inputs inside boxes */
        .stDataFrame { border-radius: 8px; }
        
        /* Custom Info Text */
        .ai-log { color: #425466; font-size: 14px; margin-bottom: 5px; }
        .ai-log strong { color: #0066FF; }
        .ai-reject { color: #D32F2F; font-size: 13px; }
        
        /* Divider */
        hr { border-color: #EAEAEA; }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 Corporate AI Trading System")

# --- INITIALIZE JOURNAL ---
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

st.markdown(f"**💰 Total Capital:** ₹{current_capital:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp; **🛡️ Max Active Trades:** 3 &nbsp;&nbsp;|&nbsp;&nbsp; **🎯 Capital Per Trade:** ₹{current_capital/3:,.2f}")
st.divider()

# TAB LAYOUT: Main Dashboard vs Backtesting
tab1, tab2 = st.tabs(["📊 Live Trading Floor", "⏳ Historical Backtester (Jan - Apr)"])

with tab1:
    @st.cache_data(ttl=3600)
    def fetch_data(capital):
        agents = SwingTradingAgents(current_capital=capital)
        stocks_df = agents.run_pipeline()
        return stocks_df

    with st.spinner(f"🚀 AI Staff is analyzing the market..."):
        sector_rrg, stocks_df, dynamic_risk, logs = fetch_data(current_capital)

    # --- AI OPERATIONS ROOM (TOP SECTION) ---
    st.subheader("👨‍💻 Live Operations Room")
    col_op1, col_op2, col_op3 = st.columns(3)

    with col_op1:
        with st.container(border=True):
            st.markdown("#### 🕵️‍♂️ Rahul (Data Miner)")
            st.markdown(f"<div class='ai-log'><strong>Status:</strong> {logs['scraper']}</div>", unsafe_allow_html=True)

    with col_op2:
        with st.container(border=True):
            st.markdown("#### 📊 Amit (Sector Analyst)")
            st.markdown(f"<div class='ai-log'><strong>Status:</strong> {logs['analyst']}</div>", unsafe_allow_html=True)

    with col_op3:
        with st.container(border=True):
            st.markdown("#### 🛡️ Vikram (Risk Manager)")
            rejection_count = len(logs['risk'])
            st.markdown(f"<div class='ai-log'><strong>Status:</strong> Screened all stocks. {rejection_count} stocks rejected to protect capital.</div>", unsafe_allow_html=True)
            if rejection_count > 0:
                with st.expander("View Rejection Report"):
                    for rej in logs['risk']:
                        st.markdown(f"<div class='ai-reject'>🚫 <b>{rej['Stock']}</b>: {rej['Reason']}</div>", unsafe_allow_html=True)

    st.divider()

    # --- MAIN DASHBOARD ---
    col_left, col_right = st.columns([1.2, 1], gap="large")

    with col_left:
        with st.container(border=True):
            st.subheader("🧑‍💼 Vimal (The CEO)")
            st.markdown(f"<div class='ai-log'>Based on Vikram's risk parameters, here are the safest Top Picks for deployment. Risk per trade is locked at <b>₹{dynamic_risk:,.2f}</b>.</div>", unsafe_allow_html=True)
            
            if stocks_df is not None and not stocks_df.empty:
                st.dataframe(stocks_df, use_container_width=True, hide_index=True)
                st.success(f"✅ Setup Approved. Proceed with execution.")
            else:
                st.warning("⚠️ CEO's Verdict: Market conditions are too hostile today. Keep capital in cash. No execution.")
                
        with st.container(border=True):
            st.subheader("🌐 Sector RRG Map")
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
                # Top Left (Improving, Blue)
                fig.add_shape(type="rect", x0=-limit, y0=0, x1=0, y1=limit, fillcolor="#F0F8FF", layer="below", line_width=0)
                # Bottom Left (Lagging, Red)
                fig.add_shape(type="rect", x0=-limit, y0=-limit, x1=0, y1=0, fillcolor="#FFF0F5", layer="below", line_width=0)
                # Top Right (Leading, Green)
                fig.add_shape(type="rect", x0=0, y0=0, x1=limit, y1=limit, fillcolor="#F0FFF0", layer="below", line_width=0)
                # Bottom Right (Weakening, Yellow)
                fig.add_shape(type="rect", x0=0, y0=-limit, x1=limit, y1=0, fillcolor="#FFFFF0", layer="below", line_width=0)

                # Crosshairs at 0,0
                fig.add_hline(y=0, line_width=1, line_color="#333333")
                fig.add_vline(x=0, line_width=1, line_color="#333333")
                
                # Plot each sector's tail and head
                for sec, data in sector_rrg.items():
                    # X is Momentum, Y is Ratio (Matching Mockup)
                    ratios = [r - 100 for r in data['Ratios']]
                    moms = [m - 100 for m in data['Momentums']]
                    quad = data['Quadrant']
                    
                    color_map = {'Leading': '#2E7D32', 'Improving': '#1565C0', 'Weakening': '#F9A825', 'Lagging': '#C62828'}
                    color = color_map.get(quad, '#333333')
                    
                    # 1. Plot the tail (smooth, translucent line)
                    fig.add_trace(go.Scatter(
                        x=moms, y=ratios, mode='lines', 
                        showlegend=False,
                        line=dict(color=color, width=5),
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
                
                fig.update_xaxes(range=[-limit, limit], showgrid=True, gridcolor='#EAEAEA', title="Momentum", zeroline=False)
                fig.update_yaxes(range=[-limit, limit], showgrid=True, gridcolor='#EAEAEA', title="Relative Strength", zeroline=False)
                
                fig.update_layout(plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF', font=dict(color='#333333'), height=450, margin=dict(l=20, r=20, t=30, b=20), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

    with col_right:
        with st.container(border=True):
            st.subheader("🤖 Neha (Journal Clerk)")
            st.caption("E.g., 'Bought TCS at 3500' or 'TCS target hit'.")
            
            chat_container = st.container(height=300)
            
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = [{"role": "assistant", "content": "Hello Boss! I am ready to log your trades."}]

            for msg in st.session_state.chat_history:
                with chat_container.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if user_input := st.chat_input("Type your order here..."):
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with chat_container.chat_message("user"):
                    st.markdown(user_input)
                    
                ui_lower = user_input.lower()
                reply = "I didn't quite catch that. Try 'buy [stock]' or '[stock] hit'."
                
                if "buy" in ui_lower or "bought" in ui_lower:
                    words = ui_lower.split()
                    try:
                        stock_idx = words.index("buy") + 1 if "buy" in words else words.index("bought") + 1
                        stock = words[stock_idx].upper()
                        new_trade = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Stock": stock, "Entry": 0, "Quantity": 1, "Status": "Open", "P&L": 0}])
                        st.session_state.journal = pd.concat([st.session_state.journal, new_trade], ignore_index=True)
                        reply = f"✅ Noted! Added **{stock}** to the Journal."
                    except:
                        reply = "Couldn't parse the stock name. Try 'buy RELIANCE'."
                        
                elif "hit" in ui_lower or "sold" in ui_lower or "exit" in ui_lower:
                    stock_match = [s for s in st.session_state.journal['Stock'].unique() if s.lower() in ui_lower]
                    if stock_match:
                        stock = stock_match[0]
                        status = "Won" if "target" in ui_lower or "won" in ui_lower else "Lost"
                        pnl = dynamic_risk * 3 if status == "Won" else -dynamic_risk
                        
                        st.session_state.journal.loc[st.session_state.journal['Stock'] == stock, 'Status'] = status
                        st.session_state.journal.loc[st.session_state.journal['Stock'] == stock, 'P&L'] = pnl
                        
                        reply = f"🎯 Closed **{stock}** as '{status}'. P&L: ₹{pnl:,.2f}."
                    else:
                        reply = "Which stock? I couldn't find it in open trades."

                st.session_state.chat_history.append({"role": "assistant", "content": reply})
                with chat_container.chat_message("assistant"):
                    st.markdown(reply)
                    st.rerun()

        with st.container(border=True):
            st.subheader("📊 The Vault (Live Journal Data)")
            edited_df = st.data_editor(
                df_journal, num_rows="dynamic",
                column_config={"Status": st.column_config.SelectboxColumn(options=["Open", "Won", "Lost"])},
                use_container_width=True, hide_index=True
            )
            if st.button("💾 Update Cloud & Capital"):
                try:
                    conn.update(worksheet="Journal", data=edited_df)
                    st.success("Saved!")
                except:
                    st.session_state.journal = edited_df
                    st.success("Saved locally. Refresh page to update Capital!")

with tab2:
    st.subheader("⏳ AI Backtesting Engine (Simulated)")
    st.markdown("""
    > **Note:** Chartink does not provide historical scan results for free. 
    > Our AI has run a simulated backtest applying our strict **RRG Leading Sector + RSI Exhaustion Filter** 
    > across top Nifty stocks from **January 1, 2026** to **April 30, 2026** to calculate realistic Win Rates.
    """)
    
    agents = SwingTradingAgents()
    bt_df, metrics = agents.run_backtest(start_date="2026-01-01", end_date="2026-04-30")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Trades Taken", metrics["Total Trades"])
    col2.metric("Win Rate (%)", metrics["Win Rate"], delta="Profitable Model")
    col3.metric("Wins vs Losses", f"{metrics['Wins']}W / {metrics['Losses']}L")
    col4.metric("Net Profit", metrics["Net Profit"], delta="Capital Growth")
    
    st.divider()
    
    col_bt1, col_bt2 = st.columns([1.5, 1])
    with col_bt1:
        st.subheader("Trade Log (Jan - Apr 2026)")
        st.dataframe(bt_df, use_container_width=True, hide_index=True)
    with col_bt2:
        st.subheader("Capital Growth Curve")
        fig_eq = px.line(bt_df, x="Exit Date", y="Capital After", markers=True, title="Portfolio Value Over Time")
        fig_eq.update_layout(plot_bgcolor='#FFFFFF', paper_bgcolor='#FFFFFF', font=dict(color='#333333'))
        st.plotly_chart(fig_eq, use_container_width=True)
