# 🐾 Rover Market Intelligence & Pricing Analytics Platform

[![CI / Tests](https://github.com/dagudelob/Rover-rate-analisis/actions/workflows/ci.yml/badge.svg)](https://github.com/dagudelob/Rover-rate-analisis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Stealth-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![KaTeX](https://img.shields.io/badge/KaTeX-LaTeX_Math-329894?style=for-the-badge)](https://katex.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An end-to-end **Data Science & Market Intelligence Platform** for **Rover.com** (with multi-platform support for Wag! and Care.com). This platform extracts multi-page market listings, models the empirical relationship between pricing and booking conversion probability via **Empirical Survival Analysis**, identifies the mathematical **Revenue Sweet Spot** using **Price Elasticity of Demand (PED)**, renders interactive geospatial heatmaps with service radius overlays, supports statistical outlier management, and synchronizes real-time market data directly to **Supabase PostgreSQL** with local **SQLite** fallback.

---

## 🌟 Key Features

1. **High-Volume Multi-Page Scraping (100+ Sitters)**:
   - Built with **Playwright** and **Playwright-Stealth** to bypass Cloudflare anti-bot fingerprinting (`navigator.webdriver`, WebGL, canvas).
   - Coordinate-anchored search URLs (`lat`/`lng`) and browser geolocation spoofing guarantee accurate local market targeting regardless of remote server IP geolocation (e.g. Render, AWS).
   - Simulates human behavior with smooth progressive scrolling, realistic navigation headers (`Sec-Fetch`, `Accept-Language`), and stochastic delay intervals.
   - Streams live progress and page-by-page events directly to the UI via **Server-Sent Events (SSE)**.

2. **Multi-Platform Support**:
   - Extensible Strategy Pattern supporting **Rover.com**, **Wag!**, and **Care.com** with normalized service price catalogs.

3. **Supabase PostgreSQL & Dual Persistence**:
   - Fully normalized relational database schema (`sitters`, `search_sessions`, `session_sitters`, `sitter_services`).
   - Scraped sessions persist in local SQLite and automatically synchronize to **Supabase** in real-time.
   - Fault-tolerant resilience: network drops or cloud downtime gracefully fall back without interrupting ongoing scrapes.

2. **Empirical Revenue Maximizer & Price Elasticity (PED)**:
   - Solves the fundamental market pricing trade-off: **Low price** (high volume, minimal margin) vs. **High price** (high margin, near-zero conversion).
   - Uses the **Empirical Survival Function (ESF)** with Silverman's Gaussian kernel smoothing:
     $$P(\text{conversion} \mid P) = \frac{1}{N} \sum_{i=1}^N \frac{1}{1 + \exp\left(\frac{P - P_i}{h}\right)}$$
   - Evaluates the **Expected Value / Revenue Index**:
     $$\text{EVI}(P) = P \times P(\text{conversion} \mid P)$$
   - Computes **Price Elasticity of Demand (PED)** to locate the unitary elasticity point ($|\epsilon| \approx 1.0$) where total revenue is mathematically maximized.

3. **🌓 Dual-Theme Interface (Dark Mode & Light Mode)**:
   - Built using **Color Theory** tokens to guarantee **WCAG AAA** (7:1+) contrast in both themes.
   - **Dark Mode (Midnight Blue)**: Deep slate backgrounds (`#0a0e17`, `#111827`) with glowing accents.
   - **Light Mode (Nordic Slate)**: High-contrast slate typography (`#0f172a`, `#1e293b`) on clean cards.
   - Preferences automatically persist across sessions using `localStorage`.

4. **📐 KaTeX LaTeX Mathematical Typesetting**:
   - Scientific formulas across the **Data Science Academy** and **Econometrics Encyclopedia** render using the **KaTeX** LaTeX math engine with crisp mathematical notation ($$IQR$$, $$\text{EVI}(P)$$, $$\hat{f}_h(x)$$, $$\arg\min \sum \|\mathbf{x} - \boldsymbol{\mu}_i\|^2$$).

5. **Geospatial Heatmap & Dynamic Service Area Buffers**:
   - Interactive Leaflet heatmap visualizing localized price density gradients.
   - **Dynamic hover interaction**: hovering over any sitter row draws their active service radius coverage circle on the map in real-time.

6. **Statistical Data Studio & Outlier Control**:
   - Automatic outlier detection using the **Interquartile Range (IQR) Rule** ($[Q_1 - 1.5\cdot\text{IQR}, \; Q_3 + 1.5\cdot\text{IQR}]$).
   - Individual sitter checkboxes for manual filtering with **SQLite persistence** (`is_excluded`, `excluded_reason`).
   - Live recalculation of **10% Trimmed Mean**, **Standard Deviation ($\sigma$)**, **Variance ($\sigma^2$)**, and percentiles ($P_{10}, P_{25}, P_{75}, P_{90}$).

7. **Historical Archive & Batch Search Deletion**:
   - Multi-select checkboxes, "Select All", and "Delete Selected" buttons to manage search history.
   - Direct trash can (`🗑️`) action for single-click session cleanup.
   - Direct export of SQLite database (`.db`) and consolidated master CSV archive.

---

## 📊 In-Depth 5-Service Strategic Pricing Analysis

Rover sitters operate across 5 distinct service categories. Because each service has different time commitments, travel overhead, and customer trust barriers, optimal pricing models vary significantly:

| Service Category | Typical Unit | Demand Elasticity | Operational Constraints | Recommended Pricing Strategy & Margin Multiplier |
| :--- | :--- | :--- | :--- | :--- |
| **🦮 Dog Walking** | 30 / 60 min walk | **High Elasticity** ($|\epsilon| > 1.2$) | Travel time between clients; route density dependent. | **Base Rate ($1.0\times$)**: Price competitively at market median. Maximize revenue through geographic route clustering (multiple dogs in the same neighborhood). |
| **🏠 Drop-In Visits** | 30 min home visit | **Moderate Elasticity** ($|\epsilon| \approx 1.0$) | Low pet interaction risk, multi-species (cats & dogs). | **$0.9\times - 1.1\times$ Base Rate**: Charge base price equal to walking + offer multi-pet add-ons ($+\$8-12$/extra pet) for high incremental margin. |
| **🏡 Overnight Boarding** | Per night (in sitter's home) | **Low Elasticity** ($|\epsilon| < 0.8$) | Physical home capacity limit (1–3 pets max); 24/7 supervision. | **$1.8\times - 2.5\times$ Base Rate**: Premium positioning. Owners prioritize safety and trust over price. Apply 25-40% surcharges during holiday peaks. |
| **🛋️ House Sitting** | Per night (in owner's home) | **Very Inelastic** ($|\epsilon| < 0.6$) | 100% time-exclusive; cannot take multiple concurrent house sits. | **$2.2\times - 3.2\times$ Base Rate**: Highest rate tier. Justified by exclusivity, home care, and plant/mail management. Best for sitters who work remotely. |
| **☀️ Day Care** | Full day (8 AM – 6 PM) | **Moderate Elasticity** ($|\epsilon| \approx 1.0$) | Supervised daily schedule; weekday recurring clientele. | **$1.4\times - 1.9\times$ Base Rate**: Subscription/package pricing. Offer recurring weekly discounts to lock in predictable recurring revenue. |

### Strategic Recommendation Matrix
```
Revenue Potential / Exclusivity
  ▲
  │   [House Sitting] ($65 - $110/night) ── High Trust / Exclusive Time
  │   [Overnight Boarding] ($45 - $85/night) ── Scalable with Home Capacity
  │   [Day Care] ($35 - $60/day) ── Recurring Monday-Friday Income
  │   [Dog Walking] ($20 - $35/walk) ── High Volume / Route Clustered
  │   [Drop-In Visits] ($18 - $30/visit) ── Low Risk / Great for Cats
  └─────────────────────────────────────────────────────────────► Booking Frequency
```

---

## 📡 REST API & Streaming Endpoints Reference

Interactive documentation is available at **`http://localhost:8000/docs`** (Swagger UI) or **`http://localhost:8000/redoc`**.

### Summary of Endpoints

| Method | Endpoint | Description | Request Parameters / Body | Response Payload |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | Serves the single-page dashboard UI | None | `text/html` |
| `GET` | `/api/services` | Returns supported Rover service types | `platform` (query, opt) | `{"dog-walking": "Dog Walking", ...}` |
| `GET` | `/api/platforms` | Returns supported marketplace platforms | None | `{"platforms": ["rover", "wag", "care"]}` |
| `GET` | `/api/sitters/normalized` | Master catalog of sitters & multi-service rates | None | `{"sitters": [...]}` |
| `GET` | `/api/history` | Lists all historical scraping sessions | None | `{"sessions": [...]}` |
| `GET` | `/api/history/{session_id}` | Detailed session statistics & listings | `session_id` (path, int) | Complete session object + `full_stats` |
| `POST`| `/api/history/analyze` | Combined analysis across selected sessions | `{"session_ids": [int]}` | Aggregated stats, 5-service matrix & records |
| `DELETE`| `/api/history/{session_id}`| Deletes a single session and its sitters | `session_id` (path, int) | `{"status": "success", "deleted_session_id": int}` |
| `DELETE`| `/api/history` | Batch deletes multiple search sessions | `{"session_ids": [int]}` | `{"status": "success", "deleted_count": int}` |
| `POST`| `/api/database/reset` | Clears all tables in the database | None | `{"status": "success", "message": str}` |
| `GET` | `/api/scrape/stream` | Multi-page scraping live SSE stream | `location`, `service_type`, `radius_km`, `max_pages`, `max_results`, `platform` | `text/event-stream` SSE events |
| `POST` | `/api/analytics/recalculate` | Dynamic stats re-calculation | `{"session_id": int, "excluded_indices": [int], "records": [...]}` | `{"stats": {...}, "auto_outliers": [...]}` |
| `GET` | `/api/analytics/temporal-trends` | Time-series historical price trends | None | `{"trends": [...]}` |
| `GET` | `/api/export/csv/{session_id}` | CSV download of a specific session | `session_id` (path, int) | `text/csv` attachment |
| `GET` | `/api/export/master-csv` | Consolidated historical CSV archive | None | `text/csv` master archive |
| `GET` | `/api/export/database` | Direct SQLite database binary backup | None | `application/x-sqlite3` file download |

---

## 🧪 Automated Testing Suite

The repository includes a comprehensive unit testing suite using [`pytest`](https://docs.pytest.org/) with **45 automated tests** covering analytics, persistence, scrapers, and Supabase synchronization:

### Running the Tests

```bash
# Run all automated tests with verbose output
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

### Test Coverage Highlights

- **[`tests/test_analytics.py`](tests/test_analytics.py)**:
  - Percentiles ($P_{10}, P_{25}, P_{75}, P_{90}$), trimmed means, and IQR dispersion.
  - Safe handling of empty datasets without division-by-zero crashes.
  - Dynamic outlier exclusion calculation and Tukey's $1.5 \times \text{IQR}$ boundary classification.
  - Pricing sweet spot empirical survival curves and Price Elasticity of Demand.

- **[`tests/test_database.py`](tests/test_database.py)**:
  - Table creation, schema migrations, and index validation in SQLite.
  - Write-read cycles, sitter exclusion state updates, and batch deletions.

- **[`tests/test_scraper_logic.py`](tests/test_scraper_logic.py)**:
  - Scraper factory instantiation and platform dispatch (`rover`, `wag`, `care`).
  - Search URL query parameter construction and coordinate anchoring (`lat`/`lng`) to prevent cloud IP location drift.
  - CSS selector heuristics and fallback extraction routines.

- **[`tests/test_supabase_sync.py`](tests/test_supabase_sync.py)**:
  - Real-time automatic background syncing of scraped sessions to Supabase PostgreSQL.
  - Payload transformation and UUID generation.
  - Resilience against network drops or missing Supabase credentials (graceful fallback).

---

## 🚀 Deployment & Installation

### Option 1: Cloud Deployment on Render.com (Recommended for Free Hosting)

Deploy with a managed Docker environment on Render connected to Supabase:
- Follow the detailed step-by-step guide in [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md).
- To configure and migrate your Supabase PostgreSQL database, follow [SUPABASE_DEPLOYMENT.md](SUPABASE_DEPLOYMENT.md).

### Option 2: Quick Deployment with Docker

```bash
# Clone repository
git clone https://github.com/dagudelob/Rover-rate-analisis.git
cd Rover-rate-analisis

# Build and start container
docker compose up --build -d
```
Access the application at **`http://localhost:8000`**.

### Option 3: Local Setup using `uv` or `venv`

```bash
# Using uv (fastest)
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📁 Repository Structure

```
.
├── app/                              # Modular FastAPI application package
│   ├── main.py                       # FastAPI application factory, middleware, SSE streaming & lifespan
│   ├── config.py                     # Centralized settings & Supabase/SQLite environment config
│   ├── api/
│   │   └── routes/                   # Modular REST API endpoints
│   │       ├── analytics.py          # Temporal trends & recalculation routes
│   │       ├── export.py             # CSV and direct database backup endpoints
│   │       ├── history.py            # Session management, batch deletion & analysis
│   │       └── scraping.py           # SSE stream scraper & real-time Supabase sync trigger
│   ├── db/
│   │   ├── session.py                # SQLite context manager, indexing & schema migrations
│   │   ├── supabase_client.py        # Supabase client singleton & connectivity checks
│   │   └── supabase_sync.py          # Real-time background sync engine (SQLite -> Supabase)
│   └── services/
│       ├── analytics.py              # Empirical survival pricing, PED, & IQR statistics
│       └── scraper/                  # Multi-platform browser crawler engine
│           ├── browser.py            # Playwright browser manager with geolocation spoofing
│           ├── factory.py            # Strategy factory for Rover, Wag, and Care
│           └── rover_strategy.py     # Rover crawler with lat/lng anchor & anti-fingerprinting
├── tests/                            # Comprehensive Pytest suite (44 unit tests)
│   ├── test_analytics.py             # Math, economics, and statistical validations
│   ├── test_database.py              # SQLite persistence, migrations, and transactions
│   ├── test_scraper_logic.py         # Crawler strategies, coordinate anchoring & parsers
│   └── test_supabase_sync.py         # Dual-persistence & Supabase sync resilience tests
├── static/                           # Modern SPA dashboard frontend
│   ├── index.html                    # Dashboard UI with Leaflet, KaTeX, and Chart.js
│   ├── style.css                     # Responsive design system & dark/light theme tokens
│   └── app.js                        # Frontend state, SSE client, Leaflet map & charting
├── Dockerfile                        # Multi-stage production container with Playwright Chromium
├── docker-compose.yml                # Local orchestration configuration
├── RENDER_DEPLOYMENT.md              # Complete Render.com deployment manual
├── SUPABASE_DEPLOYMENT.md            # Supabase schema definitions and migration manual
├── requirements.txt                  # Python dependencies
├── LICENSE                           # MIT License
└── README.md                         # Project documentation and architecture guide
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
