import streamlit as st
import pandas as pd
import datetime
import time
import json
import requests
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components  

# ==========================================
# PAGE CONFIG 
# ==========================================
st.set_page_config(page_title="F&O LIVE Dashboard", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 1. 🔥 THE "HARD RESET" JAVASCRIPT HACK 🔥
# ==========================================
components.html(
    """
    <script>
    const targetNode = window.parent.document.body;
    const config = { childList: true, subtree: true };
    const callback = function(mutationsList, observer) {
        const deployBtn = window.parent.document.querySelector('[data-testid="stAppDeployButton"]');
        if (deployBtn) { deployBtn.style.display = 'none'; deployBtn.style.visibility = 'hidden'; }
        
        const toolbar = window.parent.document.querySelector('[data-testid="stToolbar"]');
        if (toolbar) { toolbar.style.display = 'none'; }
        
        const header = window.parent.document.querySelector('header');
        if (header) { header.style.display = 'none'; }
    };
    const observer = new MutationObserver(callback);
    observer.observe(targetNode, config);
    callback();
    </script>
    """,
    height=0,
    width=0
)

# ==========================================
# 2. UI CSS (ULTRA COMPACT & ZERO TOP SPACE)
# ==========================================
css_str = """
<style>
header, footer, [data-testid="stAppDeployButton"], [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; opacity: 0 !important; }

.block-container { 
    padding-top: 1rem !important; 
    padding-bottom: 0rem !important; 
    padding-left: 0.5rem !important; 
    padding-right: 0.5rem !important; 
    margin-top: -20px !important; 
} 

[data-testid='stAppViewContainer'], [data-testid='stAppViewBlockContainer'], .stApp { opacity: 1 !important; filter: none !important; transition: none !important; } 
[data-testid='stStatusWidget'], [data-testid="stConnectionStatus"], [data-testid="stModal"], div[role="dialog"], [data-baseweb="modal"] { display: none !important; visibility: hidden !important; opacity: 0 !important; } 
[data-testid="stRadio"], [data-testid="stToggle"], .stRadio, .stToggle { opacity: 1 !important; filter: none !important; transition: none !important; }
div[data-testid="stVerticalBlock"] > div { opacity: 1 !important; filter: none !important; }

/* EQUAL SIZE BUTTONS */
.stRadio div[role='radiogroup'] { gap: 4px; width: 100%; flex-wrap: nowrap !important; }
.stRadio div[role='radiogroup'] > label > div:first-child { display: none !important; } 
.stRadio div[role='radiogroup'] > label { 
    flex: 1 1 0px !important; 
    border: 1px solid rgba(128, 128, 128, 0.4) !important; 
    border-radius: 6px !important; 
    background-color: rgba(128, 128, 128, 0.1) !important; 
    cursor: pointer !important; 
    display: flex !important; 
    align-items: center !important; 
    justify-content: center !important; 
    font-weight: 600 !important; 
    margin-top: 0px; 
    white-space: nowrap !important; 
    height: 36px !important; 
    padding: 0 4px !important;
    overflow: hidden !important;
}
.stRadio div[role='radiogroup'] > label > div { white-space: nowrap !important; }
.stRadio div[role='radiogroup'] > label:hover { background-color: rgba(128, 128, 128, 0.2) !important; }

/* Time Box - Width fixed to content size */
.time-box { border: 1px solid rgba(128, 128, 128, 0.4); padding: 0px 15px; border-radius: 6px; background-color: rgba(128, 128, 128, 0.1); text-align: center; font-weight: bold; font-size: 13px; color: #00BFFF; margin: 0; display: flex; align-items: center; justify-content: center; height: 36px; white-space: nowrap; width: max-content; }

/* Toggle Box styling for "SHOW %" */
div[data-testid="stToggle"] label { flex-direction: row-reverse !important; justify-content: flex-end !important; gap: 8px !important; margin-top: 5px; }
div[data-testid="stToggle"] label p { font-weight: 700 !important; font-size: 14px !important; color: #FF4B4B !important; }

/* MOBILE STRICT 1-LINE LAYOUT */
@media (max-width: 768px) { 
    .block-container { padding-top: 0.5rem !important; margin-top: -30px !important; } 
    .stRadio div[role='radiogroup'] > label { font-size: 12px !important; height: 34px !important; padding: 0 2px !important; }
    .time-box { font-size: 11px !important; height: 34px !important; padding: 0 10px !important; }
    div[data-testid="stColumns"] { display: flex !important; flex-direction: row !important; align-items: center !important; flex-wrap: nowrap !important; gap: 4px !important; }
    div[data-testid="stColumns"] > div[data-testid="column"] { width: auto !important; min-width: 0 !important; padding: 0 !important; }
    div[data-testid="stColumns"] > div:nth-child(3) { display: none !important; } /* Hides empty space column on mobile */
    .stToggle { height: 34px !important; display: flex !important; align-items: center !important; justify-content: center !important; margin: 0 !important; padding: 0 !important; }
    div[data-testid="stToggle"] label p { font-size: 12px !important; }
}
</style>
"""
st.markdown(css_str, unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
today_str = datetime.datetime.now(IST).strftime("%Y-%m-%d")
today_prefix = today_str.replace("-", "")

FIREBASE_URL = "https://fyers-bot-606b9-default-rtdb.firebaseio.com"

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
    "RADICO", "RBLBANK", "RECLTD", "RELIANCE", "RVNL", "SAIL", "SBICARD", "SBILIFE", "SBIN", 
    "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF", "SUNPHARMA", "SUPREMEIND", "SUZLON", "SWIGGY", 
    "TATACONSUM", "TATAELXSI", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TIINDIA", "TITAN", "TMPV", "TORNTPHARM", 
    "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "UNOMINDA", "UPL", "VBL", "VEDL", "VMM", 
    "VOLTAS", "WAAREEENER", "WIPRO", "YESBANK", "ZYDUSLIFE"
]

# ==========================================
# 3. HIGH-SPEED FIREBASE FETCH
# ==========================================
st_autorefresh(interval=5000, limit=100000, key="viewer_fetch_loop") 

try:
    dash_resp = requests.get(f"{FIREBASE_URL}/Dashboard/Latest.json", timeout=4)
    if dash_resp.status_code == 200 and dash_resp.json():
        shared_pack = dash_resp.json()
        st.session_state.cached_data = shared_pack.get("data", [])
        last_scan_timestamp = shared_pack.get("time", time.time())
        st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
        st.session_state.missing_stocks_list = shared_pack.get("missing", [])
    else:
        if 'cached_data' not in st.session_state: st.session_state.cached_data = []
except Exception:
    if 'cached_data' not in st.session_state: st.session_state.cached_data = []

@st.cache_data(ttl=60)
def fetch_chart_history_raw(prefix):
    try:
        req_url = f'{FIREBASE_URL}/ChartHistory.json?orderBy="$key"&limitToLast=100'
        r = requests.get(req_url, timeout=10)
        
        if r.status_code == 200 and r.json():
            data = r.json()
            all_rows = []
            if isinstance(data, dict):
                for doc_id, chart_batch in data.items():
                    if str(doc_id).startswith(prefix) and 'data' in chart_batch: 
                        all_rows.extend(chart_batch['data'])
            return all_rows
    except Exception:
        pass
    return []

raw_chart_data = fetch_chart_history_raw(today_prefix)
st.session_state.chart_df = pd.DataFrame(raw_chart_data) if raw_chart_data else pd.DataFrame()


# ==========================================
# 3B. 🚀 TREND SCANNER LOGIC
# ==========================================
# Isse Vol CPR aur OPT PCR dono ka "continuously rising" trend detect hota hai
# har symbol ke liye, jaise AUROPHARMA ke chart mein dikh raha tha.
def compute_trending_stocks(chart_df, today_str, symbols, min_rise_pct=15.0, max_pullback_pct=15.0, min_points=8):
    results = []
    if chart_df is None or chart_df.empty or 'Date' not in chart_df.columns:
        return pd.DataFrame(results)

    day_df = chart_df.copy()
    day_df['Date'] = day_df['Date'].astype(str).str.strip()
    day_df['Symbol'] = day_df['Symbol'].astype(str).str.strip()
    day_df = day_df[day_df['Date'] == today_str]
    if day_df.empty:
        return pd.DataFrame(results)

    def trend_stats(series):
        # returns (rise_pct_from_start, pullback_from_high_pct, last_value)
        series = series.dropna()
        if len(series) < min_points:
            return None
        first_val = series.iloc[0]
        last_val = series.iloc[-1]
        max_val = series.max()
        if first_val == 0 or max_val == 0:
            return None
        rise_pct = ((last_val - first_val) / abs(first_val)) * 100.0
        pullback_pct = ((max_val - last_val) / abs(max_val)) * 100.0
        return rise_pct, pullback_pct, last_val

    for sym in symbols:
        sdf = day_df[day_df['Symbol'] == sym]
        if len(sdf) < min_points:
            continue
        sdf = sdf.sort_values(by='Time')

        if 'VOL CPR' not in sdf.columns or 'OPT PCR' not in sdf.columns:
            continue

        vol_series = pd.to_numeric(sdf['VOL CPR'], errors='coerce')
        opt_series = pd.to_numeric(sdf['OPT PCR'], errors='coerce')
        ltp_series = pd.to_numeric(sdf['LTP'], errors='coerce') if 'LTP' in sdf.columns else pd.Series(dtype=float)

        vol_stats = trend_stats(vol_series)
        opt_stats = trend_stats(opt_series)
        if vol_stats is None or opt_stats is None:
            continue

        vol_rise, vol_pullback, vol_last = vol_stats
        opt_rise, opt_pullback, opt_last = opt_stats

        # 🔥 CORE FILTER: dono indicators rise honi chahiye AUR abhi bhi
        # apne day-high ke paas hone chahiye (rise karke gir gaye wale bahar)
        if (vol_rise >= min_rise_pct and vol_pullback <= max_pullback_pct and
                opt_rise >= min_rise_pct and opt_pullback <= max_pullback_pct):

            ltp_last = ltp_series.dropna().iloc[-1] if not ltp_series.dropna().empty else 0

            results.append({
                'SYMBOL': sym,
                'LTP': ltp_last,
                'VOL CPR': vol_last,
                'VOL CPR RISE %': vol_rise,
                'OPT PCR': opt_last,
                'OPT PCR RISE %': opt_rise,
                'SCORE': vol_rise + opt_rise
            })

    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by='SCORE', ascending=False)
    return res_df


# ==========================================
# 4. DASHBOARD HEADER & RENDERING
# ==========================================
if 'cached_data' in st.session_state and len(st.session_state.cached_data) > 0:
    
    # 🔥 LAYOUT: Menu & Time close on left, Toggle pushed to far right 🔥
    col_menu, col_tim, col_space, col_tog = st.columns([1.5, 1.2, 5.8, 1.5])
    
    with col_menu:
        selected_tab = st.radio("Menu", ["📊 Dash", "📈 CHART", "🚀 TREND"], horizontal=True, label_visibility="collapsed")
        
    ref_time = st.session_state.last_api_call.strftime('%H:%M:%S') if 'last_api_call' in st.session_state else "Waiting..."
    show_pct = True 
    
    with col_tim:
        if selected_tab == "📊 Dash":
            st.markdown(f"<div class='time-box'>⏱️ {ref_time}</div>", unsafe_allow_html=True)
        else:
            st.empty() 
            
    with col_space:
        st.empty() # Empty space to push toggle to the right
        
    with col_tog:
        if selected_tab == "📊 Dash":
            show_pct = st.toggle("SHOW %", value=True)
        else:
            st.empty() 

    st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

    # ==========================================
    # DASHBOARD VIEW
    # ==========================================
    if selected_tab == "📊 Dash":
        
        if 'missing_stocks_list' in st.session_state and len(st.session_state.missing_stocks_list) > 0:
            missing_str = ", ".join(st.session_state.missing_stocks_list)
            st.warning(f"⚠️ Fyers API missed data for: {missing_str}")
            
        def color_open(val):
            if "Gap Up" in str(val): return f"<span style='color: #00AA00;'>{val}</span>"
            if "Gap Down" in str(val): return f"<span style='color: #FF0000;'>{val}</span>"
            if "Same" in str(val): return f"<span style='color: #00BFFF;'>{val}</span>"
            return str(val)

        def color_num(val, is_pct=False):
            try:
                v = float(val)
                fmt = f"{v:+.2f}%" if is_pct else f"{v:+.2f}"
                if v > 0: return f"<span style='color: #00AA00;'>{fmt}</span>"
                if v < 0: return f"<span style='color: #FF0000;'>{fmt}</span>"
                return f"<span style='color: #888888;'>{fmt}</span>"
            except: return str(val)

        def color_pcr(val):
            try:
                v = float(val)
                fmt = f"{v:.2f}"
                if v >= 1.0: return f"<span style='color: #00AA00;'>{fmt}</span>"
                if 0 < v < 1.0: return f"<span style='color: #FF0000;'>{fmt}</span>"
                return fmt
            except: return str(val)

        def format_ltp(val):
            try: return f"{float(val):.2f}"
            except: return str(val)
        
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
                'V_PCR': 'VOL<br>PCR', 
                'O_PCR': 'OPTION<br>PCR', 
                'V_CPR': 'VOL<br>CPR', 
                'LTP_CH': 'LTP<br>CHANGE', 
                'CHG_%': 'CHANGE<br>%', 
                'LTP': 'LTP', 
                'CE_CON': 'CE<br>CONTRACT', 
                'PE_CON': 'PE<br>CONTRACT',
                'PCR CHECKER': 'PCR<br>CHECKER', 
                'VOL CHECKER': 'VOL<br>CHECKER'
            })

            df['OPENING'] = df['OPENING'].apply(color_open)
            df['LTP<br>CHANGE'] = df['LTP<br>CHANGE'].apply(lambda x: color_num(x, False))
            df['CHANGE<br>%'] = df['CHANGE<br>%'].apply(lambda x: color_num(x, True))
            df['CE<br>CONTRACT'] = df['CE<br>CONTRACT'].apply(lambda x: color_num(x, True))
            df['PE<br>CONTRACT'] = df['PE<br>CONTRACT'].apply(lambda x: color_num(x, True))
            df['PCR<br>CHECKER'] = df['PCR<br>CHECKER'].apply(lambda x: color_num(x, show_pct))
            df['VOL<br>CHECKER'] = df['VOL<br>CHECKER'].apply(lambda x: color_num(x, show_pct))
            df['VOL<br>PCR'] = df['VOL<br>PCR'].apply(color_pcr)
            df['OPTION<br>PCR'] = df['OPTION<br>PCR'].apply(color_pcr)
            df['VOL<br>CPR'] = df['VOL<br>CPR'].apply(color_pcr)
            df['LTP'] = df['LTP'].apply(format_ltp)
            
            html_table = df.to_html(escape=False, index=False, classes="dataframe")
            
            full_interactive_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {{ margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: transparent; }}
                .table-wrapper {{ height: 800px; overflow: auto; border-radius: 5px; }}
                table.dataframe {{ width: 100%; border-collapse: collapse; font-size: 12px; margin: 0 auto; background-color: #ffffff; color: #000000; }}
                table.dataframe th {{ 
                    background-color: darkblue !important; color: white !important; font-weight: bold !important; text-align: center !important; 
                    padding: 8px 3px !important; position: sticky; top: 0; z-index: 10; border: 1px solid rgba(255,255,255,0.2);
                    cursor: pointer; user-select: none; transition: background 0.2s;
                }}
                table.dataframe th:hover {{ background-color: #0000cc !important; }}
                table.dataframe td {{ 
                    text-align: center !important; 
                    padding: 6px 3px !important; 
                    border-bottom: 1px solid rgba(128,128,128,0.2); border-right: 1px solid rgba(128,128,128,0.1); font-weight: bold; 
                }}
                table.dataframe tr:hover {{ background-color: rgba(128,128,128,0.1); }}
                ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
                ::-webkit-scrollbar-thumb {{ background: rgba(128,128,128,0.5); border-radius: 3px; }}
            </style>
            </head>
            <body>
            <div class="table-wrapper">
                {html_table}
            </div>
            <script>
                document.querySelectorAll('th').forEach(th => {{
                    th.title = "Click to Sort Ascending / Descending";
                    th.addEventListener('click', function() {{
                        const table = th.closest('table');
                        const tbody = table.querySelector('tbody');
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        const idx = Array.from(th.parentNode.children).indexOf(th);
                        const asc = this.asc = !this.asc;

                        table.querySelectorAll('th').forEach(el => el.innerHTML = el.innerHTML.replace(/ ▲| ▼/g, ''));
                        th.innerHTML += asc ? ' ▲' : ' ▼';

                        const parseVal = (td) => {{
                            let val = td.innerText || td.textContent;
                            val = val.replace(/,/g, '').replace(/%/g, '').replace(/[+]/g, '').trim();
                            let num = parseFloat(val);
                            return isNaN(num) ? val : num;
                        }};

                        rows.sort((a, b) => {{
                            let v1 = parseVal(a.children[idx]);
                            let v2 = parseVal(b.children[idx]);
                            if (typeof v1 === 'number' && typeof v2 === 'number') {{ return asc ? v1 - v2 : v2 - v1; }}
                            return asc ? String(v1).localeCompare(String(v2)) : String(v2).localeCompare(String(v1));
                        }});
                        rows.forEach(tr => tbody.appendChild(tr));
                    }});
                }});
            </script>
            </body>
            </html>
            """
            components.html(full_interactive_html, height=800, scrolling=False)

    # ==========================================
    # CHART VIEW
    # ==========================================
    elif selected_tab == "📈 CHART":
        
        col_c1, col_c2 = st.columns([1, 1])
        
        with col_c1: 
            # 🔥 SEARCH BOX: index=0 (NIFTY Default) 🔥
            sel_stock = st.selectbox(
                "Stock:", 
                raw_symbols, 
                index=0,                                
                placeholder="🔍 Search Stock...",          
                key="c_stock", 
                label_visibility="collapsed"
            )
            
        with col_c2: 
            chart_mode = st.radio("View:", ["Vol CPR", "OPT PCR"], horizontal=True, label_visibility="collapsed")

        c_main_h, c_iframe_h = 350, 470    

        if 'chart_df' in st.session_state and not st.session_state.chart_df.empty:
            if sel_stock: 
                try:
                    hist_df = st.session_state.chart_df.copy()
                    if 'Date' in hist_df.columns:
                        hist_df['Date'] = hist_df['Date'].astype(str).str.strip()
                        hist_df['Symbol'] = hist_df['Symbol'].astype(str).str.strip()
                        df_sym = hist_df[(hist_df['Date'] == today_str) & (hist_df['Symbol'] == sel_stock)].copy()
                        if not df_sym.empty:
                            df_sym = df_sym.sort_values(by='Time')
                            
                            target_col = 'VOL CPR' if chart_mode == "Vol CPR" else 'OPT PCR'
                            indicator_color = "#FF4D4D" if chart_mode == "Vol CPR" else "#00BFFF"
                            
                            time_list = df_sym['Time'].tolist()
                            indicator_list = pd.to_numeric(df_sym[target_col], errors='coerce').fillna(0).tolist()
                            ltp_list = pd.to_numeric(df_sym['LTP'], errors='coerce').fillna(0).tolist()

                            apex_html = f"""
                            <!DOCTYPE html>
                            <html>
                            <head>
                                <script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
                                <link href="https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.0/nouislider.min.css" rel="stylesheet">
                                <script src="https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.0/nouislider.min.js"></script>
                                <style> 
                                    body {{ margin: 0; padding: 0; background-color: transparent; font-family: 'Segoe UI', Arial, sans-serif; overflow: hidden; }} 
                                    .apexcharts-toolbar {{ display: none !important; }}
                                    #custom-reset-btn {{ position: absolute; top: 10px; left: 15px; z-index: 9999; background: #2962FF; border: none; border-radius: 4px; padding: 4px 10px; font-size: 12px; font-weight: bold; color: #fff; cursor: pointer; }}
                                    .slider-wrapper {{ padding: 10px 25px; margin-top: -10px; position: relative; }}
                                    .time-labels {{ display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #666; margin-bottom: 15px; }}
                                    .noUi-target {{ background: #e0e0e0; border: none; box-shadow: none; height: 5px; }}
                                    .noUi-connect {{ background: #2962FF; }}
                                    .noUi-handle {{ width: 22px !important; height: 22px !important; border-radius: 50%; background: #2962FF; box-shadow: 0 2px 5px rgba(0,0,0,0.3); border: none; right: -11px !important; top: -9px !important; cursor: pointer; }}
                                    .noUi-handle:before, .noUi-handle:after {{ display: none; }}
                                </style>
                            </head>
                            <body>
                                <button id="custom-reset-btn">🔄 Reset Zoom</button>
                                <div id="chart-main"></div>
                                
                                <div class="slider-wrapper">
                                    <div class="time-labels"><span id="lbl-start"></span><span id="lbl-end"></span></div>
                                    <div id="dual-slider"></div>
                                </div>
                                
                                <script>
                                    var dataIndicator = {json.dumps(indicator_list)}; 
                                    var dataLTP = {json.dumps(ltp_list)}; 
                                    var timeCats = {json.dumps(time_list)}; 
                                    
                                    var optionsMain = {{
                                        series: [{{ name: '{chart_mode}', type: 'area', data: dataIndicator }}, {{ name: 'LTP', type: 'line', data: dataLTP }}],
                                        chart: {{ id: 'mainChart', height: {c_main_h}, type: 'line', toolbar: {{ show: false }}, zoom: {{ enabled: false }}, animations: {{ enabled: false }} }},
                                        colors: ['{indicator_color}', '#00CC66'], 
                                        stroke: {{ curve: 'smooth', width: [3, 3] }}, 
                                        fill: {{ type: ['gradient', 'solid'], gradient: {{ shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }} }},
                                        dataLabels: {{ enabled: false }}, 
                                        xaxis: {{ categories: timeCats, tickAmount: 10, labels: {{ style: {{ colors: '#888' }} }}, tooltip: {{ enabled: false }} }},
                                        yaxis: [
                                            {{ title: {{ text: '{chart_mode}', style: {{ color: '{indicator_color}' }} }}, labels: {{ style: {{ colors: '{indicator_color}' }} }}, decimalsInFloat: 2 }}, 
                                            {{ opposite: true, title: {{ text: 'LTP', style: {{ color: '#00CC66' }} }}, labels: {{ style: {{ colors: '#00CC66' }} }}, decimalsInFloat: 2 }}
                                        ],
                                        tooltip: {{ shared: true, intersect: false }}, 
                                        legend: {{ position: 'top', horizontalAlign: 'right' }}
                                    }};
                                    
                                    var chartMain = new ApexCharts(document.querySelector("#chart-main"), optionsMain); 
                                    chartMain.render();
                                    
                                    var slider = document.getElementById('dual-slider'); 
                                    var lblStart = document.getElementById('lbl-start'); 
                                    var lblEnd = document.getElementById('lbl-end');
                                    
                                    if(timeCats.length > 0) {{
                                        noUiSlider.create(slider, {{ start: [0, timeCats.length - 1], connect: true, range: {{ 'min': 0, 'max': timeCats.length - 1 }}, step: 1 }});
                                        slider.noUiSlider.on('update', function (values, handle) {{
                                            var sIdx = parseInt(values[0]), eIdx = parseInt(values[1]);
                                            lblStart.innerText = "From: " + timeCats[sIdx]; 
                                            lblEnd.innerText = "To: " + timeCats[eIdx];
                                            chartMain.updateOptions({{ xaxis: {{ categories: timeCats.slice(sIdx, eIdx + 1) }}, series: [{{ name: '{chart_mode}', data: dataIndicator.slice(sIdx, eIdx + 1) }}, {{ name: 'LTP', data: dataLTP.slice(sIdx, eIdx + 1) }}] }}, false, false, false);
                                        }});
                                        document.getElementById('custom-reset-btn').addEventListener('click', function() {{ slider.noUiSlider.set([0, timeCats.length - 1]); }});
                                    }}
                                </script>
                            </body>
                            </html>
                            """
                            components.html(apex_html, height=c_iframe_h)
                        else: 
                            st.info(f"⏳ Waiting for Market Data for {sel_stock}...")
                    else: 
                        st.info("⏳ Market data hasn't started logging yet today.")
                except Exception as e: 
                    st.error(f"Chart Load Error: {e}")
        else: 
            st.info("⏳ Chart data sheet is empty. Waiting for Master Engine...")

    # ==========================================
    # 🚀 TREND VIEW (NAYA TAB)
    # ==========================================
    elif selected_tab == "🚀 TREND":

        st.markdown("<div style='font-size:13px; opacity:0.75; margin-bottom:4px;'>Vol CPR + OPT PCR dono continuously rising wale stocks (auto-scan, sab symbols par)</div>", unsafe_allow_html=True)

        # Sensitivity sliders — inko adjust karke tum strict/loose scan kar sakte ho
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            min_rise_pct = st.slider("Min Rise % (start se ab tak)", min_value=5, max_value=100, value=15, step=5)
        with col_s2:
            max_pullback_pct = st.slider("Max Pullback % (day-high se)", min_value=5, max_value=50, value=15, step=5)

        chart_df = st.session_state.get('chart_df', pd.DataFrame())

        if chart_df is None or chart_df.empty:
            st.info("⏳ Chart history abhi load nahi hua — thodi der baad try karo.")
        else:
            trend_df = compute_trending_stocks(
                chart_df, today_str, raw_symbols,
                min_rise_pct=float(min_rise_pct),
                max_pullback_pct=float(max_pullback_pct)
            )

            if trend_df.empty:
                st.info("🔍 Abhi koi stock is criteria pe match nahi kar raha. Sliders thode loose kar ke try karo.")
            else:
                def color_pcr_val(v):
                    try:
                        v = float(v)
                        fmt = f"{v:.2f}"
                        if v >= 1.0: return f"<span style='color:#00AA00;'>{fmt}</span>"
                        if 0 < v < 1.0: return f"<span style='color:#FF0000;'>{fmt}</span>"
                        return fmt
                    except: return str(v)

                def color_rise(v):
                    try:
                        v = float(v)
                        return f"<span style='color:#00AA00;'>+{v:.1f}%</span>"
                    except: return str(v)

                disp = trend_df.copy()
                disp['LTP'] = disp['LTP'].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) else "-")
                disp['VOL CPR'] = disp['VOL CPR'].apply(color_pcr_val)
                disp['VOL CPR RISE %'] = disp['VOL CPR RISE %'].apply(color_rise)
                disp['OPT PCR'] = disp['OPT PCR'].apply(color_pcr_val)
                disp['OPT PCR RISE %'] = disp['OPT PCR RISE %'].apply(color_rise)
                disp = disp.drop(columns=['SCORE'])

                disp = disp.rename(columns={
                    'SYMBOL': 'SYMBOL',
                    'LTP': 'LTP',
                    'VOL CPR': 'VOL<br>CPR',
                    'VOL CPR RISE %': 'VOL CPR<br>RISE %',
                    'OPT PCR': 'OPT<br>PCR',
                    'OPT PCR RISE %': 'OPT PCR<br>RISE %'
                })

                html_table = disp.to_html(escape=False, index=False, classes="dataframe")

                trend_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                    body {{ margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: transparent; }}
                    .table-wrapper {{ height: 650px; overflow: auto; border-radius: 5px; }}
                    table.dataframe {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 0 auto; background-color: #ffffff; color: #000000; }}
                    table.dataframe th {{ 
                        background-color: #B8860B !important; color: white !important; font-weight: bold !important; text-align: center !important; 
                        padding: 8px 6px !important; position: sticky; top: 0; z-index: 10; border: 1px solid rgba(255,255,255,0.2);
                    }}
                    table.dataframe td {{ 
                        text-align: center !important; 
                        padding: 7px 6px !important; 
                        border-bottom: 1px solid rgba(128,128,128,0.2); border-right: 1px solid rgba(128,128,128,0.1); font-weight: bold; 
                    }}
                    table.dataframe tr:hover {{ background-color: rgba(128,128,128,0.1); }}
                </style>
                </head>
                <body>
                <div class="table-wrapper">
                    {html_table}
                </div>
                </body>
                </html>
                """
                components.html(trend_html, height=650, scrolling=False)
                st.caption(f"✅ {len(trend_df)} stocks match kar rahe hain current criteria pe.")

else:
    st.info("⏳ Booting up... Waiting for Engine to push data.")
