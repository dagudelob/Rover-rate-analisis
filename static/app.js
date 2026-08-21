// ==========================================================================
// Central Reactive State Store (Store Pattern)
// ==========================================================================
const AppState = {
    sessionId: null,
    records: [],
    excludedIndices: new Set(),
    autoOutliers: [],
    
    // UI Table & Filter state
    sortKey: "default",
    sortOrder: "asc",
    filterQuery: "",
    statusFilter: "all",
    minRating: "all",
    
    // History selection state
    selectedHistorySessionIds: new Set(),

    resetSession() {
        this.sessionId = null;
        this.records = [];
        this.excludedIndices.clear();
        this.autoOutliers = [];
    },

    resetFilters() {
        this.filterQuery = "";
        this.statusFilter = "all";
        this.minRating = "all";
        this.sortKey = "default";
        this.sortOrder = "asc";
    }
};

// Global references
let currentRecords = [];
let currentExcludedIndices = AppState.excludedIndices;
let currentAutoOutliers = [];
let currentSessionId = null;
let activeEventSource = null;

// Chart runtime instances
let priceChartInstance = null;
let cdfChartInstance = null;
let ratingChartInstance = null;
let serviceComparisonChartInstance = null;
let neighborhoodChartInstance = null;
let temporalChartInstance = null;
let revenueChartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    setupSidebarNavigation();
    setupCollapsibleTable();
    setupCollapsibleHistorySection();
    setupPlatformSelector();
    loadServices("rover");
    loadHistory();
    loadTemporalTrends();
    setupForm();
    setupOutlierToolbar();
    setupSitterTableFilters();

    if (window.renderMathInElement) {
        renderMathInElement(document.body, {
            delimiters: [
                {left: "$$", right: "$$", display: true},
                {left: "$", right: "$", display: false}
            ]
        });
    }
});

// ── Theme Management (Dark / Light Mode) ──────────────────────────────────────
function initTheme() {
    const savedTheme = localStorage.getItem("rover_theme") || "dark";
    applyTheme(savedTheme);

    const btnHeader = document.getElementById("themeToggleHeader");
    const btnSidebar = document.getElementById("themeToggleSidebar");

    if (btnHeader) {
        btnHeader.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
            applyTheme(current === "dark" ? "light" : "dark");
        });
    }

    if (btnSidebar) {
        btnSidebar.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
            applyTheme(current === "dark" ? "light" : "dark");
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("rover_theme", theme);

    const iconHeader = document.getElementById("themeIconHeader");
    const iconSidebar = document.getElementById("themeIconSidebar");
    const textSidebar = document.getElementById("themeTextSidebar");

    if (theme === "light") {
        if (iconHeader) iconHeader.textContent = "☀️";
        if (iconSidebar) iconSidebar.textContent = "☀️";
        if (textSidebar) textSidebar.textContent = "Dark Mode";
    } else {
        if (iconHeader) iconHeader.textContent = "🌙";
        if (iconSidebar) iconSidebar.textContent = "🌙";
        if (textSidebar) textSidebar.textContent = "Light Mode";
    }
}

// ── 1. Collapsible Sidebar Navigation ─────────────────────────────────────────
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

// ── 2. Service Selector ───────────────────────────────────────────────────────
async function loadServices(platform = "rover") {
    try {
        const res = await fetch(`/api/services?platform=${encodeURIComponent(platform)}`);
        const services = await res.json();
        const select = document.getElementById("serviceSelect");
        if (!select) return;
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

function setupPlatformSelector() {
    const platformSelect = document.getElementById("platformSelect");
    if (platformSelect) {
        platformSelect.addEventListener("change", (e) => {
            loadServices(e.target.value);
        });
    }
}

// ── 3. Search History List & Batch Delete ──────────────────────────────────────
let selectedHistorySessionIds = new Set();

async function loadHistory() {
    try {
        const res = await fetch("/api/history");
        const data = await res.json();
        const list = document.getElementById("historyList");
        list.innerHTML = "";

        const badge = document.getElementById("historySessionsBadge");
        if (badge) {
            badge.textContent = `${data.sessions ? data.sessions.length : 0} Sessions`;
        }

        if (!data.sessions || data.sessions.length === 0) {
            list.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding: 1.5rem;">No searches saved yet.</p>`;
            selectedHistorySessionIds.clear();
            updateHistoryDeleteToolbar();
            return;
        }

        const existingIds = new Set(data.sessions.map(s => s.id));
        for (const id of selectedHistorySessionIds) {
            if (!existingIds.has(id)) selectedHistorySessionIds.delete(id);
        }
        updateHistoryDeleteToolbar();

        data.sessions.forEach((s) => {
            const date = new Date(s.timestamp).toLocaleString("en-US", {
                month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
            });
            const item = document.createElement("div");
            item.className = `history-item ${s.id === currentSessionId ? "active" : ""}`;
            item.style.display = "flex";
            item.style.alignItems = "center";
            item.style.gap = "0.75rem";
            
            const isChecked = selectedHistorySessionIds.has(s.id);
            const avgDisplay = s.avg_price ? `$${s.avg_price.toFixed(1)}` : "--";

            item.innerHTML = `
                <div style="display: flex; align-items: center;" onclick="event.stopPropagation()">
                    <input type="checkbox" class="history-checkbox" data-session-id="${s.id}" ${isChecked ? 'checked' : ''} style="cursor: pointer; width: 16px; height: 16px;">
                </div>
                <div class="history-info" style="flex-grow: 1; cursor: pointer;">
                    <h4>${escapeHtml(s.location)} (${s.total_sitters} sitters)</h4>
                    <p>${escapeHtml(s.service_type)} • ${date} ${s.radius_km ? `• ${s.radius_km}km radius` : ''}</p>
                </div>
                <div class="history-stat" style="cursor: pointer; text-align: right;">
                    <div class="avg">${avgDisplay}</div>
                    <p style="font-size:0.7rem; color:var(--text-muted);">Session #${s.id}</p>
                </div>
                <button class="btn-delete-single" data-session-id="${s.id}" title="Delete this session from database" style="background: transparent; border: none; color: #ef4444; cursor: pointer; padding: 0.35rem 0.5rem; font-size: 1.1rem;">
                    🗑️
                </button>
            `;

            item.querySelector(".history-info").addEventListener("click", () => selectSession(s.id));
            item.querySelector(".history-stat").addEventListener("click", () => selectSession(s.id));

            const chk = item.querySelector(".history-checkbox");
            chk.addEventListener("change", (e) => {
                const sid = parseInt(e.target.dataset.sessionId);
                if (e.target.checked) selectedHistorySessionIds.add(sid);
                else selectedHistorySessionIds.delete(sid);
                updateHistoryDeleteToolbar();
            });

            const delBtn = item.querySelector(".btn-delete-single");
            delBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                deleteSingleSession(s.id);
            });

            list.appendChild(item);
        });

        setupHistoryBulkToolbar(data.sessions);
    } catch (err) {
        console.error("Error loading history:", err);
    }
}

function updateHistoryDeleteToolbar() {
    const btn = document.getElementById("btnBatchDeleteHistory");
    const countSpan = document.getElementById("historySelectedCount");
    const selectAllChk = document.getElementById("historySelectAllCheckbox");

    if (countSpan) countSpan.textContent = selectedHistorySessionIds.size;
    if (btn) {
        btn.style.display = selectedHistorySessionIds.size > 0 ? "inline-flex" : "none";
    }
    if (selectAllChk) {
        const allCheckboxes = document.querySelectorAll(".history-checkbox");
        if (allCheckboxes.length > 0 && selectedHistorySessionIds.size === allCheckboxes.length) {
            selectAllChk.checked = true;
            selectAllChk.indeterminate = false;
        } else if (selectedHistorySessionIds.size > 0) {
            selectAllChk.checked = false;
            selectAllChk.indeterminate = true;
        } else {
            selectAllChk.checked = false;
            selectAllChk.indeterminate = false;
        }
    }
}

function setupHistoryBulkToolbar(sessions) {
    const selectAllChk = document.getElementById("historySelectAllCheckbox");
    const batchDeleteBtn = document.getElementById("btnBatchDeleteHistory");

    if (selectAllChk) {
        selectAllChk.onchange = (e) => {
            const checked = e.target.checked;
            selectedHistorySessionIds.clear();
            if (checked && sessions) {
                sessions.forEach(s => selectedHistorySessionIds.add(s.id));
            }
            document.querySelectorAll(".history-checkbox").forEach(cb => cb.checked = checked);
            updateHistoryDeleteToolbar();
        };
    }

    if (batchDeleteBtn) {
        batchDeleteBtn.onclick = async () => {
            const count = selectedHistorySessionIds.size;
            if (count === 0) return;
            if (!confirm(`Are you sure you want to permanently delete ${count} selected search session(s)?`)) return;

            try {
                const res = await fetch("/api/history/delete-batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_ids: Array.from(selectedHistorySessionIds) })
                });
                const result = await res.json();
                selectedHistorySessionIds.clear();
                loadHistory();
                loadTemporalTrends();
                logToTerminal(`[✓] Deleted ${result.deleted_count || count} sessions from database.`, "success");
            } catch (err) {
                console.error("Error deleting sessions:", err);
                alert("Failed to delete selected sessions.");
            }
        };
    }
}

async function deleteSingleSession(sessionId) {
    if (!confirm(`Delete Search Session #${sessionId}?`)) return;
    try {
        await fetch(`/api/history/${sessionId}`, { method: "DELETE" });
        selectedHistorySessionIds.delete(sessionId);
        loadHistory();
        loadTemporalTrends();
        logToTerminal(`[✓] Session #${sessionId} deleted.`, "success");
    } catch (err) {
        console.error("Error deleting session:", err);
    }
}

async function selectSession(sessionId) {
    try {
        const res = await fetch(`/api/history/${sessionId}`);
        const session = await res.json();
        
        currentSessionId = session.id;
        currentRecords = session.sitters || [];
        currentExcludedIndices.clear();
        currentAutoOutliers = [];

        // Identify initial outliers
        try {
            const recRes = await fetch("/api/analytics/recalculate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: currentSessionId, records: currentRecords, excluded_indices: [] })
            });
            const recData = await recRes.json();
            currentAutoOutliers = recData.auto_outliers || [];
            renderResults(recData.stats, currentRecords, session.location, session.service_type, session.id);
        } catch {
            renderResults(session, currentRecords, session.location, session.service_type, session.id);
        }

        loadHistory();
    } catch (err) {
        console.error("Error loading session details:", err);
    }
}

// ── 4. Form Submission & Real Multi-Service Extraction ─────────────────────────
function setupForm() {
    const form = document.getElementById("scraperForm");
    form.addEventListener("submit", (e) => {
        e.preventDefault();
        startScraping();
    });
}

function startScraping() {
    const platform = document.getElementById("platformSelect").value;
    const location = document.getElementById("locationInput").value.trim();
    const serviceType = document.getElementById("serviceSelect").value;
    const radius = document.getElementById("radiusInput").value;
    const maxPages = document.getElementById("maxPagesInput").value || 5;
    const maxResults = document.getElementById("maxResultsInput").value || 100;
    const proxyUrl = document.getElementById("proxyInput").value.trim();

    if (!location) {
        alert("Please enter a valid location (city, neighborhood, or postal code).");
        return;
    }

    const btn = document.getElementById("startBtn");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Extracting Real Market Data...`;

    const terminal = document.getElementById("terminal");
    terminal.innerHTML = "";
    logToTerminal(`Connecting to scraper streaming pipeline for '${location}'...`, "info");

    const progressBar = document.getElementById("progressBar");
    progressBar.style.width = "5%";

    let url = `/api/scrape/stream?location=${encodeURIComponent(location)}&service_type=${encodeURIComponent(serviceType)}&platform=${encodeURIComponent(platform)}&max_pages=${maxPages}&max_results=${maxResults}`;
    if (radius) url += `&radius_km=${radius}`;
    if (proxyUrl) url += `&proxy_url=${encodeURIComponent(proxyUrl)}`;

    if (activeEventSource) {
        activeEventSource.close();
    }

    const eventSource = new EventSource(url);
    activeEventSource = eventSource;

    eventSource.addEventListener("log", (e) => {
        const data = JSON.parse(e.data);
        logToTerminal(data.message, "info");
    });

    eventSource.addEventListener("page_start", (e) => {
        const data = JSON.parse(e.data);
        const progressPct = Math.min(95, Math.round((data.page / data.max_pages) * 85));
        progressBar.style.width = `${progressPct}%`;
        logToTerminal(`-> [${data.service_name || data.service || 'Rover'}] Scraping Page ${data.page}/${data.max_pages}...`, "info");
    });

    eventSource.addEventListener("page_done", (e) => {
        const data = JSON.parse(e.data);
        logToTerminal(`[✓] Page ${data.page} completed (+${data.records_found} sitters, total unique: ${data.total_unique_sitters || data.total_records_so_far})`, "success");
    });

    eventSource.addEventListener("complete", (e) => {
        const data = JSON.parse(e.data);
        progressBar.style.width = "100%";
        logToTerminal(`[✓] Scraping finished successfully! Total: ${data.records.length} unique sitters. Saved with Session ID #${data.session_id}`, "success");
        
        currentSessionId = data.session_id;
        currentRecords = data.records || [];
        currentExcludedIndices.clear();
        currentAutoOutliers = data.auto_outliers || [];

        renderResults(data.stats, currentRecords, data.location, data.service_type, data.session_id);
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
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Real Market Extraction`;
    });

    eventSource.onerror = () => {
        eventSource.close();
        btn.disabled = false;
        btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Start Real Market Extraction`;
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

// ── 5. Render All Dashboard Results & Charts ───────────────────────────────────
function renderResults(stats, records, location, service, sessionId) {
    document.getElementById("resultsContainer").style.display = "block";
    
    // KPI Overview Cards
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

    // Optimal Pricing Card & Revenue Curve
    const opt = stats.pricing_optimizer || {};
    if (opt.sweet_spot_price) {
        document.getElementById("optimizerSweetSpot").textContent = `$${opt.sweet_spot_price.toFixed(0)}`;
        document.getElementById("optimizerRange").textContent = `$${opt.recommended_range.min.toFixed(0)} - $${opt.recommended_range.max.toFixed(0)}`;
        renderRevenueOptimizationChart(opt.curve || [], opt.sweet_spot_price);
    }

    // Advanced Stats Matrix
    document.getElementById("statP10").textContent = stats.p10_price ? `$${stats.p10_price}` : "--";
    document.getElementById("statP25").textContent = stats.p25_price ? `$${stats.p25_price}` : "--";
    document.getElementById("statP75").textContent = stats.p75_price ? `$${stats.p75_price}` : "--";
    document.getElementById("statP90").textContent = stats.p90_price ? `$${stats.p90_price}` : "--";
    document.getElementById("statStdDevBox").textContent = stats.std_dev ? `±$${stats.std_dev}` : "--";
    document.getElementById("statTrimmedBox").textContent = stats.trimmed_mean_10 ? `$${stats.trimmed_mean_10}` : "--";

    // Outlier Toolbar Info
    document.getElementById("iqrOutlierCountBadge").textContent = currentAutoOutliers.length;
    if (stats.outlier_bounds && stats.outlier_bounds.lower !== null) {
        document.getElementById("iqrBoundsLabel").textContent = `$${stats.outlier_bounds.lower} to $${stats.outlier_bounds.upper}`;
    }

    // Export Link & Sitter Count
    const csvBtn = document.getElementById("exportCsvBtn");
    if (csvBtn && sessionId) {
        csvBtn.href = `/api/export/csv/${sessionId}`;
        csvBtn.style.display = "inline-flex";
    }
    const countBadge = document.getElementById("sittersCountBadge");
    if (countBadge) {
        countBadge.textContent = `${records ? records.length : 0} Sitters`;
    }

    updateServiceRateBenchmarks(stats);

    // Render 5 Statistical Charts
    renderPriceHistogram(stats.price_distribution || []);
    renderCDFChart(stats.cdf_curve || []);
    renderRatingScatter(records || []);
    renderServiceComparisonChart(stats.service_comparisons || {});
    renderNeighborhoodChart(stats.neighborhood_breakdown || []);
    renderTable(records || []);
}

function updateServiceRateBenchmarks(stats) {
    const baseRate = stats.median_price || stats.avg_price || 25.0;
    
    const elDogWalking = document.getElementById("serviceRateDogWalking");
    const elDropIns = document.getElementById("serviceRateDropIns");
    const elBoarding = document.getElementById("serviceRateBoarding");
    const elHouseSitting = document.getElementById("serviceRateHouseSitting");
    const elDayCare = document.getElementById("serviceRateDayCare");

    if (elDogWalking) elDogWalking.textContent = `$${Math.round(baseRate * 0.9)} - $${Math.round(baseRate * 1.15)}`;
    if (elDropIns) elDropIns.textContent = `$${Math.round(baseRate * 0.88)} - $${Math.round(baseRate * 1.05)}`;
    if (elBoarding) elBoarding.textContent = `$${Math.round(baseRate * 1.85)} - $${Math.round(baseRate * 2.45)}`;
    if (elHouseSitting) elHouseSitting.textContent = `$${Math.round(baseRate * 2.25)} - $${Math.round(baseRate * 3.20)}`;
    if (elDayCare) elDayCare.textContent = `$${Math.round(baseRate * 1.40)} - $${Math.round(baseRate * 1.85)}`;
}

// ── 6. Statistical Charts ─────────────────────────────────────────────────────

// Chart 1: Rate Histogram
function renderPriceHistogram(distribution) {
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
                backgroundColor: "rgba(59, 130, 246, 0.7)",
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

// Chart 2: Empirical CDF (Cumulative Distribution Function)
function renderCDFChart(cdfData) {
    const ctx = document.getElementById("cdfChart").getContext("2d");
    if (cdfChartInstance) cdfChartInstance.destroy();

    if (!cdfData || cdfData.length === 0) return;

    const labels = cdfData.map(c => `$${c.price}`);
    const values = cdfData.map(c => c.percentile);

    cdfChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Cumulative Percentile (%)",
                data: values,
                borderColor: "#a855f7",
                backgroundColor: "rgba(168, 85, 247, 0.15)",
                fill: true,
                tension: 0.3,
                borderWidth: 2.5,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.raw}% of sitters charge ≤ ${labels[ctx.dataIndex]}`
                    }
                }
            },
            scales: {
                x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af" } },
                y: { min: 0, max: 100, grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#c084fc", callback: (v) => `${v}%` } }
            }
        }
    });
}

// Chart 3: Price vs Review Count Scatter
function renderRatingScatter(records) {
    const ctx = document.getElementById("ratingScatterChart").getContext("2d");
    if (ratingChartInstance) ratingChartInstance.destroy();

    const scatterData = records
        .map((r, idx) => ({
            x: r.reviews_count || 0,
            y: r.price_numeric,
            name: r.name,
            rating: r.rating || "5.0",
            isExcluded: currentExcludedIndices.has(idx)
        }))
        .filter(r => r.y !== null && !r.isExcluded);

    ratingChartInstance = new Chart(ctx, {
        type: "scatter",
        data: {
            datasets: [{
                label: "Rate vs. Reviews",
                data: scatterData,
                backgroundColor: "rgba(16, 185, 129, 0.75)",
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
                        label: (ctx) => `${ctx.raw.name}: $${ctx.raw.y} | ${ctx.raw.x} reviews (${ctx.raw.rating}★)`
                    }
                }
            },
            scales: {
                x: { title: { display: true, text: "Reviews Count", color: "#9ca3af" }, ticks: { color: "#9ca3af" } },
                y: { title: { display: true, text: "Price ($)", color: "#9ca3af" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

// Chart 4: Cross-Service Comparison Bar Chart
function renderServiceComparisonChart(serviceComps) {
    const ctx = document.getElementById("serviceComparisonChart").getContext("2d");
    if (serviceComparisonChartInstance) serviceComparisonChartInstance.destroy();

    const serviceLabelsMap = {
        "dog-walking": "Dog Walking",
        "drop-in-visits": "Drop-in Visits",
        "overnight-boarding": "Overnight Boarding",
        "house-sitting": "House Sitting",
        "day-care": "Day Care",
    };

    const keys = Object.keys(serviceComps);
    if (keys.length === 0) {
        // Default visual placeholder
        serviceComparisonChartInstance = new Chart(ctx, {
            type: "bar",
            data: { labels: ["Run All-Services to Compare"], datasets: [] },
            options: { responsive: true, maintainAspectRatio: false }
        });
        return;
    }

    const labels = keys.map(k => serviceLabelsMap[k] || k);
    const avgPrices = keys.map(k => serviceComps[k].avg);
    const medianPrices = keys.map(k => serviceComps[k].median);

    serviceComparisonChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Average Rate ($)",
                    data: avgPrices,
                    backgroundColor: "rgba(56, 189, 248, 0.75)",
                    borderColor: "#38bdf8",
                    borderWidth: 1.5,
                    borderRadius: 6
                },
                {
                    label: "Median Rate ($)",
                    data: medianPrices,
                    backgroundColor: "rgba(245, 158, 11, 0.75)",
                    borderColor: "#fbbf24",
                    borderWidth: 1.5,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#cbd5e1" } }
            },
            scales: {
                x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af" } },
                y: { title: { display: true, text: "Price ($)", color: "#9ca3af" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

// Chart 5: Neighborhood / Area Comparison
function renderNeighborhoodChart(hoodData) {
    const ctx = document.getElementById("neighborhoodChart").getContext("2d");
    if (neighborhoodChartInstance) neighborhoodChartInstance.destroy();

    if (!hoodData || hoodData.length === 0) return;

    const labels = hoodData.map(h => `${h.neighborhood} (${h.sitters_count} sitters)`);
    const avgData = hoodData.map(h => h.avg_price);
    const medianData = hoodData.map(h => h.median_price);

    neighborhoodChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Average Rate ($)",
                    data: avgData,
                    backgroundColor: "rgba(59, 130, 246, 0.7)",
                    borderColor: "#3b82f6",
                    borderWidth: 1.5,
                    borderRadius: 6
                },
                {
                    label: "Median Rate ($)",
                    data: medianData,
                    backgroundColor: "rgba(16, 185, 129, 0.7)",
                    borderColor: "#10b981",
                    borderWidth: 1.5,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#cbd5e1" } }
            },
            scales: {
                x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af" } },
                y: { title: { display: true, text: "Price ($)", color: "#9ca3af" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

// Revenue Optimization Curve
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
                    label: "Expected Revenue Index",
                    data: revenueData,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.18)",
                    fill: true,
                    yAxisID: "yRevenue",
                    tension: 0.35,
                    borderWidth: 2.5,
                    pointRadius: 4
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
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: "#cbd5e1", font: { size: 11 } } }
            },
            scales: {
                x: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#9ca3af", font: { size: 10 } } },
                yRevenue: {
                    type: 'linear',
                    position: 'left',
                    title: { display: true, text: 'Expected Revenue', color: '#10b981' },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#10b981" }
                },
                yProb: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: 'Probability (%)', color: '#60a5fa' },
                    grid: { drawOnChartArea: false },
                    ticks: { color: "#60a5fa" }
                }
            }
        }
    });
}

// ── 7. Outlier Control & Recalculation ──────────────────────────────────────────
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
                session_id: currentSessionId,
                records: currentRecords,
                excluded_indices: Array.from(currentExcludedIndices)
            })
        });

        const data = await res.json();
        currentAutoOutliers = data.auto_outliers || [];
        renderResults(data.stats, currentRecords, "", "", currentSessionId);
    } catch (err) {
        console.error("Error recalculating stats:", err);
    }
}

// ── 8. Sitter Table Filtering & Sorting ─────────────────────────────────────────
let currentSortKey = "default";
let currentSortOrder = "asc";
let currentFilterQuery = "";
let currentStatusFilter = "all";
let currentMinRating = "all";

function setupSitterTableFilters() {
    const searchInput = document.getElementById("sitterSearchInput");
    const statusFilter = document.getElementById("sitterStatusFilter");
    const ratingFilter = document.getElementById("sitterRatingFilter");
    const sortSelect = document.getElementById("sitterSortSelect");
    const clearBtn = document.getElementById("btnClearSitterFilters");

    let searchDebounceTimer = null;
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                currentFilterQuery = e.target.value.trim().toLowerCase();
                renderTable(currentRecords);
            }, 120);
        });
    }

    if (statusFilter) {
        statusFilter.addEventListener("change", (e) => {
            currentStatusFilter = e.target.value;
            renderTable(currentRecords);
        });
    }

    if (ratingFilter) {
        ratingFilter.addEventListener("change", (e) => {
            currentMinRating = e.target.value;
            renderTable(currentRecords);
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", (e) => {
            const val = e.target.value;
            if (val === "default") {
                currentSortKey = "default";
                currentSortOrder = "asc";
            } else {
                const parts = val.split("_");
                const order = parts.pop();
                const key = parts.join("_");
                currentSortKey = key;
                currentSortOrder = order;
            }
            updateSortHeaderIcons();
            renderTable(currentRecords);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener("click", () => {
            currentFilterQuery = "";
            currentStatusFilter = "all";
            currentMinRating = "all";
            currentSortKey = "default";
            currentSortOrder = "asc";

            if (searchInput) searchInput.value = "";
            if (statusFilter) statusFilter.value = "all";
            if (ratingFilter) ratingFilter.value = "all";
            if (sortSelect) sortSelect.value = "default";

            updateSortHeaderIcons();
            renderTable(currentRecords);
        });
    }

    const sortableHeaders = document.querySelectorAll(".sortable-th");
    sortableHeaders.forEach(th => {
        th.addEventListener("click", () => {
            const key = th.getAttribute("data-sort-key");
            if (currentSortKey === key) {
                currentSortOrder = currentSortOrder === "asc" ? "desc" : "asc";
            } else {
                currentSortKey = key;
                currentSortOrder = (key.startsWith("price") || key === "rating" || key === "reviews") ? "desc" : "asc";
            }
            updateSortHeaderIcons();
            renderTable(currentRecords);
        });
    });
}

function updateSortHeaderIcons() {
    const sortableHeaders = document.querySelectorAll(".sortable-th");
    sortableHeaders.forEach(th => {
        const key = th.getAttribute("data-sort-key");
        const icon = document.getElementById(`sortIcon_${key}`);
        if (currentSortKey === key) {
            th.classList.add("sort-active");
            if (icon) icon.textContent = currentSortOrder === "asc" ? "▲" : "▼";
        } else {
            th.classList.remove("sort-active");
            if (icon) icon.textContent = "↕";
        }
    });
}

// ── 9. Render Sitter Table with Real Neighborhoods & 5 Services ───────────────
function renderTable(records) {
    const tbody = document.getElementById("sittersTableBody");
    const countBadge = document.getElementById("sittersCountBadge");
    const filteredCountBadge = document.getElementById("sitterFilteredCount");

    tbody.innerHTML = "";

    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:var(--text-muted); padding: 2.5rem;">No sitters found for this session.</td></tr>`;
        if (countBadge) countBadge.textContent = "0 Sitters";
        if (filteredCountBadge) filteredCountBadge.style.display = "none";
        return;
    }

    if (countBadge) countBadge.textContent = `${records.length} Sitters`;

    let indexedRecords = records.map((r, originalIdx) => ({
        data: r,
        originalIdx: originalIdx,
        isExcluded: currentExcludedIndices.has(originalIdx),
        isAutoOutlier: currentAutoOutliers.includes(originalIdx)
    }));

    let filtered = indexedRecords.filter(item => {
        const r = item.data;

        if (currentFilterQuery) {
            const nameMatch = (r.name || "").toLowerCase().includes(currentFilterQuery);
            const headlineMatch = (r.headline || "").toLowerCase().includes(currentFilterQuery);
            const hoodMatch = (r.neighborhood || "").toLowerCase().includes(currentFilterQuery);
            if (!nameMatch && !headlineMatch && !hoodMatch) return false;
        }

        if (currentStatusFilter === "active" && item.isExcluded) return false;
        if (currentStatusFilter === "excluded" && !item.isExcluded) return false;
        if (currentStatusFilter === "outliers" && !item.isAutoOutlier) return false;

        if (currentMinRating !== "all") {
            const minR = parseFloat(currentMinRating);
            const sitterR = r.rating_numeric || (r.rating ? parseFloat(r.rating) : 0);
            if (sitterR < minR) return false;
        }

        return true;
    });

    if (filteredCountBadge) {
        if (filtered.length !== records.length) {
            filteredCountBadge.style.display = "inline-block";
            filteredCountBadge.textContent = `(Showing ${filtered.length} of ${records.length})`;
        } else {
            filteredCountBadge.style.display = "none";
        }
    }

    if (currentSortKey !== "default") {
        filtered.sort((a, b) => {
            let valA, valB;
            const ra = a.data;
            const rb = b.data;

            const getP = (record, srvKey) => {
                if (record.services && record.services.length > 0) {
                    const found = record.services.find(s => s.service_type === srvKey);
                    if (found && found.price_numeric) return found.price_numeric;
                }
                if (record.service_type === srvKey && record.price_numeric) return record.price_numeric;
                return null;
            };

            switch (currentSortKey) {
                case "name":
                    valA = (ra.name || "").toLowerCase();
                    valB = (rb.name || "").toLowerCase();
                    return currentSortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);

                case "neighborhood":
                    valA = (ra.neighborhood || "").toLowerCase();
                    valB = (rb.neighborhood || "").toLowerCase();
                    return currentSortOrder === "asc" ? valA.localeCompare(valB) : valB.localeCompare(valA);

                case "price_walk":
                    valA = getP(ra, "dog-walking") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    valB = getP(rb, "dog-walking") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "price_boarding":
                    valA = getP(ra, "overnight-boarding") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    valB = getP(rb, "overnight-boarding") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "price_sitting":
                    valA = getP(ra, "house-sitting") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    valB = getP(rb, "house-sitting") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "price_dropin":
                    valA = getP(ra, "drop-in-visits") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    valB = getP(rb, "drop-in-visits") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "price_daycare":
                    valA = getP(ra, "day-care") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    valB = getP(rb, "day-care") ?? (currentSortOrder === "asc" ? 999999 : -1);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "rating":
                    valA = ra.rating_numeric || (ra.rating ? parseFloat(ra.rating) : 0);
                    valB = rb.rating_numeric || (rb.rating ? parseFloat(rb.rating) : 0);
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                case "reviews":
                    valA = ra.reviews_count || 0;
                    valB = rb.reviews_count || 0;
                    return currentSortOrder === "asc" ? valA - valB : valB - valA;

                default:
                    return 0;
            }
        });
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:var(--text-muted); padding: 2rem;">No sitters match the selected filter criteria. <button onclick="document.getElementById('btnClearSitterFilters').click();" class="btn-secondary" style="font-size:0.75rem; margin-left:0.5rem;">Reset Filters</button></td></tr>`;
        return;
    }

    const getServicePriceCell = (record, targetServiceType) => {
        let price = null;
        if (record.services && record.services.length > 0) {
            const found = record.services.find(s => s.service_type === targetServiceType);
            if (found && found.price_numeric) price = found.price_numeric;
        }
        if (price === null && record.service_type === targetServiceType && record.price_numeric) {
            price = record.price_numeric;
        }

        if (price !== null) {
            return `<td style="text-align: center;"><span class="badge-price" style="font-weight: 700;">$${Math.round(price)}</span></td>`;
        } else {
            return `<td style="text-align: center;"><span style="color: var(--text-muted); font-size: 0.78rem; opacity: 0.55;">N/A</span></td>`;
        }
    };

    filtered.forEach(item => {
        const r = item.data;
        const origIdx = item.originalIdx;
        const isExcluded = item.isExcluded;
        const isAutoOutlier = item.isAutoOutlier;

        const tr = document.createElement("tr");
        if (isExcluded) tr.classList.add("sitter-row-excluded");

        const outlierTag = isAutoOutlier ? `<span class="badge-outlier-tag" title="Flagged by 1.5*IQR Rule">Outlier</span>` : "";
        const ratingBadge = r.rating ? `<span class="badge-rating">★ ${escapeHtml(r.rating)}</span>` : `<span style="color:var(--text-muted); font-size:0.8rem;">New</span>`;
        const profileLink = r.profile_url ? `<a href="${r.profile_url}" target="_blank" style="color:var(--accent-primary); text-decoration:none; font-weight:500;" onclick="event.stopPropagation();">Profile ↗</a>` : "--";
        const hoodBadge = `<span style="background: rgba(59, 130, 246, 0.12); color: #93c5fd; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.78rem; font-weight: 500;">${escapeHtml(r.neighborhood || 'Local Area')}</span>`;

        const cellWalk = getServicePriceCell(r, "dog-walking");
        const cellBoarding = getServicePriceCell(r, "overnight-boarding");
        const cellSitting = getServicePriceCell(r, "house-sitting");
        const cellDropin = getServicePriceCell(r, "drop-in-visits");
        const cellDaycare = getServicePriceCell(r, "day-care");

        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" ${!isExcluded ? "checked" : ""} title="Check to include in statistics, uncheck to exclude" onclick="event.stopPropagation();" onchange="toggleSitterExclusion(${origIdx})">
            </td>
            <td>
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <strong style="color:var(--text-heading);">${escapeHtml(r.name || 'Anonymous')}</strong>
                    ${outlierTag}
                </div>
                ${r.headline ? `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:2px;">${escapeHtml(r.headline)}</div>` : ''}
            </td>
            <td style="text-align: center;">${hoodBadge}</td>
            ${cellWalk}
            ${cellBoarding}
            ${cellSitting}
            ${cellDropin}
            ${cellDaycare}
            <td style="text-align: center;">${ratingBadge}</td>
            <td style="text-align: center; color:var(--text-secondary); font-size:0.85rem;">${r.reviews ? escapeHtml(r.reviews) : '0 reviews'}</td>
            <td style="text-align: center;">${profileLink}</td>
        `;

        tbody.appendChild(tr);
    });
}

// ── 10. Temporal Trends Chart ──────────────────────────────────────────────────
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
                        pointRadius: 6
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
                    legend: { labels: { color: "#fff" } }
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

// ── Helpers ───────────────────────────────────────────────────────────────────
function setupCollapsibleTable() {
    const toggleBtn = document.getElementById("btnToggleSittersTable");
    const wrapper = document.getElementById("sittersCollapsibleWrapper");
    const toggleText = document.getElementById("sittersToggleText");
    const toggleIcon = document.getElementById("sittersToggleIcon");

    if (!toggleBtn || !wrapper) return;

    toggleBtn.addEventListener("click", () => {
        const isCollapsed = wrapper.classList.toggle("collapsed");
        if (isCollapsed) {
            toggleText.textContent = "Expand Table";
            toggleIcon.style.transform = "rotate(180deg)";
        } else {
            toggleText.textContent = "Collapse Table";
            toggleIcon.style.transform = "rotate(0deg)";
        }
    });
}

function setupCollapsibleHistorySection() {
    const toggleBtn = document.getElementById("btnToggleHistorySection");
    const wrapper = document.getElementById("historyCollapsibleWrapper");
    const toggleText = document.getElementById("historyToggleText");
    const toggleIcon = document.getElementById("historyToggleIcon");

    if (!toggleBtn || !wrapper) return;

    toggleBtn.addEventListener("click", () => {
        const isCollapsed = wrapper.classList.toggle("collapsed");
        if (isCollapsed) {
            toggleText.textContent = "Expand Section";
            toggleIcon.style.transform = "rotate(180deg)";
        } else {
            toggleText.textContent = "Collapse Section";
            toggleIcon.style.transform = "rotate(0deg)";
        }
    });
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
