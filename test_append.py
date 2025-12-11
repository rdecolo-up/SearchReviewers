import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import toml
import pandas as pd

# Load secrets
try:
    secrets = toml.load("reviewer_matcher_app/.streamlit/secrets.toml")
    print("✅ Loaded secrets.toml")
except Exception as e:
    print(f"❌ Could not load secrets: {e}")
    exit()

def test_append_row(sheet_id, creds):
    print(f"\n--- Testing Append to Evaluadores ({sheet_id}) ---")
    try:
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        
        try:
            ws = sh.worksheet("Evaluadores")
        except:
             # Fallback logic mirroring app.py
             print("   ⚠️ 'Evaluadores' sheet not found by name, trying index 0...")
             ws = sh.get_worksheet(0)
        
        print(f"   Target Worksheet: {ws.title}")
        
        # Create a test row matching schema:
        # ["ID Artículo", "Nombre", "Apellidos", "Correo electrónico", "LinkedIn", "Afiliación institucional", "País", "Google Scholar", "OrcId", "Temas"]
        test_row = [
            "TEST_AUTO", 
            "Juan", 
            "PruebaBot", 
            "test@example.com", 
            "n/a", 
            "Universidad de Prueba", 
            "Testland", 
            "http://google.com", 
            "0000-0000-TEST", 
            "Inteligencia Artificial"
        ]
        
        print(f"   Attempting to append: {test_row}")
        result = ws.append_row(test_row)
        
        print("✅ SUCCESS! Row appended.")
        print(f"   Updated Range: {result.get('updates', {}).get('updatedRange')}")
        print("   👉 Please check your Google Sheet to see the new row at the bottom.")
            
    except Exception as e:
        print(f"❌ FAILED: {repr(e)}")


# Setup Credentials
try:
    creds_dict = json.loads(secrets["GOOGLE_SHEETS_CREDENTIALS"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    test_append_row(secrets["SHEET_ID_EVALUADORES"], creds)

except Exception as e:
    print(f"❌ Credential Error: {e}")
