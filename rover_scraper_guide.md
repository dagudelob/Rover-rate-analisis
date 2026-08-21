# Rover.com Market Scraper & Anti-Detection Setup Guide

Guía completa para extraer y analizar precios y servicios en **Rover.com** de forma segura en entornos locales o de desarrollo (VS Code / Antigravity IDE), evitando bloqueos de IP, captchas y detección de automatización (*fingerprinting*).

---

## 1. Arquitectura y Estrategia de Seguridad

Rover.com utiliza mecanismos de protección basados en Cloudflare y detección de comportamiento automatizado. Para consultar datos públicos (precios, reseñas, disponibilidad) sin comprometer la IP local ni cuentas personales, se aplican las siguientes reglas:

1. **Aislamiento Total de Sesión:** No autenticarse ni reutilizar cookies de sesión personales. Las búsquedas de Rover son públicas.
2. **Evasión de Fingerprinting (Anti-Detect):** Uso de `playwright-stealth` para parches de `navigator.webdriver`, codecs de audio/video y huellas WebGL/Canvas.
3. **Comportamiento Humano:** Retardos estocásticos (`random.uniform`), headers realistas, scroll progresivo y límites de paginación por sesión.
4. **Soporte Opcional de Proxies / VPN:** Parámetro desacoplado para inyección de proxies HTTP/SOCKS5 si se requiere escalar el volumen.

---

## 2. Configuración del Entorno

### Dependencias (`requirements.txt`)

```text
playwright>=1.40.0
playwright-stealth>=1.0.6
pandas>=2.0.0
beautifulsoup4>=4.12.0
```

### Comandos de Instalación

```bash
# Crear y activar entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Linux/macOS
# .venv\Scripts\activate  # En Windows

# Instalar librerías y binarios de Playwright
pip install -r requirements.txt
playwright install chromium
```

---

## 3. Código Fuente

### `scraper.py`

```python
import asyncio
import random
import re
from typing import List, Dict, Optional
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


# Servicios admitidos en Rover
# - dog-walking: Paseos de perros
# - overnight-boarding: Alojamiento para perros
# - drop-in-visits: Visitas a domicilio
# - house-sitting: Cuidado de casas/mascotas
# - day-care: Guardería de día

async def scrape_rover(
    location: str,
    service_type: str = "dog-walking",
    max_pages: int = 3,
    proxy_url: Optional[str] = None,
    output_csv: Optional[str] = None
) -> pd.DataFrame:
    """
    Scraper anti-detección para Rover.com utilizando Playwright y técnicas de evasión.
    """
    records: List[Dict[str, str]] = []
    
    proxy_config = {"server": proxy_url} if proxy_url else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "locale": "en-US",
            "timezone_id": "America/Toronto",
            "viewport": {"width": 1366, "height": 768},
        }
        if proxy_config:
            context_kwargs["proxy"] = proxy_config

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        # Aplicar parches stealth
        await stealth_async(page)

        for current_page in range(1, max_pages + 1):
            url = f"https://www.rover.com/search/?service_type={service_type}&location={location}&page={current_page}"
            print(f"[*] Navegando a página {current_page}/{max_pages}: {url}")

            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Pausa humana aleatoria tras la carga
                await page.wait_for_timeout(random.uniform(2500, 4500))

                # Scroll gradual para activar lazy-loading
                await page.evaluate("""
                    window.scrollBy({
                        top: window.innerHeight * 0.8,
                        behavior: 'smooth'
                    });
                """)
                await page.wait_for_timeout(random.uniform(1000, 2000))

                # Selectores robustos para las tarjetas de perfil
                cards = await page.query_selector_all("[data-qa='search-result-card'], div[class*='SitterCard'], article")

                print(f"    -> Encontradas {len(cards)} tarjetas de prestadores.")

                for card in cards:
                    try:
                        # Extracción de datos con fallbacks
                        name_elem = await card.query_selector("h3, [data-qa='sitter-name'], a[class*='name']")
                        price_elem = await card.query_selector("[data-qa='rate'], span[class*='price'], span[class*='rate'], div[class*='Rate']")
                        rating_elem = await card.query_selector("[data-qa='rating'], span[class*='rating'], div[class*='Rating']")
                        reviews_elem = await card.query_selector("[data-qa='review-count'], span[class*='reviews']")
                        headline_elem = await card.query_selector("[data-qa='sitter-headline'], p[class*='headline']")

                        name = (await name_elem.inner_text()).strip() if name_elem else None
                        raw_price = (await price_elem.inner_text()).strip() if price_elem else None
                        rating = (await rating_elem.inner_text()).strip() if rating_elem else None
                        reviews = (await reviews_elem.inner_text()).strip() if reviews_elem else None
                        headline = (await headline_elem.inner_text()).strip() if headline_elem else None

                        if name and raw_price:
                            # Limpieza de precio numérico (e.g. '$25/walk' -> 25.0)
                            price_numeric = None
                            match = re.search(r'\$?\s*(\d+(?:\.\d+)?)', raw_price)
                            if match:
                                price_numeric = float(match.group(1))

                            records.append({
                                "name": name,
                                "raw_price": raw_price,
                                "price_numeric": price_numeric,
                                "rating": rating,
                                "reviews": reviews,
                                "headline": headline,
                                "service_type": service_type,
                                "location_query": location,
                                "page": current_page
                            })
                    except Exception as parse_err:
                        continue

            except Exception as nav_err:
                print(f"[!] Error cargando página {current_page}: {nav_err}")
                break

            # Delay aleatorio antes de la siguiente página
            if current_page < max_pages:
                delay = random.uniform(3.5, 6.5)
                print(f"    -> Esperando {delay:.2f}s antes de la siguiente página...")
                await asyncio.sleep(delay)

        await browser.close()

    df = pd.DataFrame(records)
    
    if output_csv and not df.empty:
        df.to_csv(output_csv, index=False, encoding="utf-8")
        print(f"[✓] Archivo exportado exitosamente: {output_csv} ({len(df)} registros)")

    return df


if __name__ == "__main__":
    # Configuración de prueba local
    UBICACION = "Downtown Toronto, ON"  # Ajusta tu código postal o barrio
    SERVICIO = "dog-walking"           # 'dog-walking', 'overnight-boarding', 'house-sitting'
    
    df_resultados = asyncio.run(
        scrape_rover(
            location=UBICACION,
            service_type=SERVICIO,
            max_pages=2,
            output_csv="rover_market_data.csv"
        )
    )
    print("\nResumen de resultados:")
    print(df_resultados.head())
```

---

## 4. Script de Análisis de Precios (`analyze_data.py`)

```python
import pandas as pd

def analyze_market_prices(csv_path: str = "rover_market_data.csv"):
    df = pd.read_csv(csv_path)
    
    if df.empty or "price_numeric" not in df.columns:
        print("El archivo CSV no contiene datos válidos.")
        return

    # Limpieza de nulos
    df_clean = df.dropna(subset=["price_numeric"])

    print("==========================================")
    print("       RESUMEN DE MERCADO - ROVER         ")
    print("==========================================")
    print(f"Total cuidadores analizados: {len(df_clean)}")
    print(f"Servicio:                   {df_clean['service_type'].iloc[0]}")
    print(f"Ubicación:                  {df_clean['location_query'].iloc[0]}")
    print("------------------------------------------")
    print(f"Precio Mínimo:              ${df_clean['price_numeric'].min():.2f}")
    print(f"Precio Promedio:            ${df_clean['price_numeric'].mean():.2f}")
    print(f"Mediana (P50):              ${df_clean['price_numeric'].median():.2f}")
    print(f"Percentil 25 (P25):         ${df_clean['price_numeric'].quantile(0.25):.2f}")
    print(f"Percentil 75 (P75):         ${df_clean['price_numeric'].quantile(0.75):.2f}")
    print(f"Precio Máximo:              ${df_clean['price_numeric'].max():.2f}")
    print("==========================================")

if __name__ == "__main__":
    analyze_market_prices()
```

---

## 5. Protocolo de Mitigación de Bloqueos y Banderas

| Vector de Riesgo | Causa Principal | Mitigación Implementada |
| :--- | :--- | :--- |
| **Cuenta Baneada** | Usar credenciales personales en scripts | Scrapear exclusivamente en modo anónimo / público (sin login). |
| **Detección de WebDriver** | Bandera `navigator.webdriver = true` | `playwright-stealth` + flags Chromium `--disable-blink-features=AutomationControlled`. |
| **Bloqueo de IP Local** | Frecuencia de peticiones anormal (*Burst requests*) | Delays aleatorios entre 3.5s y 6.5s por página y límite de 3-5 páginas por tanda. |
| **Discrepancia de Huella** | Desfase entre User-Agent, resolución y Timezone | Headers sincronizados (`America/Toronto`, viewport estándar 1366x768). |
| **Escalamiento Masivo** | Múltiples zonas geográficas en paralelo | Uso de Proxies HTTP/SOCKS5 o rotación de servidor VPN. |
