import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

# ==========================================
# 1. GOOGLE SHEET SETUP & CONNECTION
# ==========================================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# DHYAN DEIN: Agar aapne GitHub secrets mein file ka naam kuch aur rakha hai toh yahan badal lein
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# DHYAN DEIN: Yahan apni Google Sheet ka exact naam likhein
SHEET_NAME = "Aapki_Google_Sheet_Ka_Naam" 
sheet = client.open(SHEET_NAME)
print("Google Sheet se successfully connect ho gaye hain...")

# ==========================================
# 2. TAB CREATION & CLEANUP (Purana data saaf karna)
# ==========================================
existing_tabs = [ws.title for ws in sheet.worksheets()]

# Live_Data Tab Setup
if "Live_Data" not in existing_tabs:
    live_sheet = sheet.add_worksheet(title="Live_Data", rows="1000", cols="10")
else:
    live_sheet = sheet.worksheet("Live_Data")

# Har baar jab code chalega, purana live data saaf hoga taaki fresh data dikhe
live_sheet.clear() 
live_sheet.append_row(["Contract Name", "LTP", "Change %", "Volume", "CPR"])

# Price_Lock Tab Setup
if "Price_Lock" not in existing_tabs:
    lock_sheet = sheet.add_worksheet(title="Price_Lock", rows="100", cols="5")
    lock_sheet.append_row(["Date", "Locked_CE_LTP", "Locked_PE_LTP"])
else:
    lock_sheet = sheet.worksheet("Price_Lock")

# ==========================================
# 3. PRICE LOCK LOGIC
# ==========================================
today_date = datetime.now().strftime('%Y-%m-%d')

def get_or_set_price_lock(live_ce, live_pe):
    lock_data = lock_sheet.get_all_records()
    
    # Agar aaj ka din sheet mein hai, toh purana lock price uthao
    if len(lock_data) > 0 and str(lock_data[0].get('Date')) == today_date:
        locked_ce = float(lock_data[0].get('Locked_CE_LTP', live_ce))
        locked_pe = float(lock_data[0].get('Locked_PE_LTP', live_pe))
        print("Aaj ka price pehle se lock hai. Sheet se read kar liya.")
        return locked_ce, locked_pe
    else:
        # Naya din hai, sheet saaf karo aur aaj ka opening price daal do
        print("Naya din! Aaj ka price lock kar rahe hain...")
        lock_sheet.clear()
        lock_sheet.append_row(["Date", "Locked_CE_LTP", "Locked_PE_LTP"])
        lock_sheet.append_row([today_date, live_ce, live_pe])
        return live_ce, live_pe

# ==========================================
# 4. BROKER DATA & MAIN EXECUTION
# ==========================================
def main():
    try:
        # -----------------------------------------------------------------
        # YAHAN AAPKO APNE BROKER (Shoonya/Zerodha) KA CODE DAALNA HAI
        # Taki LTP, Vol, aur CPR ki values real live market se aayein.
        # Abhi test karne ke liye maine dummy (nakli) values daali hain.
        # -----------------------------------------------------------------
        
        # Man lijiye aapke broker se yeh data aaya:
        ce_contract = "NIFTY CE"
        ce_live_ltp = 150.50
        ce_vol = 120000
        ce_cpr = 24500.50
        
        pe_contract = "NIFTY PE"
        pe_live_ltp = 130.20
        pe_vol = 95000
        pe_cpr = 24500.50
        
        # 1. Price check aur lock karo
        locked_ce, locked_pe = get_or_set_price_lock(ce_live_ltp, pe_live_ltp)
        
        # 2. Change % Calculate karo (Lock price ke muqable kitna upar/niche)
        ce_change_pct = ((ce_live_ltp - locked_ce) / locked_ce) * 100 if locked_ce > 0 else 0
        pe_change_pct = ((pe_live_ltp - locked_pe) / locked_pe) * 100 if locked_pe > 0 else 0
        
        time.sleep(1) # API lag se bachne ke liye thoda wait
        
        # 3. Live_Data Tab mein CE aur PE ki lines add karo
        live_sheet.append_row([ce_contract, ce_live_ltp, f"{round(ce_change_pct, 2)}%", ce_vol, ce_cpr])
        live_sheet.append_row([pe_contract, pe_live_ltp, f"{round(pe_change_pct, 2)}%", pe_vol, pe_cpr])
        
        print("Success! Live Data aur Lock Data dono G-Sheet par update ho gaye hain.")
        
    except Exception as e:
        print(f"Code mein koi error aaya hai: {e}")

# Script run karne ka command
if __name__ == "__main__":
    main()
