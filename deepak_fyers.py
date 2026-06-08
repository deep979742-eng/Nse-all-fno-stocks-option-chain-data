import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
from fyers_apiv3 import fyersModel
import gspread
from google.oauth2.service_account import Credentials
import concurrent.futures
# 🚀 ADVANCED CHARTING LIBRARIES
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. FYERS CREDENTIALS & GLOBAL SETUP
# ==========================================
CLIENT_ID = "YD02909"
APP_ID = "I0QMW3KFAW-100"
SECRET_ID = "T63F5XCUSH"
REDIRECT_URI = "https://www.google.com/" 

st.set_page_config(page_title="F&O Dashboard", layout="wide")

st.markdown("""
    <style>
        [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"], 
        [data-testid="stHeader"], [data-testid="stSidebar"], .stApp, .stApp > div { 
            opacity: 1 !important; filter: none !important; transition: none !important; 
        }
        [data-testid="stDataFrame"], [data-testid="stTabs"] { 
            opacity: 1 !important; filter: none !important; transition: none !important; 
        }
        [data-testid="stStatusWidget"] { visibility: hidden !important; display: none !important; }
        .block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; }
        [data-testid="stDataFrameTable"] > thead > tr { background-color: darkblue !important; }
        [data-testid="stDataFrameTable"] > thead > tr > th { background-color: darkblue !important; color: white !important; font-weight: bold !important; text-align: center !important; }
        th { background-color: darkblue !important; color: white !important; }
        * { cursor: default !important; }
    </style>
""", unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now_ist = datetime.datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")

HISTORY_FILE = "chart_history.csv"
SNAPSHOT_FILE = "snapshot_950.json"
TOKEN_STORE_FILE = "fyers_token_store.json"
AUTO_SAVE_FILE = "auto_save_tracker.txt"
STRIKE_MEM_FILE = "intraday_strike_memory.json"

# ==========================================
# 2. GOOGLE SHEETS & MEMORY MANAGEMENT
# ==========================================
if os.path.exists(HISTORY_FILE):
    try:
        hist_check = pd.read_csv(HISTORY_FILE)
        if 'Date' in hist_check.columns and hist_check['Date'].iloc[-1] != today_str:
            os.remove(HISTORY_FILE)
    except: os.remove(HISTORY_FILE)

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

if not os.path.exists(STRIKE_MEM_FILE) or json.load(open(STRIKE_MEM_FILE)).get('date') != today_str:
    initial_mem = {}
    if sheet is not None:
        try:
            col_values = sheet.col_values(1)
            if col_values: initial_mem = json.loads("".join(col_values))
        except: pass
    with open(STRIKE_MEM_FILE, "w") as f:
        json.dump({"date": today_str, "data": initial_mem}, f)

# ==========================================
# 3. STOCK LIST & FORMULAS
# ==========================================
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

def calc_vol_pcr(ce_vol, pe_vol): return 0.0 if ce_vol == 0 else round(pe_vol / ce_vol, 2)
def calc_opt_pcr(ce_oi, pe_oi): return 0.0 if ce_oi == 0 else round(pe_oi / ce_oi, 2)
def calc_vol_cpr(ce_vol, pe_vol): return 0.0 if pe_vol == 0 else round(ce_vol / pe_vol, 2)
def get_fyers_symbol(s): return f"NSE:NIFTY50-INDEX" if s=="NIFTY" else f"NSE:NIFTYBANK-INDEX" if s=="BANKNIFTY" else f"NSE:FINNIFTY-INDEX" if s=="FINNIFTY" else f"NSE:MIDCPNIFTY-INDEX" if s=="MIDCPNIFTY" else f"NSE:{s}-EQ"
def get_raw_symbol(fyers_sym): 
    s = fyers_sym.split(':')[1].replace('-EQ', '').replace('-INDEX', '')
    return "NIFTY" if s=="NIFTY50" else "BANKNIFTY" if s=="NIFTYBANK" else s

# ==========================================
# 4. 🚀 GLOBAL CACHE LOCK (MASTER SCANNER) 🚀
# ==========================================
@st.cache_data(ttl=290, show_spinner=False)
def run_master_scan(token, date_str):
    fyers = fyersModel.FyersModel(client_id=APP_ID, is_async=False, token=token, log_path="")
    scan_time_ist = datetime.datetime.now(IST)
    time_str = scan_time_ist.strftime('%H:%M')
    
    try: strike_mem = json.load(open(STRIKE_MEM_FILE)).get("data", {})
    except: strike_mem = {}
    try: snap_950 = json.load(open(SNAPSHOT_FILE)).get("data", {})
    except: snap_950 = {}

    all_quotes = []
    for i in range(0, len(raw_symbols), 50):
        batch = raw_symbols[i:i+50]
        q_syms = ",".join([get_fyers_symbol(s) for s in batch])
        quotes = fyers.quotes({"symbols": q_syms})
        if quotes and quotes.get('s') == 'ok' and len(quotes.get('d', [])) > 0:
            all_quotes.extend(quotes['d'])
            
    if not all_quotes: return None, None 
        
    final_list = []
    new_csv_rows = []

    def fetch_option_chain_fast_local(q):
        sym = q['n']
        time.sleep(0.4) 
        try:
            oc = fyers.optionchain(data={"symbol": sym, "strikecount": 150, "timestamp": ""})
            if not (oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']):
                time.sleep(2.0) 
                oc = fyers.optionchain(data={"symbol": sym, "strikecount": 150, "timestamp": ""})
            return q, oc
        except: return q, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(fetch_option_chain_fast_local, all_quotes)
        for q, oc in results:
            s_name = get_raw_symbol(q['n'])
            v = q['v']
            ltp_val = float(v.get('lp', 0))
            open_p, prev_c = float(v.get('open_price', 0)), float(v.get('prev_close_price', 0))
            
            open_status = "NA" if open_p == 0 or prev_c == 0 else "Gap Up 🔼" if open_p > prev_c else "Gap Down 🔽" if open_p < prev_c else "Same ➖"

            if oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']:
                chain = oc['data']['optionsChain']
                c_oi = sum(float(x.get('oi', 0)) for x in chain if str(x.get('symbol', '')).endswith('CE') or x.get('option_type') == 'CE')
                p_oi = sum(float(x.get('oi', 0)) for x in chain if str(x.get('symbol', '')).endswith('PE') or x.get('option_type') == 'PE')
                c_v = sum(float(x.get('volume', 0)) for x in chain if str(x.get('symbol', '')).endswith('CE') or x.get('volume_type') == 'CE') 
                p_v = sum(float(x.get('volume', 0)) for x in chain if str(x.get('symbol', '')).endswith('PE') or x.get('option_type') == 'PE')
                o_pcr, v_cpr, v_pcr = calc_opt_pcr(c_oi, p_oi), calc_vol_cpr(c_v, p_v), calc_vol_pcr(c_v, p_v)
                
                target_time = datetime.time(9, 50)
                if scan_time_ist.time() < target_time: pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                else:
                    if s_name not in snap_950:
                        snap_950[s_name] = {'pcr': v_pcr, 'vol_cpr': v_cpr}
                        pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                    else:
                        base = snap_950[s_name]
                        pcr_abs, vol_abs = v_pcr - base['pcr'], v_cpr - base['vol_cpr']
                        pcr_pct = ((v_pcr - base['pcr']) / base['pcr']) * 100 if base['pcr'] != 0 else 0.0
                        vol_pct = ((v_cpr - base['vol_cpr']) / base['vol_cpr']) * 100 if base['vol_cpr'] != 0 else 0.0

                def get_conv(opt_type):
                    strikes = [s for s in chain if s.get('option_type') == opt_type.upper() or str(s.get('symbol', '')).endswith(opt_type.upper())]
                    tot_p, tot_m = 0, 0
                    for s in strikes:
                        sym, lp = str(s.get('symbol', '')), float(s.get('ltp', 0))
                        if lp == 0: continue
                        if sym not in strike_mem: 
                            strike_mem[sym] = lp; continue
                        diff = lp - strike_mem[sym]
                        if diff > 0: tot_p += 1 
                        elif diff < 0: tot_m += 1 
                        if scan_time_ist.time() >= datetime.time(15, 30):
                            strike_mem[sym] = lp
                    act = tot_p + tot_m
                    if act == 0: return 0.0
                    return round((tot_p / act) * 100, 1) if tot_p >= tot_m else -round((tot_m / act) * 100, 1)
                
                final_list.append({
                    'SYMS': s_name, 'OPEN_STATUS': open_status, 'V_PCR': v_pcr, 'O_PCR': o_pcr, 'V_CPR': v_cpr, 
                    'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': ltp_val,
                    'VOL_ABS': round(vol_abs, 2), 'PCR_ABS': round(pcr_abs, 2), 
                    'VOL_PCT': round(vol_pct, 1), 'PCR_PCT': round(pcr_pct, 1),
                    'CE_CON': get_conv('CE'), 'PE_CON': get_conv('PE')
                })

                if datetime.time(9, 15) <= scan_time_ist.time() <= datetime.time(15, 30):
                    new_csv_rows.append({'Date': date_str, 'Symbol': s_name, 'Time': time_str, 'LTP': ltp_val, 'VOL PCR': v_pcr, 'OPT PCR': o_pcr, 'VOL CPR': v_cpr})

            else:
                final_list.append({'SYMS': s_name + " (NA)", 'OPEN_STATUS': open_status, 'V_PCR': 0.0, 'O_PCR': 0.0, 'V_CPR': 0.0, 'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': ltp_val, 'VOL_ABS': 0.0, 'PCR_ABS': 0.0, 'VOL_PCT': 0.0, 'PCR_PCT': 0.0, 'CE_CON': 0.0, 'PE_CON': 0.0})

    try: json.dump({"date": date_str, "data": strike_mem}, open(STRIKE_MEM_FILE, "w"))
    except: pass
    try: json.dump({"date": date_str, "data": snap_950}, open(SNAPSHOT_FILE, "w"))
    except: pass
    
    if new_csv_rows:
        new_df = pd.DataFrame(new_csv_rows)[['Date', 'Symbol', 'Time', 'LTP', 'VOL PCR', 'OPT PCR', 'VOL CPR']]
        if not os.path.isfile(HISTORY_FILE): new_df.to_csv(HISTORY_FILE, index=False)
        else: new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

    return final_list, scan_time_ist.timestamp()

# ==========================================
# 5. SIDEBAR LOGIN & EOD SAVE
# ==========================================
st.sidebar.header("🔑 Fyers Quick Login")

saved_token = None
if os.path.exists(TOKEN_STORE_FILE):
    try:
        td = json.load(open(TOKEN_STORE_FILE))
        if td.get("date") == today_str: saved_token = td.get("token")
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

def save_eod_data():
    if os.path.exists(STRIKE_MEM_FILE) and sheet is not None:
        try:
            mem_data = json.load(open(STRIKE_MEM_FILE)).get("data", {})
            if mem_data:
                json_str = json.dumps(mem_data)
                chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
                sheet.clear()
                clist = sheet.range(f'A1:A{len(chunks)}')
                for i, cell in enumerate(clist): cell.value = chunks[i]
                sheet.update_cells(clist)
                return True
        except Exception as e: st.sidebar.error(f"GSheet Error: {e}")
    return False

if st.sidebar.button("Manual Save 3:30 PM Data"):
    if save_eod_data(): st.sidebar.success("✅ EOD Data Saved PERMANENTLY!")

# ==========================================
# 6. APP RENDERING & MAGIC VIEWER
# ==========================================
if auth_code:
    if auth_code != "AUTO_LOGGED_IN":
        session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code")
        session.set_token(auth_code)
        token = session.generate_token()['access_token']
        json.dump({"date": today_str, "token": token}, open(TOKEN_STORE_FILE, 'w'))
        st.sidebar.success("✅ Token Saved!")
    else:
        token = saved_token

    cached_result, last_scan_timestamp = run_master_scan(token, today_str)

    if cached_result is not None:
        st.session_state.cached_data = cached_result
        st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
        
        if now_ist.time() >= datetime.time(15, 30):
            last_save = open(AUTO_SAVE_FILE, "r").read().strip() if os.path.exists(AUTO_SAVE_FILE) else ""
            if last_save != today_str:
                if save_eod_data(): open(AUTO_SAVE_FILE, "w").write(today_str)
    else:
        st.warning("⚠️ Fyers API Data Wait... Retrying in 1 min.")
        if 'cached_data' not in st.session_state: st.session_state.cached_data = []

    if len(st.session_state.cached_data) > 0:
        
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

        header_styles = [
            {'selector': 'th', 'props': [('background-color', 'darkblue'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]},
            {'selector': 'thead th', 'props': [('background-color', 'darkblue'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
        ]

        # 🚀 TABS NAME UPDATED TO 'TREND CHART'
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🌐 NiftyTrader Web", "📈 TREND CHART"])
        
        with tab1:
            col1, col2 = st.columns([3, 1])
            with col1: search_query = st.text_input("🔍 Search Stock:", "").upper()
            with col2: st.write(""); show_pct = st.toggle("📊 Show Checker Data in Percentage (%)", value=True)
            
            checker_fmt = '{:+.1f}%' if show_pct else '{:+.2f}'
            format_dict = {'VOL PCR': '{:.2f}', 'OPTION PCR': '{:.2f}', 'VOL CPR': '{:.2f}', 'LTP': '{:.2f}', 'LTP CHANGE': '{:.2f}', 'CHANGE%': '{:+.2f}%', 'VOL CHECKER': checker_fmt, 'PCR CHECKER': checker_fmt, 'CE_CONTRACT': '{:+.1f}%', 'PE_CONTRACT': '{:+.1f}%'}
            
            df = pd.DataFrame(st.session_state.cached_data)
            if search_query: df = df[df['SYMS'].str.contains(search_query, na=False)]
            
            if not df.empty:
                df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
                df = df.sort_values
