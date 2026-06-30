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
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components  

# ==========================================
# 1. FYERS CREDENTIALS & SETUP
# ==========================================
CLIENT_ID = "YD02909"
APP_ID = "I0QMW3KFAW-100"
SECRET_ID = "T63F5XCUSH"
REDIRECT_URI = "https://www.google.com/" 

st.set_page_config(page_title="F&O Dashboard", layout="wide")

# CSS - FULLY MOBILE RESPONSIVE & LAPTOP SCREEN FIT
css_str = """<style>
[data-testid='stAppViewContainer'], [data-testid='stAppViewBlockContainer'], [data-testid='stHeader'], [data-testid='stSidebar'], .stApp, .stApp > div { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stDataFrame'], [data-testid='stTabs'] { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stStatusWidget'] { visibility: hidden !important; display: none !important; } 

.block-container { padding-top: 3.5rem !important; padding-bottom: 0rem !important; padding-left: 1rem !important; padding-right: 1rem !important; } 
[data-testid='stDataFrameTable'] > thead > tr { background-color: darkblue !important; } 

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

div[role="radiogroup"] { margin-top: 5px !important; }

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
SHARED_LIVE_DATA_FILE = "shared_live_data.json" 

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
    except Exception:
        pass
    return None

# ==========================================
# 3. STOCK LIST & HELPER FUNCTIONS
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
# 4. APP MODE SELECTION
# ==========================================
st.sidebar.markdown("### 📱 APP MODE")
app_mode = st.sidebar.radio("Select Device Role:", ["💻 Master (Data Fetcher)", "📱 Viewer (Mobile Client)"])
st.sidebar.markdown("---")

if app_mode == "📱 Viewer (Mobile Client)":
    st_autorefresh(interval=30000, limit=100000, key="viewer_fetch_loop")
elif app_mode == "💻 Master (Data Fetcher)":
    st_autorefresh(interval=300000, limit=100000, key="master_fetch_loop")

# ==========================================
# 5. DATA SCANNER (Master Fast Engine)
# ==========================================
@st.cache_data(show_spinner=False)
def run_master_scan(token, date_str, cycle_id):
    fyers = fyersModel.FyersModel(client_id=APP_ID, is_async=False, token=token, log_path="")
    scan_time_ist = datetime.datetime.now(IST)
    time_str = scan_time_ist.strftime('%H:%M')
    
    baseline_prices = {}
    snap_950 = {}
    snapshot_changed = False
    saved_date = None
    
    client = get_gspread_client()
    if client:
        try:
            ss = client.open("Fyers_EOD_Data")
            ws1 = ss.get_worksheet(0) 
            ws2 = ss.worksheet("Sheet2") 
            
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
                            saved_date = date_str
            except Exception:
                pass

            try:
                if saved_date == date_str:
                    col_vals = ws2.col_values(1)[1:]
                else:
                    col_vals = ws1.col_values(1)
                    
                if col_vals:
                    full_str = "".join(col_vals)
                    decoded_str = base64.b64decode(full_str).decode('utf-8')
                    loaded_prices = json.loads(decoded_str)
                    for k, v in loaded_prices.items():
                        baseline_prices[k] = round(float(v), 2)
            except Exception:
                pass

            try:
                snap_val = ws2.cell(1, 2).value
                if snap_val: snap_950 = json.loads(snap_val)
            except Exception:
                pass
        except Exception:
            pass

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
    missing_stock_names = []
    results_list = []

    def fetch_option_chain_fast_local(q):
        sym = q['n']
        time.sleep(0.3) 
        try:
            oc = fyers.optionchain(data={"symbol": sym, "strikecount": 60, "timestamp": ""})
            if not (oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']):
                time.sleep(1.0) 
                oc = fyers.optionchain(data={"symbol": sym, "strikecount": 60, "timestamp": ""})
            return q, oc
        except Exception: 
            return q, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_q = {executor.submit(fetch_option_chain_fast_local, q): q for q in all_quotes}
        try:
            for future in concurrent.futures.as_completed(future_to_q, timeout=120):
                try:
                    res = future.result()
                    if res: results_list.append(res)
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            missing_stock_names.append("⚠️ Fyers Server Timeout")
            
    for q, oc in results_list:
        s_name = get_raw_symbol(q['n'])
        v = q['v']
        spot_ltp = float(v.get('lp', 0)) 
        open_p = float(v.get('open_price', 0))
        float_c = float(v.get('prev_close_price', 0))
        open_status = "NA" if open_p == 0 or float_c == 0 else "Gap Up 🔼" if open_p > float_c else "Gap Down 🔽" if open_p < float_c else "Same ➖"

        try:
            if oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']:
                chain = oc['data']['optionsChain']
                
                c_oi, p_oi, c_v, p_v = 0.0, 0.0, 0.0, 0.0
                
                for s in chain:
                    sym_str = str(s.get('symbol', ''))
                    o_type = str(s.get('option_type', ''))
                    
                    if sym_str.endswith('CE') or o_type == 'CE':
                        c_oi += float(s.get('oi', 0))
                        c_v += float(s.get('volume', 0))
                    elif sym_str.endswith('PE') or o_type == 'PE':
                        p_oi += float(s.get('oi', 0))
                        p_v += float(s.get('volume', 0))
                        
                    lp_str = round(float(s.get('ltp', 0)), 2)
                    if lp_str > 0.0:
                        live_ltp_data[sym_str] = lp_str

                o_pcr = calc_opt_pcr(c_oi, p_oi)
                v_cpr = calc_vol_cpr(c_v, p_v)
                v_pcr = calc_vol_pcr(c_v, p_v)

                if scan_time_ist.time() < datetime.time(9, 50):
                    pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                else:
                    if s_name not in snap_950:
                        snap_950[s_name] = {'pcr': o_pcr, 'vol_cpr': v_cpr}
                        snapshot_changed = True
                        pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                    else:
                        base = snap_950[s_name]
                        base_pcr_val = base['pcr']
                        base_vol_val = base['vol_cpr']
                        
                        pcr_abs = o_pcr - base_pcr_val
                        vol_abs = v_cpr - base_vol_val
                        
                        def get_standard_pct(current_val, base_val):
                            if base_val == 0: return 0.0
                            return ((current_val - base_val) / base_val) * 100.0
                            
                        pcr_pct = get_standard_pct(o_pcr, base_pcr_val)
                        vol_pct = get_standard_pct(v_cpr, base_vol_val)

                def get_conv(opt_type_val):
                    if not baseline_prices: return 0.0
                    strikes = [stk for stk in chain if stk.get('option_type') == opt_type_val.upper() or str(stk.get('symbol', '')).endswith(opt_type_val.upper())]
                    tot_p, tot_m = 0, 0
                    for stk in strikes:
                        sym = str(stk.get('symbol', ''))
                        lp = round(float(stk.get('ltp', 0)), 2)
                        if lp == 0: continue
                        diff = 0.0
                        if sym in baseline_prices: diff = round(lp - baseline_prices[sym], 2)
                        if diff > 0.00: tot_p += 1 
                        elif diff < 0.00: tot_m += 1 
                    act = tot_p + tot_m
                    if act == 0: return 0.0
                    return round((tot_p / act) * 100, 2) if tot_p >= tot_m else -round((tot_m / act) * 100, 2)
                
                final_list.append({
                    'SYMS': s_name, 'OPEN_STATUS': open_status, 'V_PCR': v_pcr, 'O_PCR': o_pcr, 'V_CPR': v_cpr, 
                    'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': spot_ltp,
                    'VOL_ABS': round(vol_abs, 2), 'PCR_ABS': round(pcr_abs, 2), 
                    'VOL_PCT': round(vol_pct, 2), 'PCR_PCT': round(pcr_pct, 2),
                    'CE_CON': get_conv('CE'), 'PE_CON': get_conv('PE')
                })

                if datetime.time(9, 15) <= scan_time_ist.time() <= datetime.time(15, 30):
                    new_csv_rows.append({'Date': date_str, 'Symbol': s_name, 'Time': time_str, 'LTP': spot_ltp, 'VOL PCR': v_pcr, 'OPT PCR': o_pcr, 'VOL CPR': v_cpr})
            else:
                missing_stock_names.append(s_name) 
                final_list.append({'SYMS': s_name + " (NA)", 'OPEN_STATUS': open_status, 'V_PCR': 0.0, 'O_PCR': 0.0, 'V_CPR': 0.0, 'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': spot_ltp, 'VOL_ABS': 0.0, 'PCR_ABS': 0.0, 'VOL_PCT': 0.0, 'PCR_PCT': 0.0, 'CE_CON': 0.0, 'PE_CON': 0.0})
        except Exception:
            missing_stock_names.append(s_name)

    if snapshot_changed and client:
        try:
            ss = client.open("Fyers_EOD_Data")
            ws2 = ss.worksheet("Sheet2")
            ws2.update_cell(1, 2, json.dumps(snap_950))
        except Exception:
            pass

    st.session_state.get_live_dump = live_ltp_data
    st.session_state.missing_stocks_list = missing_stock_names 

    if client and not baseline_prices and scan_time_ist.time() >= datetime.time(9, 15) and live_ltp_data:
        try:
            ss = client.open("Fyers_EOD_Data")
            ws2 = ss.worksheet("Sheet2")
            locked_live_data = {k: round(float(v), 2) for k, v in live_ltp_data.items()}
            json_str = json.dumps(locked_live_data)
            b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
            chunks = [b64_str[i:i+40000] for i in range(0, len(b64_str), 40000)]
            ws2.batch_clear(["A2:A100"])
            clist2 = ws2.range(f'A2:A{len(chunks)+1}')
            for i, cell in enumerate(clist2): cell.value = chunks[i]
            ws2.update_cell(1, 1, f"LAST_SAVED_DATE: {date_str}")
            ws2.update_cells(clist2)
        except Exception:
            pass

    if new_csv_rows:
        new_df = pd.DataFrame(new_csv_rows)[['Date', 'Symbol', 'Time', 'LTP', 'VOL PCR', 'OPT PCR', 'VOL CPR']]
        if not os.path.isfile(HISTORY_FILE): new_df.to_csv(HISTORY_FILE, index=False)
        else: new_df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

    return final_list, scan_time_ist.timestamp()

# ==========================================
# 6. SIDEBAR SETUP & LOGIN
# ==========================================
auth_code = None
token = None
cached_result = None
last_scan_timestamp = time.time()

if app_mode == "💻 Master (Data Fetcher)":
    st.sidebar.header("🔑 Fyers Quick Login")
    saved_token = None
    if os.path.exists(TOKEN_STORE_FILE):
        try:
            td = json.load(open(TOKEN_STORE_FILE))
            if td.get("date") == today_str: saved_token = td.get("token")
        except Exception:
            pass

    if saved_token:
        auth_code = "AUTO_LOGGED_IN"
        st.sidebar.success("🚀 Master Connected via Saved Token!")
        if st.sidebar.button("🔄 Force Logout / Clear Token"):
            if os.path.exists(TOKEN_STORE_FILE): os.remove(TOKEN_STORE_FILE)
            for k in ['cached_data', 'auth_box']: 
                if k in st.session_state: del st.session_state[k]
            st.rerun()
    else:
        magic_url = f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&response_type=code&state=deepak"
        st.sidebar.markdown(f"### [👉 Step 1: Click to Get Code]({magic_url})")
        raw_code = st.sidebar.text_input("Step 2: Paste Full Google Link Here:", type="password", key="auth_box")
        if raw_code:
            if "auth_code=" in raw_code: auth_code = raw_code.split("auth_code=")[1].split("&")[0]
            elif "code=" in raw_code: auth_code = raw_code.split("code=")[1].split("&")[0]
            else: auth_code = raw_code

    st.sidebar.markdown("---")
    st.sidebar.header("💾 Baseline Save Options")

    def save_eod_data():
        if 'get_live_dump' in st.session_state:
            try:
                live_data = st.session_state.get_live_dump
                if live_data:
                    client = get_gspread_client()
                    if not client: return False
                    ss = client.open("Fyers_EOD_Data")
                    ws2 = ss.worksheet("Sheet2")
                    locked_live_data = {k: round(float(v), 2) for k, v in live_data.items()}
                    json_str = json.dumps(locked_live_data)
                    b64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
                    chunks = [b64_str[i:i+40000] for i in range(0, len(b64_str), 40000)]
                    ws2.batch_clear(["A2:A100"])
                    clist2 = ws2.range(f'A2:A{len(chunks)+1}')
                    for i, cell in enumerate(clist2): cell.value = chunks[i]
                    ws2.update_cell(1, 1, f"LAST_SAVED_DATE: {today_str}")
                    ws2.update_cells(clist2)
                    return True
            except Exception:
                pass
        return False

    if st.sidebar.button("Manual Baseline Save"):
        if save_eod_data(): 
            st.sidebar.success("Baseline Saved Successfully!")
            st.cache_data.clear() 

    if auth_code:
        if auth_code != "AUTO_LOGGED_IN":
            try:
                session = fyersModel.SessionModel(client_id=APP_ID, secret_key=SECRET_ID, redirect_uri=REDIRECT_URI, response_type="code", grant_type="authorization_code")
                session.set_token(auth_code)
                response = session.generate_token()
                if isinstance(response, dict) and "access_token" in response:
                    token = response['access_token']
                    json.dump({"date": today_str, "token": token}, open(TOKEN_STORE_FILE, 'w'))
                    st.sidebar.success("✅ Token Saved! Page refreshing...")
                    time.sleep(1) 
                    st.rerun() 
                else: st.sidebar.error(f"❌ Auth Code purana hai ya URL galat hai.")
            except Exception:
                st.sidebar.error(f"❌ Error: Kripya dobara link par click karke naya URL layein.")
        else:
            token = saved_token

        if token:
            cached_result, last_scan_timestamp = run_master_scan(token, today_str, int(time.time()))

            if cached_result is not None:
                st.session_state.cached_data = cached_result
                st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
                
                try:
                    shared_pack = {"time": last_scan_timestamp, "data": cached_result, "missing": st.session_state.get('missing_stocks_list', [])}
                    json.dump(shared_pack, open(SHARED_LIVE_DATA_FILE, 'w'))
                except Exception:
                    pass
            else:
                if 'cached_data' not in st.session_state: st.session_state.cached_data = []
    else:
        st.info("👈 Please enter Auth Code in sidebar to start Master Server.")

elif app_mode == "📱 Viewer (Mobile Client)":
    st.sidebar.success("🟢 Viewer Mode Active!\n\nNo Fyers Login needed. Receiving data from Master.")
    if os.path.exists(SHARED_LIVE_DATA_FILE):
        try:
            shared_pack = json.load(open(SHARED_LIVE_DATA_FILE, 'r'))
            st.session_state.cached_data = shared_pack.get("data", [])
            last_scan_timestamp = shared_pack.get("time", time.time())
            st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
            st.session_state.missing_stocks_list = shared_pack.get("missing", [])
        except Exception:
            pass
    else:
        st.info("⏳ Waiting for Master Server to fetch data. Master ko on rakhein...")
        st.session_state.cached_data = []

# ==========================================
# 7. APP RENDERING (UI & TABLES)
# ==========================================
if 'cached_data' in st.session_state and len(st.session_state.cached_data) > 0:
    
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

    col_menu, col_toggle, col_timer = st.columns([4, 3, 3], vertical_alignment="center")
    
    with col_menu:
        selected_tab = st.radio("Menu", ["📊 Dashboard", "📈 CHART"], horizontal=True, label_visibility="collapsed")
        
    with col_toggle:
        show_pct = st.toggle("📊 Show Checker (%)", value=True)
        
    with col_timer:
        if app_mode == "💻 Master (Data Fetcher)":
            js_code = f"""
            <div style="text-align: right; color: #FF4D4D; font-size: 13px; font-weight: bold; font-family: 'Segoe UI', Arial, sans-serif; padding-top: 5px;">
                ⏱️ Next Fetch: <span id="clock"></span>
            </div>
            <script>
                var timeLeft = 300;
                var clockTimer = setInterval(function() {{
                    if(timeLeft <= 0) {{
                        clearInterval(clockTimer);
                        document.getElementById('clock').innerHTML = "RELOADING...";
                        window.top.location.reload(true);
                    }} else {{
                        timeLeft--;
                        var m = Math.floor(timeLeft / 60);
                        var s = timeLeft % 60;
                        document.getElementById('clock').innerHTML = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
                    }}
                }}, 1000);
            </script>
            """
            components.html(js_code, height=40)
        else:
            ref_time = st.session_state.last_api_call.strftime('%H:%M:%S') if 'last_api_call' in st.session_state else "Waiting..."
            st.markdown(f"<div style='text-align: right; color: #888888; font-size: 12px; font-weight: bold; margin-top: 8px;'>⏱️ Last: {ref_time}</div>", unsafe_allow_html=True)

    st.divider()

    if selected_tab == "📊 Dashboard":
        
        if 'missing_stocks_list' in st.session_state and len(st.session_state.missing_stocks_list) > 0:
            missing_str = ", ".join(st.session_state.missing_stocks_list)
            st.warning(f"⚠️ Fyers API ne in {len(st.session_state.missing_stocks_list)} stocks ka data nahi diya: **{missing_str}**")
        
        checker_fmt = '{:+.2f}%' if show_pct else '{:+.2f}'
        
        format_dict = {
            'VOL PCR': '{:.2f}', 
            'OPTION PCR': '{:.2f}',
            'VOL CPR': '{:.2f}', 
            'LTP': '{:.2f}', 
            'LTP CHANGE': '{:.2f}', 
            'CHANGE%': '{:+.2f}%', 
            'CE_CONTRACT': '{:+.1f}%', 
            'PE_CONTRACT': '{:+.1f}%',
            'PCR CHECKER': checker_fmt, 
            'VOL CHECKER': checker_fmt
        }
        
        df = pd.DataFrame(st.session_state.cached_data)
        
        if not df.empty:
            df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
            df = df.sort_values(by='Conv_Rank', ascending=False)
            
            df['VOL CHECKER'] = df['VOL_PCT'] if show_pct else df['VOL_ABS']
            df['PCR CHECKER'] = df['PCR_PCT'] if show_pct else df['PCR_ABS']
            
            df = df[['SYMS', 'OPEN_STATUS', 'V_PCR', 'O_PCR', 'V_CPR', 'LTP_CH', 'CHG_%', 'LTP', 'CE_CON', 'PE_CON', 'PCR CHECKER', 'VOL CHECKER']]
            
            df = df.rename(columns={
                'SYMS': 'SYMBOL', 
                'OPEN_STATUS': 'OPENING',
                'V_PCR': 'VOL PCR',
                'O_PCR': 'OPTION PCR',
                'V_CPR': 'VOL CPR', 
                'LTP_CH': 'LTP CHANGE', 
                'CHG_%': 'CHANGE%', 
                'LTP': 'LTP', 
                'CE_CON': 'CE_CONTRACT', 
                'PE_CON': 'PE_CONTRACT'
            })

            styled_df = (df.style.hide(axis="index")
                         .set_properties(**{'text-align': 'center'})
                         .format(format_dict)
                         .set_table_styles(header_styles)
                         .map(style_indicators, subset=['OPENING', 'LTP CHANGE', 'CHANGE%', 'CE_CONTRACT', 'PE_CONTRACT', 'VOL CHECKER', 'PCR CHECKER'])
                         .map(style_pcr_columns, subset=['VOL PCR', 'OPTION PCR', 'VOL CPR']))

            st.dataframe(
                styled_df, 
                use_container_width=True, 
                height=800, 
                hide_index=True
            )

    elif selected_tab == "📈 CHART":
        col_c1, col_c2, col_c3 = st.columns([1.5, 1.5, 1.5])
        with col_c1: sel_stock = st.selectbox("Select Stock for Trend:", raw_symbols, index=0, key="c_stock", label_visibility="collapsed")
        with col_c2: chart_mode = st.radio("SWITCH CHART VIEW:", ["Vol CPR", "Option PCR"], horizontal=True, label_visibility="collapsed")
        
        default_device_index = 0 if app_mode == "💻 Master (Data Fetcher)" else 1
        with col_c3: device_mode = st.radio("Screen Layout:", ["💻 Laptop", "📱 Mobile"], horizontal=True, index=default_device_index, label_visibility="collapsed")

        if device_mode == "💻 Laptop":
            c_main_h = 480      
            c_iframe_h = 550    
        else:
            c_main_h = 350      
            c_iframe_h = 420    

        if os.path.exists(HISTORY_FILE):
            try:
                hist_df = pd.read_csv(HISTORY_FILE)
                if not hist_df.empty and 'Date' in hist_df.columns:
                    df_sym = hist_df[(hist_df['Date'] == today_str) & (hist_df['Symbol'] == sel_stock)].copy()
                    if not df_sym.empty:
                        df_sym = df_sym.sort_values(by='Time')
                        
                        target_col = 'VOL CPR' if chart_mode == "Vol CPR" else 'OPT PCR'
                        indicator_color = "#FF4D4D" if chart_mode == "Vol CPR" else "#00BFFF"
                        
                        time_list = df_sym['Time'].tolist()
                        indicator_list = df_sym[target_col].tolist()
                        ltp_list = df_sym['LTP'].tolist()

                        # 🔥 100% NATIVE HTML RANGE SLIDER - ONE DOT, NIFTYTRADER STYLE 🔥
                        apex_html = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
                            <style> 
                                body {{ margin: 0; padding: 0; background-color: transparent; font-family: 'Segoe UI', Arial, sans-serif; position: relative; overflow: hidden; }} 
                                
                                /* Hide Native Buggy Toolbar */
                                .apexcharts-toolbar {{ display: none !important; }}
                                
                                /* 🚀 Custom Solid Reset Button (Left Aligned) 🚀 */
                                #custom-reset-btn {{
                                    position: absolute; top: 10px; left: 15px; z-index: 9999;
                                    background-color: #f1f1f1; border: 1px solid #ccc; border-radius: 4px;
                                    padding: 4px 8px; font-size: 12px; font-weight: bold; color: #333;
                                    cursor: pointer; box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
                                }}
                                #custom-reset-btn:hover {{ background-color: #e0e0e0; }}

                                /* 🔥 NIFTYTRADER STYLE NATIVE HTML SLIDER CSS 🔥 */
                                .slider-wrapper {{
                                    padding: 10px 20px;
                                    margin-top: -5px;
                                }}
                                input[type=range] {{
                                    -webkit-appearance: none;
                                    width: 100%;
                                    height: 6px;
                                    background: #e0e0e0;
                                    border-radius: 5px;
                                    outline: none;
                                }}
                                input[type=range]::-webkit-slider-thumb {{
                                    -webkit-appearance: none;
                                    appearance: none;
                                    width: 24px;
                                    height: 24px;
                                    border-radius: 50%;
                                    background: #2962FF; /* Single big blue dot */
                                    cursor: pointer;
                                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                                }}
                                input[type=range]::-moz-range-thumb {{
                                    width: 24px;
                                    height: 24px;
                                    border-radius: 50%;
                                    background: #2962FF;
                                    cursor: pointer;
                                    box-shadow: 0 2px 5px rgba(0,0,0,0.3);
                                    border: none;
                                }}
                            </style>
                        </head>
                        <body>
                            <button id="custom-reset-btn">🔄 Reset</button>
                            
                            <div id="chart-main"></div>
                            
                            <div class="slider-wrapper">
                                <input type="range" id="native-slider" min="0" value="0">
                            </div>
                            
                            <script>
                                var dataIndicator = {json.dumps(indicator_list)};
                                var dataLTP = {json.dumps(ltp_list)};
                                var timeCats = {json.dumps(time_list)};
                                
                                var optionsMain = {{
                                    series: [{{
                                        name: '{chart_mode}',
                                        type: 'area',
                                        data: dataIndicator
                                    }}, {{
                                        name: 'LTP',
                                        type: 'line',
                                        data: dataLTP
                                    }}],
                                    chart: {{
                                        id: 'mainChart',
                                        height: {c_main_h}, 
                                        type: 'line',
                                        toolbar: {{ show: false }},
                                        zoom: {{ enabled: false }}, 
                                        selection: {{ enabled: false }},
                                        animations: {{ enabled: false }}
                                    }},
                                    colors: ['{indicator_color}', '#00CC66'],
                                    stroke: {{ curve: 'smooth', width: [2, 2] }}, 
                                    fill: {{
                                        type: ['gradient', 'solid'],
                                        gradient: {{ shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }}
                                    }},
                                    dataLabels: {{ enabled: false }},
                                    xaxis: {{
                                        categories: timeCats,
                                        tickAmount: 10,
                                        labels: {{ style: {{ colors: '#888' }} }},
                                        tooltip: {{ enabled: false }}
                                    }},
                                    yaxis: [
                                        {{
                                            title: {{ text: '{chart_mode}', style: {{ color: '{indicator_color}' }} }},
                                            labels: {{ style: {{ colors: '{indicator_color}' }} }},
                                        }},
                                        {{
                                            opposite: true,
                                            title: {{ text: 'LTP', style: {{ color: '#00CC66' }} }},
                                            labels: {{ style: {{ colors: '#00CC66' }} }},
                                        }}
                                    ],
                                    tooltip: {{
                                        shared: true,
                                        intersect: false,
                                        y: {{ formatter: function (y) {{ if (typeof y !== "undefined") {{ return y.toFixed(2); }} return y; }} }}
                                    }},
                                    legend: {{ position: 'top', horizontalAlign: 'right' }}
                                }};

                                var chartMain = new ApexCharts(document.querySelector("#chart-main"), optionsMain);
                                chartMain.render();

                                /* 🔥 NATIVE SLIDER DYNAMIC LOGIC 🔥 */
                                var totalPoints = timeCats.length;
                                
                                // Make windowSize small enough so slider always has room to move even with less data
                                var windowSize = Math.max(3, Math.floor(totalPoints / 3)); 
                                if (totalPoints <= 3) {{
                                    windowSize = totalPoints;
                                }}
                                
                                var slider = document.getElementById('native-slider');
                                var maxVal = totalPoints - windowSize;
                                slider.max = maxVal > 0 ? maxVal : 0;
                                slider.value = slider.max; // Start at the rightmost edge (latest data)
                                
                                // Color the track dynamically (Blue on left, Grey on right)
                                function updateSliderUI(el) {{
                                    var percentage = slider.max > 0 ? (el.value / slider.max) * 100 : 100;
                                    el.style.background = 'linear-gradient(to right, #2962FF ' + percentage + '%, #e0e0e0 ' + percentage + '%)';
                                }}
                                
                                // Pan chart when sliding
                                slider.addEventListener('input', function(e) {{
                                    updateSliderUI(e.target);
                                    var startIdx = parseInt(e.target.value);
                                    var endIdx = startIdx + windowSize - 1;
                                    if(endIdx >= totalPoints) endIdx = totalPoints - 1;
                                    
                                    chartMain.zoomX(timeCats[startIdx], timeCats[endIdx]);
                                }});
                                
                                // Initial setup
                                updateSliderUI(slider);
                                setTimeout(function() {{
                                    if(maxVal > 0) {{
                                        chartMain.zoomX(timeCats[parseInt(slider.value)], timeCats[parseInt(slider.value) + windowSize - 1]);
                                    }}
                                }}, 500);

                                /* Reset button shows all data */
                                document.getElementById('custom-reset-btn').addEventListener('click', function() {{
                                    chartMain.zoomX(timeCats[0], timeCats[timeCats.length - 1]);
                                    slider.value = slider.max; // Visually put dot at the end
                                    updateSliderUI(slider);
                                }});
                            </script>
                        </body>
                        </html>
                        """
                        components.html(apex_html, height=c_iframe_h)
                    else: st.info(f"⏳ Waiting for Market Data for {sel_stock}. Today's data starts logging at 9:15 AM.")
                else: st.info("⏳ Market data hasn't started logging yet today.")
            except Exception as e:
                st.error(f"Chart Load Error: {e}")
        else:
            st.info("⏳ Chart History file is being prepared... Market hours me data yahan dikhega.")
