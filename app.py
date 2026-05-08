import streamlit as st
import pandas as pd
import plotly.express as px
from agents import SwingTradingAgents
from datetime import datetime
import re

try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    pass

st.set_page_config(page_title="AI Swing Trading Dashboard", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# --- PREMIUM BLUE & WHITE THEME ---
st.markdown("""
    <style>
        /* Deep Navy Blue Background */
        .stApp { background-color: #0A192F; color: #CCD6F6; }
        .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
        
        /* Headers */
        h1, h2, h3 { color: #64FFDA !important; font-weight: 700; }
        h4, h5 { color: #E6F1FF !important; font-weight: 600; }
        
        /* Glassmorphism White Boxes */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            background-color: rgba(255, 255, 255, 0.03);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 15px;
        }
        
        /* Dataframes & Inputs inside boxes */
        .stDataFrame { background-color: #112240; border-radius: 8px; }
        .stChatFloatingInputContainer { background-color: #112240 !important; }
        
        /* Custom Info Text */
        .ai-log { color: #8892B0; font-family: monospace; font-size: 14px; margin-bottom: 5px; }
        .ai-log strong { color: #64FFDA; }
        .ai-reject { color: #FF6B6B; font-family: monospace; font-size: 13px; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 AI Trading Floor (The Operations Room)")

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

@st.cache_data(ttl=3600)
def fetch_data(capital):
    agents = SwingTradingAgents(current_capital=capital)
    stocks_df = agents.run_pipeline()
    # Now returns: sector_rrg, df_results, risk_per_trade, logs
    return stocks_df

with st.spinner(f"🚀 Your AI Staff is currently analyzing the market..."):
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
        st.subheader("🌐 Sector Map (RRG)")
        if sector_rrg:
            rrg_data = [{'Sector': sec, 'RS-Ratio': data['Ratio'], 'RS-Momentum': data['Momentum'], 'Quadrant': data['Quadrant']} for sec, data in sector_rrg.items()]
            df_rrg = pd.DataFrame(rrg_data)
            color_map = {'Leading': '#64FFDA', 'Improving': '#2196F3', 'Weakening': '#FFC107', 'Lagging': '#FF5252'}
            fig = px.scatter(df_rrg, x="RS-Ratio", y="RS-Momentum", text="Sector", color="Quadrant", color_discrete_map=color_map, size_max=60)
            fig.add_hline(y=100, line_dash="dash", line_color="gray")
            fig.add_vline(x=100, line_dash="dash", line_color="gray")
            fig.update_traces(textposition='top center', marker=dict(size=12))
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#CCD6F6'), height=350, margin=dict(l=20, r=20, t=30, b=20))
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
