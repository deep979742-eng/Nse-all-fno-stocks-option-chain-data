import streamlit as st
import pandas as pd
import datetime
import time
import os
import json
import base64
from fyers_apiv3 import fyersModel
import gspread
from google.oauth2.service_account import Credentials
import concurrent.futures
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. FYERS CREDENTIALS & SETUP
# ==========================================
CLIENT_ID = "YD02909"
APP_ID = "I0QMW3KFAW-100"
SECRET_ID = "T63F5XCUSH"
REDIRECT_URI = "https://www.google.com/" 

st.set_page_config(page_title="F&O Dashboard", layout="wide")

# CSS - FULLY MOBILE RESPONSIVE & ALL VERTICAL HEADERS
css_str = """<style>
[data-testid='stAppViewContainer'], [data-testid='stAppViewBlockContainer'], [data-testid='stHeader'], [data-testid='stSidebar'], .stApp, .stApp > div { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stDataFrame'], [data-testid='stTabs'] { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stStatusWidget'] { visibility: hidden !important; display: none !important; } 
.block-container { padding-top: 3rem !important; padding-bottom: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; } 
[data-testid='stDataFrameTable'] > thead > tr { background-color: darkblue !important; } 

/* ALL Headers Vertical (Including SYMBOL) to Save Maximum Space on Mobile */
[data-testid='stDataFrameTable'] > thead > tr > th { 
    background-color: darkblue !important; 
    color: white !important; 
    font-weight: bold !important; 
    text-align: center !important; 
    writing-mode: vertical-rl !important; 
    transform: rotate(180deg) !important; 
    white-space: nowrap !important; 
    padding: 8px 4px !important;
    height: 120px !important;
} 

th { background-color: darkblue !important; color: white !important; } 
* { cursor: default !important; } 

/* Extreme Mobile Optimization */
@media (max-width: 768px) { 
    .block-container { padding-top: 1rem !important; padding-left: 0.1rem !important; padding-right: 0.1rem !important; } 
    [data-testid='stDataFrameTable'] th { font-size: 10px !important; height: 100px !important; padding: 4px 2px !important; } 
    [data-testid='stDataFrameTable'] td { font-size: 10px !important; padding: 4px 2px !important; } 
}
</style>"""
st.markdown(css_str, unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
now_ist = datetime.datetime.now(IST)
today_str = now_ist.strftime("%Y-%m-%d")

HISTORY_FILE = "chart_history.csv"
SNAPSHOT_FILE = "snapshot_950.json"
TOKEN_STORE_FILE = "fyers_token_store.json"
AUTO_SAVE_FILE = "auto_save_tracker.txt"

if 'live_base_date' not in st.session_state or st.session_state.live_base_date != today_str:
    st.session_state.live_base = {}
    st.session_state.live_base_date = today_str

# ==========================================
# 2. GOOGLE SHEETS DYNAMIC CONNECTION
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        if "gcp_service_account" in st.secrets:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            return gspread.authorize(creds)
    except: pass
    return None

# ==========================================
# 3. STOCK LIST
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
# 4. MASTER SCANNER (WITH AUTO-ROLLOVER & SLN FORMULA)
# ==========================================
@st.cache_data(ttl=290, show_spinner=False)
def run_master_scan(token, date_str):
    fyers = fyersModel.FyersModel(client_id=APP_ID, is_async=False, token=token, log_path="")
    scan_time_ist = datetime.datetime.now(IST)
    time_str = scan_time_ist.strftime('%H:%M')
    
    baseline_prices = {}
    snap_950 = {}
    snapshot_changed = False
    
    client = get_gspread_client()
    if client:
        try:
            ss = client.open("Fyers_EOD_Data")
            ws1 = ss.get_worksheet(0) 
            ws2 = ss.worksheet("Sheet2") 
            
            # 🚀 A. NEXT MORNING AUTO-ROLLOVER LOGIC
            try:
                tab2_date_row = ws2.cell(1, 1).value
                if tab2_date_row and "LAST_SAVED_DATE:" in tab2_date_row:
                    saved_date = tab2_date_row.replace("LAST_SAVED_DATE:", "").strip()
                    if saved_date and saved_date != date_str:
                        tab2_col_vals = ws2.col_values(1)[1:] 
                        full_b64 = "".join(tab2_col_vals)
                        if full_b64:
                            ws1.clear()
                            chunks = [full_b64[i:i+40000] for i in range(0, len(full_b64), 40000)]
                            clist1 = ws1.range(f'A1:A{len(chunks)}')
                            for i, cell in enumerate(clist1): cell.value = chunks[i]
                            ws1.update_cells(clist1)
                            
                            ws2.update_cell(1, 1, f"LAST_SAVED_DATE: {date_str}")
                            ws2.batch_clear(["A2:A100"])
            except: pass

            # 🚀 B. LOAD BASELINE FROM TAB 1
            try:
                col_vals = ws1.col_values(1)
                if col_vals:
                    full_str = "".join(col_vals)
                    decoded_str = base64.b64decode(full_str).decode('utf-8')
                    loaded_prices = json.loads(decoded_str)
                    for k, v in loaded_prices.items():
                        baseline_prices[k] = round(float(v), 2)
            except: pass

            # 🚀 C. LOAD 9:50 AM SNAPSHOT
            try:
                snap_val = ws2.cell(1, 2).value
                if snap_val: snap_950 = json.loads(snap_val)
            except: pass
        except: pass

    st.session_state.baseline_count = len(baseline_prices)
    st.session_state.has_snapshot = bool(snap_950)

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
    live_ltp_data = {} 

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
            spot_ltp = float(v.get('lp', 0)) 
            open_p, float_c = float(v.get('open_price', 0)), float(v.get('prev_close_price', 0))
            open_status = "NA" if open_p == 0 or float_c == 0 else "Gap Up 🔼" if open_p > float_c else "Gap Down 🔽" if open_p < float_c else "Same ➖"

            if oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']:
                chain = oc['data']['optionsChain']
                c_oi = sum(float(x.get('oi', 0)) for x in chain if str(x.get('symbol', '')).endswith('CE') or x.get('option_type') == 'CE')
                p_oi = sum(float(x.get('oi', 0)) for x in chain if
