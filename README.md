# 🐾 Rover Market Intelligence & Pricing Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Stealth-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

An end-to-end **Data Science & Market Intelligence Platform** for **Rover.com**. This repository extracts multi-page market listings, models the empirical relationship between pricing and hiring probability to determine the mathematical **Revenue Sweet Spot**, renders interactive geospatial price heatmaps with service radius overlays, and provides statistical outlier management with complete historical archiving.

---

## 🌟 Key Features

1. **High-Volume Multi-Page Scraping (100+ Sitters)**:
   - Built with **Playwright** and **Playwright-Stealth** to bypass Cloudflare anti-bot fingerprinting (`navigator.webdriver`, WebGL, canvas).
   - Simulates human behavior with smooth progressive scrolling, realistic navigation headers (`Sec-Fetch`, `Accept-Language`), and stochastic delay intervals.
   - Streams live progress and page-by-page events directly to the UI via **Server-Sent Events (SSE)**.

2. **Optimal Pricing & Revenue Maximizer**:
   - Solves the pricing trade-off: **Low price** (high conversion, minimal margin) vs. **High price** (high margin, near-zero conversion).
   - Evaluates the **Empirical Expected Revenue Model**:
     $$\text{Expected Revenue Index}(P) = P \times \mathbb{P}(\text{Hiring Conversion} \mid P)$$
   - Outputs the recommended **Optimal Price Point (Sweet Spot)** and **Optimal Pricing Bracket**.

3. **Geospatial Price Heatmap & Hover Service Areas**:
   - Interactive Leaflet heatmap visualizing localized price density gradients.
   - Price bubble pins with full profile cards.
   - Dynamic **hover interaction**: hovering over any sitter row draws their active service radius circle on the map in real-time.

4. **Statistical Data Studio & Outlier Control**:
   - Automatic outlier detection using the **Interquartile Range (IQR) Rule** ($Q_1 - 1.5\text{IQR}$ to $Q_3 + 1.5\text{IQR}$).
   - Individual sitter checkboxes for manual filtering.
   - Live recalculation of **10% Trimmed Mean**, **Standard Deviation ($\sigma$)**, **Variance ($\sigma^2$)**, and percentiles ($P_{10}, P_{25}, P_{75}, P_{90}$).

5. **Historical Archive & Yearly Temporal Variations**:
   - Tracks market price evolution across dates to detect seasonal shifts.
   - Direct export of SQLite database (`.db`) and consolidated master CSV archive.

---

## 🔬 Data Science Techniques & Advanced Recommendations

For Data Science portfolios and academic/commercial evaluation, the platform integrates:

| Area | Techniques Applied & Extensible |
| :--- | :--- |
| **Econometrics & Pricing** | Survival Analysis on competitor prices, Logistic demand curves, Expected Value maximization. |
| **Statistical Robustness** | Interquartile Range (IQR) outlier trimming, 10% Trimmed Means, Kernel Density Estimation (KDE). |
| **Geospatial Analytics** | Nominatim OpenStreetMap geocoding, Haversine/Euclidean distance buffers, Leaflet Gaussian Heatmaps. |
| **Time Series Modeling** | Historical longitudinal price variations, seasonal trend decomposition. |
| **Machine Learning Extensions** | Multi-variable Elasticity (OLS/XGBoost on Price ~ Reviews + Badge + Response Time + Distance). |

---

## 🚀 Deployment & Installation

### Option 1: Quick Deployment with Docker (Recommended)

Make sure you have [Docker](https://www.docker.com/) and Docker Compose installed:

```bash
# Clone the repository
git clone https://github.com/dagudelo/Rover-rate-analisis.git
cd Rover-rate-analisis

# Build and start the container
docker compose up --build -d
```
The application will be live at: **`http://localhost:8000`**

To stop the container:
```bash
docker compose down
```

---

### Option 2: Local Setup using `uv` (Ultra-Fast Python Package Manager)

If you use [`uv`](https://github.com/astral-sh/uv):

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows

uv pip install -r requirements.txt
playwright install chromium

# Launch the FastAPI dev server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

### Option 3: Local Setup using standard `venv` & `pip`

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scripts\activate   # On Windows

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Install Playwright browser binaries
playwright install chromium

# 4. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📁 Repository Structure

```
.
├── main.py               # FastAPI backend with REST endpoints, SSE streams & static file mounting
├── scraper.py            # Playwright-Stealth multi-page scraper with human behavior emulation
├── analytics.py          # Optimal revenue maximizer, IQR outlier filtering & dispersion stats
├── database.py           # SQLite database schema, temporal queries & session management
├── Dockerfile            # Container definition with system dependencies and Playwright Chromium
├── docker-compose.yml    # Docker Compose deployment definition
├── requirements.txt      # Python dependencies
├── static/
│   ├── index.html        # Single-page dashboard with collapsible sidebar & 6 modules
│   ├── style.css         # Modern glassmorphism dark theme CSS
│   └── app.js            # Client logic for Leaflet, Chart.js, SSE & dynamic recalculations
└── README.md             # Project documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
