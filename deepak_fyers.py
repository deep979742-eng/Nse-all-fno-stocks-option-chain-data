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

# 🚀 COPY-PASTE ERROR FIXED: One-line CSS format to completely avoid Indentation Error!
st.markdown("<style>[data-testid='stAppViewContainer'], [data-testid='stAppViewBlockContainer'], [data-testid='stHeader'], [data-testid='stSidebar'], .stApp, .stApp > div { opacity: 1 !important; filter: none !important; transition: none !important; } [data-testid='stDataFrame'], [data-testid='stTabs'] { opacity: 1 !important; filter: none !important; transition: none !important; } [data-testid='stStatusWidget'] { visibility: hidden !important; display: none !important; } .block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; } [data-testid='stDataFrameTable'] > thead > tr { background-color: darkblue !important; } [data-testid='stDataFrameTable'] > thead > tr > th { background-color: darkblue !important; color: white !important; font-weight: bold !important; text-align: center !important; } th { background-color: darkblue !important; color: white !important; } * { cursor: default !important; }</style>", unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now_ist = datetime.datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")

HISTORY_FILE = "chart_history.csv"
SNAPSHOT_FILE = "snapshot_950.json"
TOKEN_STORE_FILE = "fyers_token_store.json"
AUTO_SAVE_FILE = "auto_save_tracker.txt"
STRIKE_MEM_FILE = "intraday_strike_memory.json"
TODAY_BASELINE_FILE = "today_baseline_fallback.json"

# ==========================================
# 2. GOOGLE SHEETS & SMART 2-DAY ROLLING MANAGEMENT
# ==========================================
if os.path.exists(HISTORY_FILE):
    try:
        hist_check = pd.read_csv(HISTORY_FILE)
        if not hist_check.empty and 'Date' in hist_check.columns and hist_check['Date'].iloc[-1] != today_str:
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
    except: pass
    return None

sheet = get_gsheet()
global_history = {}

# 🚀 FIX: Smart Migration Logic - Converts old format to new date-based format
if os.path.exists(STRIKE_MEM_FILE):
    try:
        loaded_db = json.load(open(STRIKE_MEM_FILE))
        if "data" in loaded_db and "history" not in loaded_db:
            old_date = loaded_db.get("date", (now_ist - datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
            global_history = {old_date: loaded_db["data"]}
        else:
            global_history = loaded_db.get("history", {})
    except: pass

if not global_history and sheet is not None:
    try:
        col_values = sheet.col_values(1)
        if col_values: 
            raw_gsheet = json.loads("".join(col_values))
            if raw_gsheet:
                first_key = list(raw_gsheet.keys())[0]
                if first_key.startswith("NSE:"):
                    # Converting old sheet data to include yesterday's date
                    old_date = (now_ist - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    global_history = {old_date: raw_gsheet}
                else:
                    global_history = raw_gsheet
    except: pass

with open(STRIKE_MEM_FILE, "w") as f:
    json.dump({"date": today_str, "history": global_history}, f)

def get_previous_market_baseline(history_db, today_date_str):
    past_dates = sorted([d for d in history_db.keys() if d < today_date_str])
    return history_db[past_dates[-1]] if past_dates else {}

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
    
    try:
        db_content = json.load(open(STRIKE_MEM_FILE))
        hist_db = db_content.get("history", {})
    except:
        hist_db = {}

    baseline_prices = get_previous_market_baseline(hist_db, date_str)
    
    if date_str not in hist_db:
        hist_db[date_str] = {}
        
    try: snap_950 = json.load(open(SNAPSHOT_FILE)).get("data", {})
    except: snap_950 = {}

    # 🚀 FIX: Create a local daily baseline for fallback if Google Sheet data is empty
    try: today_baseline = json.load(open(TODAY_BASELINE_FILE))
    except: today_baseline = {}
    if today_baseline.get("date") != date_str:
        today_baseline = {"date": date_str, "prices": {}}

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

    # 🚀 RESTORED ORIGINAL 2.0 SECONDS STABLE RETRY LOGIC
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
                p_v = sum(float(x.get('volume', 0)) for x in chain if str(x.get('symbol', '')).endswith('PE') or x.get('volume_type') == 'PE')
                o_pcr, v_cpr, v_pcr = calc_opt_pcr(c_oi, p_oi), calc_vol_cpr(c_v, p_v), calc_vol_pcr(c_v, p_v)
                
                for s in chain:
                    sym_str, lp_str = str(s.get('symbol', '')), float(s.get('ltp', 0))
                    if lp_str > 0: 
                        # 1. Continously update today's history for EOD Save
                        hist_db[date_str][sym_str] = lp_str
                        # 2. Save first seen price of today as fallback baseline
                        if sym_str not in today_baseline["prices"]:
                            today_baseline["prices"][sym_str] = lp_str

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

                # 🚀 100% BULLETPROOF CHAIN COMPARISON LOGIC
                def get_conv(opt_type):
                    strikes = [s for s in chain if s.get('option_type') == opt_type.upper() or str(s.get('symbol', '')).endswith(opt_type.upper())]
                    tot_p, tot_m = 0, 0
                    for s in strikes:
                        sym, lp = str(s.get('symbol', '')), float(s.get('ltp', 0
