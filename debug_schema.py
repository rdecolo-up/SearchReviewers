import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import toml
import pandas as pd

# Load secrets
try:
    secrets = toml.load("reviewer_matcher_app/.streamlit/secrets.toml")
except Exception as e:
    exit()

def print_schema(name, sheet_id, creds):
    print(f"\n--- Schema for {name} ---")
    try:
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        
        # Try to guess the sheet
        try:
            ws = sh.worksheet("APUNTES")
        except:
             try:
                 ws = sh.worksheet("Articulos")
             except:
                 ws = sh.get_worksheet(0)
        
        print(f"Worksheet: {ws.title}")
        
        # Get first records
        records = ws.get_all_records()
        if records:
            df = pd.DataFrame(records)
            print("Columns Found:")
            print(df.columns.tolist())
            print("\nFirst Row Sample:")
            print(df.iloc[0].to_dict())
        else:
            print("⚠️ Sheet appears empty.")
            
    except Exception as e:
        print(f"❌ FAILED: {repr(e)}")

# Setup Credentials
creds_dict = json.loads(secrets["GOOGLE_SHEETS_CREDENTIALS"])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

print_schema("EVALUADORES", secrets["SHEET_ID_EVALUADORES"], creds)
