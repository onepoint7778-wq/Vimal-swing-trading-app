import pandas as pd
import cloudscraper
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

        # Expanded Nifty 500 sector mapping
        self.stock_sector_map = {
            # Bank
            "HDFCBANK": "Bank", "ICICIBANK": "Bank", "KOTAKBANK": "Bank", "AXISBANK": "Bank",
            "SBIN": "PSU Bank", "BANKBARODA": "PSU Bank", "PNB": "PSU Bank", "CANBK": "PSU Bank",
            "UNIONBANK": "PSU Bank", "INDIANB": "PSU Bank", "BANKINDIA": "PSU Bank",
            "INDUSINDBK": "Pvt Bank", "FEDERALBNK": "Pvt Bank", "RBLBANK": "Pvt Bank",
            "BANDHANBNK": "Pvt Bank", "IDFCFIRSTB": "Pvt Bank", "J&KBANK": "Pvt Bank",
            "KARURVYSYA": "Pvt Bank", "DCBBANK": "Pvt Bank", "CSBBANK": "Pvt Bank",
            # IT
            "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT", "TECHM": "IT",
            "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT", "COFORGE": "IT",
            "OFSS": "IT", "KPITTECH": "IT", "TATAELXSI": "IT", "HEXAWARE": "IT",
            "NIITTECH": "IT", "MASTEK": "IT", "BSOFT": "IT", "RATEGAIN": "IT",
            # Auto
            "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto",
            "HEROMOTOCO": "Auto", "EICHERMOT": "Auto", "TVSMOTORS": "Auto", "ASHOKLEY": "Auto",
            "MOTHERSON": "Auto", "BOSCHLTD": "Auto", "EXIDEIND": "Auto", "AMARAJABAT": "Auto",
            "BALKRISIND": "Auto", "MRF": "Auto", "APOLLOTYRE": "Auto", "CEATLTD": "Auto",
            "TVSMOTOR": "Auto", "ESCORTS": "Auto", "FORCE": "Auto",
            # Pharma
            "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",
            "AUROPHARMA": "Pharma", "TORNTPHARM": "Pharma", "ALKEM": "Pharma", "LUPIN": "Pharma",
            "BIOCON": "Pharma", "ABBOTINDIA": "Pharma", "PFIZER": "Pharma", "GLAXO": "Pharma",
            "IPCALAB": "Pharma", "LAURUSLABS": "Pharma", "GRANULES": "Pharma", "GLAND": "Pharma",
            "NATCOPHARM": "Pharma", "AJANTPHARM": "Pharma", "JBCHEPHARM": "Pharma",
            # FMCG
            "ITC": "FMCG", "HINDUNILVR": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
            "DABUR": "FMCG", "MARICO": "FMCG", "GODREJCP": "FMCG", "COLPAL": "FMCG",
            "EMAMILTD": "FMCG", "TATACONSUM": "FMCG", "VBL": "FMCG", "RADICO": "FMCG",
            "MCDOWELL-N": "FMCG", "UBL": "FMCG", "PGHH": "FMCG",
            # Energy
            "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy",
            "ADANIGREEN": "Energy", "ADANIPOWER": "Energy", "TATAPOWER": "Energy",
            "BPCL": "Energy", "IOC": "Energy", "GAIL": "Energy", "PETRONET": "Energy",
            "HINDPETRO": "Energy", "CESC": "Energy", "TORNTPOWER": "Energy",
            "JSPL": "Energy", "NHPC": "Energy", "SJVN": "Energy", "IREDA": "Energy",
            # Metal
            "TATASTEEL": "Metal", "JSWSTEEL": "Metal", "HINDALCO": "Metal", "VEDL": "Metal",
            "SAIL": "Metal", "NMDC": "Metal", "APLAPOLLO": "Metal", "JINDALSTEL": "Metal",
            "WELCORP": "Metal", "RATNAMANI": "Metal", "GALLANTT": "Metal",
            "NATIONALUM": "Metal", "HINDCOPPER": "Metal", "MOIL": "Metal",
            # Fin Service
            "BAJFINANCE": "Fin Service", "BAJAJFINSV": "Fin Service", "HDFCAMC": "Fin Service",
            "MUTHOOTFIN": "Fin Service", "CHOLAFIN": "Fin Service", "MANAPPURAM": "Fin Service",
            "M&MFIN": "Fin Service", "SHRIRAMFIN": "Fin Service", "LICHOUSFIN": "Fin Service",
            "ICICIGI": "Fin Service", "ICICIPRULI": "Fin Service", "SBILIFE": "Fin Service",
            "HDFCLIFE": "Fin Service", "STARHEALTH": "Fin Service", "NIACL": "Fin Service",
            "PEL": "Fin Service", "POONAWALLA": "Fin Service",
            # Infra
            "L&T": "Infra", "BHARTIARTL": "Infra", "ADANIPORTS": "Infra", "ADANIENT": "Infra",
            "GMRINFRA": "Infra", "IRB": "Infra", "KNRCON": "Infra", "PNCINFRA": "Infra",
            "NBCC": "Infra", "RVNL": "Infra", "IRCON": "Infra", "HGINFRA": "Infra",
            "AHLUCONT": "Infra", "CAPACITE": "Infra", "NCC": "Infra",
            # Realty
            "DLF": "Realty", "GODREJPROP": "Realty", "OBEROIRLTY": "Realty", "PRESTIGE": "Realty",
            "PHOENIXLTD": "Realty", "BRIGADE": "Realty", "SOBHA": "Realty", "MAHLIFE": "Realty",
            "LODHA": "Realty", "SUNTECK": "Realty", "KOLTEPATIL": "Realty",
            # Consumption
            "TITAN": "Consumption", "ASIANPAINT": "Consumption", "BERGER": "Consumption",
            "KANSAINER": "Consumption", "PAGEIND": "Consumption", "TRENT": "Consumption",
            "DMART": "Consumption", "NYKAA": "Consumption", "MANYAVAR": "Consumption",
            "ABFRL": "Consumption", "ADITYA": "Consumption", "SHOPPERST": "Consumption",
            # Media
            "ZEEL": "Media", "SUNTV": "Media", "PVRINOX": "Media", "SAREGAMA": "Media",
            "NAZARA": "Media", "HATHWAY": "Media", "TIPSINDLTD": "Media",
            # Misc / Diversified
            "ULTRACEMCO": "Infra", "SHREECEM": "Infra", "ACC": "Infra", "AMBUJACEM": "Infra",
            "GRASIM": "Consumption", "PIDILITIND": "Consumption", "SUPREMEIND": "Consumption",
            "ASTRAL": "Consumption", "POLYCAB": "Infra", "HAVELLS": "Consumption",
            "CROMPTON": "Consumption", "VOLTAS": "Consumption", "BLUESTAR": "Consumption",
            "WHIRLPOOL": "Consumption", "DIXON": "IT", "AMBER": "Consumption",
            "MINDACORP": "Auto", "MOTHERSUMI": "Auto", "SUNDRMFAST": "Auto",
            "ZOMATO": "Consumption", "NAUKRI": "IT", "INDIAMART": "IT", "JUSTDIAL": "IT",
            "PAYTM": "Fin Service", "POLICYBZR": "Fin Service",
            "AETHER": "Pharma", "SUDARSCHEM": "Pharma", "AARTIIND": "Pharma",
            "DEEPAKNTR": "Pharma", "NAVINFLUOR": "Pharma", "ALKYLAMINE": "Pharma",
            "FLUOROCHEM": "Pharma", "CLEAN": "Pharma",
            "ATHERENERG": "Auto", "OLECTRA": "Auto", "GREENPANEL": "Consumption",
        }

        self.logs = {
            'scraper': "",
            'analyst': "",
            'risk': []
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
        # FIXED: Authorization header - only token, no app_id
        headers = {
            "Authorization": f"{self.fyers_app_id}:{self.fyers_token}",
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
                self.logs['analyst'] += f" [Fyers HTTP {response.status_code} for {fyers_symbol}]"
        except Exception as e:
            self.logs['analyst'] += f" [Fyers exception for {fyers_symbol}: {e}]"
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
            s = cloudscraper.create_scraper()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://chartink.com/",
                "Origin": "https://chartink.com"
            }
            r = s.get(self.chartink_url, verify=False, headers=headers, timeout=10)
            if r.status_code != 200:
                self.logs['scraper'] = f"Chartink returned error {r.status_code}. Use Manual Stocks input."
                return []
            soup = BeautifulSoup(r.text, 'html.parser')
            csrf = soup.select_one('meta[name="csrf-token"]')
            if not csrf:
                self.logs['scraper'] = "Chartink blocked (Cloudflare). Please use Manual Stocks input in sidebar."
                return []
            scan_clause_match = re.search(r"scan_clause\s*=\s*'(.*?)'", r.text)
            if not scan_clause_match:
                self.logs['scraper'] = "Chartink URL did not contain scan logic."
                return []
            res = s.post("https://chartink.com/screener/process",
                         data={'scan_clause': scan_clause_match.group(1)},
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
                    self.logs['scraper'] = f"Chartink scan success. Found {len(stocks)} candidates."
                    return stocks
            self.logs['scraper'] = f"Chartink POST returned {res.status_code}."
            return []
        except Exception as e:
            self.logs['scraper'] = f"Chartink failed: {e}. Please use Manual Stocks input."
            return []

    def _calc_rrg(self, asset_series, bench_series):
        df = pd.concat([asset_series, bench_series], axis=1).dropna()
        df.columns = ['Asset', 'Bench']
        rs = df['Asset'] / df['Bench']
        rs_mean = rs.rolling(window=14).mean()
        rs_std = rs.rolling(window=14).std()
        rs_ratio = 100 + ((rs - rs_mean) / (rs_std + 1e-8)) * 5
        rs_ratio_mean = rs_ratio.rolling(window=14).mean()
        rs_ratio_std = rs_ratio.rolling(window=14).std()
        rs_mom = 100 + ((rs_ratio - rs_ratio_mean) / (rs_ratio_std + 1e-8)) * 5
        if len(rs_ratio) < 20:
            return None, None
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
            self.logs['analyst'] = f"Failed to fetch Nifty 50: {e}"
            return

        leading_count = 0
        for name, ticker in self.sector_map.items():
            try:
                asset_df = self.get_data_feed(ticker, period='6mo')
                if not asset_df.empty:
                    self.sector_dfs[name] = asset_df
                    asset = asset_df['Close']
                    ratios, moms = self._calc_rrg(asset, self.benchmark_data)
                    if ratios is not None and len(ratios) == 2:
                        quad = self._get_quadrant(ratios[-1], moms[-1])
                        self.sector_rrg[name] = {
                            'Ratios': ratios,
                            'Momentums': moms,
                            'Quadrant': quad,
                            'RS_Ratio': round(ratios[-1], 2),
                            'RS_Momentum': round(moms[-1], 2)
                        }
                        if quad == "Leading":
                            leading_count += 1
            except Exception:
                pass
        self.logs['analyst'] = f"Sector RRG done. {leading_count} sectors in Leading quadrant."
        return self.sector_rrg

    def calc_momentum_score(self, stock_df, nifty_ret, sector_ret):
        """Score 0-10 based on RS strength"""
        try:
            close = stock_df['Close']
            ret_1w = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            ret_1m = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
            ret_3m = (close.iloc[-1] / close.iloc[-60] - 1) * 100 if len(close) >= 60 else 0
            vs_nifty = ret_1m - (nifty_ret * 100)
            vs_sector = ret_1m - (sector_ret * 100)
            score = 5.0
            if vs_nifty > 5: score += 2
            elif vs_nifty > 0: score += 1
            else: score -= 1
            if vs_sector > 3: score += 2
            elif vs_sector > 0: score += 1
            else: score -= 1
            if ret_3m > 15: score += 1
            score = max(0, min(10, score))
            return round(score, 1)
        except:
            return 5.0

    def is_price_action_uptrend(self, df):
        if len(df) < 30:
            return False
        b1 = df.iloc[-30:-20]
        b2 = df.iloc[-20:-10]
        b3 = df.iloc[-10:]
        h2 = b2['High'].max()
        l2 = b2['Low'].min()
        h3 = b3['High'].max()
        l3 = b3['Low'].min()
        return h3 > h2 and l3 > l2

    def run_pipeline(self, lookback_days=5, rr_ratio=2.0, manual_stocks=None):
        self.logs['analyst'] = ""
        self.logs['risk'] = []
        self.analyze_sectors_rrg()

        strong_sectors = []
        all_sectors_data = {}

        try:
            if self.benchmark_data is None or len(self.benchmark_data) < lookback_days + 1:
                raise Exception("Insufficient Nifty 50 data.")
            nifty_ret = (self.benchmark_data.iloc[-1] / self.benchmark_data.iloc[-1 - lookback_days]) - 1
            self.logs['analyst'] += f"Nifty Return ({lookback_days}d): {nifty_ret*100:.2f}%\n"
        except Exception as e:
            nifty_ret = 0.0
            self.logs['analyst'] += f"Nifty fetch failed: {e}\n"

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
            self.logs['scraper'] = f"Manual mode: {len(stocks)} stocks."
        else:
            stocks = self.fetch_chartink_stocks()

        pipeline_data = []
        for symbol in stocks:
            sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
            try:
                stock_df = self.get_data_feed(symbol, period='6mo')
                if stock_df.empty or len(stock_df) < lookback_days + 1:
                    pipeline_data.append({
                        "Stock": symbol, "Sector": sector,
                        "Current Price (₹)": "-", "Momentum Score": "-",
                        "Return vs Nifty": "-", "Return vs Sector": "-",
                        "Status": "Filtered Out", "Reason": "No data"
                    })
                    continue

                stock_close = stock_df['Close']
                current_price = float(stock_close.iloc[-1])
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = all_sectors_data.get(sector, 0.0)
                ret_vs_nifty = stock_ret - nifty_ret
                ret_vs_sector = stock_ret - sector_ret
                momentum_score = self.calc_momentum_score(stock_df, nifty_ret, sector_ret)

                reasons = []
                if sector not in strong_sectors:
                    reasons.append(f"Sector '{sector}' weaker than Nifty")
                if stock_ret <= nifty_ret:
                    reasons.append(f"Stock ({stock_ret*100:.1f}%) < Nifty ({nifty_ret*100:.1f}%)")
                if stock_ret <= sector_ret:
                    reasons.append(f"Stock ({stock_ret*100:.1f}%) < Sector ({sector_ret*100:.1f}%)")
                if not self.is_price_action_uptrend(stock_df):
                    reasons.append("Not in PA Uptrend (HH+HL missing)")

                stock_df['Vol_SMA_20'] = stock_df['Volume'].rolling(20).mean()
                latest = stock_df.iloc[-1]
                if latest['Volume'] <= latest['Vol_SMA_20']:
                    reasons.append(f"Volume below 20-day avg")

                weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                if weekly_ret > 0.10:
                    reasons.append(f"Weekly move {weekly_ret*100:.1f}% > 10% (chasing risk)")

                status = "✅ Passed" if len(reasons) == 0 else "❌ Filtered"
                reason = "Setup Confirmed ✅" if len(reasons) == 0 else " | ".join(reasons)

                pipeline_data.append({
                    "Stock": symbol,
                    "Sector": sector,
                    "Current Price (₹)": f"₹{current_price:,.2f}",
                    "Momentum Score": f"{momentum_score}/10",
                    "Return vs Nifty": f"{ret_vs_nifty*100:+.2f}%",
                    "Return vs Sector": f"{ret_vs_sector*100:+.2f}%",
                    "Status": status,
                    "Reason": reason
                })
            except Exception as e:
                pipeline_data.append({
                    "Stock": symbol, "Sector": sector,
                    "Current Price (₹)": "-", "Momentum Score": "-",
                    "Return vs Nifty": "-", "Return vs Sector": "-",
                    "Status": "❌ Filtered", "Reason": str(e)
                })

        df_pipeline = pd.DataFrame(pipeline_data)
        df_final = df_pipeline[df_pipeline["Status"] == "✅ Passed"].copy()
        if not df_final.empty:
            df_final = df_final[["Stock", "Sector", "Current Price (₹)", "Momentum Score", "Return vs Nifty", "Return vs Sector"]]
            df_final = df_final.sort_values("Momentum Score", ascending=False)

        return self.sector_rrg, df_final, self.risk_per_trade, self.logs, df_pipeline

    def run_backtest(self, start_date="2026-01-01", end_date="2026-04-30", lookback_days=5, rr_ratio=2.0):
        from datetime import datetime, timedelta
        capital = 50000
        trades = []
        stocks_pool = ["TCS", "RELIANCE", "INFY", "HDFCBANK", "ITC", "ICICIBANK", "SBIN", "L&T", "BHARTIARTL", "KOTAKBANK"]
        sd_dt = datetime.strptime(start_date, "%Y-%m-%d")
        fetch_start = (sd_dt - timedelta(days=90)).strftime("%Y-%m-%d")

        nifty_df = self.get_data_feed(self.benchmark_ticker, start_date=fetch_start, end_date=end_date)
        if nifty_df.empty:
            return pd.DataFrame(), {
                "Total Trades": 0, "Wins": 0, "Losses": 0, "Win Rate": "0%",
                "Starting Capital": "₹50,000", "Final Capital": "₹50,000",
                "Net Profit": "₹0", "Average Return": "0%",
                "Average Holding Days": "0", "Best Trade": "0%", "Worst Trade": "0%"
            }

        sector_dfs = {}
        for sec_name, sec_ticker in self.sector_map.items():
            df = self.get_data_feed(sec_ticker, start_date=fetch_start, end_date=end_date)
            if not df.empty:
                sector_dfs[sec_name] = df

        stock_dfs = {}
        for symbol in stocks_pool:
            df = self.get_data_feed(symbol, start_date=fetch_start, end_date=end_date)
            if not df.empty:
                df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
                stock_dfs[symbol] = df

        backtest_days = nifty_df.loc[start_date:end_date].index
        active_trades = []
        pending_signals = []

        for current_date in backtest_days:
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
                    is_exit, exit_price, status = True, position['Target'], "Won"
                elif low <= position['Stop Loss']:
                    is_exit, exit_price, status = True, position['Stop Loss'], "Lost"
                elif position['holding_days'] >= 20:
                    is_exit, exit_price = True, close
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

            still_pending = []
            for signal in pending_signals:
                symbol = signal['Stock']
                df = stock_dfs[symbol]
                if current_date in df.index and len(active_trades) < 2:
                    daily_data = df.loc[current_date]
                    if daily_data['Close'] > daily_data['Open']:
                        entry_price = float(daily_data['Close'])
                        stock_slice = df.loc[:current_date]
                        sl = float(stock_slice['Low'].iloc[:-1].iloc[-10:].min())
                        if sl >= entry_price:
                            sl = entry_price * 0.99
                        risk = entry_price - sl
                        target = entry_price + (rr_ratio * risk)
                        qty = math.floor((capital / 2) / entry_price)
                        if qty > 0:
                            active_trades.append({
                                'Stock': symbol, 'Entry Date': current_date.strftime("%Y-%m-%d"),
                                'Entry': entry_price, 'Stop Loss': sl, 'Target': target,
                                'Quantity': qty, 'holding_days': 0
                            })
                        continue
                sig_date = datetime.strptime(signal['Signal Date'], "%Y-%m-%d")
                if (current_date - sig_date).days <= 3:
                    still_pending.append(signal)
            pending_signals = still_pending

            if len(active_trades) + len(pending_signals) >= 2:
                continue

            nifty_slice = nifty_df.loc[:current_date]
            if len(nifty_slice) < lookback_days + 1:
                continue
            nifty_ret = (nifty_slice['Close'].iloc[-1] / nifty_slice['Close'].iloc[-1 - lookback_days]) - 1
            strong_sectors = []
            sector_rets = {}
            for sec_name, sec_df in sector_dfs.items():
                sec_slice = sec_df.loc[:current_date]
                if len(sec_slice) < lookback_days + 1: continue
                sec_ret = (sec_slice['Close'].iloc[-1] / sec_slice['Close'].iloc[-1 - lookback_days]) - 1
                sector_rets[sec_name] = sec_ret
                if sec_ret > nifty_ret:
                    strong_sectors.append(sec_name)

            candidates = []
            for symbol, df in stock_dfs.items():
                if any(p['Stock'] == symbol for p in active_trades) or any(s['Stock'] == symbol for s in pending_signals):
                    continue
                sector = self.stock_sector_map.get(symbol.upper(), "Unknown")
                if sector not in strong_sectors: continue
                stock_slice = df.loc[:current_date]
                if len(stock_slice) < 30: continue
                stock_close = stock_slice['Close']
                stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-1 - lookback_days]) - 1
                sector_ret = sector_rets.get(sector, -999)
                if stock_ret > nifty_ret and stock_ret > sector_ret:
                    if not self.is_price_action_uptrend(stock_slice): continue
                    weekly_ret = (stock_close.iloc[-1] / stock_close.iloc[-5]) - 1
                    if weekly_ret > 0.10: continue
                    latest = stock_slice.iloc[-1]
                    if latest['Volume'] <= latest['Vol_SMA_20']: continue
                    candidates.append({'Stock': symbol, 'Score': stock_ret})

            candidates = sorted(candidates, key=lambda x: x['Score'], reverse=True)
            for candidate in candidates:
                if len(active_trades) + len(pending_signals) >= 2: break
                pending_signals.append({'Stock': candidate['Stock'], 'Signal Date': current_date.strftime("%Y-%m-%d")})

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
                    "Stock": symbol, "Quantity": position['Quantity'],
                    "Entry": round(position['Entry'], 2),
                    "Stop Loss": round(position['Stop Loss'], 2),
                    "Target": round(position['Target'], 2),
                    "Status": status, "P&L": round(pnl, 2),
                    "Capital After": round(capital, 2),
                    "Holding Days": position['holding_days'],
                    "Return %": round(((close / position['Entry']) - 1) * 100, 2)
                })

        df_trades = pd.DataFrame(trades)
        if df_trades.empty:
            df_trades = pd.DataFrame(columns=["Entry Date","Exit Date","Stock","Quantity","Entry","Stop Loss","Target","Status","P&L","Capital After","Holding Days","Return %"])
        else:
            df_trades = df_trades.sort_values(by="Entry Date").reset_index(drop=True)

        wins = len(df_trades[df_trades["Status"] == "Won"])
        losses = len(df_trades[df_trades["Status"] == "Lost"])
        total = len(df_trades)

        metrics = {
            "Total Trades": total,
            "Wins": wins,
            "Losses": losses,
            "Win Rate": f"{(wins/total)*100:.1f}%" if total > 0 else "0%",
            "Starting Capital": "₹50,000.00",
            "Final Capital": f"₹{capital:,.2f}",
            "Net Profit": f"₹{capital-50000:,.2f}",
            "Average Return": f"{df_trades['Return %'].mean():.2f}%" if total > 0 else "0%",
            "Average Holding Days": f"{df_trades['Holding Days'].mean():.1f} Days" if total > 0 else "0",
            "Best Trade": f"{df_trades['Return %'].max():.2f}%" if total > 0 else "0%",
            "Worst Trade": f"{df_trades['Return %'].min():.2f}%" if total > 0 else "0%"
        }
        return df_trades, metrics
