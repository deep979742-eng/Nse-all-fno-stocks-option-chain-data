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
st.set_page_config(page_title="F&O Pro Trading Dashboard", layout="wide", initial_sidebar_state="collapsed")

# ==========================================
# 1. 🔥 HIDE WATERMARKS & ZERO TOP SPACE CSS
# ==========================================
st.markdown("""
<style>
    header, footer, .stDeployButton, [data-testid="stToolbar"], [data-testid="stHeader"], [data-testid="stBottom"] { 
        display: none !important; visibility: hidden !important; opacity: 0 !important;
    }
    button[title="View fullscreen"], [data-testid="StyledFullScreenButton"] { 
        display: none !important; visibility: hidden !important; 
    }
    
    /* REMOVE TOP WHITE SPACE / PADDING */
    .block-container { 
        padding-top: 0.5rem !important; 
        padding-bottom: 0rem !important; 
        padding-left: 0.5rem !important; 
        padding-right: 0.5rem !important; 
        margin-top: -35px !important; 
        max-width: 100% !important;
    }
    
    .stApp { background-color: #f8fafc !important; }

    /* PROFESSIONAL TOP MENU TABS */
    .stRadio div[role='radiogroup'] { gap: 4px; width: 100%; flex-wrap: nowrap !important; }
    .stRadio div[role='radiogroup'] > label > div:first-child { display: none !important; } 
    .stRadio div[role='radiogroup'] > label { 
        border: 1px solid #cbd5e1 !important; 
        border-radius: 6px !important; 
        background-color: #ffffff !important; 
        color: #0f172a !important;
        cursor: pointer !important; 
        display: flex !important; 
        align-items: center !important; 
        justify-content: center !important; 
        font-weight: bold !important; 
        height: 38px !important; 
        padding: 0 15px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* TIME BOX STYLING */
    .time-box { 
        border: 1px solid #cbd5e1; 
        padding: 0px 15px; 
        border-radius: 6px; 
        background-color: #ffffff; 
        text-align: center; 
        font-weight: bold; 
        font-size: 13px; 
        color: #0284c7; 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        height: 38px; 
        white-space: nowrap; 
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# Aggressive JS to nuke Streamlit footer watermark dynamically
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

# Auto Refresh Data Loop
st_autorefresh(interval=5000, limit=100000, key="viewer_fetch_loop") 

# ==========================================
# 2. FETCH FIREBASE DATA
# ==========================================
try:
    dash_resp = requests.get(f"{FIREBASE_URL}/Dashboard/Latest.json", timeout=4)
    if dash_resp.status_code == 200 and dash_resp.json():
        shared_pack = dash_resp.json()
        st.session_state.cached_data = shared_pack.get("data", [])
        last_scan_timestamp = shared_pack.get("time", time.time())
        st.session_state.last_api_call = datetime.datetime.fromtimestamp(last_scan_timestamp, IST)
    else:
        if 'cached_data' not in st.session_state: st.session_state.cached_data = []
except:
    if 'cached_data' not in st.session_state: st.session_state.cached_data = []

@st.cache_data(ttl=60)
def fetch_chart_history_raw(prefix):
    try:
        r = requests.get(f'{FIREBASE_URL}/ChartHistory.json?orderBy="$key"&limitToLast=100', timeout=10)
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
st.session_state.chart_df = pd.DataFrame(raw_chart_data) if raw_chart_data else pd.DataFrame()

dynamic_symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
if 'cached_data' in st.session_state and st.session_state.cached_data:
    fetched_syms = sorted(list(set([item.get('SYMS', item.get('SYMBOL', '')) for item in st.session_state.cached_data if item.get('SYMS') or item.get('SYMBOL')])))
    if fetched_syms: dynamic_symbols = fetched_syms

# ==========================================
# 3. DIVERGENCE TREND SCANNER LOGIC
# ==========================================
def find_divergence_stocks(chart_df, latest_data_list):
    bullish_list, bearish_list = [], []
    if chart_df is None or chart_df.empty or not latest_data_list:
        return pd.DataFrame(bullish_list), pd.DataFrame(bearish_list)

    latest_lookup = {item.get('SYMS', item.get('SYMBOL', '')): item for item in latest_data_list}
    day_df = chart_df.copy()
    day_df['Date'] = day_df['Date'].astype(str).str.strip()
    day_df = day_df[day_df['Date'] == today_str]

    for sym in day_df['Symbol'].unique():
        sdf = day_df[day_df['Symbol'] == sym].sort_values(by='Time')
        if len(sdf) < 5: continue 

        vol_series = pd.to_numeric(sdf['VOL CPR'], errors='coerce').dropna()
        pcr_series = pd.to_numeric(sdf['OPT PCR'], errors='coerce').dropna()
        ltp_series = pd.to_numeric(sdf['LTP'], errors='coerce').dropna()
        if vol_series.empty or pcr_series.empty or ltp_series.empty: continue

        first_vol, first_pcr, first_ltp = vol_series.iloc[:4].mean(), pcr_series.iloc[:4].mean(), ltp_series.iloc[:4].mean()
        last_vol, last_pcr, last_ltp = vol_series.iloc[-1], pcr_series.iloc[-1], ltp_series.iloc[-1]
        max_vol, min_vol = vol_series.max(), vol_series.min()

        if first_vol == 0 or first_ltp == 0: continue
        if abs((last_ltp - first_ltp) / first_ltp) * 100 > 1.5: continue 

        latest_info = latest_lookup.get(sym, {})
        ce_con, pe_con = float(latest_info.get('CE_CON', 0)), float(latest_info.get('PE_CON', 0))
        chg_pct, curr_opt_pcr, curr_vol_cpr = float(latest_info.get('CHG_%', 0)), float(latest_info.get('O_PCR', 0)), float(latest_info.get('V_CPR', 0))

        if (last_vol > first_vol) and (last_vol >= max_vol * 0.75) and (last_pcr >= first_pcr * 0.90) and (ce_con >= 70):
            bullish_list.append({'SYMBOL': sym, 'CHANGE %': chg_pct, 'OPT PCR': curr_opt_pcr, 'VOL CPR': curr_vol_cpr, 'CE CONTRACT': ce_con})

        if (last_vol < first_vol) and (last_vol <= min_vol * 1.25 if min_vol > 0.1 else last_vol <= 0.5) and (last_pcr <= first_pcr * 1.10) and (pe_con >= 70):
            bearish_list.append({'SYMBOL': sym, 'CHANGE %': chg_pct, 'OPT PCR': curr_opt_pcr, 'VOL CPR': curr_vol_cpr, 'PE CONTRACT': pe_con})

    return pd.DataFrame(bullish_list), pd.DataFrame(bearish_list)

# ==========================================
# 4. TOP CONTROL BAR (SINGLE ROW ALIGNMENT)
# ==========================================
if 'cached_data' in st.session_state and len(st.session_state.cached_data) > 0:
    col_menu, col_tim, col_space, col_tog = st.columns([2, 1.5, 4.5, 2])
    
    with col_menu:
        selected_tab = st.radio("Menu", ["📊 Dash", "📈 CHART", "🚀 TREND"], horizontal=True, label_visibility="collapsed")
        
    ref_time = st.session_state.last_api_call.strftime('%H:%M:%S') if 'last_api_call' in st.session_state else "Waiting..."
    show_pct = True 
    
    with col_tim:
        if selected_tab == "📊 Dash":
            st.markdown(f"<div class='time-box'>⏱️ {ref_time}</div>", unsafe_allow_html=True)
            
    with col_space:
        st.empty() 
        
    with col_tog:
        if selected_tab == "📊 Dash":
            show_pct = st.toggle("SHOW %", value=True)

    st.markdown("<hr style='margin: 8px 0px 15px 0px; border-top: 1px solid #cbd5e1;'>", unsafe_allow_html=True)

    # ==========================================
    # VIEW 1: DASHBOARD
    # ==========================================
    if selected_tab == "📊 Dash":
        # 🔍 STOCK FILTER INPUT FIELD
        search_query = st.text_input("🔍 Search Stock Symbol...", placeholder="Type symbol e.g. NIFTY, RELIANCE...", label_visibility="collapsed")
        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

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
            # Apply search filter if user typed something
            if search_query:
                q = search_query.strip().upper()
                df = df[df['SYMS'].astype(str).str.upper().str.contains(q) | df['SYMBOL'].astype(str).str.upper().str.contains(q)]

            df['Conv_Rank'] = df['CE_CON'].abs() + df['PE_CON'].abs()
            df = df.sort_values(by='Conv_Rank', ascending=False)
            df['VOL CHECKER'] = df['VOL_PCT'] if show_pct else df['VOL_ABS']
            df['PCR CHECKER'] = df['PCR_PCT'] if show_pct else df['PCR_ABS']
            df = df[['SYMS', 'OPEN_STATUS', 'V_PCR', 'O_PCR', 'V_CPR', 'LTP_CH', 'CHG_%', 'LTP', 'CE_CON', 'PE_CON', 'PCR CHECKER', 'VOL CHECKER']]
            
            df = df.rename(columns={
                'SYMS': 'SYMBOL ↕', 'OPEN_STATUS': 'OPENING ↕', 'V_PCR': 'VOL PCR ↕', 
                'O_PCR': 'OPTION PCR ↕', 'V_CPR': 'VOL CPR ↕', 'LTP_CH': 'LTP CHANGE ↕', 
                'CHG_%': 'CHANGE % ↕', 'LTP': 'LTP ↕', 'CE_CON': 'CE CONTRACT ↕', 
                'PE_CON': 'PE CONTRACT ↕', 'PCR CHECKER': 'PCR CHECKER ↕', 'VOL CHECKER': 'VOL CHECKER ↕'
            })

            df['OPENING ↕'] = df['OPENING ↕'].apply(color_open)
            df['LTP CHANGE ↕'] = df['LTP CHANGE ↕'].apply(lambda x: color_num(x, False))
            df['CHANGE % ↕'] = df['CHANGE % ↕'].apply(lambda x: color_num(x, True))
            df['CE CONTRACT ↕'] = df['CE CONTRACT ↕'].apply(lambda x: color_num(x, True))
            df['PE CONTRACT ↕'] = df['PE CONTRACT ↕'].apply(lambda x: color_num(x, True))
            df['PCR CHECKER ↕'] = df['PCR CHECKER ↕'].apply(lambda x: color_num(x, show_pct))
            df['VOL CHECKER ↕'] = df['VOL CHECKER ↕'].apply(lambda x: color_num(x, show_pct))
            df['VOL PCR ↕'] = df['VOL PCR ↕'].apply(color_pcr)
            df['OPTION PCR ↕'] = df['OPTION PCR ↕'].apply(color_pcr)
            df['VOL CPR ↕'] = df['VOL CPR ↕'].apply(color_pcr)
            df['LTP ↕'] = df['LTP ↕'].apply(format_ltp)
            
            html_table = df.to_html(escape=False, index=False, classes="dataframe")
            
            full_interactive_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {{ margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: transparent; }}
                .table-wrapper {{ height: 710px; overflow: auto; border-radius: 6px; border: 1px solid #cbd5e1; }}
                table.dataframe {{ width: 100%; border-collapse: collapse; font-size: 12px; background-color: #ffffff; color: #000000; }}
                table.dataframe th {{ 
                    background-color: #172554 !important; color: white !important; font-weight: bold !important; text-align: center !important; 
                    padding: 9px 4px !important; position: sticky; top: 0; z-index: 10; border: 1px solid rgba(255,255,255,0.2);
                    cursor: pointer; user-select: none; transition: background 0.2s;
                }}
                table.dataframe th:hover {{ background-color: #0000cc !important; }}
                table.dataframe td {{ 
                    text-align: center !important; padding: 7px 4px !important; 
                    border-bottom: 1px solid rgba(128,128,128,0.2); border-right: 1px solid rgba(128,128,128,0.1); font-weight: bold; 
                }}
                table.dataframe tr:hover {{ background-color: rgba(59, 130, 246, 0.06); }}
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

                        table.querySelectorAll('th').forEach(el => {{
                            el.innerHTML = el.innerHTML.replace(/ ▲| ▼/g, ' ↕');
                        }});
                        th.innerHTML = th.innerHTML.replace(/ ↕| ▲| ▼/g, '') + (asc ? ' ▲' : ' ▼');

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
            components.html(full_interactive_html, height=730, scrolling=False)

    # ==========================================
    # VIEW 2: CHART VIEW
    # ==========================================
    elif selected_tab == "📈 CHART":
        col_c1, col_c2 = st.columns([2, 2])
        with col_c1: 
            sel_stock = st.selectbox("Stock:", dynamic_symbols, index=0, label_visibility="collapsed")
        with col_c2: 
            chart_mode = st.radio("View:", ["Vol CPR", "OPT PCR"], horizontal=True, label_visibility="collapsed")

        chart_df = st.session_state.get('chart_df', pd.DataFrame())
        if not chart_df.empty and sel_stock:
            df_sym = chart_df[(chart_df['Date'].astype(str).str.strip() == today_str) & (chart_df['Symbol'].astype(str).str.strip() == sel_stock)].copy()
            if not df_sym.empty:
                df_sym = df_sym.sort_values(by='Time')
                target_col = 'VOL CPR' if chart_mode == "Vol CPR" else 'OPT PCR'
                ind_color = "#FF4D4D" if chart_mode == "Vol CPR" else "#00BFFF"
                
                time_list = df_sym['Time'].tolist()
                ind_list = pd.to_numeric(df_sym[target_col], errors='coerce').fillna(0).tolist()
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
                        #custom-reset-btn {{ position: absolute; top: 5px; left: 10px; z-index: 9999; background: #2962FF; border: none; border-radius: 4px; padding: 5px 12px; font-size: 11px; font-weight: bold; color: #fff; cursor: pointer; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }}
                        .slider-wrapper {{ padding: 0px 25px; margin-top: -10px; position: relative; }}
                        .time-labels {{ display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #888; margin-bottom: 8px; }}
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
                        var dataIndicator = {json.dumps(ind_list)}; 
                        var dataLTP = {json.dumps(ltp_list)}; 
                        var timeCats = {json.dumps(time_list)}; 
                        
                        var optionsMain = {{
                            series: [{{ name: '{chart_mode}', type: 'area', data: dataIndicator }}, {{ name: 'LTP', type: 'line', data: dataLTP }}],
                            chart: {{ id: 'mainChart', height: 410, type: 'line', toolbar: {{ show: false }}, zoom: {{ enabled: false }}, animations: {{ enabled: false }} }},
                            colors: ['{ind_color}', '#00CC66'], 
                            stroke: {{ curve: 'smooth', width: [3, 3] }}, 
                            fill: {{ type: ['gradient', 'solid'], gradient: {{ shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.05, stops: [0, 100] }} }},
                            dataLabels: {{ enabled: false }}, 
                            xaxis: {{ categories: timeCats, tickAmount: 10, labels: {{ style: {{ colors: '#888' }} }}, tooltip: {{ enabled: false }} }},
                            yaxis: [
                                {{ title: {{ text: '{chart_mode}', style: {{ color: '{ind_color}' }} }}, labels: {{ style: {{ colors: '{ind_color}' }} }}, decimalsInFloat: 2 }}, 
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
                            slider.noUiSlider.on('update', function (values) {{
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
                components.html(apex_html, height=500, width=None)
        else:
            st.info("⏳ Waiting for chart data...")

    # ==========================================
    # VIEW 3: TREND VIEW
    # ==========================================
    elif selected_tab == "🚀 TREND":
        st.markdown("<h3 style='margin-top:0; color:#0284c7;'>🚀 Divergence Trend Scanner</h3>", unsafe_allow_html=True)
        chart_df = st.session_state.get('chart_df', pd.DataFrame())
        latest_data = st.session_state.get('cached_data', [])
        
        df_bullish, df_bearish = find_divergence_stocks(chart_df, latest_data)

        def generate_trend_html(df, tab_type="Bullish"):
            if df.empty: return "<div style='text-align:center; padding: 25px; font-weight:bold; color: #64748b;'>⏳ Koi data match nahi hua.</div>"
            df = df.copy()

            def fmt_pct(v):
                try:
                    val = float(v)
                    color = "#00AA00" if val >= 0 else "#FF0000"
                    return f"<span style='color:{color}; font-weight:bold;'>{val:+.2f}%</span>"
                except: return str(v)

            def fmt_pcr(v):
                try:
                    val = float(v)
                    color = "#00AA00" if val >= 1.0 else "#FF0000"
                    return f"<span style='color:{color}; font-weight:bold;'>{val:.2f}</span>"
                except: return str(v)

            def fmt_contract(v):
                try:
                    val = float(v)
                    color = "#00AA00" if val >= 70 else ("#FF0000" if val <= -70 else "#888888")
                    return f"<span style='color:{color}; font-weight:bold;'>{val:+.1f}%</span>"
                except: return str(v)
            
            df['CHANGE %'] = df['CHANGE %'].apply(fmt_pct)
            df['OPT PCR'] = df['OPT PCR'].apply(fmt_pcr)  
            df['VOL CPR'] = df['VOL CPR'].apply(fmt_pcr)
            
            if tab_type == "Bullish":
                df['CE CONTRACT'] = df['CE CONTRACT'].apply(fmt_contract)
                head_color = "#16a34a" 
            else:
                df['PE CONTRACT'] = df['PE CONTRACT'].apply(fmt_contract)
                head_color = "#dc2626" 
                
            html_content = df.to_html(escape=False, index=False, classes="dataframe")
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                body {{ margin: 0; padding: 0; font-family: 'Segoe UI', sans-serif; background-color: transparent; }}
                table.dataframe {{ width: 100%; border-collapse: collapse; font-size: 13px; background-color: #ffffff; color: #000000; }}
                table.dataframe th {{ background-color: {head_color} !important; color: white !important; font-weight: bold !important; text-align: center !important; padding: 9px 6px !important; border: 1px solid rgba(255,255,255,0.2); position: sticky; top: 0; z-index: 10; }}
                table.dataframe td {{ text-align: center !important; padding: 8px 6px !important; border-bottom: 1px solid rgba(128,128,128,0.2); border-right: 1px solid rgba(128,128,128,0.1); font-weight: bold; }}
                table.dataframe tr:hover {{ background-color: rgba(59, 130, 246, 0.06); }}
            </style>
            </head>
            <body>
                <div style="height: 550px; overflow: auto; border-radius: 6px; border: 1px solid #cbd5e1;">
                    {html_content}
                </div>
            </body>
            </html>
            """

        tab_bullish, tab_bearish = st.tabs(["🟢 Bullish Stocks", "🔴 Bearish Stocks"])
        with tab_bullish:
            st.markdown("<div style='font-size:12px; color:#475569; margin-bottom:8px;'><b>Logic:</b> Vol CPR Rising | OPT PCR Flat/Rising | CE >= 70%</div>", unsafe_allow_html=True)
            if not df_bullish.empty:
                df_bullish = df_bullish.sort_values(by='CE CONTRACT', ascending=False)
            components.html(generate_trend_html(df_bullish, "Bullish"), height=610, scrolling=True)

        with tab_bearish:
            st.markdown("<div style='font-size:12px; color:#475569; margin-bottom:8px;'><b>Logic:</b> Vol CPR Falling | OPT PCR Flat/Falling | PE >= 70%</div>", unsafe_allow_html=True)
            if not df_bearish.empty:
                df_bearish = df_bearish.sort_values(by='PE CONTRACT', ascending=False)
            components.html(generate_trend_html(df_bearish, "Bearish"), height=610, scrolling=True)

else:
    st.info("⏳ Booting up... Waiting for Engine to push data.")
