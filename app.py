import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import urllib.parse
import requests

# --- CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Academic Reviewer Matcher", layout="wide")

# Function to get verification links
def get_verification_links(name, institution):
    query_scholar = urllib.parse.quote(f"{name} {institution}")
    query_orcid = urllib.parse.quote(f"{name}")
    
    link_scholar = f"https://scholar.google.com/scholar?q={query_scholar}"
    link_orcid = f"https://orcid.org/orcid-search/search?searchQuery={query_orcid}"
    link_linkedin = f"https://www.linkedin.com/search/results/all/?keywords={urllib.parse.quote(name)}"
    
    return link_scholar, link_orcid, link_linkedin

# --- CONNECTIVITY FUNCTIONS ---

import traceback

# --- CONNECTIVITY FUNCTIONS ---

def get_google_sheet_client():
    try:
        # Load credentials from secrets or local file
        if "GOOGLE_SHEETS_CREDENTIALS" in st.secrets:
            creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
        else:
            # Fallback for local dev
            with open("credentials.json") as f:
                creds_dict = json.load(f)
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        st.code(traceback.format_exc())
        return None

def call_gemini_api(api_key, system_instruction, user_prompt):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        # Construct payload with system instruction properly
        full_prompt = f"{system_instruction}\n\n{user_prompt}"
        
        data = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        # Extract text
        return result['candidates'][0]['content']['parts'][0]['text']
        
    except Exception as e:
        st.error(f"Error calling Gemini API: {e}")
        return None

# --- DATA HANDLING ---

@st.cache_data(ttl=600)
def load_evaluadores(sheet_id):
    try:
        client = get_google_sheet_client()
        if not client: return None
        sh = client.open_by_key(sheet_id)
        # Try explicit names: UPPERCASE (new), CamelCase (old), or explicit index if needed.
        for name in ["EVALUADORES", "Evaluadores"]:
            try:
                worksheet = sh.worksheet(name)
                break
            except:
                continue
        else:
             worksheet = sh.get_worksheet(1) # Fallback to 2nd sheet
            
        df = pd.DataFrame(worksheet.get_all_records())
        return df
    except Exception as e:
        st.error(f"Error loading Evaluadores: {e}")
        return None

def fetch_article_details(sheet_id, article_id_query):
    try:
        client = get_google_sheet_client()
        if not client: return None
        sh = client.open_by_key(sheet_id)
        try:
            worksheet = sh.worksheet("APUNTES")
        except:
            try:
                worksheet = sh.worksheet("Articulos")
            except:
                worksheet = sh.get_worksheet(0)
            
        # Use get_all_values for robustness against header issues
        data = worksheet.get_all_values()
        if not data: return None
        
        headers = [h.strip() for h in data[0]] # Normalize headers
        rows = data[1:]
        
        df = pd.DataFrame(rows, columns=headers)
        
        # Check if ID exists
        if "ID" not in df.columns:
            st.error(f"Column 'ID' not found in sheet. Available columns: {df.columns.tolist()}")
            return None
            
        # Ensure ID is string for comparison
        df['ID'] = df['ID'].astype(str)
        article_row = df[df['ID'] == str(article_id_query)]
        
        if not article_row.empty:
            row_data = article_row.iloc[0].to_dict()
            # Normalize keys to simple ones for the app
            return {
                "Titulo": row_data.get("Título", ""),
                "Abstract": row_data.get("Resumen", "") or row_data.get("Palabras clave", "") or "Abstract not available in sheet. Context based on Title/Keywords."
            }
        return None
    except Exception as e:
        st.error(f"Error fetching article: {repr(e)}")
        st.code(traceback.format_exc())
        return None

def get_active_worksheet(sheet_id):
    """Get fresh worksheet object for writing, utilizing cached client resource"""
    try:
        client = get_google_sheet_client()
        if not client: return None
        sh = client.open_by_key(sheet_id)
        # Try explicit names for writing
        for name in ["EVALUADORES", "Evaluadores"]:
            try:
                worksheet = sh.worksheet(name)
                break
            except:
                continue
        else:
            worksheet = sh.get_worksheet(1)
        return worksheet
    except Exception as e:
        st.error(f"Error connecting to write: {e}")
        return None

def append_to_sheet(worksheet, new_rows_df):
    try:
        values = new_rows_df.values.tolist()
        worksheet.append_rows(values)
        return True
    except Exception as e:
        st.error(f"Error appending rows: {e}")
        return False

# --- UI & LOGIC ---

st.title("🎓 Academic Reviewer Matcher")
st.markdown("Automated matching and verified suggestions for peer review.")

# Sidebar
st.sidebar.header("Configuration")

# Load IDs from secrets (Auto-configured)
sheet_id_articulos = st.secrets.get("SHEET_ID_ARTICULOS", "")
sheet_id_evaluadores = st.secrets.get("SHEET_ID_EVALUADORES", "")
api_key = st.secrets.get("GEMINI_API_KEY", "")

if not sheet_id_articulos or not sheet_id_evaluadores or not api_key:
    st.error("Missing Sheet IDs or API Key in secrets.toml")
    st.stop()

mode = st.sidebar.radio("Search Mode", ["By Article ID", "By Keywords/Abstract"])

target_article_context = ""
context_title = ""

if mode == "By Article ID":
    article_id_input = st.sidebar.text_input("Enter Article ID (e.g., 2746)")
    if article_id_input:
        with st.spinner(f"Fetching Article {article_id_input}..."):
            article_data = fetch_article_details(sheet_id_articulos, article_id_input)
            if article_data:
                st.sidebar.success("Article Found!")
                context_title = article_data.get('Titulo', 'Unknown Title')
                abstract = article_data.get('Resumen', article_data.get('Abstract', 'No abstract'))
                target_article_context = f"TITLE: {context_title}\nABSTRACT: {abstract}"
                st.info(f"**Analyzing:** {context_title}")
                with st.expander("View Abstract"):
                    st.write(abstract)
            else:
                st.sidebar.error("Article ID not found.")
else:
    st.sidebar.markdown("### Manual Entry")
    m_title = st.sidebar.text_input("Article Title")
    m_keywords = st.sidebar.text_area("Keywords", height=70)
    m_abstract = st.sidebar.text_area("Abstract", height=150)
    
    components = []
    if m_title: components.append(f"TITLE: {m_title}")
    if m_keywords: components.append(f"KEYWORDS: {m_keywords}")
    if m_abstract: components.append(f"ABSTRACT: {m_abstract}")
    
    target_article_context = "\n\n".join(components)

prioritize_latam = st.sidebar.checkbox("Prioritize LatAm Experts", value=True)
run_btn = st.sidebar.button("🔍 Find Reviewers")

# Main Logic
# Initialize Session State
if 'search_results' not in st.session_state:
    st.session_state['search_results'] = None

# If button pressed, run search
if run_btn and target_article_context:
    
    with st.spinner("Loading reviewer database..."):
        df_evaluadores = load_evaluadores(sheet_id_evaluadores)
        
        if df_evaluadores is not None:
            evaluadores_str = df_evaluadores.to_string(index=False)
            
            # --- PROMPT ---
            system_instruction = """
            You are an Expert Academic Editor. Your goal is to identify the best peer reviewers for a scientific article.
            
            **Process (Chain of Thought):**
            1.  **Analyze**: Extract the core topics, methodology, and regional focus from the INPUT.
            2.  **Internal Match**: Search the provided 'REGISTERED REVIEWERS' list for the best matches. Explain why they fit.
            3.  **External Search Simulation**: Suggest 3 NEW reviewers who are NOT in the list.
                *   **CRITICAL**: Prioritize experts from Latin American institutions (Universities in Chile, Mexico, Colombia, Argentina, etc.) if the 'Prioritize LatAm' flag is True.
                *   **Focus**: Look for recent authors in high-impact journals on these specific topics.
                *   **Verification**: Ensure they are real, active researchers.
                *   **Email**: Try to INFER the institutional email pattern (e.g., if you know they are at UNAM, suggested format name.surname@nam.mx) or explicitly state "Search Required".
            
            **Output Format**:
            Provide a JSON object with two keys:
            1.  "internal_matches": List of objects {Name, Institution, Reason}
            2.  "external_suggestions": List of objects with these EXACT keys: {Nombre, Apellidos, Correo, Afiliación, País, Scholar, OrcId, Temas, Reason}
                *   For 'Correo', provide a likely professional email.
                *   For 'Scholar' and 'OrcId', put "Search required".
            """
            
            user_prompt = f"""
            INPUT CONTEXT: "{target_article_context}"
            PRIORITIZE LATAM: {prioritize_latam}
            
            REGISTERED REVIEWERS DATABASE (Sample/Context):
            {evaluadores_str}
            """
            
            with st.spinner("🤖 Gemini is analyzing matches and finding experts..."):
                response_text = call_gemini_api(api_key, system_instruction, user_prompt)
            
            if response_text:
                try:
                    json_str = response_text.replace("```json", "").replace("```", "")
                    st.session_state['search_results'] = json.loads(json_str)
                    st.success("Analysis Complete!")
                except Exception as e:
                    st.error(f"Error parsing AI response: {e}")
                    st.text(response_text)

# Display Results (Persistent)
if st.session_state['search_results']:
    results = st.session_state['search_results']
    
    tab1, tab2 = st.tabs(["🏛️ Internal Matches", "🌎 External Suggestions (New)"])
    
    with tab1:
        if results.get("internal_matches"):
            st.table(pd.DataFrame(results["internal_matches"]))
        else:
            st.info("No strong internal matches found.")
            
    with tab2:
        externals = results.get("external_suggestions", [])
        if externals:
            st.info("Select candidates to add to the database:")
            
            df_externals = pd.DataFrame(externals)
            
            with st.form("add_reviewers_form"):
                selected_indices = []
                for i, row in df_externals.iterrows():
                    # Added column for Email (cols[2])
                    cols = st.columns([0.05, 0.2, 0.2, 0.2, 0.15, 0.1, 0.1])
                    with cols[0]:
                        if st.checkbox("", key=f"select_{i}"):
                            selected_indices.append(i)
                    with cols[1]:
                        st.write(f"**{row['Nombre']} {row['Apellidos']}**")
                    with cols[2]:
                        st.caption(f"📧 {row.get('Correo', 'N/A')}")
                    with cols[3]:
                        st.write(row['Afiliación'])
                    with cols[4]:
                        st.write(row['Temas'])
                    with cols[5]:
                        st.write(row['País'])
                    with cols[6]:
                        s_link, o_link, _ = get_verification_links(f"{row['Nombre']} {row['Apellidos']}", row['Afiliación'])
                        st.markdown(f"[🔎 Scholar]({s_link})")
                        st.markdown(f"[🆔 ORCID]({o_link})")
                    st.divider()
                
                submitted = st.form_submit_button("➕ Add Selected to Database")
                
                if submitted:
                    if selected_indices:
                        # Filter selected rows
                        rows_to_add = df_externals.iloc[selected_indices].drop(columns=['Reason'], errors='ignore')
                        
                        target_columns = ["ID Artículo", "Nombre", "Apellidos", "Correo electrónico", "Afiliación institucional", "País", "Google Scholar", "OrcId", "Temas"]
                        
                        rows_prepared = pd.DataFrame()
                         # Use Article ID if known
                        current_id_val = article_id_input if mode == "By Article ID" and 'article_id_input' in locals() and article_id_input else ""
                        
                        rows_prepared["ID Artículo"] = [current_id_val] * len(rows_to_add)
                        rows_prepared["Nombre"] = rows_to_add["Nombre"]
                        rows_prepared["Apellidos"] = rows_to_add["Apellidos"]
                        rows_prepared["Correo electrónico"] = rows_to_add["Correo"]
                        rows_prepared["Afiliación institucional"] = rows_to_add["Afiliación"]
                        rows_prepared["País"] = rows_to_add["País"]
                        
                        # Generate clickable links for the database
                        scholar_links = []
                        orcid_links = []
                        
                        for _, row in rows_to_add.iterrows():
                            s_link, o_link, _ = get_verification_links(f"{row['Nombre']} {row['Apellidos']}", row['Afiliación'])
                            scholar_links.append(s_link)
                            orcid_links.append(o_link)
                            
                        rows_prepared["Google Scholar"] = scholar_links
                        rows_prepared["OrcId"] = orcid_links
                        rows_prepared["Temas"] = rows_to_add["Temas"]
                        
                        # Get fresh worksheet object for writing
                        ws_to_append = get_active_worksheet(sheet_id_evaluadores)

                        # Append
                        if ws_to_append and append_to_sheet(ws_to_append, rows_prepared):
                            load_evaluadores.clear()
                            st.success(f"✅ Added {len(rows_prepared)} reviewers to the database!")
                            st.balloons()
                    else:
                        st.warning("Please select at least one reviewer.")
        else:
            st.warning("AI could not generate external suggestions.")
