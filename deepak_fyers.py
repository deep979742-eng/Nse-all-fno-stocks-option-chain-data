import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fyers_apiv3 import fyersModel
import gspread
from google.oauth2.service_account import Credentials
import concurrent.futures

# ==========================================
# 1. FYERS CREDENTIALS & MEMORY SETUP
# ==========================================
CLIENT_ID = "YD02909"
APP_ID = "I0QMW3KFAW-100"
SECRET_ID = "T63F5XCUSH"
REDIRECT_URI = "https://www.google.com/" 

st.set_page_config(page_title="F&O Dashboard", layout="wide")

# ==========================================
# SUPER CSS INJECTOR: ANTI-BLUR SHIELD
# ==========================================
st.markdown("""
    <style>
        div[data-testid="stAppViewContainer"] { opacity: 1 !important; filter: none !important; }
        [data-testid="stDataFrame"] { opacity: 1 !important; transition: none !important; }
        [data-testid="stTabs"] { opacity: 1 !important; transition: none !important; }
        [data-testid="stStatusWidget"] { visibility: hidden !important; display: none !important; }
        .block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
        [data-testid="stDataFrameTable"] > thead > tr { background-color: darkblue !important; }
        [data-testid="stDataFrameTable"] > thead > tr > th { background-color: darkblue !important; color: white !important; font-weight: bold !important; text-align: center !important; }
        th { background-color: darkblue !important; color: white !important; }
        .stApp { opacity: 1 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# STRICT IST TIMEZONE SETUP
# ==========================================
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now_ist = datetime.datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")

# ==========================================
# GOOGLE SHEETS CONNECTION
# ==========================================
HISTORY_FILE = "chart_history.csv"
SNAPSHOT_FILE = "snapshot_950.json"
TOKEN_STORE_FILE = "fyers_token_store.json"
AUTO_SAVE_FILE = "auto_save_tracker.txt"

@st.cache_resource
def get_gsheet():
    try:
        if "gcp_service_account" in st.secrets:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            client = gspread.authorize(creds)
            return client.open("Fyers_EOD_Data").sheet1
    except Exception as e:
        st.sidebar.error(f"Google Sheets Link Error: {e}")
    return None

sheet = get_gsheet()

if 'strike_memory' not in st.session_state:
    st.session_state.strike_memory = {}
    if sheet is not None:
        try:
            col_values = sheet.col_values(1)
            if col_values:
                eod_data_str = "".join(col_values)
                st.session_state.strike_memory = json.loads(eod_data_str)
        except Exception:
            pass

if 'snapshot_950' not in st.session_state:
    st.session_state.snapshot_950 = {}
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE, 'r') as f:
                saved_snap = json.load(f)
                if saved_snap.get("date") == today_str:
                    st.session_state.snapshot_950 = saved_snap.get("data", {})
        except Exception:
            pass

if 'current_date' not in st.session_state:
    st.session_state.current_date = today_str

if st.session_state.current_date != today_str:
    st.session_state.chart_history = {}
    st.session_state.current_date = today_str

if 'chart_history' not in st.session_state or not st.session_state.chart_history:
    st.session_state.chart_history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            hist_df = pd.read_csv(HISTORY_FILE)
            if 'Date' in hist_df.columns:
                hist_df = hist_df[hist_df['Date'] == today_str]
                if 'Time' in hist_df.columns:
                    hist_df['TimeObj'] = pd.to_datetime(hist_df['Time'], format='%H:%M').dt.time
                    hist_df = hist_df[(hist_df['TimeObj'] >= datetime.time(9, 15)) & (hist_df['TimeObj'] <= datetime.time(15, 30))]
                    hist_df = hist_df.drop(columns=['TimeObj'])
                
                if not hist_df.empty:
                    for sym in hist_df['Symbol'].unique():
                        sym_df = hist_df[hist_df['Symbol'] == sym].drop(columns=['Symbol', 'Date'])
                        st.session_state.chart_history[sym] = sym_df.to_dict('records')
                else:
                    os.remove(HISTORY_FILE)
            else:
                os.remove(HISTORY_FILE)
        except Exception:
            try: os.remove(HISTORY_FILE)
            except: pass

if 'last_api_call' not in st.session_state:
    st.session_state.last_api_call = datetime.datetime.min.replace(tzinfo=IST)
if 'cached_data' not in st.session_state:
    st.session_state.cached_data = []

# ==========================================
# 2. CALCULATION FORMULAS
# ==========================================
def calc_vol_pcr(ce_vol, pe_vol): return 0.0 if ce_vol == 0 else round(pe_vol / ce_vol, 2)
def calc_opt_pcr(ce_oi, pe_oi): return 0.0 if ce_oi == 0 else round(pe_oi / ce_oi, 2)
def calc_vol_cpr(ce_vol, pe_vol): return 0.0 if pe_vol == 0 else round(ce_vol / pe_vol, 2)

def calc_conviction(oc_data, opt_type):
    strikes = [s for s in oc_data if s.get('option_type') == opt_type.upper() or str(s.get('symbol', '')).endswith(opt_type.upper())]
    total_plus, total_minus = 0, 0
    for s in strikes:
        sym = str(s.get('symbol', ''))
        ltp = float(s.get('ltp', 0))
        if ltp == 0: continue
        if sym not in st.session_state.strike_memory:
            st.session_state.strike_memory[sym] = ltp
            continue 
        baseline_ltp = st.session_state.strike_memory[sym]
        price_diff = ltp - baseline_ltp
        if price_diff > 0: total_plus += 1 
        elif price_diff < 0: total_minus += 1 
    active_total = total_plus + total_minus
    if active_total == 0: return 0.0
    if total_plus >= total_minus: return round((total_plus / active_total) * 100, 1) 
    else: return -round((total_minus / active_total) * 100, 1) 

def calc_checker_data(symbol, current_pcr, current_vol, current_time):
    target_time = datetime.time(9, 50)
    if current_time < target_time: return 0.0, 0.0, 0.0, 0.0
    if symbol not in st.session_state.snapshot_950:
        st.session_state.snapshot_950[symbol] = {'pcr': current_pcr, 'vol_cpr': current_vol}
        try:
            with open(SNAPSHOT_FILE, 'w') as f: json.dump({"date": today_str, "data": st.session_state.snapshot_950}, f)
        except: pass
        return 0.0, 0.0, 0.0, 0.0
    base = st.session_state.snapshot_950[symbol]
    pcr_abs, vol_abs = current_pcr - base['pcr'], current_vol - base['vol_cpr']
    pcr_pct = ((current_pcr - base['pcr']) / base['pcr']) * 100 if base['pcr'] != 0 else 0.0
    vol_pct = ((current_vol - base['vol_cpr']) / base['vol_cpr']) * 100 if base['vol_cpr'] != 0 else 0.0
    return round(pcr_abs, 2), round(vol_abs, 2), round(pcr_pct, 1), round(vol_pct, 1)

def get_fyers_symbol(s):
    if s == "NIFTY": return "NSE:NIFTY50-INDEX"
    elif s == "BANKNIFTY": return "NSE:NIFTYBANK-INDEX"
    elif s == "FINNIFTY": return "NSE:FINNIFTY-INDEX"
    elif s == "MIDCPNIFTY": return "NSE:MIDCPNIFTY-INDEX"
    else: return f"NSE:{s}-EQ"
def get_raw_symbol(fyers_sym):
    s = fyers_sym.split(':')[1].replace('-EQ', '').replace('-INDEX', '')
    if s == "NIFTY50": return "NIFTY"
    if s == "NIFTYBANK": return "BANKNIFTY"
    return s

# 🚀 SMART SPEED & ANTI-BLOCK SYSTEM
def fetch_option_chain_fast(q):
    sym = q['n']
    time.sleep(0.3) # Fyers ko spam na lage isliye halka sa break
    try:
        oc = fyers.optionchain(data={"symbol": sym, "strikecount": 150, "timestamp": ""})
        # Agar Fyers ne API Block kardi ("NA" wala issue), to 1.5s wait karke dobara try karega
        if not (oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']):
            time.sleep(1.5) 
            oc = fyers.optionchain(data={"symbol": sym, "strikecount": 150, "timestamp": ""})
        return q, oc
    except:
        return q, None

# ==========================================
# 3. STOCK LIST & AUTO LOGIN
# ==========================================
st.sidebar.header("🔑 Fyers Quick Login")

saved_token = None
if os.path.exists(TOKEN_STORE_FILE):
    try:
        with open(TOKEN_STORE_FILE, 'r') as f:
            token_data = json.load(f)
            if token_data.get("date") == today_str:
                saved_token = token_data.get("token")
    except: pass

if saved_token:
    auth_code = "AUTO_LOGGED_IN"
    st.sidebar.success("🚀 Connected via Saved Token!")
else:
    magic_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&response_type=code&state=deepak"
    st.sidebar.markdown(f"### [👉 Step 1: Click to Get Code]({magic_url})")
    auth_code = st.sidebar.text_input("Step 2: Paste Code Here:", type="password")

st.sidebar.markdown("---")
st.sidebar.header("💾 End Of Day (EOD) Save")
st.sidebar.info("3:30 PM par data ab AUTOMATIC save hoga! Manual button bhi yahan hai.")

def save_eod_data():
    if st.session_state.strike_memory and sheet is not None:
        try:
            json_str = json.dumps(st.session_state.strike_memory)
            chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
            sheet.clear()
            cell_list = sheet.range(f'A1:A{len(chunks)}')
            for i, cell in enumerate(cell_list):
                cell.value = chunks[i]
            sheet.update_cells(cell_list)
            return True
        except Exception as e:
            st.sidebar.error(f"Google Sheet Save Error: {e}")
    return False

if st.sidebar.button("Manual Save 3:30 PM Data"):
    if save_eod_data():
        st.sidebar.success("✅ EOD Data Saved PERMANENTLY!")

raw_symbols = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", 
    "ADANIPORTS", "ADANIPOWER", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT", 
    "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG", "BAJFINANCE", "BANDHANBNK", "BANKBARODA", 
    "BANKINDIA", "BDL", "BEL", "BHARATFORG", "BHARTIARTL", "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", 
    "BRITANNIA", "BSE", "CAMS", "CANBK", "CDSL", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA", "COCHINSHIP", 
    "COFORGE", "COLPAL", "CONCOR", "CROMPTON", "CUMMINSIND", "DABUR", "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON", 
    "DLF", "DMART", "DRREDDY", "EICHERMOT", "ETERNAL", "EXIDEIND", "FEDERALBNK", "FORCEMOT", "FORTIS", "GAIL", 
    "GLENMARK", "GMRAIRPORT", "GODFRYPHLP", "GODREJCP", "GODREJPROP", "GRASIM", "GVT&D", "HAL", "HAVELLS", "HCLTECH", 
    "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDPETRO", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", 
    "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX", "INDHOTEL", "INDIANB", "INDIGO", "INDUSINDBK", "INDUSTOWER", 
    "INFY", "INOXWIND", "IOC", "IREDA", "IRFC", "ITC", "JINDALSTEL", "JIOFIN", "JSWENERGY", "JSWSTEEL", 
    "JUBLFOOD", "KALYANKJIL", "KAYNES", "KEI", "KFINTECH", "KOTAKBANK", "KPITTECH", "LAURUSLABS", "LICHSGFIN", "LICI", 
    "LODHA", "LT", "LTF", "LTM", "LUPIN", "M&M", "MANAPPURAM", "MANKIND", "MARICO", "MARUTI", 
    "MAXHEALTH", "MAZDOCK", "MCX", "MFSL", "MOTHERSON", "MOTILALOFS", "MPHASIS", "MUTHOOTFIN", "NAM-INDIA", "NATIONALUM", 
    "NAUKRI", "NBCC", "NESTLEIND", "NHPC", "NMDC", "NTPC", "NUVAMA", "NYKAA", "OBEROIRLTY", "OFSS", 
    "OIL", "ONGC", "PAGEIND", "PATANJALI", "PAYTM", "PERSISTENT", "PETRONET", "PFC", "PGEL", "PHOENIXLTD", 
    "PIDILITIND", "PIIND", "PNB", "PNBHOUSING", "POLICYBZR", "POLYCAB", "POWERGRID", "POWERINDIA", "PREMIERENE", "PRESTIGE", 
    "RADICO", "RBLBANK", "RECLTD", "RELIANCE", "RVNL", "SAIL", "SAMMAANCAP", "SBICARD", "SBILIFE", "SBIN", 
    "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF", "SUNPHARMA", "SUPREMEIND", "SUZLON", "SWIGGY", 
    "TATACONSUM", "TATAELXSI", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TIINDIA", "TITAN", "TMPV", "TORNTPHARM", 
    "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "UNOMINDA", "UPL", "VBL", "VEDL", "VMM", 
    "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK", "ZYDUSLIFE"
]

# ==========================================
# 4. APP LOGIC & DATA FETCHING
# ==========================================
if auth_code:
    try:
        if auth_code != "AUTO_LOGGED_IN":
            session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code")
            session.set_token(auth_code)
            token = session.generate_token()['access_token']
            with open(TOKEN_STORE_FILE, 'w') as f:
                json.dump({"date": today_str, "token": token}, f)
            st.sidebar.success("✅ Token Generated & Saved!")
        else:
            token = saved_token

        fyers = fyersModel.FyersModel(client_id=APP_ID, is_async=False, token=token, log_path="")

        now_ist = datetime.datetime.now(IST)
        time_since_last = (now_ist - st.session_state.last_api_call).total_seconds()
        
        is_market_hours = (datetime.time(9, 15) <= now_ist.time() <= datetime.time(15, 30))

        if time_since_last >= 300:
            final_list = []
            new_csv_rows = [] 
            time_str = now_ist.strftime('%H:%M')
            today_str = now_ist.strftime("%Y-%m-%d")
            
            with st.spinner('🚀 Smart Scan Running... (Safe Speed)'):
                all_quotes = []
                for i in range(0, len(raw_symbols), 50):
                    batch = raw_symbols[i:i+50]
                    q_syms = ",".join([get_fyers_symbol(s) for s in batch])
                    quotes = fyers.quotes({"symbols": q_syms})
                    if quotes and quotes.get('s') == 'ok' and len(quotes.get('d', [])) > 0:
                        all_quotes.extend(quotes['d'])

                # 🚀 YAHAN WORKERS 10 SE GHATAKAR 4 KAR DIYE HAIN (API Limit bypass karne ke liye)
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    results = executor.map(fetch_option_chain_fast, all_quotes)
                    
                    for q, oc in results:
                        s_name = get_raw_symbol(q['n'])
                        v = q['v']
                        ltp_val = float(v.get('lp', 0))
                        open_p, prev_c = float(v.get('open_price', 0)), float(v.get('prev_close_price', 0))
                        
                        if open_p == 0 or prev_c == 0: open_status = "NA"
                        elif open_p > prev_c: open_status = "Gap Up 🔼"
                        elif open_p < prev_c: open_status = "Gap Down 🔽"
                        else: open_status = "Same ➖"

                        if oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']:
                            chain = oc['data']['optionsChain']
                            c_oi = sum(float(x.get('oi', 0)) for x in chain if str(x.get('symbol', '')).endswith('CE') or x.get('option_type') == 'CE')
                            p_oi = sum(float(x.get('oi', 0)) for x in chain if str(x.get('symbol', '')).endswith('PE') or x.get('option_type') == 'PE')
                            c_v = sum(float(x.get('volume', 0)) for x in chain if str(x.get('symbol', '')).endswith('CE') or x.get('volume_type') == 'CE') 
                            p_v = sum(float(x.get('volume', 0)) for x in chain if str(x.get('symbol', '')).endswith('PE') or x.get('option_type') == 'PE')
                            o_pcr, v_cpr, v_pcr = calc_opt_pcr(c_oi, p_oi), calc_vol_cpr(c_v, p_v), calc_vol_pcr(c_v, p_v)
                            
                            pcr_abs, vol_abs, pcr_pct, vol_pct = calc_checker_data(s_name, v_pcr, v_cpr, now_ist.time())
                            
                            final_list.append({
                                'SYMS': s_name, 'OPEN_STATUS': open_status, 'V_PCR': v_pcr, 'O_PCR': o_pcr, 'V_CPR': v_cpr, 
                                'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': ltp_val,
                                'VOL_ABS': vol_abs, 'PCR_ABS': pcr_abs, 
                                'VOL_PCT': vol_pct, 'PCR_PCT': pcr_pct,
                                'CE_CON': calc_conviction(chain, 'CE'), 'PE_CON': calc_conviction(chain, 'PE')
                            })
                            
                            if is_market_hours:
                                if s_name not in st.session_state.chart_history: 
                                    st.session_state.chart_history[s_name] = []
                                
                                new_row = {'Date': today_str, 'Time': time_str, 'LTP': ltp_val, 'VOL PCR': v_pcr, 'OPT PCR': o_pcr, 'VOL CPR': v_cpr}
                                st.session_state.chart_history[s_name].append(new_row)
                                csv_row = new_row.copy()
                                csv_row['Symbol'] = s_name
                                new_csv_rows.append(csv_row)
                        else:
                            final_list.append({'SYMS': s_name + " (NA)", 'OPEN_STATUS': open_status, 'V_PCR': 0.0, 'O_PCR': 0.0, 'V_CPR': 0.0, 'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': ltp_val, 'VOL_ABS': 0.0, 'PCR_ABS': 0.0, 'VOL_PCT': 0.0, 'PCR_PCT': 0.0, 'CE_CON': 0.0, 'PE_CON': 0.0})
            
            st.session_state.cached_data = final_list
            st.session_state.last_api_call = datetime.datetime.now(IST)

            if new_csv_rows:
                new_df = pd.DataFrame(new_csv_rows)[['Date', 'Symbol', 'Time', 'LTP', 'VOL PCR', 'OPT PCR', 'VOL CPR']]
                if not os.path.isfile(HISTORY_FILE):
                    new_df.to_csv(HISTORY_FILE, index=False)
                else:
                    new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

            last_auto_save = ""
            if os.path.exists(AUTO_SAVE_FILE):
                try:
                    with open(AUTO_SAVE_FILE, "r") as f:
                        last_auto_save = f.read().strip()
                except: pass

            if now_ist.time() >= datetime.time(15, 30) and last_auto_save != today_str:
                if save_eod_data():
                    try:
                        with open(AUTO_SAVE_FILE, "w") as f:
                            f.write(today_str)
                    except: pass

        # ==========================================
        # 5. DASHBOARD DISPLAY & STYLING
        # ==========================================
        if len(st.session_state.cached_data) > 0:
            tab1, tab2 = st.tabs(["📊 Dashboard", "📈 Trend Graph"])
            with tab1:
                col1, col2 = st.columns([3, 1])
                with col1:
                    search_query = st.text_input("🔍 Search Stock:", "").upper()
                with col2:
                    st.write("") 
                    show_pct = st.toggle("📊 Show Checker Data in Percentage (%)", value=True)
                
                df = pd.DataFrame(st.session_state.cached_data)
                if search_query: df = df[df['SYMS'].str.contains(search_query, na=False)]
                
                if not df.empty:
                    df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
                    df = df.sort_values(by='Conv_Rank', ascending=False).drop(columns=['Conv_Rank']) 
                    
                    if show_pct:
                        df['VOL CHECKER'] = df['VOL_PCT']
                        df['PCR CHECKER'] = df['PCR_PCT']
                        checker_fmt = '{:+.1f}%'
                    else:
                        df['VOL CHECKER'] = df['VOL_ABS']
                        df['PCR CHECKER'] = df['PCR_ABS']
                        checker_fmt = '{:+.2f}'
                        
                    df = df.drop(columns=['VOL_ABS', 'PCR_ABS', 'VOL_PCT', 'PCR_PCT'])
                    df = df.rename(columns={'SYMS': 'SYMBOL', 'OPEN_STATUS': 'OPENING', 'V_PCR': 'VOL PCR', 'O_PCR': 'OPTION PCR', 'V_CPR': 'VOL CPR', 'LTP_CH': 'LTP CHANGE', 'CHG_%': 'CHANGE%', 'LTP': 'LTP', 'CE_CON': 'CE_CONTRACT', 'PE_CON': 'PE_CONTRACT'})

                    def style_indicators(val):
                        if isinstance(val, str): 
                            if "Gap Up" in val: return 'color: #00AA00; font-weight: bold; text-align: center;'
                            if "Gap Down" in val: return 'color: #FF0000; font-weight: bold; text-align: center;'
                            if "Same" in val: return 'color: #00BFFF; font-weight: bold; text-align: center;'
                            return 'text-align: center;'
                        if val > 0: return 'color: #00AA00; font-weight: bold; text-align: center;'
                        elif val < 0: return 'color: #FF0000; font-weight: bold; text-align: center;'
                        return 'color: #888888; font-weight: bold; text-align: center;'

                    def style_pcr_columns(val):
                        if isinstance(val, (int, float)):
                            if val >= 1.0: return 'color: #00AA00; font-weight: bold; text-align: center;'
                            elif val > 0 and val < 1.0: return 'color: #FF0000; font-weight: bold; text-align: center;'
                        return 'text-align: center;'

                    format_dict = {'VOL PCR': '{:.2f}', 'OPTION PCR': '{:.2f}', 'VOL CPR': '{:.2f}', 'LTP': '{:.2f}', 'LTP CHANGE': '{:.2f}', 'CHANGE%': '{:+.2f}%', 'VOL CHECKER': checker_fmt, 'PCR CHECKER': checker_fmt, 'CE_CONTRACT': '{:+.1f}%', 'PE_CONTRACT': '{:+.1f}%'}
                    header_styles = [
                        {'selector': 'th', 'props': [('background-color', 'darkblue'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]},
                        {'selector': 'thead th', 'props': [('background-color', 'darkblue'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                    ]

                    styled_df = (df.style.set_properties(**{'text-align': 'center'}).format(format_dict).set_table_styles(header_styles)
                                 .map(style_indicators, subset=['OPENING', 'LTP CHANGE', 'CHANGE%', 'CE_CONTRACT', 'PE_CONTRACT', 'VOL CHECKER', 'PCR CHECKER'])
                                 .map(style_pcr_columns, subset=['VOL PCR', 'OPTION PCR', 'VOL CPR']))

                    st.dataframe(styled_df, use_container_width=True, height=800, hide_index=True)

            with tab2:
                col1, col2 = st.columns([1, 2])
                selected_stock = col1.selectbox("Select Stock:", raw_symbols, index=0)
                graph_filter = col2.radio("Metric:", ["VOL CPR", "OPT PCR"], horizontal=True)
                
                if selected_stock in st.session_state.chart_history and len(st.session_state.chart_history[selected_stock]) > 0:
                    chart_df = pd.DataFrame(st.session_state.chart_history[selected_stock])
                    
                    chart_df['Datetime'] = pd.to_datetime(st.session_state.current_date + ' ' + chart_df['Time'])
                    
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    fig.add_trace(go.Scatter(x=chart_df['Datetime'], y=chart_df[graph_filter], name=graph_filter, line=dict(color='deepskyblue', width=3)), secondary_y=False)
                    fig.add_trace(go.Scatter(x=chart_df['Datetime'], y=chart_df['LTP'], name="LTP", line=dict(color='#00AA00', width=3)), secondary_y=True)
                    
                    fig.update_layout(title_text=f"{selected_stock} Trend", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"), height=450)
                    
                    start_dt = pd.to_datetime(f"{st.session_state.current_date} 09:15:00")
                    end_dt = pd.to_datetime(f"{st.session_state.current_date} 15:30:00")
                    
                    fig.update_xaxes(
                        type="date",
                        range=[start_dt, end_dt],
                        rangeslider_visible=True, 
                        rangeslider_thickness=0.05,
                        tickformat="%H:%M"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)

            st.write(f"🔄 Next scan in 5 mins... Last updated: {st.session_state.last_api_call.strftime('%H:%M:%S')}")
            time_diff = (datetime.datetime.now(IST) - st.session_state.last_api_call).total_seconds()
            time.sleep(max(0, 300 - time_diff))
            st.rerun()

    except Exception as e:
        st.sidebar.error(f"❌ Error: {e}")
else:
    st.info("👈 Please enter Auth Code in sidebar.")
