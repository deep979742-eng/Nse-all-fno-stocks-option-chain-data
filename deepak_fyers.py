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

# CSS - FULLY MOBILE RESPONSIVE
css_str = """<style>
[data-testid='stAppViewContainer'], [data-testid='stAppViewBlockContainer'], [data-testid='stHeader'], [data-testid='stSidebar'], .stApp, .stApp > div { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stDataFrame'], [data-testid='stTabs'] { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stStatusWidget'] { visibility: hidden !important; display: none !important; } 
.block-container { padding-top: 3.5rem !important; padding-bottom: 0rem !important; padding-left: 1rem !important; padding-right: 1rem !important; } 
[data-testid='stDataFrameTable'] > thead > tr { background-color: darkblue !important; } 
[data-testid='stDataFrameTable'] > thead > tr > th { 
    background-color: darkblue !important; color: white !important; font-weight: bold !important; text-align: center !important; 
    writing-mode: vertical-rl !important; transform: rotate(180deg) !important; white-space: nowrap !important; padding: 8px 4px !important; height: 120px !important;
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
# 4. APP MODE SELECTION & DATA SCANNER
# ==========================================
st.sidebar.markdown("### 📱 APP MODE")
app_mode = st.sidebar.radio("Select Device Role:", ["💻 Master (Data Fetcher)", "📱 Viewer (Mobile Client)"])
st.sidebar.markdown("---")

if app_mode == "📱 Viewer (Mobile Client)":
    st_autorefresh(interval=30000, limit=100000, key="viewer_fetch_loop")
elif app_mode == "💻 Master (Data Fetcher)":
    st_autorefresh(interval=310000, limit=100000, key="master_fetch_loop")

@st.cache_data(show_spinner=False)
def run_master_scan(token, date_str, cycle_id):
    fyers = fyersModel.FyersModel(client_id=APP_ID, is_async=False, token=token, log_path="")
    scan_time_ist = datetime.datetime.now(IST)
    time_str = scan_time_ist.strftime('%H:%M')
    
    baseline_prices = {}
    snap_950 = {}
    snapshot_changed = False
    
    # Logic to fetch data from GSheet/Fyers... (Skipping long detail for clarity, assuming logic exists)
    # [Rest of your scan logic remains exactly as per your working structure]
    # ...
    return final_list, scan_time_ist.timestamp()

# ==========================================
# 6. SIDEBAR SETUP & LOGIN (Retaining your exact logic)
# ==========================================
# [Your Sidebar/Login logic here...]

# ==========================================
# 7. APP RENDERING (THE ENGINE)
# ==========================================
if 'cached_data' in st.session_state and len(st.session_state.cached_data) > 0:
    # [Table rendering logic...]
    
    if selected_tab == "📈 CHART":
        # ... [Your Chart/Iframe logic block]
        # This is where the Reset Button and Native Refresh logic resides
        apex_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
            <style> 
                /* Your custom CSS/JS for Slider/Zoom/Refresh goes here */
            </style>
        </head>
        <body>
            <button type="button" id="reset-btn" onclick="resetChart()">🔄 Reset</button>
            <div id="chart-main"></div>
            <div id="chart-slider" style="margin-top: -10px;"></div>
            <script>
                /* 🚀 NATIVE RELOAD ENGINE 🚀 */
                var timeLeft = 308;
                setInterval(function() {{
                    if(timeLeft <= 0) {{
                        if (window.parent) window.parent.location.reload(true);
                    }}
                    timeLeft--;
                }}, 1000);
            </script>
        </body>
        </html>
        """
        components.html(apex_html, height=500)
