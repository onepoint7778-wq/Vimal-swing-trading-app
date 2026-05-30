
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
            
        if self.fyers_app_id and self.fyers_token:
            df = self.fetch_fyers_historical(symbol, from_date, to_date)
            if df is not None and not df.empty:
                return df
            self.logs['analyst'] += f" [Fyers feed failed for {symbol}]"
            
        return pd.DataFrame()

    def fetch_chartink_stocks(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://chartink.com/",
                "Origin": "https://chartink.com",
                "Accept": "application/json, text/javascript, */*; q=0.01"
            }
            with requests.Session() as s:
                r = s.get(self.chartink_url, verify=False, headers=headers, timeout=10)
                if r.status_code != 200:
                    self.logs['scraper'] = f"Chartink server returned error code {r.status_code}."
                    return []
                    
                soup = BeautifulSoup(r.text, 'html.parser')
                csrf = soup.select_one('meta[name="csrf-token"]')
                if not csrf: 
                    self.logs['scraper'] = "Chartink blocked the request (Could not find CSRF token). Cloudflare challenge active."
                    return []
                
                scan_clause_match = re.search(r"scan_clause\s*=\s*'(.*?)'", r.text)
                if not scan_clause_match: 
                    self.logs['scraper'] = "Chartink URL page did not contain the scanning logic query."
                    return []
                
                res = s.post("https://chartink.com/screener/process", data={'scan_clause': scan_clause_match.group(1)}, 
                             headers={
                                 'x-csrf-token': csrf['content'], 
                                 'X-Requested-With': 'XMLHttpRequest', 
                                 'User-Agent': headers['User-Agent'],
                                 'Referer': self.chartink_url
                             }, 
                             verify=False, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if 'data' in data:
                        stocks = [item['nsecode'] for item in data['data']]
                        self.logs['scraper'] = f"Successfully scanned Chartink. Found {len(stocks)} raw candidates."
                        return stocks
                self.logs['scraper'] = f"Chartink POST request returned status {res.status_code}."
                return []
        except Exception as e:
            self.logs['scraper'] = f"Chartink connection failed: {e}"
            return []

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
            return df, sector
        except Exception as e:
            self.logs['analyst'] += f" [Error processing stock data for {symbol}: {e}]"
            return None, None

    def is_price_action_uptrend(self, df):
        if len(df) < 30:
            return False
        # Divide last 30 days of data into three 10-day blocks
        b1 = df.iloc[-30:-20]
        b2 = df.iloc[-20:-10]
        b3 = df.iloc[-10:]
        
        h2 = b2['High'].max()
        l2 = b2['Low'].min()
        h3 = b3['High'].max()
        l3 = b3['Low'].min()
        
        # Rising peaks and troughs (H3 > H2 and L3 > L2)
        return h3 > h2 and l3 > l2

    def run_pipeline(self, lookback_days=5, rr_ratio=2.0, manual_stocks=None):
        self.logs['analyst'] = ""
        self.logs['risk'] = []
        
        # Run sector calculations
        self.analyze_sectors_rrg()
        
        strong_sectors = []
        all_sectors_data = {}
        
        try:
            if self.benchmark_data is None or len(self.benchmark_data) < lookback_days + 1:
                raise Exception("Insufficient Nifty 50 benchmark data.")
            nifty_ret = (self.benchmark_data.iloc[-1] / self.benchmark_data.iloc[-1 - lookback_days]) - 1
            self.logs['analyst'] += f"Nifty 50 Return ({lookback_days}d): {nifty_ret*100:.2f}%\n"
        except Exception as e:
            nifty_ret = 0.0
            self.logs['analyst'] += f"Failed to fetch Nifty 50 benchmark return: {e}\n"
            
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
                
        if manual_stocks and manual_stocks.strip():
            stocks = [s.strip().upper() for s in re.split(r'[,\s]+', manual_stocks) if s.strip()]
            self.logs['scraper'] = f"Using {len(stocks)} manual stock symbols."
        else:
            stocks = self.fetch_chartink_stocks()
        pipeline_data = []
        
        for symbol in stocks:
            sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
            
            try:
                stock_df = self.get_data_feed(symbol, period='6mo')
                if stock_df.empty or len(stock_df) < lookback_days + 1:
                    pipeline_data.append({
                        "Stock": symbol,
                        "Sector": sector,
                        "Current Price (₹)": "-",
                        "Return vs Nifty": "-",
                        "Return vs Sector": "-",
                        "Status": "Filtered Out",
                        "Reason": "No data available"
                    })
                    continue
                
                stock_close = stock_df['Close']
                current_price = float(stock_close.iloc[-1])
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = all_sectors_data.get(sector, 0.0)
                
                ret_vs_nifty = stock_ret - nifty_ret
                ret_vs_sector = stock_ret - sector_ret
                
                # Check conditions sequentially
                reasons = []
                
                # 1. Sector Strength Check
                if sector not in strong_sectors:
                    reasons.append(f"Sector '{sector}' is weaker than Nifty 50")
                
                # 2. RS checks
                if stock_ret <= nifty_ret:
                    reasons.append(f"Stock return ({stock_ret*100:.1f}%) is below Nifty ({nifty_ret*100:.1f}%)")
                if stock_ret <= sector_ret:
                    reasons.append(f"Stock return ({stock_ret*100:.1f}%) is below Sector ({sector_ret*100:.1f}%)")
                
                # 3. Uptrend Check (Price Action)
                is_uptrend = self.is_price_action_uptrend(stock_df)
                if not is_uptrend:
                    reasons.append("Not in Price Action Uptrend (Higher Highs & Higher Lows)")
                
                # 4. Volume Check
                stock_df['Vol_SMA_20'] = stock_df['Volume'].rolling(20).mean()
                latest = stock_df.iloc[-1]
                if latest['Volume'] <= latest['Vol_SMA_20']:
                    reasons.append(f"Volume ({latest['Volume']/1e6:.1f}M) below 20-day average")
                    
                # 5. Anti-chasing logic (weekly move <= 10%)
                weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                if weekly_ret > 0.10:
                    reasons.append(f"Weekly return ({weekly_ret*100:.1f}%) exceeds 10%")
                
                if len(reasons) == 0:
                    status = "Passed"
                    reason = "Setup Confirmed"
                else:
                    status = "Filtered Out"
                    reason = ", ".join(reasons)
                    
                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Current Price (₹)": f"₹{current_price:,.2f}",
                    "Return vs Nifty": f"{ret_vs_nifty*100:+.2f}%",
                    "Return vs Sector": f"{ret_vs_sector*100:+.2f}%",
                    "Status": status,
                    "Reason": reason
                })
            except Exception as e:
                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Current Price (₹)": "-",
                    "Return vs Nifty": "-",
                    "Return vs Sector": "-",
                    "Status": "Filtered Out",
                    "Reason": str(e)
                })
                
        df_pipeline = pd.DataFrame(pipeline_data)
        
        # Filter final picks
        df_final = df_pipeline[df_pipeline["Status"] == "Passed"].copy()
        if not df_final.empty:
            df_final = df_final[["Stock", "Sector", "Current Price (₹)", "Return vs Nifty", "Return vs Sector"]]
            
        return self.sector_rrg, df_final, self.risk_per_trade, self.logs, df_pipeline

    def run_backtest(self, start_date="2026-01-01", end_date="2026-04-30", lookback_days=5, rr_ratio=2.0):
        from datetime import datetime, timedelta
        
        capital = 50000
        trades = []
        
        # 1. Define backtest stock pool and sectors
        stocks_pool = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC", "ICICIBANK", "SBIN", "L&T", "BHARTIARTL", "KOTAKBANK"]
        
        # Calculate fetch start date with 90 days buffer
        sd_dt = datetime.strptime(start_date, "%Y-%m-%d")
        fetch_start = (sd_dt - timedelta(days=90)).strftime("%Y-%m-%d")
        
        # 2. Pre-fetch NIFTY baseline
        nifty_df = self.get_data_feed(self.benchmark_ticker, start_date=fetch_start, end_date=end_date)
        if nifty_df.empty:
            return pd.DataFrame(), {"Total Trades": 0, "Wins": 0, "Losses": 0, "Win Rate": "0%", "Starting Capital": "₹50,000.00", "Final Capital": "₹50,000.00", "Net Profit": "₹0.00", "Average Return": "0.00%", "Average Holding Days": "0.0 Days", "Best Trade": "0.00%", "Worst Trade": "0.00%"}
            
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
                df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
                stock_dfs[symbol] = df
                
        # Get all business days in the backtest range from Nifty close index
        backtest_days = nifty_df.loc[start_date:end_date].index
        active_trades = [] # List of dicts representing held positions
        pending_signals = [] # List of signals waiting for "Strong Candle" entry: {'Stock', 'Signal Date'}
        
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
            
            # B. Check pending signals for "Strong Candle" entry (Close > Open)
            still_pending = []
            for signal in pending_signals:
                symbol = signal['Stock']
                df = stock_dfs[symbol]
                if current_date in df.index and len(active_trades) < 2:
                    daily_data = df.loc[current_date]
                    if daily_data['Close'] > daily_data['Open']: # Strong candle check
                        entry_price = float(daily_data['Close'])
                        # Structure based swing low from 10-day low prior to this entry day
                        stock_slice = df.loc[:current_date]
                        sl = float(stock_slice['Low'].iloc[:-1].iloc[-10:].min())
                        if sl >= entry_price:
                            sl = entry_price * 0.99
                        risk = entry_price - sl
                        target = entry_price + (rr_ratio * risk)
                        
                        qty = math.floor((capital / 2) / entry_price)
                        if qty > 0:
                            active_trades.append({
                                'Stock': symbol,
                                'Entry Date': current_date.strftime("%Y-%m-%d"),
                                'Entry': entry_price,
                                'Stop Loss': sl,
                                'Target': target,
                                'Quantity': qty,
                                'holding_days': 0
                            })
                            continue
                # Keep pending if we haven't entered and it's less than 3 days old
                sig_date = datetime.strptime(signal['Signal Date'], "%Y-%m-%d")
                if (current_date - sig_date).days <= 3:
                    still_pending.append(signal)
            pending_signals = still_pending
            
            # C. Filter and scan for new setups if we have capital space
            if len(active_trades) + len(pending_signals) >= 2:
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
                if any(pos['Stock'] == symbol for pos in active_trades) or any(sig['Stock'] == symbol for sig in pending_signals):
                    continue
                    
                sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
                if sector not in strong_sectors:
                    continue
                    
                stock_slice = df.loc[:current_date]
                if len(stock_slice) < 30:
                    continue
                    
                stock_close = stock_slice['Close']
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = sector_rets.get(sector, -999)
                
                if stock_ret > nifty_ret and stock_ret > sector_ret:
                    # Agent 3: Setup Scanner (Price Action Uptrend + Anti-chasing + Volume)
                    is_uptrend = self.is_price_action_uptrend(stock_slice)
                    if not is_uptrend:
                        continue
                        
                    weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                    if weekly_ret > 0.10:
                        continue
                        
                    latest = stock_slice.iloc[-1]
                    if latest['Volume'] <= latest['Vol_SMA_20']:
                        continue
                        
                    candidates.append({
                        'Stock': symbol,
                        'Score': stock_ret
                    })
                    
            # Sort candidates and store as pending signals
            candidates = sorted(candidates, key=lambda x: x['Score'], reverse=True)
            for candidate in candidates:
                if len(active_trades) + len(pending_signals) >= 2:
                    break
                pending_signals.append({
                    'Stock': candidate['Stock'],
                    'Signal Date': current_date.strftime("%Y-%m-%d")
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
