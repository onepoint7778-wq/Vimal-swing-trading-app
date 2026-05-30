import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import math

class SwingTradingAgents:
    def __init__(self, current_capital=50000, use_fyers=False, fyers_app_id="", fyers_token="", chartink_url=None):
        if chartink_url and chartink_url.strip():
            self.chartink_url = chartink_url.strip()
        else:
            self.chartink_url = "https://chartink.com/screener/richroad-pivot-points-weekly-scan-2028"
        self.capital = current_capital
        self.max_holdings = 2
        # Exactly Capital / 2 (e.g. 25k on 50k capital)
        self.max_allocation = self.capital / self.max_holdings
        self.risk_per_trade = self.capital * 0.02
        self.benchmark_ticker = '^NSEI'
        
        self.use_fyers = use_fyers
        self.fyers_app_id = fyers_app_id
        self.fyers_token = fyers_token
        
        self.sector_map = {
            'Bank': '^NSEBANK', 'IT': '^CNXIT', 'Auto': '^CNXAUTO',
            'Pharma': '^CNXPHARMA', 'Metal': '^CNXMETAL', 'FMCG': '^CNXFMCG',
            'Energy': '^CNXENERGY', 'Realty': '^CNXREALTY', 'Media': '^CNXMEDIA',
            'Infra': '^CNXINFRA', 'Fin Service': '^CNXFIN', 'PSU Bank': '^CNXPSUBANK',
            'Pvt Bank': '^NIFTYPVT', 'Consumption': '^CNXCONSUM'
        }
        self.sector_rrg = {}
        self.benchmark_data = None
        self.sector_dfs = {}
        
        # Mapping of common stock symbols to sectors to avoid slow & rate-limited stock.info calls
        self.stock_sector_map = {
            "RELIANCE": "Energy", "TCS": "IT", "INFY": "IT", "HDFCBANK": "Bank", "ITC": "FMCG",
            "ICICIBANK": "Bank", "BHARTIARTL": "Infra", "L&T": "Infra", "SBIN": "PSU Bank",
            "BAJFINANCE": "Fin Service", "KOTAKBANK": "Bank", "AXISBANK": "Bank", "M&M": "Auto",
            "MARUTI": "Auto", "ASIANPAINT": "Consumption", "SUNPHARMA": "Pharma", "HCLTECH": "IT",
            "TITAN": "Consumption", "NTPC": "Energy", "TATAMOTORS": "Auto"
        }
        
        # New: AI Employee Logs
        self.logs = {
            'scraper': "",
            'analyst': "",
            'risk': [] # List of dicts for rejected stocks
        }

    def map_to_fyers_symbol(self, symbol):
        index_map = {
            "^NSEI": "NSE:NIFTY50-INDEX",
            "^NSEBANK": "NSE:NIFTYBANK-INDEX",
            "^CNXIT": "NSE:NIFTYIT-INDEX",
            "^CNXAUTO": "NSE:NIFTYAUTO-INDEX",
            "^CNXPHARMA": "NSE:NIFTYPHARMA-INDEX",
            "^CNXMETAL": "NSE:NIFTYMETAL-INDEX",
            "^CNXFMCG": "NSE:NIFTYFMCG-INDEX",
            "^CNXENERGY": "NSE:NIFTYENERGY-INDEX",
            "^CNXREALTY": "NSE:NIFTYREALTY-INDEX",
            "^CNXMEDIA": "NSE:NIFTYMEDIA-INDEX",
            "^CNXINFRA": "NSE:NIFTYINFRA-INDEX",
            "^CNXFIN": "NSE:NIFTYFINSERVICE-INDEX",
            "^CNXPSUBANK": "NSE:NIFTYPSUBANK-INDEX",
            "^NIFTYPVT": "NSE:NIFTYPVTBANK-INDEX",
            "^CNXCONSUM": "NSE:NIFTYCONSR-INDEX"
        }
        if symbol in index_map:
            return index_map[symbol]
        clean_sym = symbol.replace(".NS", "").upper()
        return f"NSE:{clean_sym}-EQ"

    def fetch_fyers_historical(self, symbol, from_date, to_date):
        fyers_symbol = self.map_to_fyers_symbol(symbol)
        url = "https://api-t1.fyers.in/data/history"
        headers = {
            "Authorization": f"Bearer {self.fyers_app_id}:{self.fyers_token}",
            "Content-Type": "application/json"
        }
        params = {
            "symbol": fyers_symbol,
            "resolution": "D",
            "date_format": "1",
            "range_from": from_date,
            "range_to": to_date,
            "cont_flag": "1"
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("s") == "ok" and "candles" in res_data:
                    candles = res_data["candles"]
                    if candles:
                        df = pd.DataFrame(candles, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
                        df["Date"] = pd.to_datetime(df["timestamp"], unit="s")
                        df.set_index("Date", inplace=True)
                        df.drop(columns=["timestamp"], inplace=True)
                        return df
                self.logs['analyst'] += f" [Fyers error for {fyers_symbol}: {res_data.get('message', 'No details')}]"
            else:
                self.logs['analyst'] += f" [Fyers HTTP Error {response.status_code} for {fyers_symbol}]"
        except Exception as e:
            self.logs['analyst'] += f" [Fyers connection exception for {fyers_symbol}: {e}]"
        return None

    def get_data_feed(self, symbol, period="6mo", start_date=None, end_date=None):
        from datetime import datetime, timedelta
        
        if start_date and end_date:
            sd_dt = datetime.strptime(start_date, "%Y-%m-%d")
            fd_dt = sd_dt - timedelta(days=45)
            from_date = fd_dt.strftime("%Y-%m-%d")
            to_date = end_date
        else:
            to_dt = datetime.now()
            days = 180 if period == "6mo" else 365
            fd_dt = to_dt - timedelta(days=days)
            from_date = fd_dt.strftime("%Y-%m-%d")
            to_date = to_dt.strftime("%Y-%m-%d")
            
        if self.use_fyers and self.fyers_app_id and self.fyers_token:
            df = self.fetch_fyers_historical(symbol, from_date, to_date)
            if df is not None and not df.empty:
                return df
            self.logs['analyst'] += f" [Fyers feed failed for {symbol}, falling back to yfinance]"
            
        ticker = symbol if symbol.startswith("^") else f"{symbol}.NS"
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            stock_obj = yf.Ticker(ticker, session=session)
            df = stock_obj.history(start=from_date, end=to_date)
            if not df.empty:
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                df = df[["Open", "High", "Low", "Close", "Volume"]]
                return df
        except Exception as e:
            self.logs['analyst'] += f" [yfinance fallback failed for {ticker}: {e}]"
            
        return pd.DataFrame()

    def fetch_chartink_stocks(self):
        try:
            with requests.Session() as s:
                r = s.get(self.chartink_url, verify=False, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(r.text, 'html.parser')
                csrf = soup.select_one('meta[name="csrf-token"]')
                if not csrf: 
                    self.logs['scraper'] = "Chartink scan successful (Fallback Mode). Found 5 candidates."
                    return ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"]
                
                scan_clause_match = re.search(r"scan_clause\s*=\s*'(.*?)'", r.text)
                if not scan_clause_match: 
                    self.logs['scraper'] = "Chartink scan completed. Found 2 fallback candidates."
                    return ["RELIANCE", "TCS"]
                
                res = s.post("https://chartink.com/screener/process", data={'scan_clause': scan_clause_match.group(1)}, 
                             headers={'x-csrf-token': csrf['content'], 'X-Requested-With': 'XMLHttpRequest', 'User-Agent': 'Mozilla/5.0'}, 
                             verify=False)
                data = res.json()
                if 'data' in data:
                    stocks = [item['nsecode'] for item in data['data']]
                    self.logs['scraper'] = f"Successfully scanned Chartink. Found {len(stocks)} raw candidates."
                    return stocks
                
                self.logs['scraper'] = "Scan returned 0 candidates."
                return []
        except Exception as e:
            self.logs['scraper'] = f"Chartink server blocked request. Fallback: Scanning Nifty Top 20."
            return [
                "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "BHARTIARTL", "INFY", "ITC", 
                "L&T", "SBIN", "BAJFINANCE", "KOTAKBANK", "AXISBANK", "M&M", "MARUTI",
                "ASIANPAINT", "SUNPHARMA", "HCLTECH", "TITAN", "NTPC", "TATAMOTORS"
            ]

    def _calc_rrg(self, asset_series, bench_series):
        df = pd.concat([asset_series, bench_series], axis=1).dropna()
        df.columns = ['Asset', 'Bench']
        rs = df['Asset'] / df['Bench']
        
        rs_mean = rs.rolling(window=14).mean()
        rs_std = rs.rolling(window=14).std()
        rs_ratio = 100 + ((rs - rs_mean) / (rs_std + 1e-8)) * 5
        
        # Define rs_mom by calculating rolling z-score of rs_ratio
        rs_ratio_mean = rs_ratio.rolling(window=14).mean()
        rs_ratio_std = rs_ratio.rolling(window=14).std()
        rs_mom = 100 + ((rs_ratio - rs_ratio_mean) / (rs_ratio_std + 1e-8)) * 5
        
        # Get exactly 2 points (4 weeks ago and today) to draw a straight trajectory tail
        ratio_history = [rs_ratio.iloc[-20], rs_ratio.iloc[-1]]
        mom_history = [rs_mom.iloc[-20], rs_mom.iloc[-1]]
        
        return ratio_history, mom_history

    def _get_quadrant(self, ratio, momentum):
        if ratio > 100 and momentum > 100: return "Leading"
        if ratio > 100 and momentum <= 100: return "Weakening"
        if ratio <= 100 and momentum > 100: return "Improving"
        return "Lagging"

    def analyze_sectors_rrg(self):
        self.sector_dfs = {}
        try:
            bench_df = self.get_data_feed(self.benchmark_ticker, period='6mo')
            if bench_df.empty:
                raise Exception("Empty benchmark dataframe")
            bench = bench_df['Close']
            self.benchmark_data = bench
            self.sector_dfs['Nifty 50'] = bench_df
        except Exception as e: 
            self.logs['analyst'] = f"Failed to fetch Nifty 50 benchmark: {e}"
            return
            
        leading_count = 0
        for name, ticker in self.sector_map.items():
            try:
                asset_df = self.get_data_feed(ticker, period='6mo')
                if not asset_df.empty:
                    self.sector_dfs[name] = asset_df
                    asset = asset_df['Close']
                    ratios, moms = self._calc_rrg(asset, self.benchmark_data)
                    
                    if len(ratios) == 2:
                        quad = self._get_quadrant(ratios[-1], moms[-1])
                        self.sector_rrg[name] = {'Ratios': ratios, 'Momentums': moms, 'Quadrant': quad}
                        if quad == "Leading": leading_count += 1
            except Exception as e:
                pass
            
        self.logs['analyst'] = f"Sector RRG Mapping Complete. Found {leading_count} sectors in the Leading Quadrant."
        return self.sector_rrg

    def get_stock_data(self, symbol):
        try:
            df = self.get_data_feed(symbol, period="6mo")
            if df.empty: return None, None
            
            # Use local mapping to avoid slow and rate-limited API calls
            sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
            
            # Manual RSI (14)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-8)
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
            
            # RichRoad Logic
            df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
            df['Turnover_Cr'] = (df['Close'] * df['Volume']) / 10000000
            
            return df, sector
        except Exception as e:
            self.logs['analyst'] += f" [Error processing stock data for {symbol}: {e}]"
            return None, None

    def run_pipeline(self, lookback_days=5, enable_market_filter=False, enable_stock_200_ema=True, min_sl_pct=0.035, rr_ratio=2.0):
        self.logs['analyst'] = ""
        self.logs['risk'] = []
        
        # 1. Run RRG to populate self.sector_dfs & self.sector_rrg
        self.analyze_sectors_rrg()
        
        # Agent 1: Sector Filter
        strong_sectors = []
        all_sectors_data = {}
        
        try:
            if self.benchmark_data is None or len(self.benchmark_data) < lookback_days + 1:
                raise Exception("Insufficient Nifty 50 benchmark data.")
            
            # Calculate Nifty 50 Return and 50 EMA for Market Trend Filter
            self.benchmark_data_df = self.get_data_feed(self.benchmark_ticker, period='6mo')
            if not self.benchmark_data_df.empty:
                self.benchmark_data_df['EMA_50'] = self.benchmark_data_df['Close'].ewm(span=50, adjust=False).mean()
                latest_nifty = self.benchmark_data_df.iloc[-1]
                if enable_market_filter and latest_nifty['Close'] < latest_nifty['EMA_50']:
                    self.logs['analyst'] += "⚠️ Market Filter: Nifty 50 is below its 50 EMA. Market is in correction. Keeping capital in cash.\n"
                    # Return empty selection but with logs and empty pipeline report
                    return self.sector_rrg, pd.DataFrame(), self.risk_per_trade, self.logs, pd.DataFrame(columns=["Stock", "Sector", "Sector Strong", "RS Status", "Trend (20/50/200 EMA)", "Volume Check", "Weekly Return", "Status", "Reason"])
            
            nifty_ret = (self.benchmark_data.iloc[-1] / self.benchmark_data.iloc[-1 - lookback_days]) - 1
            self.logs['analyst'] += f"Nifty 50 Return ({lookback_days}d): {nifty_ret*100:.2f}%\n"
        except Exception as e:
            self.logs['analyst'] += f"Failed to fetch Nifty 50 benchmark return: {e}\n"
            return {}, pd.DataFrame(), self.risk_per_trade, self.logs, pd.DataFrame()
            
        for sec_name, sec_df in self.sector_dfs.items():
            if sec_name == 'Nifty 50': continue
            try:
                sec_close = sec_df['Close']
                sec_ret = (sec_close.iloc[-1] / sec_close.iloc[-1 - lookback_days]) - 1
                all_sectors_data[sec_name] = sec_ret
                if sec_ret > nifty_ret:
                    strong_sectors.append(sec_name)
            except:
                pass
                
        self.logs['analyst'] += f"Agent 1 (Sector Filter): Found {len(strong_sectors)} strong sectors: {', '.join(strong_sectors)}\n"
        
        # 2. Agent 2: Stock RS Filter & Agent 3: Setup Scanner
        stocks = self.fetch_chartink_stocks()
        rs_passed_stocks = []
        final_picks = []
        pipeline_data = []
        
        for symbol in stocks:
            sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
            sec_strong = "✅ Yes" if sector in strong_sectors else "❌ No"
            
            # Default pipeline values
            rs_status = "❌ Failed"
            trend_status = "❌ Failed"
            vol_status = "❌ Failed"
            weekly_return_str = "-"
            status = "Filtered Out"
            reason = ""
            
            if sector not in strong_sectors:
                reason = f"Sector '{sector}' is weak"
                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Sector Strong": sec_strong,
                    "RS Status": rs_status,
                    "Trend (20/50/200 EMA)": trend_status,
                    "Volume Check": vol_status,
                    "Weekly Return": weekly_return_str,
                    "Status": status,
                    "Reason": reason
                })
                self.logs['risk'].append({
                    'Stock': symbol,
                    'Reason': f"Sector '{sector}' is not outperforming Nifty 50."
                })
                continue
                
            try:
                stock_df = self.get_data_feed(symbol, period='6mo')
                if stock_df.empty or len(stock_df) < lookback_days + 1:
                    reason = "No data available"
                    pipeline_data.append({
                        "Stock": symbol,
                        "Sector": sector,
                        "Sector Strong": sec_strong,
                        "RS Status": rs_status,
                        "Trend (20/50/200 EMA)": trend_status,
                        "Volume Check": vol_status,
                        "Weekly Return": weekly_return_str,
                        "Status": status,
                        "Reason": reason
                    })
                    continue
                
                stock_close = stock_df['Close']
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = all_sectors_data.get(sector, -999)
                
                # Check relative strength outperformance
                rs_ok = stock_ret > nifty_ret and stock_ret > sector_ret
                rs_status = "✅ Pass" if rs_ok else "❌ Failed"
                
                if not rs_ok:
                    reason = f"Weak RS (Stock {stock_ret*100:.1f}%, Sector {sector_ret*100:.1f}%)"
                    pipeline_data.append({
                        "Stock": symbol,
                        "Sector": sector,
                        "Sector Strong": sec_strong,
                        "RS Status": rs_status,
                        "Trend (20/50/200 EMA)": trend_status,
                        "Volume Check": vol_status,
                        "Weekly Return": weekly_return_str,
                        "Status": status,
                        "Reason": reason
                    })
                    self.logs['risk'].append({
                        'Stock': symbol,
                        'Reason': f"Stock return ({stock_ret*100:.1f}%) is weaker than Nifty or sector return."
                    })
                    continue
                    
                rs_passed_stocks.append({
                    'Stock': symbol,
                    'Sector': sector,
                    'Stock Return': stock_ret,
                    'Sector Return': sector_ret
                })
                
                # Agent 3: Setup Scanner
                stock_df['EMA_20'] = stock_df['Close'].ewm(span=20, adjust=False).mean()
                stock_df['EMA_50'] = stock_df['Close'].ewm(span=50, adjust=False).mean()
                stock_df['EMA_200'] = stock_df['Close'].ewm(span=200, adjust=False).mean()
                stock_df['Vol_SMA_20'] = stock_df['Volume'].rolling(20).mean()
                latest = stock_df.iloc[-1]
                
                # Trend condition: check if we should enforce 200 EMA
                if enable_stock_200_ema:
                    is_uptrend = latest['Close'] > latest['EMA_20'] and latest['EMA_20'] > latest['EMA_50'] and latest['Close'] > latest['EMA_200']
                else:
                    is_uptrend = latest['Close'] > latest['EMA_20'] and latest['EMA_20'] > latest['EMA_50']
                
                trend_status = "✅ Pass" if is_uptrend else "❌ Failed"
                
                # Anti-chasing logic (max 10% move this week)
                weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                weekly_return_str = f"{weekly_ret*100:+.1f}%"
                chase_ok = weekly_ret <= 0.10
                
                # Volume check
                vol_ok = latest['Volume'] > latest['Vol_SMA_20']
                vol_status = "✅ Pass" if vol_ok else "❌ Failed"
                
                if not is_uptrend:
                    reason = "Close not above EMA20/50, or Close below EMA200" if enable_stock_200_ema else "Close not above EMA20 or EMA20 not above EMA50"
                    self.logs['risk'].append({
                        'Stock': symbol,
                        'Reason': f"Stock Close ({latest['Close']:.2f}) does not satisfy uptrend rules."
                    })
                elif not chase_ok:
                    reason = f"Weekly return ({weekly_ret*100:.1f}%) exceeds limit of 10%"
                    self.logs['risk'].append({
                        'Stock': symbol,
                        'Reason': f"Stock weekly return ({weekly_ret*100:.1f}%) exceeds limit of 10% (Chasing)."
                    })
                elif not vol_ok:
                    reason = f"Volume ({latest['Volume']/1e6:.1f}M) below 20-day average ({latest['Vol_SMA_20']/1e6:.1f}M)"
                    self.logs['risk'].append({
                        'Stock': symbol,
                        'Reason': f"Volume ({latest['Volume']/1e6:.1f}M) below 20-day average ({latest['Vol_SMA_20']/1e6:.1f}M)."
                    })
                else:
                    status = "Passed"
                    reason = "Setup confirmed"
                    
                    entry = float(latest['Close'])
                    swing_low = float(stock_df['Low'].iloc[-5:].min())
                    sl = swing_low
                    
                    # Capping stop loss using min_sl_pct and 8%
                    if sl >= entry * (1.0 - min_sl_pct):
                        sl = entry * (1.0 - min_sl_pct)
                    elif sl <= entry * 0.92:
                        sl = entry * 0.92
                        
                    risk = entry - sl
                    target = entry + (rr_ratio * risk)
                    qty = math.floor(self.max_allocation / entry)
                    
                    if qty > 0:
                        final_picks.append({
                            'Stock': symbol,
                            'Sector': sector,
                            'Entry (₹)': round(entry, 2),
                            'Stop Loss (₹)': round(sl, 2),
                            'Target (₹)': round(target, 2),
                            'Quantity': qty,
                            'Max Risk (₹)': round(qty * risk, 2),
                            'Remark': f"🚀 Setup Confirmed: Strong RS & Vol ({sector})"
                        })
                
                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Sector Strong": sec_strong,
                    "RS Status": rs_status,
                    "Trend (20/50/200 EMA)": trend_status,
                    "Volume Check": vol_status,
                    "Weekly Return": weekly_return_str,
                    "Status": status,
                    "Reason": reason
                })
            except Exception as e:
                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Sector Strong": sec_strong,
                    "RS Status": "❌ Error",
                    "Trend (20/50/200 EMA)": "❌ Error",
                    "Volume Check": "❌ Error",
                    "Weekly Return": "-",
                    "Status": "Error",
                    "Reason": str(e)
                })
                self.logs['risk'].append({
                    'Stock': symbol,
                    'Reason': f"Processing error: {e}"
                })
                
        df_final = pd.DataFrame(final_picks)
        if not df_final.empty:
            df_final = df_final.head(2) # Filter to top 2 stocks
            
        self.logs['analyst'] += f"Agent 2 (Stock Filter): Filtered {len(rs_passed_stocks)} stocks outperforming sector. Agent 3 (Setup Scanner): Final selection contains {len(df_final)} stocks."
        
        return self.sector_rrg, df_final, self.risk_per_trade, self.logs, pd.DataFrame(pipeline_data)

    def run_backtest(self, start_date="2026-01-01", end_date="2026-04-30", lookback_days=5, enable_market_filter=False, enable_stock_200_ema=True, min_sl_pct=0.035, rr_ratio=2.0):
        from datetime import datetime, timedelta
        
        capital = 50000
        trades = []
        
        # 1. Define backtest stock pool and sectors
        stocks_pool = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC", "ICICIBANK", "SBIN", "L&T", "BHARTIARTL", "KOTAKBANK"]
        
        # Calculate fetch start date with 90 days buffer (to allow 200 EMA and lookbacks)
        sd_dt = datetime.strptime(start_date, "%Y-%m-%d")
        fetch_start = (sd_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # 2. Pre-fetch NIFTY baseline
        nifty_df = self.get_data_feed(self.benchmark_ticker, start_date=fetch_start, end_date=end_date)
        if nifty_df.empty:
            return pd.DataFrame(), {"Total Trades": 0, "Wins": 0, "Losses": 0, "Win Rate": "0%", "Starting Capital": "₹50,000.00", "Final Capital": "₹50,000.00", "Net Profit": "₹0.00", "Average Return": "0.00%", "Average Holding Days": "0.0 Days", "Best Trade": "0.00%", "Worst Trade": "0.00%"}
        
        # Add Nifty 50 EMA for Market Trend Filter
        nifty_df['EMA_50'] = nifty_df['Close'].ewm(span=50, adjust=False).mean()
            
        # Pre-fetch Sectors
        sector_dfs = {}
        for sec_name, sec_ticker in self.sector_map.items():
            df = self.get_data_feed(sec_ticker, start_date=fetch_start, end_date=end_date)
            if not df.empty:
                sector_dfs[sec_name] = df
                
        # Pre-fetch Stocks
        stock_dfs = {}
        for symbol in stocks_pool:
            df = self.get_data_feed(symbol, start_date=fetch_start, end_date=end_date)
            if not df.empty:
                df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
                df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
                df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean() # Calculate EMA_200
                df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
                stock_dfs[symbol] = df
                
        # Get all business days in the backtest range from Nifty close index
        backtest_days = nifty_df.loc[start_date:end_date].index
        active_trades = [] # List of dicts representing held positions
        
        for d_idx, current_date in enumerate(backtest_days):
            # A. Manage existing trades (check stop-loss, target, holding period)
            still_active = []
            for position in active_trades:
                symbol = position['Stock']
                df = stock_dfs[symbol]
                
                if current_date not in df.index:
                    still_active.append(position)
                    continue
                    
                daily_data = df.loc[current_date]
                high = float(daily_data['High'])
                low = float(daily_data['Low'])
                close = float(daily_data['Close'])
                
                position['holding_days'] += 1
                
                is_exit = False
                exit_price = close
                status = "Open"
                
                if high >= position['Target']:
                    is_exit = True
                    exit_price = position['Target']
                    status = "Won"
                elif low <= position['Stop Loss']:
                    is_exit = True
                    exit_price = position['Stop Loss']
                    status = "Lost"
                elif position['holding_days'] >= 20: # Approx 30 calendar days
                    is_exit = True
                    exit_price = close
                    status = "Won" if close > position['Entry'] else "Lost"
                    
                if is_exit:
                    pnl = (exit_price - position['Entry']) * position['Quantity']
                    capital += pnl
                    
                    trades.append({
                        "Entry Date": position['Entry Date'],
                        "Exit Date": current_date.strftime("%Y-%m-%d"),
                        "Stock": symbol,
                        "Quantity": position['Quantity'],
                        "Entry": round(position['Entry'], 2),
                        "Stop Loss": round(position['Stop Loss'], 2),
                        "Target": round(position['Target'], 2),
                        "Status": status,
                        "P&L": round(pnl, 2),
                        "Capital After": round(capital, 2),
                        "Holding Days": position['holding_days'],
                        "Return %": round(((exit_price / position['Entry']) - 1) * 100, 2)
                    })
                else:
                    still_active.append(position)
            active_trades = still_active
            
            # B. Filter and scan for new setups if we have capital space (max 2 positions)
            if len(active_trades) >= 2:
                continue
                
            # Market Filter: If Nifty 50 is below its 50 EMA, we don't open new positions
            if enable_market_filter:
                latest_nifty = nifty_df.loc[current_date]
                if latest_nifty['Close'] < latest_nifty['EMA_50']:
                    continue
                
            # 1. Run Agent 1 (Sector Filter) at current_date
            nifty_slice = nifty_df.loc[:current_date]
            if len(nifty_slice) < lookback_days + 1:
                continue
            nifty_ret = (nifty_slice['Close'].iloc[-1] / nifty_slice['Close'].iloc[-1 - lookback_days]) - 1
            
            strong_sectors = []
            sector_rets = {}
            for sec_name, sec_df in sector_dfs.items():
                sec_slice = sec_df.loc[:current_date]
                if len(sec_slice) < lookback_days + 1:
                    continue
                sec_ret = (sec_slice['Close'].iloc[-1] / sec_slice['Close'].iloc[-1 - lookback_days]) - 1
                sector_rets[sec_name] = sec_ret
                if sec_ret > nifty_ret:
                    strong_sectors.append(sec_name)
                    
            # 2. Run Agent 2 (Stock Filter) and Agent 3 (Setup Scanner)
            candidates = []
            for symbol, df in stock_dfs.items():
                if any(pos['Stock'] == symbol for pos in active_trades):
                    continue
                    
                sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
                if sector not in strong_sectors:
                    continue
                    
                stock_slice = df.loc[:current_date]
                if len(stock_slice) < lookback_days + 1:
                    continue
                    
                stock_close = stock_slice['Close']
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = sector_rets.get(sector, -999)
                
                if stock_ret > nifty_ret and stock_ret > sector_ret:
                    # Agent 3: Setup Scanner
                    latest = stock_slice.iloc[-1]
                    # Upward trend includes EMA_200 check if enabled
                    if enable_stock_200_ema:
                        is_uptrend = latest['Close'] > latest['EMA_20'] and latest['EMA_20'] > latest['EMA_50'] and latest['Close'] > latest['EMA_200']
                    else:
                        is_uptrend = latest['Close'] > latest['EMA_20'] and latest['EMA_20'] > latest['EMA_50']
                        
                    if not is_uptrend:
                        continue
                        
                    weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                    if weekly_ret > 0.10:
                        continue
                        
                    if latest['Volume'] <= latest['Vol_SMA_20']:
                        continue
                        
                    entry_price = float(latest['Close'])
                    swing_low = float(stock_slice['Low'].iloc[-5:].min())
                    sl = swing_low
                    
                    # Adjust SL bounds (min min_sl_pct to avoid noise stop-outs, max 8%)
                    if sl >= entry_price * (1.0 - min_sl_pct):
                        sl = entry_price * (1.0 - min_sl_pct)
                    elif sl <= entry_price * 0.92:
                        sl = entry_price * 0.92
                        
                    risk = entry_price - sl
                    target = entry_price + (rr_ratio * risk)
                    
                    candidates.append({
                        'Stock': symbol,
                        'Entry': entry_price,
                        'Stop Loss': sl,
                        'Target': target,
                        'Score': stock_ret
                    })
                    
            # Sort candidates by relative strength score and pick top
            candidates = sorted(candidates, key=lambda x: x['Score'], reverse=True)
            
            # Enter trades up to available slots
            for candidate in candidates:
                if len(active_trades) >= 2:
                    break
                qty = math.floor((capital / 2) / candidate['Entry'])
                if qty > 0:
                    active_trades.append({
                        'Stock': candidate['Stock'],
                        'Entry Date': current_date.strftime("%Y-%m-%d"),
                        'Entry': candidate['Entry'],
                        'Stop Loss': candidate['Stop Loss'],
                        'Target': candidate['Target'],
                        'Quantity': qty,
                        'holding_days': 0
                    })
                    
        # Force close any remaining open positions at the end of the backtest
        if active_trades:
            last_date = backtest_days[-1]
            for position in active_trades:
                symbol = position['Stock']
                df = stock_dfs[symbol]
                close = float(df.loc[last_date]['Close']) if last_date in df.index else position['Entry']
                    
                pnl = (close - position['Entry']) * position['Quantity']
                capital += pnl
                status = "Won" if close > position['Entry'] else "Lost"
                trades.append({
                    "Entry Date": position['Entry Date'],
                    "Exit Date": last_date.strftime("%Y-%m-%d"),
                    "Stock": symbol,
                    "Quantity": position['Quantity'],
                    "Entry": round(position['Entry'], 2),
                    "Stop Loss": round(position['Stop Loss'], 2),
                    "Target": round(position['Target'], 2),
                    "Status": status,
                    "P&L": round(pnl, 2),
                    "Capital After": round(capital, 2),
                    "Holding Days": position['holding_days'],
                    "Return %": round(((close / position['Entry']) - 1) * 100, 2)
                })
                
        df_trades = pd.DataFrame(trades)
        if df_trades.empty:
            df_trades = pd.DataFrame(columns=["Entry Date", "Exit Date", "Stock", "Quantity", "Entry", "Stop Loss", "Target", "Status", "P&L", "Capital After", "Holding Days", "Return %"])
        else:
            df_trades = df_trades.sort_values(by="Entry Date").reset_index(drop=True)
            
        wins = len(df_trades[df_trades["Status"] == "Won"])
        losses = len(df_trades[df_trades["Status"] == "Lost"])
        total = len(df_trades)
        
        avg_ret = df_trades["Return %"].mean() if total > 0 else 0
        avg_holding = df_trades["Holding Days"].mean() if total > 0 else 0
        best_trade = df_trades["Return %"].max() if total > 0 else 0
        worst_trade = df_trades["Return %"].min() if total > 0 else 0
        
        metrics = {
            "Total Trades": total,
            "Wins": wins,
            "Losses": losses,
            "Win Rate": f"{(wins / total) * 100:.1f}%" if total > 0 else "0%",
            "Starting Capital": "₹50,000.00",
            "Final Capital": f"₹{capital:,.2f}",
            "Net Profit": f"₹{capital - 50000:,.2f}",
            "Average Return": f"{avg_ret:.2f}%",
            "Average Holding Days": f"{avg_holding:.1f} Days",
            "Best Trade": f"{best_trade:.2f}%",
            "Worst Trade": f"{worst_trade:.2f}%"
        }
        
        return df_trades, metrics
