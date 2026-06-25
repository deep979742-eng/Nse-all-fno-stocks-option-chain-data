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

CLIENT_ID = "YD02909"
APP_ID = "I0QMW3KFAW-100"
SECRET_ID = "T63F5XCUSH"
REDIRECT_URI = "https://www.google.com/" 
st.set_page_config(page_title="F&O Dashboard", layout="wide")

css_str = """<style>
[data-testid='stAppViewContainer'], [data-testid='stHeader'], [data-testid='stSidebar'] { opacity: 1 !important; }
.block-container { padding-top: 3.5rem !important; }
@media (max-width: 768px) { .block-container { padding-top: 1rem !important; } }
</style>"""
st.markdown(css_str, unsafe_allow_html=True)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
today_str = datetime.datetime.now(IST).strftime("%Y-%m-%d")
HISTORY_FILE, TOKEN_STORE_FILE = "chart_history.csv", "fyers_token_store.json"
AUTO_SAVE_FILE, SHARED_LIVE_DATA_FILE = "auto_save_tracker.txt", "shared_live_data.json"
