import requests
import toml

try:
    secrets = toml.load(".streamlit/secrets.toml")
    api_key = secrets["GEMINI_API_KEY"]
except Exception as e:
    print(f"❌ Error loading secrets: {e}")
    exit()

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("Available Gemini Models:")
        for m in models:
            if "gemini" in m['name']:
                print(f" - {m['name']}")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

except Exception as e:
    print(f"❌ Connection Failed: {e}")
