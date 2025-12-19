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

import time

def call_gemini_api(api_key, system_instruction, user_prompt, model_name="gemini-1.5-flash"):
    max_retries = 3
    base_delay = 4 # Increased delay
    
    for attempt in range(max_retries):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
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
            
            # Handle Rate Limits (429) specifically
            if response.status_code == 429:
                sleep_time = base_delay * (2 ** attempt)
                st.warning(f"⚠️ Tráfico alto (429). Esperando {sleep_time}s... (Intento {attempt + 1}/{max_retries})")
                time.sleep(sleep_time)
                continue # Retry
                
            response.raise_for_status()
            
            result = response.json()
            # Extract text
            return result['candidates'][0]['content']['parts'][0]['text']
            
        except Exception as e:
            if attempt == max_retries - 1: # Last attempt
                st.error(f"🔴 GEMINI FAIL (Final): {e}")
                return None
            else:
                # Check if it was a 429 that somehow slipped through (shouldn't happen with logic above)
                # or a network error we want to retry
                st.warning(f"⚠️ API Error (Retrying): {e}")
                time.sleep(2) # Short sleep for non-429 errors
                continue
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

@st.cache_data(ttl=600)
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
                "Resumen": row_data.get("Resumen", ""),
                "Palabras clave": row_data.get("Palabras clave", ""),
                "Autores": row_data.get("Autores", ""),
                "Link": row_data.get("Enlace archivo", row_data.get("Link", row_data.get("URL", "")))
            }
        return None
    except Exception as e:
        st.error(f"Error fetching article: {repr(e)}")
        st.code(traceback.format_exc())
        return None

@st.cache_data(ttl=3600)
def verify_article_integrity(api_key, author_name, title, abstract, keywords, model_name):
    """
    Uses Gemini to verify:
    1. If the author is likely an Undergraduate Student.
    2. If the article appears to be previously published.
    """
    try:
        system_instruction = """
        Eres un asistente de integridad académica. Tu tarea es analizar los metadatos de un artículo y su autor para detectar posibles problemas y evaluar la solidez del perfil académico.
        
        **Tareas de Verificación:**
        **Tareas de Verificación:**
        1.  **Perfil del Autor (Checklist Detallado):**
            *   **Scholar/ORCID:** NO busques enlaces. Solo evalúa si debería tenerlos.
            *   **Publicaciones Recientes:** Enumera 2 publicaciones recientes (Título y Año).
            *   **Publicaciones Recientes:** Enumera 2 publicaciones recientes (Título y Año).
            *   **Afiliación y Cargo:** Identifica cargo y universidad.
        2.  **Metodología del Artículo:** Determina si es Cuantitativa, Cualitativa o Mixta basándote en el resumen.
        3.  **Publicación Previa (Solo Revistas):** Analiza si el trabajo ya ha sido publicado en una **REVISTA ACADÉMICA (Journal)**.
            *   **IMPORTANTE:** NO consideres como "publicación previa" a: Tesis, Repositorios Institucionales, Working Papers o Preprints. Esto es normal.
            *   **ALERTA:** Solo marca TRUE si detectas que ya salió en otra revista. Si es una tesis o repositorio, marca FALSE.
        
        **Salida JSON**:
        {
            "author_checklist": {
                "recent_publications_list": [
                    {"title": "Pub 1", "year": "2023"},
                    {"title": "Pub 2", "year": "2022"}
                ],
                "role_and_institution": "Cargo e Institución"
            },
            "author_comment": "Evaluación breve del perfil.",
            "is_previously_published": boolean,
            "reason_publication": "Explicación (ej. 'Coincide con artículo en Revista X' o 'Es tesis/repositorio, no cuenta')",
            "article_methodology": "Cuantitativo/Cualitativo/Mixto (Breve justificación)"
        }
        """
        
        user_prompt = f"""
        Analizar Autor: "{author_name}"
        Título Artículo: "{title}"
        Resumen: "{abstract}"
        Palabras Clave: "{keywords}"
        """
        
        response_text = call_gemini_api(api_key, system_instruction, user_prompt, model_name)
        
        if response_text:
            cleaned_text = response_text.replace("```json", "").replace("```", "")
            return json.loads(cleaned_text)
        return None
    except Exception as e:
        print(f"Integrity check failed: {e}")
        return None

@st.cache_data(ttl=3600)
def find_reviewers_with_gemini(api_key, target_article_context, prioritize_latam, evaluadores_str, model_name):
    """
    Cached function to find reviewers using Gemini.
    Separating this ensures we don't re-run the expensive API call on every interaction.
    """
    try:
        system_instruction = """
        Eres un Editor Académico Experto. Tu objetivo es identificar a los mejores revisores pares para un artículo científico.
        
        **IMPORTANTE**: Responde SIEMPRE en ESPAÑOL.
        
        **Proceso (Chain of Thought):**
        1.  **Analizar**:
            *   Extrae los temas centrales.
            *   **DETERMINA LA METODOLOGÍA**: ¿Es Cuantitativa, Cualitativa o Mixta? (Basado en el Abstract/Keywords).
            *   Identifica el enfoque regional.
        2.  **Match Interno**: Busca en 'REGISTERED REVIEWERS' candidatos.
            *   **Filtro de Metodología**: Prioriza revisores que manejen la metodología detectada.
            *   Explica en ESPAÑOL por qué encajan (Tema + Metodología).
        3.  **Búsqueda Externa Simulada**: Sugiere 3 NUEVOS revisores.
            *   **CRÍTICO**: Prioriza LatAm.
            *   **Expertise**: Debe encajar con el tema y la metodología.
        
        **Formato de Salida (JSON)**:
        {
            "internal_matches": [
                {"Nombre": "...", "Apellidos": "...", "Institucion": "...", "Temas": "...", "Methodology": "Cuanti/Cuali/Mixto", "Reason": "..."}
            ],
            "external_suggestions": [
                 {"Nombre": "...", "Apellidos": "...", "Correo": "...", "Afiliación": "...", "País": "...", "Scholar": "Search required", "OrcId": "Search required", "Temas": "...", "Methodology": "Cuanti/Cuali/Mixto", "Reason": "..."}
            ]
        }
        """
        
        user_prompt = f"""
        INPUT CONTEXT: "{target_article_context}"
        PRIORITIZE LATAM: {prioritize_latam}
        
        REGISTERED REVIEWERS DATABASE (Sample/Context):
        {evaluadores_str}
        """
        
        response_text = call_gemini_api(api_key, system_instruction, user_prompt, model_name)
        
        if response_text:
            cleaned_text = response_text.replace("```json", "").replace("```", "")
            return json.loads(cleaned_text)
        return None
    except Exception as e:
        st.error(f"Reviewer search failed: {e}")
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

try:
    st.image("UPacifico.png", width=100)
except:
    pass # Handle case where image is missing locally or in cloud without proper path

st.title("Buscador de pares evaluadores")
st.markdown("""
**Apuntes, Revista de Ciencias Sociales y Journal of Business**  
Universidad del Pacífico  
*Desarrollado por: Renato De Col*

⚠️ *Para uso exclusivo de los Editores-en-Jefe de las revistas académicas de la Universidad del Pacífico.*
""")

# --- AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("### 🔐 Acceso Requerido")
    password = st.text_input("Ingrese la contraseña:", type="password")
    if st.button("Ingresar"):
        if password == "pacificorevistas":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

# Sidebar
st.sidebar.header("Configuración")

# Load IDs from secrets (Auto-configured)
sheet_id_articulos = st.secrets.get("SHEET_ID_ARTICULOS", "")
sheet_id_evaluadores = st.secrets.get("SHEET_ID_EVALUADORES", "")
api_key = st.secrets.get("GEMINI_API_KEY", "")

if not sheet_id_articulos or not sheet_id_evaluadores or not api_key:
    st.error("Missing Sheet IDs or API Key in secrets.toml")
    st.stop()

# Model Selector
model_options = {
    "⚡ Gemini 1.5 Flash (Rápido - 1500 usos/día)": "gemini-flash-latest",
    "🧠 Gemini 1.5 Pro (Potente - 50 usos/día)": "gemini-pro-latest",
    "🚀 Gemini 3.0 Flash (Preview - Nuevo)": "gemini-3-flash-preview",
    "🧪 Gemini 3.0 Pro (Preview - Experimental)": "gemini-3-pro-preview"
}
selected_model_label = st.sidebar.selectbox("Modelo de Inteligencia Artificial", list(model_options.keys()))
selected_model_name = model_options[selected_model_label]

mode = st.sidebar.radio("Modo de Búsqueda", ["Por ID de Artículo", "Por Contenido"])

target_article_context = ""
context_title = ""

if mode == "Por ID de Artículo":
    article_id_input = st.sidebar.text_input("Ingrese ID del Artículo (ej. 2746)")
    if article_id_input:
        with st.spinner(f"Buscando Artículo {article_id_input}..."):
            article_data = fetch_article_details(sheet_id_articulos, article_id_input)
            if article_data:
                st.sidebar.success("¡Artículo Encontrado!")
                context_title = article_data.get('Titulo', 'Título Desconocido')
                abstract = article_data.get('Resumen', '')
                keywords = article_data.get('Palabras clave', '')
                author_name = article_data.get('Autores', 'Autor Desconocido')
                link = article_data.get('Link', '')
                
                # Context is built from everything available
                target_article_context = f"TITLE: {context_title}\nKEYWORDS: {keywords}\nABSTRACT: {abstract}\nLINK: {link}"
                
                if link:
                    st.sidebar.markdown(f"[🔗 **Ver Texto Completo**]({link})")
                
                # --- INTEGRITY CHECK ---
                if author_name:
                    st.info(f"**Analizando:** {context_title} | Autor: {author_name}")
                    
                    # Verify Author & Integrity
                    with st.spinner(f"Verificando integridad y estatus académico..."):
                        integrity = verify_article_integrity(api_key, author_name, context_title, abstract, keywords, selected_model_name)
                        
                    if integrity:
                        # --- Check 1: Author Profile ---
                        st.markdown("### 👤 Perfil Académico del Autor")
                        checklist = integrity.get("author_checklist", {})
                        
                        cols = st.columns(3)
                        
                        # Col 1: Links (Precision Search)
                        with cols[0]:
                            # Precision Scholar Link (Search Authors)
                            s_search = f"https://scholar.google.com/citations?view_op=search_authors&hl=es&mauthors={urllib.parse.quote(author_name)}"
                            # Precision ORCID Link
                            o_search = f"https://orcid.org/orcid-search/search?searchQuery={urllib.parse.quote(author_name)}"
                            
                            st.markdown("**Búsqueda Inteligente:**")
                            st.markdown(f"🔎 [Buscar en Scholar]({s_search})")
                            st.markdown(f"🆔 [Buscar en ORCID]({o_search})")

                        # Col 2: Recent Pubs
                        with cols[1]:
                            pubs = checklist.get("recent_publications_list", [])
                            st.markdown("**Publicaciones Recientes:**")
                            if pubs and len(pubs) > 0:
                                for p in pubs[:2]: # Show top 2
                                    if isinstance(p, dict):
                                        title = p.get("title", "Sin título")
                                        year = p.get("year", "")
                                        # Precision Pub Link: "Title" + author:"Name" (intitle removed)
                                        query = f'"{title}" author:"{author_name}"'
                                        search_url = f"https://scholar.google.com/scholar?q={urllib.parse.quote(query)}"
                                        st.markdown(f"📄 [{title} ({year})]({search_url})")
                                    else:
                                        # Fallback if string
                                        query = f'"{str(p)}" author:"{author_name}"'
                                        search_url = f"https://scholar.google.com/scholar?q={urllib.parse.quote(query)}"
                                        st.markdown(f"📄 [{p}]({search_url})")
                            else:
                                st.warning("⚠️ No se listaron publicaciones recientes.")

                        # Col 3: Affiliation
                        with cols[2]:
                            role = checklist.get("role_and_institution", "No identificado")
                            st.markdown("**Afiliación (Inferida):**")
                            if role and "No identificado" not in role:
                                st.success(f"🏛️ {role}")
                                # Precision Affiliation Link (Quoted Name + Institution)
                                google_search = f"https://www.google.com/search?q=\"{urllib.parse.quote(author_name)}\"+{urllib.parse.quote(role)}"
                                st.markdown(f"[🔗 Verificar Afiliación]({google_search})")
                            else:
                                st.error("❌ Cargo/Institución no claros")

                        st.info(f"💡 **Evaluación:** {integrity.get('author_comment', 'No disponible')}")
                        
                        # --- Check 3: Methodology ---
                        meth = integrity.get("article_methodology", "No detectado")
                        st.info(f"📊 **Metodología Detectada:** {meth}")
                        
                        # --- Check 2: Prior Publication ---
                        if integrity.get("is_previously_published"):
                            st.error(f"🚨 **ALERTA PUBLICACIÓN:** Este artículo podría haber sido publicado previamente.")
                            st.write(f"**Detalle:** {integrity.get('reason_publication')}")
                            
                            # Precision Duplicate Link (intitle: context_title)
                            dup_query = f'intitle:"{context_title}"'
                            dup_search = f"https://scholar.google.com/scholar?q={urllib.parse.quote(dup_query)}"
                            st.markdown(f"🔴 [🔗 **VERIFICAR DUPLICADO**]({dup_search})")
                        else:
                            st.markdown("✅ **Originalidad:** No se detectaron publicaciones previas obvias.")
                            
                else:
                    st.info(f"**Analizando:** {context_title}")
                
                # Show details
                if keywords:
                    with st.expander("Ver Palabras Clave"):
                        st.write(keywords)
                if abstract and abstract != keywords:
                     with st.expander("Ver Resumen"):
                        st.write(abstract)
                        
            else:
                st.sidebar.error("ID de artículo no encontrado.")
else:
    st.sidebar.markdown("### Búsqueda Manual")
    m_title = st.sidebar.text_input("Título del Artículo")
    m_keywords = st.sidebar.text_area("Palabras Clave", height=70)
    m_abstract = st.sidebar.text_area("Resumen / Abstract", height=150)
    
    components = []
    if m_title: components.append(f"TITLE: {m_title}")
    if m_keywords: components.append(f"KEYWORDS: {m_keywords}")
    if m_abstract: components.append(f"ABSTRACT: {m_abstract}")
    
    target_article_context = "\n\n".join(components)

prioritize_latam = st.sidebar.checkbox("Priorizar Expertos de LatAm", value=True)
run_btn = st.sidebar.button("🔍 Buscar Revisores")

st.sidebar.divider()
st.sidebar.markdown(f"[📂 Abrir Base de Datos Google Sheets](https://docs.google.com/spreadsheets/d/{sheet_id_evaluadores})")

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
            
            with st.spinner("🤖 Gemini is analyzing matches and finding experts..."):
                json_results = find_reviewers_with_gemini(api_key, target_article_context, prioritize_latam, evaluadores_str, selected_model_name)
            
            if json_results:
                st.session_state['search_results'] = json_results
                st.success("¡Análisis Completo!")

# Display Results (Persistent)
if st.session_state['search_results']:
    results = st.session_state['search_results']
    
    # Removed global methodology display from here (moved to Profile)
    
    tab1, tab2 = st.tabs(["🏛️ Coincidencias Internas (BD)", "🌎 Sugerencias Externas (Nuevos)"])
    
    with tab1:
        if results.get("internal_matches"):
            df_internal = pd.DataFrame(results["internal_matches"])
            # Reorder columns: Add Methodology
            desired_order = ["Nombre", "Apellidos", "Institucion", "Temas", "Methodology", "Reason"]
            # Filter to only columns that actually exist
            cols = [c for c in desired_order if c in df_internal.columns]
            # Add remaining
            remaining = [c for c in df_internal.columns if c not in cols]
            
            st.table(df_internal[cols + remaining])
        else:
            st.info("No se encontraron coincidencias internas fuertes.")
            
    with tab2:
        externals = results.get("external_suggestions", [])
        if externals:
            st.info("Seleccione candidatos para añadir a la base de datos:")
            
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
                        st.caption(f"🛠 {row.get('Methodology', '')}")
                    with cols[5]:
                        st.write(row['País'])
                    with cols[6]:
                        s_link, o_link, _ = get_verification_links(f"{row['Nombre']} {row['Apellidos']}", row['Afiliación'])
                        st.markdown(f"[🔎 Scholar]({s_link})")
                        st.markdown(f"[🆔 ORCID]({o_link})")
                    st.divider()
                
                submitted = st.form_submit_button("➕ Añadir Seleccionados a la BD")
                
                if submitted:
                    if selected_indices:
                        # Filter selected rows
                        rows_to_add = df_externals.iloc[selected_indices].drop(columns=['Reason'], errors='ignore')
                        
                        target_columns = ["ID Artículo", "Nombre", "Apellidos", "Correo electrónico", "Afiliación institucional", "País", "Google Scholar", "OrcId", "Temas"]
                        
                        rows_prepared = pd.DataFrame()
                         # Use Article ID if known
                        current_id_val = article_id_input if mode == "Por ID de Artículo" and 'article_id_input' in locals() and article_id_input else ""
                        
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
                        
                        # Sanitize data for JSON (gspread)
                        rows_prepared = rows_prepared.fillna("")
                        
                        # Get fresh worksheet object for writing
                        ws_to_append = get_active_worksheet(sheet_id_evaluadores)

                        # Append
                        if ws_to_append and append_to_sheet(ws_to_append, rows_prepared):
                            load_evaluadores.clear()
                            st.success(f"✅ ¡Se añadieron {len(rows_prepared)} revisores a la base de datos!")
                            st.balloons()
                    else:
                        st.warning("Por favor seleccione al menos un revisor.")
        else:
            st.warning("La IA no pudo generar sugerencias externas.")
