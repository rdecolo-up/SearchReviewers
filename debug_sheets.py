import gspread
from google.oauth2.service_account import Credentials
import json
import toml

# Load secrets
try:
    secrets = toml.load("reviewer_matcher_app/.streamlit/secrets.toml")
    print("✅ Loaded secrets.toml")
except Exception as e:
    print(f"❌ Could not load secrets: {e}")
    exit()

def test_sheet(name, sheet_id, creds):
    print(f"\n--- Testing {name} ({sheet_id}) ---")
    try:
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        print(f"✅ Connection Successful to '{sh.title}'")
        
        print("   Available Worksheets:")
        for ws in sh.worksheets():
            print(f"   - {ws.title}")
            
    except Exception as e:
        print(f"❌ FAILED: {repr(e)}")

# Setup Credentials
try:
    creds_dict = json.loads(secrets["GOOGLE_SHEETS_CREDENTIALS"])
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    print("✅ Credentials Object Created")
    print(f"   Service Email: {creds_dict['client_email']}")
except Exception as e:
    print(f"❌ Error parsing JSON credentials: {e}")
    exit()

# Run Tests (checking the single ID for both intended uses)
test_sheet("MAIN SPREADSHEET", secrets["SHEET_ID_ARTICULOS"], creds)

