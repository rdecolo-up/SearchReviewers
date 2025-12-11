import gspread
from google.oauth2.service_account import Credentials
import json
import toml
import pandas as pd

# Load secrets
try:
    secrets = toml.load("reviewer_matcher_app/.streamlit/secrets.toml")
except:
    print("Error loading secrets")
    exit()

def inspect_sheet(sheet_id):
    try:
        creds_dict = json.loads(secrets["GOOGLE_SHEETS_CREDENTIALS"])
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        sh = client.open_by_key(sheet_id)
        ws = sh.worksheet("APUNTES")
        
        print(f"✅ Sheet Open: {ws.title}")
        header = ws.row_values(1)
        print(f"📌 Columns: {header}")
        
        # Print first row just in case
        first_row = ws.row_values(2)
        print(f"📝 First Row Data: {first_row}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

inspect_sheet(secrets["SHEET_ID_ARTICULOS"])
