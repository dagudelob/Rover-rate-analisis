// Chart instances
let priceChartInstance = null;
let ratingChartInstance = null;
let temporalChartInstance = null;
let revenueChartInstance = null;

// Active Session state
let currentSessionId = null;
let currentRecords = [];
let currentExcludedIndices = new Set();
let currentAutoOutliers = [];
let currentCenterLat = null;
let currentCenterLng = null;
let activeEventSource = null;

// Leaflet Map & Layer instances
let mapInstance = null;
let heatLayerInstance = null;
let markersLayerGroup = null;
let activeCoverageCircle = null;
let sitterMarkersMap = new Map();

document.addEventListener("DOMContentLoaded", () => {
    setupSidebarNavigation();
    loadServices();
    loadHistory();
    loadTemporalTrends();
    setupForm();
    setupOutlierToolbar();
});

// 1. Collapsible Sidebar Navigation and Smooth Scrolling
function setupSidebarNavigation() {
    const sidebar = document.getElementById("appNavSidebar");
    const toggleBtn = document.getElementById("sidebarToggleBtn");
    const navLinks = document.querySelectorAll(".nav-link");

    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            sidebar.classList.toggle("collapsed");
        });
    }

    window.addEventListener("scroll", () => {
        let currentSectionId = "";
        const sections = document.querySelectorAll(".content-section");
        
        sections.forEach((sec) => {
            const top = sec.offsetTop - 120;
            if (window.scrollY >= top) {
                currentSectionId = sec.getAttribute("id");
            }
        });

        navLinks.forEach((link) => {
            link.classList.remove("active");
            if (link.getAttribute("href") === `#${currentSectionId}`) {
                link.classList.add("active");
            }
        });
    });
}

// 2. Load Service categories
async function loadServices() {
    try {
        const res = await fetch("/api/services");
        const services = await res.json();
        const select = document.getElementById("serviceSelect");
        select.innerHTML = "";
        
        for (const [key, label] of Object.entries(services)) {
            const opt = document.createElement("option");
            opt.value = key;
            opt.textContent = label;
            select.appendChild(opt);
        }
    } catch (err) {
        console.error("Error loading services:", err);
    }
}

// 3. Load Search History List
async function loadHistory() {
    try {
        const res = await fetch("/api/history");
        const data = await res.json();
        const list = document.getElementById("historyList");
        list.innerHTML = "";

        if (!data.sessions || data.sessions.length === 0) {
            list.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding: 1.5rem;">No searches saved yet.</p>`;
            return;
        }

        data.sessions.forEach((s) => {
            const date = new Date(s.timestamp).toLocaleString("en-US", {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
            });
            const item = document.createElement("div");
            item.className = `history-item ${s.id === currentSessionId ? "active" : ""}`;
            item.onclick = () => loadSessionDetails(s.id);
            
            const avgDisplay = s.avg_price ? `$${s.avg_price.toFixed(1)}` : "--";

            item.innerHTML = `
                <div class="history-info">
                    <h4>${escapeHtml(s.location)} (${s.total_sitters} sitters)</h4>
                    <p>${escapeHtml(s.service_type)} • ${date} ${s.radius_km ? `• ${s.radius_km}km radius` : ''}</p>
                </div>
                <div class="history-stat">
                    <div class="avg">${avgDisplay}</div>
                    <p style="font-size:0.7rem; color:var(--text-muted);">Session #${s.id}</p>
                </div>
            `;
            list.appendChild(item);
        });
    } catch (err) {
        console.error("Error loading history:", err);
    }
}

// 4. Load Detailed Session
async function loadSessionDetails(sessionId) {
    currentSessionId = sessionId;
    loadHistory();

    try {
        const res = await fetch(`/api/history/${sessionId}`);
        if (!res.ok) throw new Error("Could not load session");
        const data = await res.json();
        
        currentRecords = data.sitters || [];
        currentExcludedIndices.clear();
        currentAutoOutliers = data.auto_outliers || [];
        currentCenterLat = data.center_lat;
        currentCenterLng = data.center_lng;

        renderResults(data.full_stats, currentRecords, data.location, data.service_type, sessionId, data.center_lat, data.center_lng);
        logToTerminal(`[History] Loaded session #${sessionId} with ${currentRecords.length} sitters.`, "info");
        
        const resContainer = document.getElementById("resultsContainer");
        if (resContainer) {
            resContainer.scrollIntoView({ behavior: "smooth" });
        }
    } catch (err) {
        console.error("Error loading session details:", err);
    }
}

// 5. Setup Form Submission with High-Volume Multi-Page & Radius
function setupForm() {
    const form = document.getElementById("scraperForm");

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const location = document.getElementById("locationInput").value.trim();
        const service = document.getElementById("serviceSelect").value;
        const radiusKm = document.getElementById("radiusInput").value.trim();
        const maxPages = document.getElementById("maxPagesInput").value;
        const maxResults = document.getElementById("maxResultsInput").value.trim();
        const proxy = document.getElementById("proxyInput").value.trim();

        if (!location) {
            alert("Please provide a valid location or postal code.");
            return;
        }

        startScrapeStream(location, service, radiusKm, maxPages, maxResults, proxy);
    });
}

function startScrapeStream(location, service, radiusKm, maxPages, maxResults, proxy) {
    const btn = document.getElementById("startBtn");
    const progressBar = document.getElementById("progressBar");
    const terminal = document.getElementById("terminal");
    
    btn.disabled = true;
    btn.innerHTML = `<svg class="animate-spin" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle><path d="M12 2a10 10 0 0 1 10 10" stroke-linecap="round"></path></svg> Multi-Page Scraping in Progress...`;
    terminal.innerHTML = "";
    progressBar.style.width = "5%";

    if (activeEventSource) {
        activeEventSource.close();
    }

    let url = `/api/scrape/stream?location=${encodeURIComponent(location)}&service_type=${encodeURIComponent(service)}&max_pages=${maxPages}`;
    if (radiusKm) url += `&radius_km=${radiusKm}`;
    if (maxResults) url += `&max_results=${maxResults}`;
    if (proxy) url += `&proxy_url=${encodeURIComponent(proxy)}`;

    const eventSource = new EventSource(url);
    activeEventSource = eventSource;

    eventSource.addEventListener("log", (e) => {
        const data = JSON.parse(e.data);
        logToTerminal(data.message, "info");
    });

    eventSource.addEventListener("page_start", (e) => {
        const data = JSON.parse(e.data);
        const progress = Math.min(95, ((data.page - 0.5) / data.max_pages) * 100);
        progressBar.style.width = `${progress}%`;
        logToTerminal(`-> Processing page ${data.page}/${data.max_pages}`, "info");
    });

    eventSource.addEventListener("page_done", (e) => {
        const data = JSON.parse(e.data);
        logToTerminal(`[✓] Page ${data.page} completed (+${data.records_found} sitters, total imported: ${data.total_records_so_far})`, "success");
    });

    eventSource.addEventListener("complete", (e) => {
        const data = JSON.parse(e.data);
        progressBar.style.width = "100%";
        logToTerminal(`[✓] Scraping finished successfully. Total: ${data.records.length} sitters. Saved with Session ID #${data.session_id}`, "success");
        
        currentSessionId = data.session_id;
        currentRecords = data.records || [];
        currentExcludedIndices.clear();
        currentAutoOutliers = data.auto_outliers || [];
        currentCenterLat = data.center_lat;
        currentCenterLng = data.center_lng;

        renderResults(data.stats, currentRecords, data.location, data.service_type, data.session_id, data.center_lat, data.center_lng);
        loadHistory();
        loadTemporalTrends();
    });

    eventSource.addEventListener("error", (e) => {
        if (e.data) {
            try {
                const data = JSON.parse(e.data);
                logToTerminal(`[ERROR] ${data.message}`, "error");
            } catch {
                logToTerminal("[ERROR] Stream error occurred.", "error");
            }
        }
    });

    eventSource.addEventListener("end", () => {
        eventSource.close();
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start 100-Sitter Import`;
    });

    eventSource.onerror = () => {
        eventSource.close();
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start 100-Sitter Import`;
    };
}

function logToTerminal(msg, type = "info") {
    const terminal = document.getElementById("terminal");
    const line = document.createElement("div");
    line.className = `terminal-line ${type}`;
    const time = new Date().toLocaleTimeString("en-US", { hour12: false });
    line.textContent = `[${time}] ${msg}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

// 6. Render All Dashboard Results, Price Optimizer & Outlier Indicators
function renderResults(stats, records, location, service, sessionId, centerLat, centerLng) {
    document.getElementById("resultsContainer").style.display = "block";
    
    // Update KPI Overview Cards
    document.getElementById("statTotal").textContent = stats.active_sitters || (records ? records.length : 0);
    document.getElementById("statExcludedCount").textContent = `${stats.excluded_sitters || 0} excluded outliers`;
    
    document.getElementById("statAvg").textContent = stats.avg_price ? `$${stats.avg_price}` : "--";
    document.getElementById("statTrimmed").textContent = stats.trimmed_mean_10 ? `$${stats.trimmed_mean_10}` : "--";
    document.getElementById("statMedian").textContent = stats.median_price ? `$${stats.median_price}` : "--";
    document.getElementById("statMin").textContent = stats.min_price ? `$${stats.min_price}` : "--";
    document.getElementById("statMax").textContent = stats.max_price ? `$${stats.max_price}` : "--";
    document.getElementById("statIQR").textContent = (stats.p25_price && stats.p75_price) ? `$${stats.p25_price} - $${stats.p75_price}` : "--";
    document.getElementById("statStdDev").textContent = stats.std_dev ? `±$${stats.std_dev}` : "--";
    document.getElementById("statVariance").textContent = stats.variance ? `${stats.variance}` : "--";

    // Update Optimal Pricing Card & Revenue Curve
    const opt = stats.pricing_optimizer || {};
    if (opt.sweet_spot_price) {
        document.getElementById("optimizerSweetSpot").textContent = `$${opt.sweet_spot_price.toFixed(0)}`;
        document.getElementById("optimizerRange").textContent = `$${opt.recommended_range.min.toFixed(0)} - $${opt.recommended_range.max.toFixed(0)}`;
        renderRevenueOptimizationChart(opt.curve || [], opt.sweet_spot_price);
    }

    // Update Advanced Stats Matrix
    document.getElementById("statP10").textContent = stats.p10_price ? `$${stats.p10_price}` : "--";
    document.getElementById("statP25").textContent = stats.p25_price ? `$${stats.p25_price}` : "--";
    document.getElementById("statP75").textContent = stats.p75_price ? `$${stats.p75_price}` : "--";
    document.getElementById("statP90").textContent = stats.p90_price ? `$${stats.p90_price}` : "--";
    document.getElementById("statStdDevBox").textContent = stats.std_dev ? `±$${stats.std_dev}` : "--";
    document.getElementById("statTrimmedBox").textContent = stats.trimmed_mean_10 ? `$${stats.trimmed_mean_10}` : "--";

    // Update Outlier Toolbar Info
    document.getElementById("iqrOutlierCountBadge").textContent = currentAutoOutliers.length;
    if (stats.outlier_bounds && stats.outlier_bounds.lower !== null) {
        document.getElementById("iqrBoundsLabel").textContent = `$${stats.outlier_bounds.lower} to $${stats.outlier_bounds.upper}`;
    }

    // Setup Export Link
    const csvBtn = document.getElementById("exportCsvBtn");
    if (csvBtn && sessionId) {
        csvBtn.href = `/api/export/csv/${sessionId}`;
        csvBtn.style.display = "inline-flex";
    }

    // Render Components
    renderHeatmap(records || [], centerLat, centerLng, stats);
    renderPriceChart(stats.price_distribution || []);
    renderRatingScatter(records || []);
    renderTable(records || []);
}

// 7. Render Revenue Optimization Chart (Price vs. Conversion & Expected Revenue)
function renderRevenueOptimizationChart(curveData, sweetSpotPrice) {
    const ctx = document.getElementById("revenueOptimizationChart").getContext("2d");
    if (revenueChartInstance) revenueChartInstance.destroy();

    if (!curveData || curveData.length === 0) return;

    const labels = curveData.map(c => `$${c.price}`);
    const conversionData = curveData.map(c => c.conversion_probability_pct);
    const revenueData = curveData.map(c => c.expected_revenue_index);

    revenueChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Expected Revenue Index (Profit × Probability)",
                    data: revenueData,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.18)",
                    fill: true,
                    yAxisID: "yRevenue",
                    tension: 0.35,
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: "Hiring Conversion Probability (%)",
                    data: conversionData,
                    borderColor: "#3b82f6",
                    backgroundColor: "transparent",
                    borderDash: [4, 4],
                    yAxisID: "yProb",
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: { color: "#cbd5e1", font: { size: 11 } }
                },
                tooltip: {
                    callbacks: {
                        afterLabel: (ctx) => {
                            const p = curveData[ctx.dataIndex];
                            if (p.price === sweetSpotPrice) {
                                return "⭐ OPTIMAL REVENUE SWEET SPOT";
                            }
                            return "";
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#9ca3af", font: { size: 10 } }
                },
                yRevenue: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: { display: true, text: 'Expected Revenue Score', color: '#10b981' },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#10b981" }
                },
                yProb: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: { display: true, text: 'Hiring Probability (%)', color: '#60a5fa' },
                    grid: { drawOnChartArea: false },
                    ticks: { color: "#60a5fa" }
                }
            }
        }
    });
}

// 8. Dynamic Outlier Manipulation & Recalculation
function setupOutlierToolbar() {
    const btnAutoIQR = document.getElementById("btnAutoFilterIQR");
    const btnReset = document.getElementById("btnResetFilters");

    btnAutoIQR.addEventListener("click", () => {
        if (currentAutoOutliers.length === 0) {
            alert("No price points fall outside the 1.5 * IQR outlier boundary.");
            return;
        }
        currentAutoOutliers.forEach(idx => currentExcludedIndices.add(idx));
        recalculateAndRefresh();
    });

    btnReset.addEventListener("click", () => {
        currentExcludedIndices.clear();
        recalculateAndRefresh();
    });
}

async function toggleSitterExclusion(index) {
    if (currentExcludedIndices.has(index)) {
        currentExcludedIndices.delete(index);
    } else {
        currentExcludedIndices.add(index);
    }
    await recalculateAndRefresh();
}

async function recalculateAndRefresh() {
    try {
        const res = await fetch("/api/analytics/recalculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                records: currentRecords,
                excluded_indices: Array.from(currentExcludedIndices)
            })
        });

        const data = await res.json();
        currentAutoOutliers = data.auto_outliers || [];

        renderResults(data.stats, currentRecords, "", "", currentSessionId, currentCenterLat, currentCenterLng);
    } catch (err) {
        console.error("Error recalculating stats:", err);
    }
}

// 9. Leaflet Map with Price Pins & Active Coverage
function initMapIfNeeded(centerLat, centerLng) {
    const lat = centerLat || 43.6532;
    const lng = centerLng || -79.3832;

    if (!mapInstance) {
        mapInstance = L.map('mapContainer', {
            center: [lat, lng],
            zoom: 13,
            zoomControl: true
        });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(mapInstance);

        markersLayerGroup = L.layerGroup().addTo(mapInstance);
    } else {
        mapInstance.setView([lat, lng], 13);
        mapInstance.invalidateSize();
    }
}

function renderHeatmap(records, centerLat, centerLng, stats) {
    initMapIfNeeded(centerLat, centerLng);

    markersLayerGroup.clearLayers();
    if (heatLayerInstance) {
        mapInstance.removeLayer(heatLayerInstance);
        heatLayerInstance = null;
    }
    if (activeCoverageCircle) {
        mapInstance.removeLayer(activeCoverageCircle);
        activeCoverageCircle = null;
    }
    sitterMarkersMap.clear();

    if (!records || records.length === 0) return;

    const minPrice = stats.min_price || 15;
    const maxPrice = stats.max_price || 40;
    const priceRange = Math.max(1, maxPrice - minPrice);
    const heatPoints = [];

    records.forEach((sitter, index) => {
        if (currentExcludedIndices.has(index)) return;

        const lat = sitter.lat || (centerLat || 43.6532);
        const lng = sitter.lng || (centerLng || -79.3832);
        const price = sitter.price_numeric || 20;

        const intensity = 0.3 + 0.7 * ((price - minPrice) / priceRange);
        heatPoints.push([lat, lng, intensity]);

        let markerBg = "#10b981";
        if (price > minPrice + 0.66 * priceRange) {
            markerBg = "#ef4444";
        } else if (price > minPrice + 0.33 * priceRange) {
            markerBg = "#3b82f6";
        }

        const customIcon = L.divIcon({
            className: 'custom-price-marker',
            html: `<div id="map-pin-${index}" class="price-marker-pin" style="background-color: ${markerBg};">$${price.toFixed(0)}</div>`,
            iconSize: [42, 24],
            iconAnchor: [21, 12]
        });

        const marker = L.marker([lat, lng], { icon: customIcon }).addTo(markersLayerGroup);

        const popupContent = `
            <div class="sitter-popup-card">
                <h4>${escapeHtml(sitter.name)}</h4>
                <p>${escapeHtml(sitter.headline || sitter.neighborhood || 'Local Pet Sitter')}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <span class="sitter-popup-badge">${escapeHtml(sitter.raw_price)}</span>
                    <span style="font-size:0.8rem; color:#f59e0b;">★ ${escapeHtml(sitter.rating || '5.0')} (${sitter.reviews_count || 0})</span>
                </div>
                ${sitter.profile_url ? `<a href="${sitter.profile_url}" target="_blank" style="display:block; margin-top:8px; font-size:0.75rem; color:#3b82f6; text-decoration:none;">View Rover Profile ↗</a>` : ''}
            </div>
        `;
        marker.bindPopup(popupContent);

        marker.on('mouseover', () => highlightSitterCoverage(sitter, index, false));
        marker.on('mouseout', () => clearSitterCoverage(index));

        sitterMarkersMap.set(index, { marker, sitter, lat, lng });
    });

    if (typeof L.heatLayer === 'function' && heatPoints.length > 0) {
        heatLayerInstance = L.heatLayer(heatPoints, {
            radius: 35,
            blur: 22,
            maxZoom: 15,
            max: 1.0,
            gradient: { 0.2: '#10b981', 0.5: '#3b82f6', 0.8: '#f59e0b', 1.0: '#ef4444' }
        }).addTo(mapInstance);
    }
}

function highlightSitterCoverage(sitter, index, panTo = false) {
    if (!mapInstance) return;

    if (activeCoverageCircle) {
        mapInstance.removeLayer(activeCoverageCircle);
        activeCoverageCircle = null;
    }

    const lat = sitter.lat;
    const lng = sitter.lng;
    const radiusMeters = (sitter.service_radius_km || 1.8) * 1000;

    activeCoverageCircle = L.circle([lat, lng], {
        radius: radiusMeters,
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.18,
        weight: 2,
        dashArray: '4, 6'
    }).addTo(mapInstance);

    const rows = document.querySelectorAll("#sittersTableBody tr");
    rows.forEach(r => r.classList.remove("sitter-row-active"));
    if (rows[index]) {
        rows[index].classList.add("sitter-row-active");
    }

    const pin = document.getElementById(`map-pin-${index}`);
    if (pin) {
        pin.style.transform = "scale(1.35)";
        pin.style.borderColor = "#fff";
        pin.style.boxShadow = "0 0 15px rgba(59, 130, 246, 0.9)";
    }

    if (panTo) {
        mapInstance.panTo([lat, lng], { animate: true, duration: 0.5 });
    }
}

function clearSitterCoverage(index) {
    if (activeCoverageCircle && mapInstance) {
        mapInstance.removeLayer(activeCoverageCircle);
        activeCoverageCircle = null;
    }

    const rows = document.querySelectorAll("#sittersTableBody tr");
    if (rows[index]) {
        rows[index].classList.remove("sitter-row-active");
    }

    const pin = document.getElementById(`map-pin-${index}`);
    if (pin) {
        pin.style.transform = "scale(1)";
        pin.style.borderColor = "rgba(255,255,255,0.8)";
        pin.style.boxShadow = "0 4px 12px rgba(0,0,0,0.6)";
    }
}

// 10. Charts Rendering
function renderPriceChart(distribution) {
    const ctx = document.getElementById("priceDistributionChart").getContext("2d");
    if (priceChartInstance) priceChartInstance.destroy();

    const labels = distribution.map(d => d.range);
    const data = distribution.map(d => d.count);

    priceChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels.length ? labels : ["No data"],
            datasets: [{
                label: "Sitters Count",
                data: data.length ? data : [0],
                backgroundColor: "rgba(59, 130, 246, 0.65)",
                borderColor: "#3b82f6",
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af" } },
                y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af", stepSize: 1 } }
            }
        }
    });
}

function renderRatingScatter(records) {
    const ctx = document.getElementById("ratingScatterChart").getContext("2d");
    if (ratingChartInstance) ratingChartInstance.destroy();

    const scatterData = records
        .map((r, idx) => ({
            x: r.reviews_count || 0,
            y: r.price_numeric,
            name: r.name,
            rating: r.rating || "N/A",
            isExcluded: currentExcludedIndices.has(idx)
        }))
        .filter(r => r.y !== null && !r.isExcluded);

    ratingChartInstance = new Chart(ctx, {
        type: "scatter",
        data: {
            datasets: [{
                label: "Rate vs. Reviews",
                data: scatterData,
                backgroundColor: "rgba(16, 185, 129, 0.7)",
                borderColor: "#10b981",
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.raw.name}: $${ctx.raw.y} | ${ctx.raw.x} reviews (${ctx.raw.rating})`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: "Reviews Count", color: "#6b7280" }, ticks: { color: "#9ca3af" } },
                y: { title: { display: true, text: "Price ($)", color: "#6b7280" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

// 11. Temporal Variation Trend Chart across Sessions
async function loadTemporalTrends() {
    try {
        const res = await fetch("/api/analytics/temporal-trends");
        const data = await res.json();
        const trends = data.trends || [];
        
        const ctx = document.getElementById("temporalTrendsChart").getContext("2d");
        if (temporalChartInstance) temporalChartInstance.destroy();

        if (trends.length === 0) {
            temporalChartInstance = new Chart(ctx, {
                type: "line",
                data: { labels: ["No search history"], datasets: [] },
                options: { responsive: true, maintainAspectRatio: false }
            });
            return;
        }

        const labels = trends.map(t => {
            const d = new Date(t.timestamp);
            return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric" })} - ${t.location.split(',')[0]}`;
        });

        const avgPrices = trends.map(t => t.avg_price);
        const medianPrices = trends.map(t => t.median_price);

        temporalChartInstance = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Average Price ($)",
                        data: avgPrices,
                        borderColor: "#3b82f6",
                        backgroundColor: "rgba(59, 130, 246, 0.15)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 6,
                        pointHoverRadius: 8
                    },
                    {
                        label: "Median Price ($)",
                        data: medianPrices,
                        borderColor: "#10b981",
                        backgroundColor: "transparent",
                        borderDash: [5, 5],
                        tension: 0.3,
                        pointRadius: 5
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: "#fff" } },
                    tooltip: {
                        callbacks: {
                            afterLabel: (ctx) => {
                                const t = trends[ctx.dataIndex];
                                return `Sitters: ${t.total_sitters} | Min: $${t.min_price} | Max: $${t.max_price}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af" } },
                    y: { title: { display: true, text: "Price ($)", color: "#6b7280" }, ticks: { color: "#9ca3af" } }
                }
            }
        });
    } catch (err) {
        console.error("Error loading temporal trends:", err);
    }
}

// 12. Render Sitter Table with Interactive Outlier Exclusion Toggles
function renderTable(records) {
    const tbody = document.getElementById("sittersTableBody");
    tbody.innerHTML = "";

    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding: 2rem;">No sitters found.</td></tr>`;
        return;
    }

    records.forEach((r, idx) => {
        const isExcluded = currentExcludedIndices.has(idx);
        const isAutoOutlier = currentAutoOutliers.includes(idx);

        const tr = document.createElement("tr");
        if (isExcluded) tr.classList.add("sitter-row-excluded");

        const priceBadge = r.raw_price ? `<span class="badge-price">${escapeHtml(r.raw_price)}</span>` : "--";
        const outlierTag = isAutoOutlier ? `<span class="badge-outlier-tag" title="Flagged by 1.5*IQR Rule">Outlier</span>` : "";
        const ratingBadge = r.rating ? `<span class="badge-rating">★ ${escapeHtml(r.rating)}</span>` : `<span style="color:var(--text-muted)">New</span>`;
        const profileLink = r.profile_url ? `<a href="${r.profile_url}" target="_blank" style="color:var(--accent-primary); text-decoration:none;" onclick="event.stopPropagation();">Profile ↗</a>` : "--";
        const coverageArea = r.neighborhood ? `<span style="color:#60a5fa; font-weight:500;">${escapeHtml(r.neighborhood)}</span> (~${r.service_radius_km || 2} km)` : `~${r.service_radius_km || 2} km radius`;

        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" ${!isExcluded ? "checked" : ""} title="Check to include in statistics, uncheck to exclude" onclick="event.stopPropagation();" onchange="toggleSitterExclusion(${idx})">
            </td>
            <td>
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <strong style="color:#fff;">${escapeHtml(r.name || 'Anonymous')}</strong>
                    ${outlierTag}
                </div>
                ${r.headline ? `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">${escapeHtml(r.headline)}</div>` : ''}
            </td>
            <td>${priceBadge}</td>
            <td style="font-size:0.8rem; color:var(--text-secondary);">${coverageArea}</td>
            <td>${ratingBadge}</td>
            <td style="color:var(--text-secondary);">${r.reviews ? escapeHtml(r.reviews) : '0 reviews'}</td>
            <td>${profileLink}</td>
        `;

        tr.addEventListener("mouseenter", () => highlightSitterCoverage(r, idx, true));
        tr.addEventListener("mouseleave", () => clearSitterCoverage(idx));
        tr.addEventListener("click", () => {
            const item = sitterMarkersMap.get(idx);
            if (item && item.marker) {
                item.marker.openPopup();
                mapInstance.panTo([item.lat, item.lng]);
            }
        });

        tbody.appendChild(tr);
    });
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// ========================================
// Data Science Academy — Interactive Demos
// ========================================

let kdeChartInstance = null;

/** Parses a comma-separated string of numbers into a sorted array. */
function parseNumberList(str) {
    return str.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n)).sort((a, b) => a - b);
}

/** Demo 1: IQR Outlier Detection — runs entirely in JS */
function runIQRDemo() {
    const raw = document.getElementById('iqrInput').value;
    const prices = parseNumberList(raw);
    if (prices.length < 4) {
        document.getElementById('iqrResult').textContent = 'Need at least 4 prices.';
        return;
    }

    const n = prices.length;
    const q1 = prices[Math.floor(n * 0.25)];
    const q3 = prices[Math.ceil(n * 0.75) - 1] ?? prices[n - 1];
    const iqr = q3 - q1;
    const lower = +(q1 - 1.5 * iqr).toFixed(2);
    const upper = +(q3 + 1.5 * iqr).toFixed(2);
    const outliers = prices.filter(p => p < lower || p > upper);
    const clean = prices.filter(p => p >= lower && p <= upper);
    const avg = +(clean.reduce((a, b) => a + b, 0) / clean.length).toFixed(2);

    document.getElementById('iqrResult').textContent =
        `Q1 = $${q1}  |  Q3 = $${q3}  |  IQR = $${iqr.toFixed(2)}
` +
        `Safe Bounds: [$${lower} — $${upper}]
` +
        `Outliers detected (${outliers.length}): ${outliers.map(p => '$' + p).join(', ') || 'None'}
` +
        `Clean prices (${clean.length}): ${clean.map(p => '$' + p).join(', ')}
` +
        `Mean after filtering: $${avg}`;
}

/** Demo 2: Expected Value / Revenue Index optimizer */
function runEVIDemo() {
    const mean = parseFloat(document.getElementById('eviMean').value) || 22;
    const std = parseFloat(document.getElementById('eviStd').value) || 7;
    const candidates = Array.from({length: 40}, (_, i) => mean - 2.5 * std + i * (5 * std / 40));
    
    let bestPrice = mean;
    let bestEVI = -1;

    const points = candidates.map(p => {
        const z = (p - mean) / std;
        const prob = 1 / (1 + Math.exp(1.2 * z));
        const evi = p * prob;
        if (evi > bestEVI) { bestEVI = evi; bestPrice = p; }
        return { p: +p.toFixed(1), prob: +(prob * 100).toFixed(1), evi: +evi.toFixed(2) };
    });

    const nearBest = points.filter(pt => Math.abs(pt.p - bestPrice) < 2.5);
    document.getElementById('eviResult').textContent =
        `Optimal Price (Sweet Spot): $${bestPrice.toFixed(1)}
` +
        `Max Revenue Index: ${bestEVI.toFixed(2)} (price × conversion prob.)
` +
        `Recommended range: $${(bestPrice * 0.90).toFixed(1)} — $${(bestPrice * 1.12).toFixed(1)}
` +
        `At that price, booking probability ≈ ${nearBest[0]?.prob ?? '--'}%`;
}

/** Demo 3: Gaussian KDE on active sitter prices */
function runKDEDemo() {
    const h = parseFloat(document.getElementById('kdeBandwidth').value) || 3;

    const prices = currentRecords
        .filter((r, i) => !currentExcludedIndices.has(i) && r.price_numeric !== null)
        .map(r => r.price_numeric);

    if (prices.length < 3) {
        alert('Load a search session first — need at least 3 active sitters.');
        return;
    }

    const minP = Math.min(...prices) - h * 2;
    const maxP = Math.max(...prices) + h * 2;
    const steps = 60;
    const xVals = Array.from({length: steps}, (_, i) => minP + (i / (steps - 1)) * (maxP - minP));

    // Gaussian KDE kernel: K(u) = (1/sqrt(2π)) * exp(-0.5 * u²)
    const kdeVals = xVals.map(x => {
        const density = prices.reduce((sum, xi) => {
            const u = (x - xi) / h;
            return sum + Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI);
        }, 0) / (prices.length * h);
        return +density.toFixed(6);
    });

    const ctx = document.getElementById('kdeChart').getContext('2d');
    if (kdeChartInstance) kdeChartInstance.destroy();

    kdeChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: xVals.map(x => '$' + x.toFixed(0)),
            datasets: [{
                label: 'Price Density (KDE)',
                data: kdeVals,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                fill: true,
                tension: 0.4,
                borderWidth: 2,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: '#9ca3af', maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,0.05)' } },
                y: { ticks: { color: '#9ca3af' }, title: { display: true, text: 'Density', color: '#6b7280' }, grid: { color: 'rgba(255,255,255,0.05)' } }
            }
        }
    });
}

/** Demo 4: 1-D K-Means clustering on sitter prices */
function runKMeansDemo() {
    const K = parseInt(document.getElementById('kmeansK').value) || 3;
    const prices = currentRecords
        .filter((r, i) => !currentExcludedIndices.has(i) && r.price_numeric !== null)
        .map(r => r.price_numeric);

    if (prices.length < K) {
        alert('Not enough sitters loaded. Run a search first.');
        return;
    }

    // Initialize centroids by spreading evenly across price range
    const sorted = [...prices].sort((a, b) => a - b);
    let centroids = Array.from({length: K}, (_, i) => sorted[Math.floor(i * sorted.length / K)]);

    let clusters;
    for (let iter = 0; iter < 50; iter++) {
        // Assign each price to nearest centroid
        clusters = Array.from({length: K}, () => []);
        prices.forEach(p => {
            const nearest = centroids.reduce((best, c, i) =>
                Math.abs(p - c) < Math.abs(p - centroids[best]) ? i : best, 0);
            clusters[nearest].push(p);
        });
        // Update centroids
        const newCentroids = clusters.map(cl =>
            cl.length > 0 ? cl.reduce((a, b) => a + b, 0) / cl.length : 0);
        if (newCentroids.every((c, i) => Math.abs(c - centroids[i]) < 0.01)) break;
        centroids = newCentroids;
    }

    const clusterNames = ['Budget', 'Mid-Tier', 'Premium', 'Ultra-Premium', 'Luxury', 'Elite'];
    const sorted_clusters = clusters
        .map((cl, i) => ({ name: clusterNames[i] || `Cluster ${i + 1}`, prices: cl.sort((a, b) => a - b), centroid: centroids[i] }))
        .sort((a, b) => a.centroid - b.centroid)
        .map((cl, i) => ({ ...cl, name: clusterNames[i] || cl.name }));

    const lines = sorted_clusters.map(cl =>
        `${cl.name.padEnd(14)} → Centroid: $${cl.centroid.toFixed(1)}  |  Range: $${cl.prices[0]?.toFixed(0)} – $${cl.prices[cl.prices.length-1]?.toFixed(0)}  |  n=${cl.prices.length} sitters`);

    document.getElementById('kmeansResult').textContent = lines.join('\n');
}
