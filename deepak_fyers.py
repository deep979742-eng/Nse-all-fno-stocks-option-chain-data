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
            
            # A. NEXT MORNING AUTO-ROLLOVER LOGIC
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

            # B. LOAD BASELINE FROM TAB 1
            try:
                col_vals = ws1.col_values(1)
                if col_vals:
                    full_str = "".join(col_vals)
                    decoded_str = base64.b64decode(full_str).decode('utf-8')
                    loaded_prices = json.loads(decoded_str)
                    for k, v in loaded_prices.items():
                        baseline_prices[k] = round(float(v), 2)
            except: pass

            # C. LOAD 9:50 AM SNAPSHOT
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
            open_p = float(v.get('open_price', 0))
            float_c = float(v.get('prev_close_price', 0))
            open_status = "NA" if open_p == 0 or float_c == 0 else "Gap Up 🔼" if open_p > float_c else "Gap Down 🔽" if open_p < float_c else "Same ➖"

            if oc and oc.get('s') == 'ok' and 'optionsChain' in oc['data']:
                chain = oc['data']['optionsChain']
                
                # 🚀 OPTIMIZED AND ERROR-FREE OI/VOLUME LOGIC 🚀
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
                        
                    # Live LTP Recording
                    lp_str = round(float(s.get('ltp', 0)), 2)
                    if lp_str > 0: 
                        live_ltp_data[sym_str] = lp_str

                o_pcr = calc_opt_pcr(c_oi, p_oi)
                v_cpr = calc_vol_cpr(c_v, p_v)
                v_pcr = calc_vol_pcr(c_v, p_v)

                # DEEPAK BHAI'S SLN ACADEMY PERCENTAGE FORMULA
                if scan_time_ist.time() < datetime.time(9, 50):
                    pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                else:
                    if s_name not in snap_950:
                        snap_950[s_name] = {'pcr': v_pcr, 'vol_cpr': v_cpr}
                        snapshot_changed = True
                        pcr_abs, vol_abs, pcr_pct, vol_pct = 0.0, 0.0, 0.0, 0.0
                    else:
                        base = snap_950[s_name]
                        pcr_abs = v_pcr - base['pcr']
                        vol_abs = v_cpr - base['vol_cpr']
                        
                        def ratio_to_pct(r): return (r / (r + 1.0)) * 100.0 if r > 0 else 0.0
                        
                        pcr_pct = ratio_to_pct(v_pcr) - ratio_to_pct(base['pcr'])
                        vol_pct = ratio_to_pct(v_cpr) - ratio_to_pct(base['vol_cpr'])

                # ACCURATE CE/PE LOGIC
                def get_conv(opt_type_val):
                    strikes = [stk for stk in chain if stk.get('option_type') == opt_type_val.upper() or str(stk.get('symbol', '')).endswith(opt_type_val.upper())]
                    tot_p, tot_m = 0, 0
                    for stk in strikes:
                        sym = str(stk.get('symbol', ''))
                        lp = round(float(stk.get('ltp', 0)), 2) 
                        
                        if lp == 0 or sym not in baseline_prices: 
                            continue
                            
                        base_p = baseline_prices[sym]
                        diff = round(lp - base_p, 2)
                        
                        if diff > 0.00: tot_p += 1 
                        elif diff < 0.00: tot_m += 1 

                    act = tot_p + tot_m
                    if act == 0: return 0.0
                    return round((tot_p / act) * 100, 1) if tot_p >= tot_m else -round((tot_m / act) * 100, 1)
                
                final_list.append({
                    'SYMS': s_name, 'OPEN_STATUS': open_status, 'V_PCR': v_pcr, 'O_PCR': o_pcr, 'V_CPR': v_cpr, 
                    'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': spot_ltp,
                    'VOL_ABS': round(vol_abs, 2), 'PCR_ABS': round(pcr_abs, 2), 
                    'VOL_PCT': round(vol_pct, 1), 'PCR_PCT': round(pcr_pct, 1),
                    'CE_CON': get_conv('CE'), 'PE_CON': get_conv('PE')
                })

                if datetime.time(9, 15) <= scan_time_ist.time() <= datetime.time(15, 30):
                    new_csv_rows.append({'Date': date_str, 'Symbol': s_name, 'Time': time_str, 'LTP': spot_ltp, 'VOL PCR': v_pcr, 'OPT PCR': o_pcr, 'VOL CPR': v_cpr})
            else:
                final_list.append({'SYMS': s_name + " (NA)", 'OPEN_STATUS': open_status, 'V_PCR': 0.0, 'O_PCR': 0.0, 'V_CPR': 0.0, 'LTP_CH': float(v.get('ch', 0)), 'CHG_%': float(v.get('chp', 0)), 'LTP': spot_ltp, 'VOL_ABS': 0.0, 'PCR_ABS': 0.0, 'VOL_PCT': 0.0, 'PCR_PCT': 0.0, 'CE_CON': 0.0, 'PE_CON': 0.0})

    if snapshot_changed and client:
        try:
            ss = client.open("Fyers_EOD_Data")
            ws2 = ss.worksheet("Sheet2")
            ws2.update_cell(1, 2, json.dumps(snap_950))
        except: pass

    st.session_state.get_live_dump = live_ltp_data

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
        except: pass
    return False

if st.sidebar.button("Manual Save Data"):
    if save_eod_data(): st.sidebar.success("Sheet Saved Successfully!")

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
        
        # BRAHMASTRA AUTO LOCK
        if datetime.time(8, 0) <= now_ist.time() < datetime.time(9, 15):
            last_save = open(AUTO_SAVE_FILE, "r").read().strip() if os.path.exists(AUTO_SAVE_FILE) else ""
            if last_save != today_str:
                if save_eod_data(): open(AUTO_SAVE_FILE, "w").write(today_str)
    else:
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

        # 🚀 ONLY 2 TABS NOW 🚀
        tab1, tab2 = st.tabs(["📊 Dashboard", "📈 TREND CHART"])
        
        with tab1:
            # 🚀 ONLY TOGGLE LEFT (SEARCH BAR REMOVED) 🚀
            show_pct = st.toggle("📊 Show Checker Data in Percentage (%)", value=True)
            
            checker_fmt = '{:+.1f}%' if show_pct else '{:+.2f}'
            format_dict = {'VOL PCR': '{:.2f}', 'OPTION PCR': '{:.2f}', 'VOL CPR': '{:.2f}', 'LTP': '{:.2f}', 'LTP CHANGE': '{:.2f}', 'CHANGE%': '{:+.2f}%', 'VOL CHECKER': checker_fmt, 'PCR CHECKER': checker_fmt, 'CE_CONTRACT': '{:+.1f}%', 'PE_CONTRACT': '{:+.1f}%'}
            
            df = pd.DataFrame(st.session_state.cached_data)
            
            if not df.empty:
                df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
                df = df.sort_values(by='Conv_Rank', ascending=False).drop(columns=['Conv_Rank']) 
                df['VOL CHECKER'] = df['VOL_PCT'] if show_pct else df['VOL_ABS']
                df['PCR CHECKER'] = df['PCR_PCT'] if show_pct else df['PCR_ABS']
                df = df.drop(columns=['VOL_ABS', 'PCR_ABS', 'VOL_PCT', 'PCR_PCT'])
                df = df.rename(columns={'SYMS': 'SYMBOL', 'OPEN_STATUS': 'OPENING', 'V_PCR': 'VOL PCR', 'O_PCR': 'OPTION PCR', 'V_CPR': 'VOL CPR', 'LTP_CH': 'LTP CHANGE', 'CHG_%': 'CHANGE%', 'LTP': 'LTP', 'CE_CON': 'CE_CONTRACT', 'PE_CON': 'PE_CONTRACT'})

                styled_df = (df.style.set_properties(**{'text-align': 'center'}).format(format_dict).set_table_styles(header_styles)
                             .map(style_indicators, subset=['OPENING', 'LTP CHANGE', 'CHANGE%', 'CE_CONTRACT', 'PE_CONTRACT', 'VOL CHECKER', 'PCR CHECKER'])
                             .map(style_pcr_columns, subset=['VOL PCR', 'OPTION PCR', 'VOL CPR']))

                st.dataframe(styled_df, use_container_width=True, height=800, hide_index=True)

        with tab2:
            st.markdown("### 📈 SIR TREND CHART")
            col_c1, col_c2 = st.columns([2, 2])
            with col_c1: sel_stock = st.selectbox("Select Stock for Trend:", raw_symbols, index=0, key="c_stock")
            with col_c2: 
                chart_mode = st.radio("SWITCH CHART VIEW:", ["Vol CPR", "Option PCR"], horizontal=True)

            if os.path.exists(HISTORY_FILE):
                try:
                    hist_df = pd.read_csv(HISTORY_FILE)
                    
                    if not hist_df.empty and 'Date' in hist_df.columns:
                        df_sym = hist_df[(hist_df['Date'] == today_str) & (hist_df['Symbol'] == sel_stock)].copy()
                        
                        if not df_sym.empty:
                            df_sym = df_sym.sort_values(by='Time')
                            df_sym['Datetime'] = pd.to_datetime(df_sym['Date'] + ' ' + df_sym['Time'])
                            
                            target_col = 'VOL CPR' if chart_mode == "Vol CPR" else 'OPT PCR'
                            line_color = "#FF4D4D" if chart_mode == "Vol CPR" else "#00BFFF" 
                            
                            fig = make_subplots(specs=[[{"secondary_y": True}]])
                            
                            fig.add_trace(go.Scatter(
                                x=df_sym['Datetime'], y=df_sym[target_col], name=f"{chart_mode}", 
                                line=dict(color=line_color, width=3, shape="spline"), mode="lines"
                            ), secondary_y=False)
                            
                            fig.add_trace(go.Scatter(
                                x=df_sym['Datetime'], y=df_sym['LTP'], name="Stock LTP", 
                                line=dict(color="#00CC66", width=3, shape="spline"), mode="lines"
                            ), secondary_y=True)

                            market_open_time = pd.to_datetime(f"{today_str} 09:15:00")
                            actual_first_data_time = df_sym['Datetime'].min()
                            dynamic_start_time = max(actual_first_data_time, market_open_time)
                            fixed_end_time = pd.to_datetime(f"{today_str} 15:30:00")

                            fig.update_layout(
                                template="plotly_white", 
                                hovermode="x unified",
                                height=600,
                                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", 
                                xaxis=dict(
                                    rangeslider=dict(visible=False), 
                                    type="date", 
                                    range=[dynamic_start_time, fixed_end_time], 
                                    gridcolor="#E5E5E5", 
                                    color="black"
                                ),
                                yaxis=dict(
                                    title=dict(text=f"{chart_mode} Scale", font=dict(color=line_color)), 
                                    tickfont=dict(color=line_color), 
                                    gridcolor="#E5E5E5",
                                    autorange=True 
                                ),
                                yaxis2=dict(
                                    title=dict(text="LTP Price Scale", font=dict(color="#00CC66")), 
                                    tickfont=dict(color="#00CC66"), 
                                    showgrid=False,
                                    autorange=True 
                                ),
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="black"))
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else: st.info(f"⏳ Waiting for Market Data for {sel_stock}. Today's data starts logging at 9:15 AM.")
                    else: st.info("⏳ Market data hasn't started logging yet today.")
                except Exception as e:
                    st.error(f"Chart Load Error: {e}")
            else:
                st.info("⏳ Chart History file is being prepared... Market hours me data yahan dikhega.")

    # 🚀 FIXED CLOCK BOUNDARY AUTO-UPDATE LOOP 🚀
    now_refresh = datetime.datetime.now(IST)
    current_min = now_refresh.minute
    current_sec = now_refresh.second

    next_mult_5 = ((current_min // 5) + 1) * 5
    mins_wait = next_mult_5 - current_min
    secs_wait = (mins_wait * 60) - current_sec + 5

    if secs_wait <= 0 or secs_wait > 305:
        secs_wait = 300

    time.sleep(secs_wait)
    st.rerun()
else:
    st.info("👈 Please enter Auth Code in sidebar.")
