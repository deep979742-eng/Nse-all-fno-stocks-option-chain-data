import streamlit as st
import pandas as pd
import datetime
import json
import requests
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components  

# ==========================================
# PAGE CONFIG 
# ==========================================
st.set_page_config(page_title="Chart & Trend Engine", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 1. 🔥 FORCE LIGHT THEME & HIDE WATERMARK / FULLSCREEN
# ==========================================
st.markdown("""
<style>
    header, footer, .stDeployButton, [data-testid="stToolbar"], [data-testid="stHeader"], [data-testid="stBottom"] { 
        display: none !important; visibility: hidden !important; opacity: 0 !important;
    }
    button[title="View fullscreen"], [data-testid="StyledFullScreenButton"] { 
        display: none !important; visibility: hidden !important; 
    }
    .stApp, .block-container, iframe { 
        background-color: #ffffff !important; 
        color: #000000 !important; 
    }
    .block-container { 
        padding-top: 0rem !important; padding-bottom: 0rem !important; 
        padding-left: 0.2rem !important; padding-right: 0.2rem !important; 
        margin-top: -60px !important; max-width: 100% !important;
    }
    div[data-testid="stColumns"] { gap: 0.5rem !important; margin-bottom: -15px !important; padding: 0 10px;}
    
    .stRadio div[role='radiogroup'] { flex-wrap: nowrap !important; }
    .stRadio div[role='radiogroup'] > label { 
        background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; 
        border-radius: 6px !important; padding: 5px 15px !important; 
        font-weight: bold !important; font-size: 13px !important; cursor: pointer !important; color: #000000 !important;
    }
    .stRadio div[role='radiogroup'] > label div, .stRadio div[role='radiogroup'] > label p { color: #000000 !important; }

    div[data-baseweb="select"] > div { background-color: #ffffff !important; color: #000000 !important; border-color: #cbd5e1 !important; }
    div[data-baseweb="select"] span { color: #000000 !important; }
</style>
""", unsafe_allow_html=True)

components.html(
    """
    <script>
    const observer = new MutationObserver(() => {
        const footer = window.parent.document.querySelector('footer');
        if (footer) footer.style.display = 'none';
        const fullScreenBtns = window.parent.document.querySelectorAll('button[title="View fullscreen"]');
        fullScreenBtns.forEach(btn => btn.style.display = 'none');
    });
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
    </script>
    """,
    height=0, width=0
)

FIREBASE_URL = "https://fyers-bot-606b9-default-rtdb.firebaseio.com"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
today_str = datetime.datetime.now(IST).strftime("%Y-%m-%d")
today_prefix = today_str.replace("-", "")

st_autorefresh(interval=5000, limit=100000, key="viewer_fetch_loop") 

# ==========================================
# 2. FETCH DATA FROM FIREBASE (Dashboard & Charts)
# ==========================================
dynamic_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
try:
    dash_resp = requests.get(f"{FIREBASE_URL}/Dashboard/Latest.json", timeout=3)
    if dash_resp.status_code == 200 and dash_resp.json():
        shared_pack = dash_resp.json()
        data = shared_pack.get("data", [])
        st.session_state.cached_data = data
        fetched_syms = sorted(list(set([item.get('SYMS', item.get('SYMBOL', '')) for item in data if item.get('SYMS') or item.get('SYMBOL')])))
        if fetched_syms: dynamic_symbols = fetched_syms
except: pass

@st.cache_data(ttl=30)
def fetch_chart_history_raw(prefix):
    try:
        r = requests.get(f'{FIREBASE_URL}/ChartHistory.json?orderBy="$key"&limitToLast=100', timeout=6)
        if r.status_code == 200 and r.json():
            data = r.json()
            all_rows = []
            if isinstance(data, dict):
                for doc_id, chart_batch in data.items():
                    if str(doc_id).startswith(prefix) and 'data' in chart_batch: 
                        all_rows.extend(chart_batch['data'])
            return all_rows
    except: pass
    return []

raw_chart_data = fetch_chart_history_raw(today_prefix)
chart_df = pd.DataFrame(raw_chart_data) if raw_chart_data else pd.DataFrame()

# ==========================================
# 3. PURE CHART UI & BACKEND SUPPORT
# ==========================================
col1, col2 = st.columns([2, 2])
with col1: 
    sel_stock = st.selectbox("Stock:", dynamic_symbols, index=0, label_visibility="collapsed")
with col2: 
    chart_mode = st.radio("View:", ["Vol CPR", "OPT PCR"], horizontal=True, label_visibility="collapsed")

if not chart_df.empty and sel_stock:
    try:
        hist_df = chart_df.copy()
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
                    body {{ margin: 0; padding: 0; background-color: #ffffff; font-family: 'Segoe UI', Arial, sans-serif; overflow: hidden; }} 
                    .apexcharts-toolbar {{ display: none !important; }}
                    #custom-reset-btn {{ position: absolute; top: 10px; left: 15px; z-index: 9999; background: #2962FF; border: none; border-radius: 4px; padding: 5px 12px; font-size: 11px; font-weight: bold; color: #fff; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
                    .slider-wrapper {{ padding: 0px 25px; margin-top: -15px; position: relative; }}
                    .time-labels {{ display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #888; margin-bottom: 10px; }}
                    .noUi-target {{ background: #e2e8f0; border: none; box-shadow: none; height: 6px; }}
                    .noUi-connect {{ background: #2962FF; }}
                    .noUi-handle {{ width: 20px !important; height: 20px !important; border-radius: 50%; background: #2962FF; box-shadow: 0 2px 5px rgba(0,0,0,0.3); border: none; right: -10px !important; top: -7px !important; cursor: pointer; }}
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
                        chart: {{ id: 'mainChart', height: 420, type: 'line', toolbar: {{ show: false }}, zoom: {{ enabled: false }}, animations: {{ enabled: false }} }},
                        colors: ['{indicator_color}', '#00CC66'], 
                        stroke: {{ curve: 'smooth', width: [3, 3] }}, 
                        fill: {{ type: ['gradient', 'solid'], gradient: {{ shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }} }},
                        dataLabels: {{ enabled: false }}, 
                        xaxis: {{ categories: timeCats, tickAmount: 10, labels: {{ style: {{ colors: '#888' }} }}, tooltip: {{ enabled: false }} }},
                        yaxis: [
                            {{ title: {{ text: '{chart_mode}', style: {{ color: '{indicator_color}' }} }}, labels: {{ style: {{ colors: '{indicator_color}' }} }}, decimalsInFloat: 2 }}, 
                            {{ opposite: true, title: {{ text: 'LTP', style: {{ color: '#00CC66' }} }}, labels: {{ style: {{ colors: '#00CC66' }} }}, decimalsInFloat: 2 }}
                        ],
                        grid: {{ borderColor: '#e2e8f0', strokeDashArray: 3 }},
                        tooltip: {{ shared: true, intersect: false, theme: 'light' }}, 
                        legend: {{ position: 'top', horizontalAlign: 'right', labels: {{ colors: '#000' }} }}
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
            components.html(apex_html, height=520, width=None)
    except Exception as e: 
        st.error(f"Chart Load Error: {e}")
