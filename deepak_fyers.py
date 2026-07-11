import streamlit as st
import pandas as pd
import datetime
import time
import json
import requests
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components  

st.set_page_config(page_title="F&O LIVE Dashboard", layout="wide")

# ==========================================
# 1. UI & CSS SETUP
# ==========================================
css_str = """
<style>
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
</style>
"""
st.markdown(css_str, unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
today_str = datetime.datetime.now(IST).strftime("%Y-%m-%d")

# ==========================================
# 2. FIREBASE CONNECTION DETAILS
# ==========================================
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
# 3. AUTO-REFRESH & FIREBASE FETCH
# ==========================================
st_autorefresh(interval=30000, limit=100000, key="viewer_fetch_loop")

st.sidebar.success("🟢 LIVE VIEWER ACTIVE\n\nReceiving data from Firebase Mobile Engine.")

try:
    # --- FETCH DASHBOARD DATA ---
    dash_resp = requests.get(f"{FIREBASE_URL}/Dashboard/Latest.json", timeout=10)
    if dash_resp.status_code == 200 and dash_resp.json():
        shared_pack = dash_resp.json()
        st.session_state.cached_data = shared_pack.get("data", [])
        last_scan_timestamp = shared_pack.get("time", time.time())
        st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
        st.session_state.missing_stocks_list = shared_pack.get("missing", [])
    else:
        st.info("⏳ Waiting for Firebase Master Engine data...")
        if 'cached_data' not in st.session_state: st.session_state.cached_data = []
        
    # --- FETCH CHART HISTORY DATA ---
    chart_resp = requests.get(f"{FIREBASE_URL}/ChartHistory.json", timeout=10)
    if chart_resp.status_code == 200 and chart_resp.json():
        all_chart_data = chart_resp.json()
        all_rows = []
        # Sirf aaj ka data filter karein
        for doc_id, chart_batch in all_chart_data.items():
            if str(doc_id).startswith(today_str.replace("-", "")): 
                if 'data' in chart_batch:
                    all_rows.extend(chart_batch['data'])
        
        if all_rows:
            st.session_state.chart_df = pd.DataFrame(all_rows)
        else:
            st.session_state.chart_df = pd.DataFrame()
    else:
        st.session_state.chart_df = pd.DataFrame()

except Exception as e:
    st.error(f"⚠️ Error fetching from Firebase: {e}")
    if 'cached_data' not in st.session_state: st.session_state.cached_data = []

# ==========================================
# 4. DASHBOARD & CHART RENDERING
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
        ref_time = st.session_state.last_api_call.strftime('%H:%M:%S') if 'last_api_call' in st.session_state else "Waiting..."
        st.markdown(f"<div style='text-align: right; color: #888888; font-size: 13px; font-weight: bold; margin-top: 8px;'>⏱️ Last Updated: {ref_time}</div>", unsafe_allow_html=True)

    st.divider()

    if selected_tab == "📊 Dashboard":
        
        if 'missing_stocks_list' in st.session_state and len(st.session_state.missing_stocks_list) > 0:
            missing_str = ", ".join(st.session_state.missing_stocks_list)
            st.warning(f"⚠️ Fyers API ne in {len(st.session_state.missing_stocks_list)} stocks ka data nahi diya: **{missing_str}**")
        
        checker_fmt = '{:+.2f}%' if show_pct else '{:+.2f}'
        
        format_dict = {
            'VOL PCR': '{:.2f}', 'OPTION PCR': '{:.2f}', 'VOL CPR': '{:.2f}', 
            'LTP': '{:.2f}', 'LTP CHANGE': '{:.2f}', 'CHANGE%': '{:+.2f}%', 
            'CE_CONTRACT': '{:+.1f}%', 'PE_CONTRACT': '{:+.1f}%',
            'PCR CHECKER': checker_fmt, 'VOL CHECKER': checker_fmt
        }
        
        df = pd.DataFrame(st.session_state.cached_data)
        
        if not df.empty:
            df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
            df = df.sort_values(by='Conv_Rank', ascending=False)
            
            df['VOL CHECKER'] = df['VOL_PCT'] if show_pct else df['VOL_ABS']
            df['PCR CHECKER'] = df['PCR_PCT'] if show_pct else df['PCR_ABS']
            
            df = df[['SYMS', 'OPEN_STATUS', 'V_PCR', 'O_PCR', 'V_CPR', 'LTP_CH', 'CHG_%', 'LTP', 'CE_CON', 'PE_CON', 'PCR CHECKER', 'VOL CHECKER']]
            
            df = df.rename(columns={
                'SYMS': 'SYMBOL', 'OPEN_STATUS': 'OPENING', 'V_PCR': 'VOL PCR', 'O_PCR': 'OPTION PCR',
                'V_CPR': 'VOL CPR', 'LTP_CH': 'LTP CHANGE', 'CHG_%': 'CHANGE%', 'LTP': 'LTP', 
                'CE_CON': 'CE_CONTRACT', 'PE_CON': 'PE_CONTRACT'
            })

            styled_df = (df.style.hide(axis="index")
                         .set_properties(**{'text-align': 'center'})
                         .format(format_dict)
                         .set_table_styles(header_styles)
                         .map(style_indicators, subset=['OPENING', 'LTP CHANGE', 'CHANGE%', 'CE_CONTRACT', 'PE_CONTRACT', 'VOL CHECKER', 'PCR CHECKER'])
                         .map(style_pcr_columns, subset=['VOL PCR', 'OPTION PCR', 'VOL CPR']))

            st.dataframe(styled_df, use_container_width=True, height=800, hide_index=True)

    elif selected_tab == "📈 CHART":
        col_c1, col_c2, col_c3 = st.columns([1.5, 1.5, 1.5])
        with col_c1: sel_stock = st.selectbox("Select Stock for Trend:", raw_symbols, index=0, key="c_stock", label_visibility="collapsed")
        with col_c2: chart_mode = st.radio("SWITCH CHART VIEW:", ["Vol CPR", "Option PCR"], horizontal=True, label_visibility="collapsed")
        with col_c3: device_mode = st.radio("Screen Layout:", ["💻 Laptop", "📱 Mobile"], horizontal=True, index=1, label_visibility="collapsed")

        if device_mode == "💻 Laptop": c_main_h, c_iframe_h = 480, 610    
        else: c_main_h, c_iframe_h = 350, 470    

        if 'chart_df' in st.session_state and not st.session_state.chart_df.empty:
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
                                body {{ margin: 0; padding: 0; background-color: transparent; font-family: 'Segoe UI', Arial, sans-serif; position: relative; overflow: hidden; }} 
                                .apexcharts-toolbar {{ display: none !important; }}
                                #custom-reset-btn {{ position: absolute; top: 10px; left: 15px; z-index: 9999; background-color: #f1f1f1; border: 1px solid #ccc; border-radius: 4px; padding: 4px 8px; font-size: 12px; font-weight: bold; color: #333; cursor: pointer; box-shadow: 0px 2px 4px rgba(0,0,0,0.1); }}
                                .slider-wrapper {{ padding: 10px 25px; margin-top: -10px; position: relative; }}
                                .time-labels {{ display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #666; margin-bottom: 15px; }}
                                .noUi-target {{ background: #e0e0e0; border: none; box-shadow: none; height: 5px; }}
                                .noUi-connect {{ background: #2962FF; }}
                                .noUi-handle {{ width: 22px !important; height: 22px !important; border-radius: 50%; background: #2962FF; box-shadow: 0 2px 5px rgba(0,0,0,0.3); border: none; right: -11px !important; top: -9px !important; cursor: pointer; }}
                                .noUi-handle:before, .noUi-handle:after {{ display: none; }}
                            </style>
                        </head>
                        <body>
                            <button id="custom-reset-btn">🔄 Reset</button>
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
                                    chart: {{ id: 'mainChart', height: {c_main_h}, type: 'line', toolbar: {{ show: false }}, zoom: {{ enabled: false }}, selection: {{ enabled: false }}, animations: {{ enabled: false }} }},
                                    colors: ['{indicator_color}', '#00CC66'],
                                    stroke: {{ curve: 'smooth', width: [3, 3] }}, 
                                    fill: {{ type: ['gradient', 'solid'], gradient: {{ shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }} }},
                                    dataLabels: {{ enabled: false }},
                                    xaxis: {{ categories: timeCats, tickAmount: 10, labels: {{ style: {{ colors: '#888' }} }}, tooltip: {{ enabled: false }} }},
                                    yaxis: [
                                        {{ title: {{ text: '{chart_mode}', style: {{ color: '{indicator_color}' }} }}, labels: {{ style: {{ colors: '{indicator_color}' }} }}, decimalsInFloat: 2 }},
                                        {{ opposite: true, title: {{ text: 'LTP', style: {{ color: '#00CC66' }} }}, labels: {{ style: {{ colors: '#00CC66' }} }}, decimalsInFloat: 2 }}
                                    ],
                                    tooltip: {{ shared: true, intersect: false, y: {{ formatter: function (y) {{ if (typeof y !== "undefined") {{ return y.toFixed(2); }} return y; }} }} }},
                                    legend: {{ position: 'top', horizontalAlign: 'right' }}
                                }};

                                var chartMain = new ApexCharts(document.querySelector("#chart-main"), optionsMain);
                                chartMain.render();

                                var totalPoints = timeCats.length;
                                var slider = document.getElementById('dual-slider');
                                var lblStart = document.getElementById('lbl-start');
                                var lblEnd = document.getElementById('lbl-end');

                                if(totalPoints > 0) {{
                                    noUiSlider.create(slider, {{ start: [0, totalPoints - 1], connect: true, range: {{ 'min': 0, 'max': totalPoints - 1 }}, step: 1 }});
                                    slider.noUiSlider.on('update', function (values, handle) {{
                                        var startIdx = parseInt(values[0]);
                                        var endIdx = parseInt(values[1]);
                                        lblStart.innerText = "From: " + timeCats[startIdx];
                                        lblEnd.innerText = "To: " + timeCats[endIdx];
                                        chartMain.updateOptions({{
                                            xaxis: {{ categories: timeCats.slice(startIdx, endIdx + 1) }},
                                            series: [{{ name: '{chart_mode}', data: dataIndicator.slice(startIdx, endIdx + 1) }}, {{ name: 'LTP', data: dataLTP.slice(startIdx, endIdx + 1) }}]
                                        }}, false, false, false);
                                    }});
                                    document.getElementById('custom-reset-btn').addEventListener('click', function() {{ slider.noUiSlider.set([0, totalPoints - 1]); }});
                                }}
                            </script>
                        </body>
                        </html>
                        """
                        components.html(apex_html, height=c_iframe_h)
                    else: st.info(f"⏳ Waiting for Market Data for {sel_stock}...")
                else: st.info("⏳ Market data hasn't started logging yet today.")
            except Exception as e: st.error(f"Chart Load Error: {e}")
        else: st.info("⏳ Chart data sheet is empty. Waiting for Master Engine...")
