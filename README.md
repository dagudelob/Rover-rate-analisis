# 🐾 Rover Market Intelligence & Pricing Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Stealth-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

An end-to-end **Data Science & Market Intelligence Platform** for **Rover.com**. This platform extracts multi-page market listings, models the empirical relationship between pricing and booking conversion probability via **Empirical Survival Analysis**, identifies the mathematical **Revenue Sweet Spot** using **Price Elasticity of Demand (PED)**, renders interactive geospatial heatmaps with service radius overlays, and provides statistical outlier management with persistent database storage.

---

## 🌟 Key Features

1. **High-Volume Multi-Page Scraping (100+ Sitters)**:
   - Built with **Playwright** and **Playwright-Stealth** to bypass Cloudflare anti-bot fingerprinting (`navigator.webdriver`, WebGL, canvas).
   - Simulates human behavior with smooth progressive scrolling, realistic navigation headers (`Sec-Fetch`, `Accept-Language`), and stochastic delay intervals.
   - Streams live progress and page-by-page events directly to the UI via **Server-Sent Events (SSE)**.

2. **Empirical Revenue Maximizer & Price Elasticity**:
   - Solves the classic pricing trade-off: **Low price** (high volume, minimal margin) vs. **High price** (high margin, near-zero conversion).
   - Uses the **Empirical Survival Function (ESF)** with Silverman's Gaussian kernel smoothing:
     $$P(\text{conversion} \mid P) = \frac{1}{N} \sum_{i=1}^N \frac{1}{1 + \exp\left(\frac{P - P_i}{h}\right)}$$
   - Evaluates the **Expected Revenue Index**:
     $$\text{EVI}(P) = P \times P(\text{conversion} \mid P)$$
   - Computes **Price Elasticity of Demand (PED)** to locate the unitary elasticity point ($|\epsilon| \approx 1.0$) where revenue is mathematically maximized.

3. **Geospatial Price Heatmap & Dynamic Service Buffers**:
   - Interactive Leaflet heatmap visualizing localized price density gradients.
   - Dynamic **hover interaction**: hovering over any sitter row draws their active service radius circle on the map in real-time.

4. **Statistical Data Studio & Outlier Control**:
   - Automatic outlier detection using the **Interquartile Range (IQR) Rule** ($Q_1 - 1.5\text{IQR}$ to $Q_3 + 1.5\text{IQR}$).
   - Individual sitter checkboxes for manual filtering with **SQLite persistence** (`is_excluded`, `excluded_reason`).
   - Live recalculation of **10% Trimmed Mean**, **Standard Deviation ($\sigma$)**, **Variance ($\sigma^2$)**, and percentiles ($P_{10}, P_{25}, P_{75}, P_{90}$).

5. **Historical Archive & Yearly Temporal Variations**:
   - Tracks market price evolution across dates to detect seasonal shifts.
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
| `GET` | `/api/services` | Returns supported Rover service types | None | `{"dog-walking": "Dog Walking", ...}` |
| `GET` | `/api/history` | Lists all historical scraping sessions | None | `{"sessions": [...]}` |
| `GET` | `/api/history/{session_id}` | Detailed session statistics & listings | `session_id` (path, int) | Complete session object + `full_stats` |
| `GET` | `/api/scrape/stream` | Multi-page scraping live SSE stream | `location`, `service_type`, `radius_km`, `max_pages`, `max_results` | `text/event-stream` SSE events |
| `POST` | `/api/analytics/recalculate` | Dynamic stats re-calculation | `{"session_id": int, "excluded_indices": [int], "records": [...]}` | `{"stats": {...}, "auto_outliers": [...]}` |
| `POST` | `/api/sitters/{sitter_id}/exclude` | Persists sitter exclusion in SQLite | `sitter_id` (path), `{"is_excluded": bool, "reason": str}` | `{"status": "success", "sitter_id": int}` |
| `GET` | `/api/analytics/temporal-trends` | Time-series historical price trends | None | `{"trends": [...]}` |
| `GET` | `/api/export/csv/{session_id}` | CSV download of a specific session | `session_id` (path, int) | `text/csv` attachment |
| `GET` | `/api/export/master-csv` | Consolidated historical CSV archive | None | `text/csv` master archive |
| `GET` | `/api/export/database` | Direct SQLite database binary backup | None | `application/x-sqlite3` file download |

---

## 🧪 Automated Testing Suite

The repository includes a comprehensive unit testing suite using [`pytest`](https://docs.pytest.org/):

### Running the Tests

```bash
# Run all automated tests with verbose output
PYTHONPATH=. .venv/bin/pytest tests/ -v
```

### Test Coverage

- **[`tests/test_analytics.py`](tests/test_analytics.py)**:
  - `test_market_statistics_basic`: Validates percentiles ($P_{10}, P_{25}, P_{75}, P_{90}$), trimmed means, and IQR dispersion.
  - `test_market_statistics_empty`: Verifies safe handling of empty datasets without division-by-zero crashes.
  - `test_market_statistics_with_exclusions`: Tests dynamic outlier exclusion calculation accuracy.
  - `test_detect_outliers_iqr`: Validates Tukey's $1.5 \times \text{IQR}$ upper and lower boundary classification.
  - `test_pricing_sweet_spot_empirical_survival`: Verifies monotonicity of the survival demand curve and Price Elasticity calculation.

- **[`tests/test_database.py`](tests/test_database.py)**:
  - `test_database_lifecycle_and_schema`: Verifies table creation, schema integrity, and index existence.
  - `test_save_and_retrieve_session`: Tests full write-read cycle and verifies that sitter exclusion state updates persist correctly in SQLite.

---

## 🚀 Deployment & Installation

### Option 1: Quick Deployment with Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/dagudelob/Rover-rate-analisis.git
cd Rover-rate-analisis

# Build and start container
docker compose up --build -d
```
Access the application at **`http://localhost:8000`**.

### Option 2: Local Setup using `uv` (Fastest)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Standard `venv` & `pip`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📁 Repository Structure

```
.
├── main.py               # FastAPI server, SSE streaming, lifespan management & REST API
├── scraper.py            # Playwright-Stealth multi-page crawler with human anti-fingerprinting
├── analytics.py          # Empirical Survival pricing, Price Elasticity of Demand & IQR statistics
├── database.py           # SQLite context manager, indexing, schema migrations & persistence
├── tests/
│   ├── test_analytics.py # Unit tests for statistics, IQR filtering & empirical optimizer
│   └── test_database.py  # Unit tests for database transactions, indexes & exclusions
├── Dockerfile            # Container image with Playwright Chromium & dependencies
├── docker-compose.yml    # Compose orchestration configuration
├── requirements.txt      # Python dependencies (FastAPI, Playwright, Pandas, NumPy, etc.)
├── static/
│   ├── index.html        # Interactive Single-Page Dashboard & DS Academy
│   ├── style.css         # Modern glassmorphism dark theme CSS
│   └── app.js            # Leaflet map, Chart.js, SSE live stream & interactive demos
└── README.md             # Project documentation and API reference
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
