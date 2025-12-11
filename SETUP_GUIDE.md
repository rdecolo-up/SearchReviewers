# 🔑 Guía para Obtener Credenciales

Para que la aplicación funcione, necesitas obtener credenciales de Google. Aquí te explico cómo hacerlo paso a paso.

## 1. Obtener Gemini API Key (Cerebro de la IA)

1.  Ve a [Google AI Studio](https://aistudio.google.com/).
2.  Inicia sesión con tu cuenta de Google.
3.  Haz clic en el botón azul **"Get API key"** (o "Create API key").
4.  Copia la clave que empieza por `AIza...`.
5.  Pégala en tu archivo `secrets.toml`.

## 2. Obtener Credenciales de Google Sheets (Base de Datos)

Esto es un poco más técnico, pero solo hay que hacerlo una vez.

### Paso A: Crear Proyecto en Google Cloud
1.  Ve a la [Consola de Google Cloud](https://console.cloud.google.com/).
2.  Crea un **Nuevo Proyecto** (nómbralo "Reviewer App" o similar).

### Paso B: Habilitar APIs
1.  En el menú lateral, ve a **APIs & Services > Library**.
2.  Busca y habilita:
    *   **Google Sheets API**
    *   **Google Drive API**

### Paso C: Crear Service Account
1.  Ve a **APIs & Services > Credentials**.
2.  Haz clic en **"Create Credentials"** -> **"Service Account"**.
3.  Dale un nombre (ej. "bot-revisor") y crea la cuenta.
4.  Una vez creada, haz clic en el email de la cuenta (que se ve como `bot-revisor@tu-proyecto.iam.gserviceaccount.com`).
5.  Ve a la pestaña **Keys** (Claves).
6.  Haz clic en **Add Key > Create new key** y selecciona **JSON**.
7.  Se descargará un archivo a tu computadora. **Ese es tu archivo de credenciales**.

### Paso D: Compartir la Hoja de Cálculo
1.  Abre el archivo JSON que descargaste y copia el `client_email` (el correo que termina en `@...iam.gserviceaccount.com`).
2.  Ve a tu **Google Sheet** (donde tienes la lista de "Evaluadores").
3.  Haz clic en **Compartir** (Share) y pega ese correo.
4.  Dale permisos de **Editor**.

## 3. Obtener el ID de la Hoja (Sheet ID)

1.  Abre tu Google Sheet en el navegador.
2.  Mira la URL. Se ve así:
    `https://docs.google.com/spreadsheets/d/1XyZ_AbCdEfGhIjKlMnOpQrStUvWxYz/edit#gid=0`
3.  Tu ID es la parte larga entre `/d/` y `/edit`.
    *   En este ejemplo: `1XyZ_AbCdEfGhIjKlMnOpQrStUvWxYz`
4.  Copia ese ID y pégalo en `secrets.toml`.

---
**¡Listo!** Con esos 3 datos en tu `secrets.toml`, la aplicación podrá leer tu Excel y usar la IA.
