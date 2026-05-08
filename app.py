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

# Inject Custom CSS for Premium Look & Boxes
st.markdown("""
    <style>
        .stApp { background-color: #F4F6F9; color: #1E1E1E; }
        .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
        h1 { color: #0D47A1 !important; font-weight: 800; }
        h2, h3 { color: #1565C0 !important; }
        /* Add shadows to containers to make them look like real boxes */
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
            background-color: #FFFFFF;
            padding: 10px;
            border: 1px solid #E0E0E0;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Premium AI Swing Trading System")

# --- INITIALIZE JOURNAL TO CALCULATE DYNAMIC CAPITAL ---
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

st.info(f"💰 **Total Capital:** ₹{current_capital:,.2f} | 🛡️ **Max Trades:** 3 | 🎯 **Capital Per Trade:** ₹{current_capital/3:,.2f}")

@st.cache_data(ttl=3600)
def fetch_data(capital):
    agents = SwingTradingAgents(current_capital=capital)
    stocks_df = agents.run_pipeline()
    return agents.sector_rrg, stocks_df, agents.risk_per_trade

with st.spinner(f"🚀 AI is calculating Position Sizes based on your ₹{current_capital:,.2f} capital..."):
    sector_rrg, stocks_df, dynamic_risk = fetch_data(current_capital)

# --- SPLIT LAYOUT (LIKE THE MOCKUP) ---
col_left, col_right = st.columns([1.2, 1], gap="large")

with col_left:
    with st.container(border=True):
        st.subheader("🎯 The Final Decision (Strictly Top 2)")
        st.markdown(f"*Risk per trade automatically adjusted to **₹{dynamic_risk:,.2f}***")
        
        if stocks_df is not None and not stocks_df.empty:
            st.dataframe(stocks_df, use_container_width=True, hide_index=True)
            st.success(f"✅ Here are your Top {len(stocks_df)} safest setups.")
        else:
            st.warning("⚠️ Market is too stretched. No stocks passed the strict filters today.")
            
    with st.container(border=True):
        st.subheader("🌐 Sector Relative Rotation Graph (RRG)")
        if sector_rrg:
            rrg_data = [{'Sector': sec, 'RS-Ratio': data['Ratio'], 'RS-Momentum': data['Momentum'], 'Quadrant': data['Quadrant']} for sec, data in sector_rrg.items()]
            df_rrg = pd.DataFrame(rrg_data)
            color_map = {'Leading': 'green', 'Improving': 'blue', 'Weakening': 'orange', 'Lagging': 'red'}
            fig = px.scatter(df_rrg, x="RS-Ratio", y="RS-Momentum", text="Sector", color="Quadrant", color_discrete_map=color_map, size_max=60)
            fig.add_hline(y=100, line_dash="dash", line_color="gray")
            fig.add_vline(x=100, line_dash="dash", line_color="gray")
            fig.update_traces(textposition='top center', marker=dict(size=12))
            fig.update_layout(plot_bgcolor='rgba(255,255,255,1)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#1E1E1E'), height=350, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig, use_container_width=True)

with col_right:
    with st.container(border=True):
        st.subheader("🤖 Chat Journal Agent")
        st.caption("Tell me your trades! E.g., 'Bought TCS at 3500' or 'TCS target hit'.")
        
        # Chat history container with fixed height
        chat_container = st.container(height=300)
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [{"role": "assistant", "content": "Hello Boss! I am ready to log your trades."}]

        for msg in st.session_state.chat_history:
            with chat_container.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_input := st.chat_input("Type here..."):
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
        st.subheader("📊 Live Journal Data")
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
