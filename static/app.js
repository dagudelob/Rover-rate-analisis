// ==========================================================================
// Central Reactive State Store (Store Pattern)
// ==========================================================================
const AppState = {
    sessionId: null,
    records: [],
    stats: {},
    perServiceAnalytics: {},
    activeServiceTab: "all", // "all", "dog-walking", "overnight-boarding", "house-sitting", "drop-in-visits", "day-care"
    excludedIndices: new Set(),
    autoOutliers: [],
    centerLat: 43.6532,
    centerLng: -79.3832,
    
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
        this.stats = {};
        this.perServiceAnalytics = {};
        this.activeServiceTab = "all";
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
let currentStatsPayload = null;

// Chart & Map runtime instances
let priceChartInstance = null;
let cdfChartInstance = null;
let ratingChartInstance = null;
let serviceComparisonChartInstance = null;
let neighborhoodChartInstance = null;
let temporalChartInstance = null;
let revenueChartInstance = null;
let mapInstance = null;
let heatLayerInstance = null;
let markersLayerGroup = null;

const SERVICE_TITLES = {
    "all": "Master Summary",
    "dog-walking": "Dog Walking",
    "overnight-boarding": "Overnight Boarding",
    "house-sitting": "House Sitting",
    "drop-in-visits": "Drop-in Visits",
    "day-care": "Day Care",
};

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    setupSidebarNavigation();
    setupCollapsibleTable();
    setupCollapsibleHistorySection();
    setupPlatformSelector();
    setupServiceTabs();
    loadServices("rover");
    loadHistory();
    loadTemporalTrends();
    setupForm();
    setupOutlierToolbar();
    setupSitterTableFilters();
    setupProfitSimulator();

    if (window.renderMathInElement) {
        renderMathInElement(document.body, {
            delimiters: [
                {left: "$$", right: "$$", display: true},
                {left: "$", right: "$", display: false}
            ]
        });
    }
});

// ── Theme Management ──────────────────────────────────────────────────────────
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

// ── 2. Service Tabs Switcher ──────────────────────────────────────────────────
function setupServiceTabs() {
    const tabBtns = document.querySelectorAll(".service-tab-btn");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            
            const targetService = btn.getAttribute("data-service-tab");
            AppState.activeServiceTab = targetService;
            
            const activeBadge = document.getElementById("activeServiceBadge");
            if (activeBadge) {
                activeBadge.textContent = `Viewing: ${SERVICE_TITLES[targetService] || targetService}`;
            }

            // Re-render dashboard for active service tab
            switchActiveServiceView(targetService);
        });
    });
}

function switchActiveServiceView(serviceTab) {
    if (!currentStatsPayload) return;

    let displayStats = currentStatsPayload;
    if (serviceTab !== "all" && currentStatsPayload.per_service_analytics && currentStatsPayload.per_service_analytics[serviceTab]) {
        displayStats = currentStatsPayload.per_service_analytics[serviceTab];
    }

    const titleText = SERVICE_TITLES[serviceTab] || serviceTab;
    const optNameEl = document.getElementById("optimizerServiceName");
    const chartsNameEl = document.getElementById("chartsServiceName");
    if (optNameEl) optNameEl.textContent = titleText;
    if (chartsNameEl) chartsNameEl.textContent = titleText;

    // Update KPIs
    document.getElementById("statTotal").textContent = displayStats.total_sitters || displayStats.active_sitters || 0;
    document.getElementById("statAvg").textContent = displayStats.avg_price ? `$${displayStats.avg_price}` : "--";
    document.getElementById("statTrimmed").textContent = displayStats.trimmed_mean_10 ? `$${displayStats.trimmed_mean_10}` : "--";
    document.getElementById("statMedian").textContent = displayStats.median_price ? `$${displayStats.median_price}` : "--";
    document.getElementById("statMin").textContent = displayStats.min_price ? `$${displayStats.min_price}` : "--";
    document.getElementById("statMax").textContent = displayStats.max_price ? `$${displayStats.max_price}` : "--";
    document.getElementById("statIQR").textContent = (displayStats.p25_price && displayStats.p75_price) ? `$${displayStats.p25_price} - $${displayStats.p75_price}` : "--";
    document.getElementById("statStdDev").textContent = displayStats.std_dev ? `±$${displayStats.std_dev}` : "--";
    document.getElementById("statVariance").textContent = displayStats.variance ? `${displayStats.variance}` : "--";

    // Update Advanced Stats Matrix
    document.getElementById("statP10").textContent = displayStats.p10_price ? `$${displayStats.p10_price}` : "--";
    document.getElementById("statP25").textContent = displayStats.p25_price ? `$${displayStats.p25_price}` : "--";
    document.getElementById("statP75").textContent = displayStats.p75_price ? `$${displayStats.p75_price}` : "--";
    document.getElementById("statP90").textContent = displayStats.p90_price ? `$${displayStats.p90_price}` : "--";
    document.getElementById("statStdDevBox").textContent = displayStats.std_dev ? `±$${displayStats.std_dev}` : "--";
    document.getElementById("statTrimmedBox").textContent = displayStats.trimmed_mean_10 ? `$${displayStats.trimmed_mean_10}` : "--";

    // Update Outlier Bounds Label & Badge for the active service
    const activeOutliers = (serviceTab !== "all" && displayStats.outlier_indices) ? displayStats.outlier_indices : currentAutoOutliers;
    const outlierBadge = document.getElementById("iqrOutlierCountBadge");
    if (outlierBadge) outlierBadge.textContent = activeOutliers ? activeOutliers.length : 0;

    if (displayStats.outlier_bounds && displayStats.outlier_bounds.lower !== null) {
        document.getElementById("iqrBoundsLabel").textContent = `$${displayStats.outlier_bounds.lower} to $${displayStats.outlier_bounds.upper}`;
    } else {
        document.getElementById("iqrBoundsLabel").textContent = "--";
    }

    // Update Optimal Pricing Card & Revenue Curve for this specific service
    const opt = displayStats.pricing_optimizer || {};
    if (opt.sweet_spot_price) {
        document.getElementById("optimizerSweetSpot").textContent = `$${opt.sweet_spot_price.toFixed(0)}`;
        document.getElementById("optimizerRange").textContent = `$${opt.recommended_range.min.toFixed(0)} - $${opt.recommended_range.max.toFixed(0)}`;
        const strategyTextEl = document.getElementById("optimizerStrategyText");
        if (strategyTextEl) strategyTextEl.textContent = opt.strategy || "Optimizes booking yield against local price resistance.";
        renderRevenueOptimizationChart(opt.curve || [], opt.sweet_spot_price);
    } else {
        document.getElementById("optimizerSweetSpot").textContent = "$--";
        document.getElementById("optimizerRange").textContent = "$-- to $--";
        const strategyTextEl = document.getElementById("optimizerStrategyText");
        if (strategyTextEl) strategyTextEl.textContent = "Insufficient active sitter rate data to model conversion curves.";
        renderRevenueOptimizationChart([], null);
    }

    // Render Charts for this service
    renderPriceHistogram(displayStats.price_distribution || []);
    renderCDFChart(displayStats.cdf_curve || []);
    
    if (serviceTab === "all") {
        renderRatingScatter(currentRecords);
    } else {
        renderScatterFromPoints(displayStats.scatter_points || []);
    }

    renderServiceComparisonChart(currentStatsPayload.service_comparisons || {});
    renderNeighborhoodChart(currentStatsPayload.neighborhood_breakdown || []);
    
    // Update Map with Quartile-based Heatmap and Colored Pins for active service
    renderHeatmap(currentRecords, AppState.centerLat, AppState.centerLng, serviceTab);
    renderEconometricModels(currentStatsPayload);
    if (currentRecords && currentRecords.length > 0) {
        renderTable(currentRecords);
    }
}

// ── 3. Service Selector ───────────────────────────────────────────────────────
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

// ── 4. Search History & Multi-Session Studio ─────────────────────────────────
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
            list.innerHTML = `<p style="font-size: 0.85rem; color: var(--text-muted); text-align: center; padding: 1.5rem;">No searches saved yet in the database.</p>`;
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
            item.style.padding = "0.75rem";
            item.style.borderRadius = "var(--radius-sm)";
            item.style.marginBottom = "0.5rem";
            item.style.background = s.id === currentSessionId ? "rgba(59, 130, 246, 0.12)" : "var(--bg-card)";
            item.style.border = s.id === currentSessionId ? "1px solid var(--accent-primary)" : "1px solid var(--border-color)";
            item.style.cursor = "pointer";
            item.style.transition = "background-color 0.15s, border-color 0.15s";
            
            const isChecked = selectedHistorySessionIds.has(s.id);
            const avgDisplay = s.avg_price ? `$${s.avg_price.toFixed(1)}` : "--";

            item.innerHTML = `
                <div style="display: flex; align-items: center;" onclick="event.stopPropagation()">
                    <input type="checkbox" class="history-checkbox" data-session-id="${s.id}" ${isChecked ? 'checked' : ''} style="cursor: pointer; width: 16px; height: 16px;">
                </div>
                <div class="history-info" style="flex-grow: 1;">
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                        <strong style="color: var(--text-heading); font-size: 0.9rem;">#${s.id} ${escapeHtml(s.location)}</strong>
                        <span class="badge-stealth" style="font-size: 0.7rem; padding: 0.1rem 0.4rem;">${s.total_sitters} sitters</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--text-muted); margin: 2px 0 0 0;">${escapeHtml(s.service_type)} &bull; ${date} ${s.radius_km ? `&bull; ${s.radius_km}km` : ''}</p>
                </div>
                <div class="history-stat" style="text-align: right;">
                    <div class="avg" style="font-weight: 700; color: #10b981; font-size: 1.05rem;">${avgDisplay}</div>
                    <p style="font-size:0.7rem; color:var(--text-muted); margin:0;">Avg Rate</p>
                </div>
                <button class="btn-delete-single" data-session-id="${s.id}" title="Delete this session from database" style="background: transparent; border: none; color: #ef4444; cursor: pointer; padding: 0.35rem 0.5rem; font-size: 1.1rem; transition: transform 0.15s;">
                    🗑️
                </button>
            `;

            // Entire card click opens session (unless clicking checkbox or delete)
            item.addEventListener("click", (e) => {
                if (e.target.closest(".history-checkbox") || e.target.closest(".btn-delete-single")) return;
                selectSession(s.id);
            });

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

        // Auto-select latest historical session if no session is currently active
        if (currentSessionId === null && data.sessions && data.sessions.length > 0) {
            selectSession(data.sessions[0].id);
        }

        setupHistoryBulkToolbar(data.sessions);
    } catch (err) {
        console.error("Error loading history:", err);
    }
}

function updateHistoryDeleteToolbar() {
    const deleteBtn = document.getElementById("btnBatchDeleteHistory");
    const analyzeBtnCount = document.getElementById("historyAnalyzeBtnCount");
    const countSpan = document.getElementById("historySelectedCount");
    const selectAllChk = document.getElementById("historySelectAllCheckbox");
    const analyzeBtn = document.getElementById("btnAnalyzeSelectedHistory");

    const count = selectedHistorySessionIds.size;
    if (countSpan) countSpan.textContent = count;
    if (analyzeBtnCount) analyzeBtnCount.textContent = count;

    if (deleteBtn) {
        deleteBtn.style.display = count > 0 ? "inline-flex" : "none";
    }

    if (analyzeBtn) {
        if (count > 0) {
            analyzeBtn.style.opacity = "1";
            analyzeBtn.removeAttribute("disabled");
        } else {
            analyzeBtn.style.opacity = "0.7";
        }
    }

    if (selectAllChk) {
        const allCheckboxes = document.querySelectorAll(".history-checkbox");
        if (allCheckboxes.length > 0 && count === allCheckboxes.length) {
            selectAllChk.checked = true;
            selectAllChk.indeterminate = false;
        } else if (count > 0) {
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
    const analyzeSelectedBtn = document.getElementById("btnAnalyzeSelectedHistory");
    const wipeDbBtn = document.getElementById("btnWipeEntireDatabase");

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

    if (analyzeSelectedBtn) {
        analyzeSelectedBtn.onclick = async () => {
            const count = selectedHistorySessionIds.size;
            if (count === 0) {
                alert("Please check at least one session from the database list to analyze.");
                return;
            }

            try {
                analyzeSelectedBtn.disabled = true;
                analyzeSelectedBtn.innerHTML = `<span class="spinner"></span> Analyzing ${count} Session(s)...`;

                const res = await fetch("/api/history/analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ session_ids: Array.from(selectedHistorySessionIds) })
                });

                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.detail || "Failed to analyze selected sessions.");
                }

                const data = await res.json();
                currentSessionId = data.session_ids[0];
                currentRecords = data.records || [];
                currentExcludedIndices.clear();
                currentAutoOutliers = data.auto_outliers || [];
                AppState.centerLat = data.center_lat || 43.6532;
                AppState.centerLng = data.center_lng || -79.3832;

                // Update Active Dataset Banner
                const bannerTitle = document.getElementById("activeSessionTitle");
                const bannerSub = document.getElementById("activeSessionSubtitle");
                if (bannerTitle) bannerTitle.textContent = `Active Dataset: Selected Session(s) #${data.session_ids.join(", ")}`;
                if (bannerSub) bannerSub.textContent = `Analyzing ${data.total_sitters} unique sitters from ${data.location}`;

                renderResults(data.stats, currentRecords, data.location, data.service_type, currentSessionId);
                loadHistory();

                const resultsEl = document.getElementById("resultsContainer");
                if (resultsEl) resultsEl.scrollIntoView({ behavior: "smooth" });

                logToTerminal(`[✓] Successfully loaded & analyzed ${data.total_sitters} sitters from Session(s) #${data.session_ids.join(", ")}.`, "success");
            } catch (err) {
                console.error("Error analyzing selected sessions:", err);
                alert(`Error analyzing sessions: ${err.message}`);
            } finally {
                analyzeSelectedBtn.disabled = false;
                analyzeSelectedBtn.innerHTML = `⚡ Load & Analyze Selected (<span id="historyAnalyzeBtnCount">${selectedHistorySessionIds.size}</span>)`;
            }
        };
    }

    if (batchDeleteBtn) {
        batchDeleteBtn.onclick = async () => {
            const count = selectedHistorySessionIds.size;
            if (count === 0) return;
            if (!confirm(`Permanently delete ${count} selected search session(s) from the database?`)) return;

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
                logToTerminal(`[✓] Permanently deleted ${result.deleted_count || count} session(s) from database.`, "success");
            } catch (err) {
                console.error("Error deleting sessions:", err);
                alert("Failed to delete selected sessions.");
            }
        };
    }

    if (wipeDbBtn) {
        wipeDbBtn.onclick = async () => {
            if (!confirm("⚠️ WARNING: Are you sure you want to completely PURGE all database records, sessions, sitters, and start 100% fresh?")) return;

            try {
                const res = await fetch("/api/database/reset", { method: "POST" });
                const result = await res.json();
                
                selectedHistorySessionIds.clear();
                currentRecords = [];
                currentExcludedIndices.clear();
                currentStatsPayload = null;
                document.getElementById("resultsContainer").style.display = "none";
                
                loadHistory();
                loadTemporalTrends();
                logToTerminal("[✓] Database completely purged and reset to 0 records.", "success");
                alert("Database has been completely wiped and reset.");
            } catch (err) {
                console.error("Error resetting database:", err);
                alert("Failed to reset database.");
            }
        };
    }
}

async function deleteSingleSession(sessionId) {
    if (!confirm(`Permanently delete Search Session #${sessionId} from database?`)) return;
    try {
        await fetch(`/api/history/${sessionId}`, { method: "DELETE" });
        selectedHistorySessionIds.delete(sessionId);
        loadHistory();
        loadTemporalTrends();
        logToTerminal(`[✓] Session #${sessionId} permanently deleted from database.`, "success");
    } catch (err) {
        console.error("Error deleting session:", err);
    }
}

async function selectSession(sessionId) {
    try {
        const res = await fetch(`/api/history/${sessionId}`);
        if (!res.ok) {
            alert(`Session #${sessionId} not found.`);
            return;
        }
        const session = await res.json();
        
        currentSessionId = session.id;
        currentRecords = session.sitters || [];
        currentExcludedIndices.clear();
        currentAutoOutliers = session.auto_outliers || [];
        AppState.centerLat = session.center_lat || 43.6532;
        AppState.centerLng = session.center_lng || -79.3832;

        // Update Active Dataset Banner
        const bannerTitle = document.getElementById("activeSessionTitle");
        const bannerSub = document.getElementById("activeSessionSubtitle");
        if (bannerTitle) bannerTitle.textContent = `Active Dataset: Session #${session.id} (${session.location})`;
        if (bannerSub) bannerSub.textContent = `Analyzing ${currentRecords.length} sitters & real multi-service rates from database archive`;

        renderResults(session.full_stats || session, currentRecords, session.location, session.service_type, session.id);
        loadHistory();

        const resultsEl = document.getElementById("resultsContainer");
        if (resultsEl) resultsEl.scrollIntoView({ behavior: "smooth" });

        logToTerminal(`[✓] Loaded & analyzed Session #${session.id} (${session.location} - ${currentRecords.length} sitters).`, "success");
    } catch (err) {
        console.error("Error loading session details:", err);
    }
}

// ── 5. Form Submission & Real Multi-Service Extraction ─────────────────────────
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
        AppState.centerLat = data.center_lat || 43.6532;
        AppState.centerLng = data.center_lng || -79.3832;

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

// ── 6. Render All Dashboard Results & Charts ───────────────────────────────────
function renderResults(stats, records, location, service, sessionId) {
    document.getElementById("resultsContainer").style.display = "block";
    currentStatsPayload = stats;
    AppState.stats = stats;
    AppState.records = records;

    // Reset service tab to Master Summary on fresh results
    const masterTabBtn = document.querySelector('.service-tab-btn[data-service-tab="all"]');
    if (masterTabBtn) {
        document.querySelectorAll(".service-tab-btn").forEach(b => b.classList.remove("active"));
        masterTabBtn.classList.add("active");
        AppState.activeServiceTab = "all";
        const activeBadge = document.getElementById("activeServiceBadge");
        if (activeBadge) activeBadge.textContent = "Viewing: Master Summary";
    }

    // Setup Export Link & Sitter Count
    const csvBtn = document.getElementById("exportCsvBtn");
    if (csvBtn && sessionId) {
        csvBtn.href = `/api/export/csv/${sessionId}`;
        csvBtn.style.display = "inline-flex";
    }
    const countBadge = document.getElementById("sittersCountBadge");
    if (countBadge) {
        countBadge.textContent = `${records ? records.length : 0} Sitters`;
    }

    // Update 5-service benchmark cards
    updateServiceRateBenchmarks(stats);

    // Initial render for active view (Master Summary)
    switchActiveServiceView("all");
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

// ── 7. Leaflet Geospatial Map & Real FSA Heatmap ────────────────────────────────
function initMapIfNeeded(centerLat, centerLng) {
    const lat = centerLat || 43.6532;
    const lng = centerLng || -79.3832;

    if (!mapInstance) {
        mapInstance = L.map('mapContainer', {
            center: [lat, lng],
            zoom: 12,
            zoomControl: true
        });

        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(mapInstance);

        markersLayerGroup = L.layerGroup().addTo(mapInstance);
    } else {
        mapInstance.setView([lat, lng], 12);
        mapInstance.invalidateSize();
    }
}

function renderHeatmap(records, centerLat, centerLng, targetService = "all") {
    initMapIfNeeded(centerLat, centerLng);

    markersLayerGroup.clearLayers();
    if (heatLayerInstance) {
        mapInstance.removeLayer(heatLayerInstance);
        heatLayerInstance = null;
    }

    if (!records || records.length === 0) return;

    // 1. Collect all active prices for targetService to compute real quartiles
    const activePrices = [];
    records.forEach((sitter, index) => {
        if (currentExcludedIndices.has(index)) return;
        if (!sitter.lat || !sitter.lng) return;

        let price = sitter.price_numeric;
        if (targetService !== "all" && sitter.services) {
            const srv = sitter.services.find(s => s.service_type === targetService);
            if (srv && srv.price_numeric) price = srv.price_numeric;
        }
        if (price !== null && price !== undefined && !isNaN(price)) {
            activePrices.push(parseFloat(price));
        }
    });

    activePrices.sort((a, b) => a - b);
    const n = activePrices.length;
    let q1 = 25, q2 = 35, q3 = 50;
    if (n >= 4) {
        q1 = activePrices[Math.floor(n * 0.25)];
        q2 = activePrices[Math.floor(n * 0.50)];
        q3 = activePrices[Math.floor(n * 0.75)];
    } else if (n > 0) {
        q1 = activePrices[0];
        q2 = activePrices[Math.floor(n / 2)];
        q3 = activePrices[n - 1];
    }

    const heatPoints = [];
    const validLatLngs = [];
    const coordGroups = {};

    // Group valid sitters by coordinate key
    records.forEach((sitter, index) => {
        if (currentExcludedIndices.has(index)) return;
        if (!sitter.lat || !sitter.lng) return;

        const key = `${sitter.lat.toFixed(4)}_${sitter.lng.toFixed(4)}`;
        if (!coordGroups[key]) coordGroups[key] = [];
        coordGroups[key].push({ sitter, index });
    });

    // Render pins and heat points
    Object.values(coordGroups).forEach(group => {
        const totalInGroup = group.length;

        group.forEach((item, i) => {
            const { sitter, index } = item;

            // Get price for target service
            let price = sitter.price_numeric || 25;
            if (targetService !== "all" && sitter.services) {
                const srv = sitter.services.find(s => s.service_type === targetService);
                if (srv && srv.price_numeric) price = srv.price_numeric;
            }

            // Determine price quartile color & heat intensity matching Photo 3:
            // Lower Rates [Green -> Blue -> Orange -> Red] Higher Rates
            let pinColor = "#10b981"; // Green (Q1 - Lower rates)
            let heatIntensity = 0.20;

            if (price > q3) {
                pinColor = "#ef4444"; // Red (Q4 - Highest rates)
                heatIntensity = 0.95;
            } else if (price > q2) {
                pinColor = "#f59e0b"; // Orange (Q3 - Upper-mid rates)
                heatIntensity = 0.70;
            } else if (price > q1) {
                pinColor = "#3b82f6"; // Blue (Q2 - Lower-mid rates)
                heatIntensity = 0.45;
            }

            // If multiple sitters share the exact same centroid, apply subtle radial dispersion
            let displayLat = sitter.lat;
            let displayLng = sitter.lng;
            if (totalInGroup > 1) {
                const angle = (i * 2 * Math.PI) / totalInGroup;
                const radiusMeters = 85 + (i % 2) * 45; // 85m to 130m offset
                displayLat += (radiusMeters * Math.sin(angle)) / 111320;
                displayLng += (radiusMeters * Math.cos(angle)) / (111320 * Math.cos(sitter.lat * Math.PI / 180));
            }

            // Price-weighted heat point
            heatPoints.push([displayLat, displayLng, heatIntensity]);
            validLatLngs.push([displayLat, displayLng]);

            const customIcon = L.divIcon({
                className: 'custom-price-marker',
                html: `<div id="map-pin-${index}" class="price-marker-pin" style="background-color: ${pinColor}; color: #ffffff; font-weight: 700; border: 2px solid rgba(255,255,255,0.85); box-shadow: 0 2px 6px rgba(0,0,0,0.35); text-shadow: 0 1px 2px rgba(0,0,0,0.4);">$${Math.round(price)}</div>`,
                iconSize: [46, 26],
                iconAnchor: [23, 13]
            });

            const marker = L.marker([displayLat, displayLng], { icon: customIcon }).addTo(markersLayerGroup);

            const postalBadge = sitter.postal_code ? `<span style="background:rgba(59,130,246,0.2); color:#60a5fa; padding:2px 6px; border-radius:4px; font-size:0.75rem; font-weight:700;">📮 ${escapeHtml(sitter.postal_code)}</span>` : '';
            const hoodDisplay = sitter.neighborhood ? `<div style="font-size:0.8rem; color:#cbd5e1; margin-top:2px;">📍 ${escapeHtml(sitter.neighborhood)}</div>` : '';
            const popupContent = `
                <div class="sitter-popup-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h4 style="margin:0; font-size:0.95rem;">${escapeHtml(sitter.name)}</h4>
                        ${postalBadge}
                    </div>
                    ${hoodDisplay}
                    <p style="margin:6px 0; font-size:0.8rem; color:var(--text-muted); line-height:1.4;">${escapeHtml(sitter.headline || 'Local Pet Sitter')}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                        <span class="sitter-popup-badge" style="background-color: ${pinColor}; color: #fff;">$${Math.round(price)}</span>
                        <span style="font-size:0.8rem; color:#f59e0b;">★ ${escapeHtml(sitter.rating || '5.0')} (${sitter.reviews_count || 0})</span>
                    </div>
                    ${sitter.profile_url ? `<a href="${sitter.profile_url}" target="_blank" style="display:block; margin-top:8px; font-size:0.75rem; color:#3b82f6; text-decoration:none;">View Rover Profile ↗</a>` : ''}
                </div>
            `;
            marker.bindPopup(popupContent);
        });
    });

    if (typeof L.heatLayer === 'function' && heatPoints.length > 0) {
        heatLayerInstance = L.heatLayer(heatPoints, {
            radius: 35,
            blur: 22,
            maxZoom: 14,
            max: 1.0,
            gradient: {
                0.15: '#10b981', // Lower Rates (Green)
                0.45: '#3b82f6', // Mid-Low (Blue)
                0.70: '#f59e0b', // Mid-High (Orange)
                0.95: '#ef4444'  // Higher Rates (Red)
            }
        }).addTo(mapInstance);
    }

    if (validLatLngs.length > 0) {
        const bounds = L.latLngBounds(validLatLngs);
        if (bounds.isValid()) {
            mapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
        }
    }
}

// ── 8. Statistical Charts ─────────────────────────────────────────────────────

function renderPriceHistogram(distribution, parametricCurve) {
    const ctx = document.getElementById("priceDistributionChart").getContext("2d");
    if (priceChartInstance) priceChartInstance.destroy();

    const labels = distribution.map(d => d.range);
    const data = distribution.map(d => d.count);

    const datasets = [{
        type: "bar",
        label: "Observed Sitters",
        data: data.length ? data : [0],
        backgroundColor: "rgba(59, 130, 246, 0.7)",
        borderColor: "#3b82f6",
        borderWidth: 1.5,
        borderRadius: 6,
        order: 2,
    }];

    priceChartInstance = new Chart(ctx, {
        data: {
            labels: labels.length ? labels : ["No data"],
            datasets: datasets
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
                pointRadius: 4
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

function renderScatterFromPoints(points) {
    const ctx = document.getElementById("ratingScatterChart").getContext("2d");
    if (ratingChartInstance) ratingChartInstance.destroy();

    const scatterData = points.map(p => ({
        x: p.reviews_count,
        y: p.price,
        name: p.name,
        rating: p.rating
    }));

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
                    backgroundColor: "rgba(59, 130, 246, 0.75)",
                    borderColor: "#3b82f6",
                    borderWidth: 1.5,
                    borderRadius: 4
                },
                {
                    label: "Median Rate ($)",
                    data: medianData,
                    backgroundColor: "rgba(16, 185, 129, 0.75)",
                    borderColor: "#10b981",
                    borderWidth: 1.5,
                    borderRadius: 4
                }
            ]
        },
        options: {
            indexAxis: 'y', // Renders horizontally so neighborhood names form a clear vertical column
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#cbd5e1", font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: $${ctx.raw}`
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: {
                        color: "#cbd5e1",
                        font: { size: 11, weight: '500' },
                        autoSkip: false
                    }
                },
                x: {
                    title: { display: true, text: "Price ($)", color: "#9ca3af" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#9ca3af" }
                }
            }
        }
    });
}

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

// ── 9. Outlier Control & Recalculation ──────────────────────────────────────────
function setupOutlierToolbar() {
    const btnAutoIQR = document.getElementById("btnAutoFilterIQR");
    const btnReset = document.getElementById("btnResetFilters");

    btnAutoIQR.addEventListener("click", () => {
        const activeOutliers = (AppState.activeServiceTab !== "all" && currentStatsPayload && currentStatsPayload.per_service_analytics && currentStatsPayload.per_service_analytics[AppState.activeServiceTab])
            ? (currentStatsPayload.per_service_analytics[AppState.activeServiceTab].outlier_indices || [])
            : (currentAutoOutliers || []);

        if (activeOutliers.length === 0) {
            alert(`No price points fall outside the 1.5 * IQR outlier boundary for ${SERVICE_TITLES[AppState.activeServiceTab] || 'active service'}.`);
            return;
        }
        activeOutliers.forEach(idx => currentExcludedIndices.add(idx));
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
        currentStatsPayload = data.stats;
        switchActiveServiceView(AppState.activeServiceTab);
        renderTable(currentRecords);
    } catch (err) {
        console.error("Error recalculating stats:", err);
    }
}

// ── 10. Sitter Table Filtering & Sorting ────────────────────────────────────────
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

// ── 11. Render Sitter Table with Real Postal Code Badges & 5 Services ─────────
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

    const activeSittersCount = records.filter((_, idx) => !currentExcludedIndices.has(idx)).length;
    if (countBadge) countBadge.textContent = `${activeSittersCount} Active / ${records.length} Total`;

    const activeOutlierIndices = (AppState.activeServiceTab !== "all" && currentStatsPayload && currentStatsPayload.per_service_analytics && currentStatsPayload.per_service_analytics[AppState.activeServiceTab])
        ? (currentStatsPayload.per_service_analytics[AppState.activeServiceTab].outlier_indices || [])
        : (currentAutoOutliers || []);

    let indexedRecords = records.map((r, originalIdx) => ({
        data: r,
        originalIdx: originalIdx,
        isExcluded: currentExcludedIndices.has(originalIdx),
        isAutoOutlier: activeOutlierIndices.includes(originalIdx)
    }));

    let filtered = indexedRecords.filter(item => {
        const r = item.data;

        if (currentFilterQuery) {
            const nameMatch = (r.name || "").toLowerCase().includes(currentFilterQuery);
            const headlineMatch = (r.headline || "").toLowerCase().includes(currentFilterQuery);
            const hoodMatch = (r.neighborhood || "").toLowerCase().includes(currentFilterQuery);
            const postalMatch = (r.postal_code || "").toLowerCase().includes(currentFilterQuery);
            if (!nameMatch && !headlineMatch && !hoodMatch && !postalMatch) return false;
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

                case "postal_code":
                    valA = (ra.postal_code || ra.neighborhood || "").toLowerCase();
                    valB = (rb.postal_code || rb.neighborhood || "").toLowerCase();
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

        const isCurrentActiveCol = (AppState.activeServiceTab === targetServiceType);
        const colHighlightStyle = isCurrentActiveCol ? "background: rgba(59, 130, 246, 0.12); border-left: 1px solid rgba(59, 130, 246, 0.25); border-right: 1px solid rgba(59, 130, 246, 0.25);" : "";

        if (price !== null) {
            return `<td style="text-align: center; ${colHighlightStyle}"><span class="badge-price" style="font-weight: 700;">$${Math.round(price)}</span></td>`;
        } else {
            return `<td style="text-align: center; ${colHighlightStyle}"><span style="color: var(--text-muted); font-size: 0.78rem; opacity: 0.55;">N/A</span></td>`;
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
        
        const postalText = r.postal_code ? `📮 ${r.postal_code}` : (r.neighborhood || 'Local Area');
        const hoodBadge = `<span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 0.2rem 0.55rem; border-radius: 4px; font-size: 0.8rem; font-weight: 700; border: 1px solid rgba(59, 130, 246, 0.3);">${escapeHtml(postalText)}</span>`;

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

// ── 12. Temporal Trends Chart ──────────────────────────────────────────────────
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

// ── 9. Econometric Hedonic Model & Spatial Premiums ─────────────────────────────
function renderEconometricModels(stats) {
    if (!stats) return;

    // 1. Hedonic Regression Model Output
    const hedonic = stats.hedonic_decomposition || {};
    const r2Badge = document.getElementById("hedonicR2Badge");
    const elReviewElasticity = document.getElementById("hedonicReviewElasticity");
    const elReviewDesc = document.getElementById("hedonicReviewDesc");
    const elStarPremium = document.getElementById("hedonicStarPremium");
    const elStarDesc = document.getElementById("hedonicStarDesc");
    const elBaseRate = document.getElementById("hedonicBaseRate");

    if (hedonic.status === "success") {
        if (r2Badge) r2Badge.textContent = `Model Fit R²: ${(hedonic.r_squared * 100).toFixed(1)}% (N=${hedonic.sample_size})`;
        if (elReviewElasticity) elReviewElasticity.textContent = `+${(hedonic.review_elasticity * 100).toFixed(1)}%`;
        if (elReviewDesc && hedonic.interpretation) elReviewDesc.textContent = hedonic.interpretation.review_impact;
        if (elStarPremium) elStarPremium.textContent = `${hedonic.star_sitter_premium_pct >= 0 ? '+' : ''}${hedonic.star_sitter_premium_pct.toFixed(1)}%`;
        if (elStarDesc && hedonic.interpretation) elStarDesc.textContent = hedonic.interpretation.star_badge_impact;
        if (elBaseRate) elBaseRate.textContent = `$${hedonic.base_baseline_rate.toFixed(2)}`;
    } else {
        if (r2Badge) r2Badge.textContent = "Model Fit: Insufficient Data (<6 sitters)";
        if (elReviewElasticity) elReviewElasticity.textContent = "--";
        if (elStarPremium) elStarPremium.textContent = "--";
        if (elBaseRate) elBaseRate.textContent = "$--";
    }

    // 2. Spatial Location Quotients & Neighborhood Premiums Table
    const spatialList = document.getElementById("spatialPremiumsList");
    if (spatialList) {
        const premiums = stats.spatial_premiums || [];
        if (premiums.length === 0) {
            spatialList.innerHTML = `<p style="font-size: 0.8rem; color: var(--text-muted); text-align: center; padding: 1rem;">No spatial data available yet.</p>`;
        } else {
            spatialList.innerHTML = "";
            premiums.forEach(p => {
                const item = document.createElement("div");
                item.style.cssText = "display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0.75rem; background: var(--bg-card); border-radius: 6px; border: 1px solid var(--border-color); font-size: 0.82rem;";
                
                const sign = p.premium_pct >= 0 ? "+" : "";
                const color = p.premium_pct >= 15 ? "#10b981" : (p.premium_pct <= -15 ? "#ef4444" : "#fbbf24");
                
                item.innerHTML = `
                    <div style="display: flex; flex-direction: column;">
                        <span style="color: #fff; font-weight: 600;">📮 ${escapeHtml(p.postal_code)} <span style="font-weight: 400; color: var(--text-muted); font-size: 0.78rem;">(${p.sitters_count} sitters)</span></span>
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">${escapeHtml(p.neighborhood)}</span>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-weight: 700; color: ${color};">${sign}${p.premium_pct}%</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">$${p.median_price} med</div>
                    </div>
                `;
                spatialList.appendChild(item);
            });
        }
    }
}

// ── 10. Platform Fee & Net Profit Simulator ────────────────────────────────────
function setupProfitSimulator() {
    const rateInput = document.getElementById("simListedRate");
    const nightsInput = document.getElementById("simNightsCount");
    const petsInput = document.getElementById("simPetsCount");
    const constantCareToggle = document.getElementById("simConstantCareToggle");

    function calculateProfit() {
        const baseRate = parseFloat(rateInput?.value) || 65;
        const nights = parseInt(nightsInput?.value) || 1;
        const pets = parseInt(petsInput?.value) || 1;
        const isConstantCare = constantCareToggle?.checked || false;

        // Additional pets typically charged at 50% extra
        const petMultiplier = 1 + (pets - 1) * 0.5;
        // Constant care premium: +45%
        const constantCareMultiplier = isConstantCare ? 1.45 : 1.0;

        const effectiveRatePerNight = baseRate * petMultiplier * constantCareMultiplier;
        const sitterSubtotal = effectiveRatePerNight * nights;

        // Rover takes 20% from the sitter's listed earnings
        const netBankPayout = sitterSubtotal * 0.80;

        // Client pays listed subtotal + 11% Rover service fee (capped at $50 on Rover, but standard 11%)
        const clientBookingFee = Math.min(50, sitterSubtotal * 0.11);
        const clientTotalAtCheckout = sitterSubtotal + clientBookingFee;

        // Total platform take = Sitter 20% fee + Client 11% fee
        const totalPlatformTake = (sitterSubtotal * 0.20) + clientBookingFee;

        // Update DOM
        const elPayout = document.getElementById("simNetPayout");
        const elClientTotal = document.getElementById("simClientTotal");
        const elRoverCut = document.getElementById("simRoverCut");
        const elRecommended = document.getElementById("simRecommendedListing");

        if (elPayout) elPayout.textContent = `$${netBankPayout.toFixed(2)}`;
        if (elClientTotal) elClientTotal.textContent = `$${clientTotalAtCheckout.toFixed(2)}`;
        if (elRoverCut) elRoverCut.textContent = `$${totalPlatformTake.toFixed(2)}`;
        
        // Sitter wants to net $60/unit -> List at 60 / 0.8 = $75
        const targetRateForNet60 = (60.0 / 0.80) * (isConstantCare ? 1.45 : 1.0);
        if (elRecommended) elRecommended.textContent = `$${targetRateForNet60.toFixed(2)}`;
    }

    if (rateInput) rateInput.addEventListener("input", calculateProfit);
    if (nightsInput) nightsInput.addEventListener("input", calculateProfit);
    if (petsInput) petsInput.addEventListener("input", calculateProfit);
    if (constantCareToggle) constantCareToggle.addEventListener("change", calculateProfit);

    calculateProfit();
}

