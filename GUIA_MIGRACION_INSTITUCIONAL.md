# Guía de Migración a Credenciales Institucionales
## 🛡️ ¿Por qué no usar claves personales?
Actualmente, la aplicación funciona con tus credenciales personales. Esto presenta tres riesgos principales:
1.  **Continuidad**: Si dejas de trabajar en la revista o cambias tu contraseña, la aplicación dejará de funcionar para todos.
2.  **Seguridad**: Tus archivos personales podrían quedar expuestos si compartes la carpeta del proyecto.
3.  **Límites y Costes**: El uso de la API consume tu cuota personal gratuita.

## 🚀 Pasos para la Migración
Para "oficializar" la herramienta, debes crear cuentas dedicadas para la revista.

### Paso 1: Google Cloud (Para las Hojas de Cálculo)
1.  Entra a [Google Cloud Console](https://console.cloud.google.com/) con una cuenta corporativa/institucional (o crea una Gmail dedicada tipo `fondo.editorial.bot@gmail.com`).
2.  Crea un **Nuevo Proyecto** llamado `Sistema-Revisores`.
3.  Busca y **Habilita** estas dos APIs:
    *   Google Sheets API
    *   Google Drive API
4.  Ve a **Credenciales** > **Crear Credenciales** > **Cuenta de Servicio**.
    *   Nombre: `bot-revisores`.
    *   Permisos: "Editor" (opcional, pero útil).
5.  Haz clic en la cuenta creada > pestaña **Claves** > **Agregar Clave** > **Crear nueva clave JSON**.
    *   Se descargará un archivo `.json`. Este es el nuevo "carnet de identidad" del bot.
6.  **IMPORTANTE**: Abre el JSON, copia el `client_email` y **comparte tus Google Sheets (Artículos y Evaluadores)** con ese correo.

### Paso 2: Gemini API (Para la IA)
1.  Ve a [Google AI Studio](https://aistudio.google.com/).
2.  Asegúrate de estar logueado con la cuenta institucional.
3.  Haz clic en **Get API key** > **Create API key in new project**.
4.  Copia la clave `AIza...`.

### Paso 3: Actualizar la Aplicación
Una vez tengas los nuevos archivos:

1.  Ve a la carpeta de la aplicación: `reviewer_matcher_app/.streamlit/`.
2.  Abre el archivo `secrets.toml`.
3.  Reemplaza los valores viejos por los nuevos:
    *   `GEMINI_API_KEY`: Pega la nueva clave del Paso 2.
    *   `GOOGLE_SHEETS_CREDENTIALS`: Copia y pega *todo* el contenido del nuevo archivo JSON del Paso 1.

¡Listo! Ahora la aplicación es independiente de tu cuenta personal.
