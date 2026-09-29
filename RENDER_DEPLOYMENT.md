# 🚀 Guía de Despliegue en Render.com (Plan Gratuito)

Esta guía describe el paso a paso detallado para desplegar la plataforma **Rover Market Intelligence** en [Render.com](https://render.com) utilizando **Docker**, configurando las variables de entorno de **Supabase** y optimizando el consumo de recursos.

---

## 📌 Requisitos Previos

1. Una cuenta activa en [Render.com](https://dashboard.render.com/) (puedes ingresar con tu cuenta de GitHub).
2. Repositorio de GitHub con la rama principal actualizada (`main`).
3. Credenciales activas de tu proyecto en Supabase:
   - `SUPABASE_URL`
   - `SUPABASE_PUBLISHABLE_KEY` (o `SUPABASE_KEY`)
   - `SUPABASE_SECRET_KEY` (o `SUPABASE_SERVICE_ROLE_KEY`)

---

## ⚙️ Análisis de Arquitectura en Render Free Tier

| Recurso | Límite Render Free | Configuración Rover Platform |
|---|---|---|
| **RAM** | 512 MB | Chromium optimizado con `--disable-dev-shm-usage`, `--no-sandbox` y `--disable-gpu` (~280MB en ejecución). |
| **CPU** | 0.1 vCPU compartida | Uvicorn single-worker optimizado para I/O asíncrono con FastAPI. |
| **Puerto Web** | Variable dinámica `$PORT` | Dockerfile configurado con `uvicorn --port ${PORT:-8000}`. |
| **Persistencia** | Efímera (el disco se reinicia) | **Supabase Postgres** actúa como base de datos persistente externa. |
| **Inactividad** | Duerme tras 15m sin tráfico | Se reactiva automáticamente al recibir una petición web (~45s de arranque). |

---

## 🛠️ Paso a Paso: Despliegue en Render

### Paso 1: Conectar el Repositorio

1. Inicia sesión en [Render Dashboard](https://dashboard.render.com/).
2. Haz clic en el botón **New +** en la esquina superior derecha y selecciona **Web Service**.
3. Selecciona la opción **Build and deploy from a Git repository** y pulsa **Next**.
4. Busca y selecciona tu repositorio: `dagudelob/Rover-rate-analisis` (si no aparece, pulsa *Configure access* para darle permisos a Render en tu organización de GitHub).

---

### Paso 2: Configuración del Servicio

En el formulario de configuración, completa los campos:

| Campo | Valor Recomendado |
|---|---|
| **Name** | `rover-market-intelligence` (o el nombre que prefieras) |
| **Region** | `Oregon (US West)` o `Ohio (US East)` (elige la más cercana a tu región de Supabase) |
| **Branch** | `main` |
| **Root Directory** | *(Dejar vacío / raíz)* |
| **Runtime / Environment** | **Docker** *(Render detectará automáticamente el `Dockerfile`)* |
| **Instance Type** | **Free** ($0 / mes) |

---

### Paso 3: Configurar Variables de Entorno (Environment Variables)

Desplázate hacia abajo hasta la sección **Environment Variables** y agrega las siguientes claves (copiando los valores de tu `.env` local):

| Clave (Key) | Valor (Value) | Descripción |
|---|---|---|
| `PYTHONUNBUFFERED` | `1` | Asegura que los logs de Python y FastAPI aparezcan en tiempo real en la consola de Render. |
| `SUPABASE_URL` | `https://<tu-project-id>.supabase.co` | URL del proyecto Supabase. |
| `SUPABASE_PUBLISHABLE_KEY` | `sb_publishable_...` | Clave pública para consultas anonimas. |
| `SUPABASE_SECRET_KEY` | `sb_secret_...` | Clave de servicio para omitir RLS durante scraping e inserciones masivas. |
| `CORS_ORIGINS` | `*` o `https://tu-app.onrender.com` | Orígenes permitidos (puedes empezar con `*` y luego poner tu dominio de Render). |
| `SCRAPER_MAX_PAGES` | `5` | *Recomendado para Free Tier:* limita páginas concurrentes para no saturar los 512MB de RAM. |
| `SCRAPER_MAX_RESULTS` | `50` | *Recomendado para Free Tier:* optimiza memoria durante el análisis de outliers. |

> [!CAUTION]
> Asegúrate de **NO comitear jamás** tu archivo `.env` en GitHub. Las variables deben añadirse exclusivamente a través del formulario web de Render.

---

### Paso 4: Crear y Desplegar el Web Service

1. Haz clic en **Create Web Service** al final de la página.
2. Render iniciará la construcción del contenedor Docker:
   - Descarga `python:3.12-slim`.
   - Instala librerías del sistema para Chromium.
   - Instala `requirements.txt`.
   - Ejecuta `playwright install --with-deps chromium`.
   - Inicia Uvicorn en el puerto asignado por Render.
3. El primer build toma entre **3 y 5 minutos**. Podrás observar los logs en vivo en la pantalla de Render.
4. Cuando veas el mensaje:
   ```text
   Application startup complete.
   Uvicorn running on http://0.0.0.0:10000 (o puerto asignado)
   ==> Your service is live 🎉
   ```
   Tu aplicación estará publicada y accesible en la URL proporcionada por Render (ej. `https://rover-market-intelligence.onrender.com`).

---

## 🔍 Paso 5: Verificación Post-Despliegue

1. **Prueba de Health / Interfaz:**
   Abre la URL de Render en tu navegador. Deberías ver la interfaz completa del dashboard con mapa OSM, selectores de servicio y panel analítico.
2. **Prueba de Documentación Swagger:**
   Visita `https://tu-app.onrender.com/docs` para verificar que los endpoints OpenAPI respondan con código `200 OK`.
3. **Prueba de Scraping con Ingesta a Supabase:**
   Ejecuta una búsqueda de prueba (ej. código postal `M5G2A1`, servicio `dog-walking`, 1 página).
   - Abre la pestaña **Logs** en Render para observar la navegación con Playwright.
   - Abre **Supabase Table Editor** y verifica que las nuevas filas se inserten en `sitters` y `search_sessions`.

---

## 💡 Recomendaciones para el Plan Gratuito (Best Practices)

1. **Evitar Scrapes Masivos Simultáneos en Free Tier:**
   El contenedor de 512 MB corre de forma estable con 1 sesión de Playwright a la vez. No lances múltiples scrapes en paralelo desde pestañas distintas.
2. **Cold Starts:**
   Si la web no recibe visitas por 15 minutos, el contenedor se apaga para ahorrar energía. La primera persona que entre esperará ~45 segundos mientras Render enciende el contenedor. Esto es normal en el plan gratuito.
3. **Auto-Deploy:**
   Cada vez que hagas un `git push` o merge a la rama `main` en GitHub, Render detectará los cambios y actualizará el servicio automáticamente sin downtime prolongado.
