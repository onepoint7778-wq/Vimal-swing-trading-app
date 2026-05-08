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

st.set_page_config(page_title="AI Swing Trading Dashboard", page_icon="📈", layout="wide")

st.markdown("""
    <style>
        .stApp { background-color: #0E1117; color: #FAFAFA; }
        h1, h2, h3 { color: #00E5FF !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 AI Swing Trading System (Dynamic Capital)")

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

st.markdown(f"**Total Capital:** ₹{current_capital:,.2f} | **Max Trades:** 3 | **Capital Per Trade:** ₹{current_capital/3:,.2f}")

tab1, tab2, tab3 = st.tabs(["📊 Final Selection (Top 2)", "🌐 Sector RRG Map", "🤖 Chat Journal Agent"])

@st.cache_data(ttl=3600)
def fetch_data(capital):
    agents = SwingTradingAgents(current_capital=capital)
    stocks_df = agents.run_pipeline()
    return agents.sector_rrg, stocks_df, agents.risk_per_trade

with st.spinner(f"🚀 AI is calculating Position Sizes based on your ₹{current_capital:,.2f} capital..."):
    sector_rrg, stocks_df, dynamic_risk = fetch_data(current_capital)

with tab1:
    st.subheader(f"🎯 The Final Decision (Risk: ₹{dynamic_risk:,.2f} per trade)")
    st.info("💡 **Dynamic Compounding:** As your Journal P&L grows, your Capital per Trade automatically increases, but is strictly capped at 3 simultaneous trades.")
    
    if stocks_df is not None and not stocks_df.empty:
        st.dataframe(stocks_df, use_container_width=True, height=200)
        st.success(f"✅ Here are your Top {len(stocks_df)} safest setups. Quantity is auto-adjusted for your ₹{current_capital:,.2f} bank.")
    else:
        st.warning("⚠️ Market is too stretched. No stocks passed the strict filters today.")

with tab2:
    st.subheader("🌐 Sector Relative Rotation Graph (RRG)")
    if sector_rrg:
        rrg_data = [{'Sector': sec, 'RS-Ratio': data['Ratio'], 'RS-Momentum': data['Momentum'], 'Quadrant': data['Quadrant']} for sec, data in sector_rrg.items()]
        df_rrg = pd.DataFrame(rrg_data)
        color_map = {'Leading': 'green', 'Improving': 'blue', 'Weakening': 'yellow', 'Lagging': 'red'}
        fig = px.scatter(df_rrg, x="RS-Ratio", y="RS-Momentum", text="Sector", color="Quadrant", color_discrete_map=color_map, size_max=60)
        fig.add_hline(y=100, line_dash="dash", line_color="gray")
        fig.add_vline(x=100, line_dash="dash", line_color="gray")
        fig.update_traces(textposition='top center', marker=dict(size=12))
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), height=600)
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("🤖 Talk to your Journal Agent")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "assistant", "content": "Hello Boss! Tell me your trades to update the capital. E.g., 'Bought TCS at 3500 target 3800' or 'TCS target hit'."}]

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Tell me about your trade..."):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        ui_lower = user_input.lower()
        reply = "I didn't quite catch that. Try 'buy [stock] at [price]' or '[stock] hit'."
        
        if "buy" in ui_lower or "bought" in ui_lower:
            words = ui_lower.split()
            try:
                stock_idx = words.index("buy") + 1 if "buy" in words else words.index("bought") + 1
                stock = words[stock_idx].upper()
                new_trade = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "Stock": stock, "Entry": 0, "Quantity": 1, "Status": "Open", "P&L": 0}])
                st.session_state.journal = pd.concat([st.session_state.journal, new_trade], ignore_index=True)
                reply = f"✅ Noted Boss! Added **{stock}** to the Journal. Capital remains ₹{current_capital:,.2f} until closed."
            except:
                reply = "I see you bought something, but couldn't parse the stock name. Try 'buy RELIANCE'."
                
        elif "hit" in ui_lower or "sold" in ui_lower or "exit" in ui_lower:
            stock_match = [s for s in st.session_state.journal['Stock'].unique() if s.lower() in ui_lower]
            if stock_match:
                stock = stock_match[0]
                status = "Won" if "target" in ui_lower or "won" in ui_lower else "Lost"
                
                # Dynamic P&L Demo (Since strict 1:3 RR with dynamic 2% risk)
                pnl = dynamic_risk * 3 if status == "Won" else -dynamic_risk
                
                st.session_state.journal.loc[st.session_state.journal['Stock'] == stock, 'Status'] = status
                st.session_state.journal.loc[st.session_state.journal['Stock'] == stock, 'P&L'] = pnl
                
                reply = f"🎯 Done! Closed **{stock}** as '{status}'. P&L is updated by ₹{pnl:,.2f}. Your capital will grow!"
                # Force rerun to update capital at the top
                st.rerun()
            else:
                reply = "Which stock hit the target? I couldn't find it in your open trades."

        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

    st.divider()
    st.markdown("### 📊 Live Journal Data (Edit P&L manually if needed)")
    edited_df = st.data_editor(
        df_journal, num_rows="dynamic",
        column_config={"Status": st.column_config.SelectboxColumn(options=["Open", "Won", "Lost"])},
        use_container_width=True
    )
    if st.button("💾 Save to Cloud / Update Capital"):
        try:
            conn.update(worksheet="Journal", data=edited_df)
            st.success("Saved to Google Sheets!")
        except:
            st.session_state.journal = edited_df
            st.success("Saved locally. Refresh the page to see your updated Capital!")
