import yfinance as yf
import pandas as pd
import math

class SwingTradingAgents:
    def __init__(self, current_capital=50000):
        self.capital = current_capital
        self.max_holdings = 2

    def fetch_chartink_stocks(self):
        return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ITC.NS", "LT.NS"]

    def run_backtest(self, start_date="2026-01-01", end_date="2026-04-30"):
        stocks = self.fetch_chartink_stocks()
        capital = 50000
        trades = []
        positions = []
        data_map = {s: yf.download(s, start="2025-06-01", end=end_date, progress=False) for s in stocks}
        bench = yf.download("^NSEI", start="2025-06-01", end=end_date, progress=False)
        
        for date in bench.loc[start_date:end_date].index:
            still_holding = []
            for pos in positions:
                df = data_map[pos['Stock']]
                if date not in df.index: continue
                price = df.loc[date, 'Close'].iloc[0]
                if price >= pos['Target'] or price <= pos['SL']:
                    pnl = (price - pos['Entry']) * pos['Qty']
                    capital += (price * pos['Qty'])
                    trades.append({"Date": date.strftime("%Y-%m-%d"), "Stock": pos['Stock'], "Status": "Won" if price >= pos['Target'] else "Lost", "P&L": round(pnl, 2)})
                else: still_holding.append(pos)
            positions = still_holding
            
            if len(positions) < self.max_holdings:
                for s in stocks:
                    df = data_map[s]
                    if date not in df.index: continue
                    price = df.loc[date, 'Close'].iloc[0]
                    ema200 = df.loc[:date]['Close'].ewm(span=200).mean().iloc[-1]
                    if price > ema200:
                        qty = math.floor((capital / 2) / price)
                        if qty > 0:
                            sl = price * 0.95
                            target = price + (2 * (price - sl))
                            positions.append({'Stock': s, 'Entry': price, 'Qty': qty, 'SL': sl, 'Target': target})
                            capital -= (qty * price)
                            break
        
        df_trades = pd.DataFrame(trades)
        wins = len(df_trades[df_trades["Status"] == "Won"]) if not df_trades.empty else 0
        metrics = {"Total Trades": len(df_trades), "Wins": wins, "Losses": len(df_trades)-wins, "Win Rate": f"{(wins/len(df_trades))*100:.1f}%" if len(df_trades)>0 else "0%", "Net Profit": f"₹{capital - 50000:,.2f}"}
        return df_trades, metrics
