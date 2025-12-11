import requests
import toml

try:
    secrets = toml.load("reviewer_matcher_app/.streamlit/secrets.toml")
    api_key = secrets["GEMINI_API_KEY"]
except Exception as e:
    print(f"❌ Error loading secrets: {e}")
    exit()

print(f"🔑 Testing API Key: {api_key[:5]}...{api_key[-5:]}")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url)
    if response.status_code == 200:
        print("✅ API Key is Valid! Connection Successful.\n")
        models = response.json().get('models', [])
        print("Available Models:")
        for m in models:
            if "gemini" in m['name']:
                print(f" - {m['name']}")
                if "generateContent" in m.get('supportedGenerationMethods', []):
                    print(f"   (Supports generateContent) ✅")
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

except Exception as e:
    print(f"❌ Connection Failed: {e}")
