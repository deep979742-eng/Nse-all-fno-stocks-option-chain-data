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
.block-container { padding-top: 4rem !important; padding-bottom: 1rem !important; padding-left: 1rem !important; padding-right: 1rem !important; } 
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
    .block-container { padding-top: 4rem !important; padding-left: 0.1rem !important; padding-right: 0.1rem !important; } 
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
# 3. STOCK LIST & HELPER FUNCTIONS
# ==========================================
raw_symbols = [
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIENT", "ADANIGREEN", 
    "ADANIPORTS", "ADANIPOWER", "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP", "ASHOKLEY", "ASIANPAINT", 
    "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK", "BAJA
