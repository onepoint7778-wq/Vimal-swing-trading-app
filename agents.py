import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import math

class SwingTradingAgents:
    def __init__(self, current_capital=50000):
        self.chartink_url = "https://chartink.com/screener/richroad-pivot-points-weekly-scan-2028"
        self.capital = current_capital
        self.max_holdings = 3
        # Max allocation is dynamically exactly Capital / 3
        self.max_allocation = self.capital / self.max_holdings
        # Risk per trade is strictly 2% of current capital (e.g., 1000 on 50k, 1500 on 75k)
        self.risk_per_trade = self.capital * 0.02
        self.benchmark_ticker = '^NSEI'
        
        self.sector_map = {
            'Bank': '^NSEBANK', 'IT': '^CNXIT', 'Auto': '^CNXAUTO',
            'Pharma': '^CNXPHARMA', 'Metal': '^CNXMETAL', 'FMCG': '^CNXFMCG',
            'Energy': '^CNXENERGY'
        }
        self.sector_rrg = {}
        self.benchmark_data = None

    def fetch_chartink_stocks(self):
        try:
            with requests.Session() as s:
                r = s.get(self.chartink_url, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(r.text, 'html.parser')
                csrf = soup.select_one('meta[name="csrf-token"]')
                if not csrf: return ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"]
                
                scan_clause_match = re.search(r"scan_clause\s*=\s*'(.*?)'", r.text)
                if not scan_clause_match: return ["RELIANCE", "TCS"]
                
                res = s.post("https://chartink.com/screener/process", data={'scan_clause': scan_clause_match.group(1)}, 
                             headers={'x-csrf-token': csrf['content'], 'X-Requested-With': 'XMLHttpRequest', 'User-Agent': 'Mozilla/5.0'}, 
                             verify=False)
                data = res.json()
                if 'data' in data:
                    return [item['nsecode'] for item in data['data']]
                return []
        except:
            return ["TATASTEEL", "INFY", "ITC", "SBIN", "MARUTI"]

    def _calc_rrg(self, asset_series, bench_series):
        df = pd.concat([asset_series, bench_series], axis=1).dropna()
        df.columns = ['Asset', 'Bench']
        rs = df['Asset'] / df['Bench']
        
        rs_mean = rs.rolling(window=14).mean()
        rs_std = rs.rolling(window=14).std()
        rs_ratio = 100 + ((rs - rs_mean) / rs_std) * 5
        
        ratio_mean = rs_ratio.rolling(window=14).mean()
        ratio_std = rs_ratio.rolling(window=14).std()
        rs_mom = 100 + ((rs_ratio - ratio_mean) / ratio_std) * 5
        
        return rs_ratio.iloc[-1], rs_mom.iloc[-1]

    def _get_quadrant(self, ratio, momentum):
        if ratio > 100 and momentum > 100: return "Leading"
        if ratio > 100 and momentum <= 100: return "Weakening"
        if ratio <= 100 and momentum > 100: return "Improving"
        return "Lagging"

    def analyze_sectors_rrg(self):
        try:
            bench = yf.download(self.benchmark_ticker, period='6mo', progress=False)['Close']
            if isinstance(bench, pd.DataFrame): bench = bench.iloc[:, 0]
            self.benchmark_data = bench
        except: return
            
        for name, ticker in self.sector_map.items():
            try:
                asset = yf.download(ticker, period='6mo', progress=False)['Close']
                if isinstance(asset, pd.DataFrame): asset = asset.iloc[:, 0]
                ratio, mom = self._calc_rrg(asset, self.benchmark_data)
                self.sector_rrg[name] = {'Ratio': ratio, 'Momentum': mom, 'Quadrant': self._get_quadrant(ratio, mom)}
            except: pass
        return self.sector_rrg

    def get_stock_data(self, symbol):
        ticker = f"{symbol}.NS"
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo")
            if df.empty: return None, None
            
            sector = stock.info.get('sector', 'Unknown')
            for key in self.sector_map.keys():
                if key.lower() in sector.lower():
                    sector = key
                    break
            
            # Manual RSI (14)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI_14'] = 100 - (100 / (1 + rs))
            
            # Manual ATR (14)
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df['ATRr_14'] = tr.rolling(window=14).mean()
            
            # Manual Bollinger Bands (20, 2)
            sma = df['Close'].rolling(window=20).mean()
            std = df['Close'].rolling(window=20).std()
            df['BBU_20_2.0'] = sma + (2 * std)
            
            return df, sector
        except:
            return None, None

    def run_pipeline(self):
        self.analyze_sectors_rrg()
        stocks = self.fetch_chartink_stocks()
        
        results = []
        for stock in stocks:
            df, sector = self.get_stock_data(stock)
            if df is not None and len(df) > 50:
                latest = df.iloc[-1]
                entry = float(latest['Close'])
                atr = float(latest.get('ATRr_14', entry * 0.05))
                rsi = float(latest.get('RSI_14', 50))
                
                # Bollinger Bands values (pandas_ta creates columns like BBL_20_2.0, BBU_20_2.0)
                upper_bb_cols = [c for c in df.columns if c.startswith('BBU')]
                upper_bb = float(latest[upper_bb_cols[0]]) if upper_bb_cols else entry * 1.05
                
                sl = entry - (1.5 * atr)
                risk = entry - sl
                target = entry + (3 * risk)
                
                # EXHAUSTION FILTER
                # If price is above or too close to Upper Bollinger Band (within 0.5%), or RSI > 75, reject it!
                if entry >= (upper_bb * 0.995) or rsi > 75:
                    continue # Rejects exhausted stocks
                
                # Position Sizing
                raw_qty = self.risk_per_trade / risk if risk > 0 else 0
                max_qty = self.max_allocation / entry
                qty = math.floor(min(raw_qty, max_qty))
                
                # Sector RRG Logic
                sector_status = self.sector_rrg.get(sector, {'Quadrant': 'Improving', 'Momentum': 105})
                quad = sector_status['Quadrant']
                sec_mom = sector_status['Momentum']
                
                if quad in ["Lagging", "Weakening"]:
                    continue # Strict reject
                    
                remark = f"🚀 Top Pick ({quad} Sector)"
                
                # Calculate Score based on Sector Momentum and Stock RSI (Higher is better, but capped RSI is good)
                score = sec_mom + (rsi * 0.5)
                
                if qty > 0:
                    results.append({
                        'Score': score,
                        'Stock': stock,
                        'Entry (₹)': round(entry, 2),
                        'Stop Loss (₹)': round(sl, 2),
                        'Target (₹)': round(target, 2),
                        'Quantity': qty,
                        'Max Risk (₹)': round(qty * risk, 2),
                        'Remark': remark
                    })
                    
        df_results = pd.DataFrame(results)
        
        # STRICT FINAL SELECTION: TOP 2 ONLY
        if not df_results.empty:
            df_results = df_results.sort_values(by='Score', ascending=False).head(2)
            df_results = df_results.drop(columns=['Score']) # Hide internal score
            
        return df_results
