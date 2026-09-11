let currentLang = 'en';
let produceBatches = [];
let mandiRecordsCache = [];
let selectedImageBase64 = null;
let chatImageBase64 = null;
let isLiveVoiceActive = false;
let isRecognizing = false;
let voiceDebounceTimer = null; // New timer to wait before sending
let weatherRequestPromise = null;
let weatherCache = null;
let farmerProfile = null;
let storageFinderMap = null;
let storageFinderLayer = null;

const translations = {
    en: {
        analyzing: "⏳ Running Gemini Quality & Spoilage AI...",
        analyzeBtn: "Analyze Quality and Predict Spoilage",
        settleBtn: "Confirm Sale, Settle Financials & Archive to History",
        settling: "⏳ Finalizing Financial Settlement & Generating Next Crop Plan...",
        customCostPrompt: "Enter Custom Cost Name (e.g., Cold Truck Transport, Sacking):",
        toastSaved: "Produce Batch registered and diagnosed successfully!",
        toastSettled: "Produce sold, profit calculated, and archived!",
        toastError: "Encountered an issue. Processed via fallback rules.",
        voiceListening: "Listening... speak now",
        voiceActive: "Live Voice On",
        voiceChatStatus: "Voice Chat",
        voiceNotSupported: "Speech recognition is not supported in this browser. Please use Chrome/Edge.",
        micBlocked: "Microphone permission was denied. Please allow microphone access in browser settings.",
        voiceError: "Voice input failed. Please try again or type your message.",
        batches: "Batches",
        records: "Records",
        activeBatch: "Select Active Batch",
        storedVolume: "Stored Volume",
        spoilageRisk: "Spoilage Risk",
        storage: "Storage",
        processing: "Processing",
        daysLeft: "Days left",
        currentGrowingCrop: "Current Growing Crop",
        suggestedHarvest: "Suggested harvest",
        sale: "Settle Sale ➔",
        noStored: "No active stored produce batches.",
        noHistory: "No completed sales history recorded yet.",
        nextCropTitle: "AI Next Crop Recommendations for this Field:",
        nextCropFallbackTitle: "Suggested Next Crops:",
        qtyProducedSold: "Qty Produced / Sold",
        sellingPrice: "Selling Price",
        totalRevenue: "Total Revenue",
        totalCost: "Total Cost",
        demoLoaded: "Tomato demo data loaded. Review it and register the crop for AI analysis.",
        noWeatherWarnings: "No rule-based weather warnings right now.",
        weatherUnavailable: "No real weather data is available for your location right now.",
        weatherNeedsGps: "Weather requires your GPS location."
    },
    hi: {
        analyzing: "⏳ जेमिनी एआई द्वारा गुणवत्ता व सड़न जांच जारी है...",
        analyzeBtn: "गुणवत्ता जांचें एवं सड़न का अनुमान लगाएं",
        settleBtn: "बिक्री पक्की करें, मुनाफा निकालें एवं इतिहास में दर्ज करें",
        settling: "⏳ वित्तीय गणना एवं अगली फसल सुझाव तैयार किए जा रहे हैं...",
        customCostPrompt: "अतिरिक्त खर्च का नाम लिखें (उदा. कोल्ड वैन किराया, विशेष पैकिंग):",
        toastSaved: "उपज बैच सफलतापूर्वक पंजीकृत और विश्लेषित हुआ!",
        toastSettled: "बिक्री पूर्ण! शुद्ध लाभ दर्ज हुआ और अगली फसल का सुझाव तैयार है।",
        toastError: "त्रुटि हुई। ऑफलाइन मोड में सुरक्षित किया गया।",
        voiceListening: "सुन रहे हैं... कृपया बोलें",
        voiceActive: "लाइव आवाज चालू",
        voiceChatStatus: "आवाज संवाद",
        voiceNotSupported: "इस ब्राउज़र में आवाज पहचान उपलब्ध नहीं है। कृपया Chrome का उपयोग करें।",
        micBlocked: "माइक्रोफ़ोन अनुमति नहीं मिली। कृपया ब्राउज़र सेटिंग में अनुमति दें।",
        voiceError: "आवाज पहचान में त्रुटि हुई। कृपया पुनः प्रयास करें।",
        batches: "बैच",
        records: "रिकॉर्ड",
        activeBatch: "सक्रिय बैच चुनें",
        storedVolume: "भंडारित मात्रा",
        spoilageRisk: "सड़न जोखिम",
        storage: "भंडारण",
        processing: "प्रसंस्करण",
        daysLeft: "दिन शेष",
        currentGrowingCrop: "वर्तमान बढ़ती फसल",
        suggestedHarvest: "अनुमानित कटाई",
        sale: "बिक्री दर्ज करें ➔",
        noStored: "कोई सक्रिय भंडारित फसल नहीं है।",
        noHistory: "कोई पुराना बिक्री रिकॉर्ड उपलब्ध नहीं है।",
        nextCropTitle: "इस खेत के लिए एआई अगली फसल सुझाव:",
        nextCropFallbackTitle: "अगली फसल के सुझाव:",
        qtyProducedSold: "उत्पादित / बेची मात्रा",
        sellingPrice: "विक्रय मूल्य",
        totalRevenue: "कुल आय",
        totalCost: "कुल लागत",
        demoLoaded: "टमाटर डेमो डेटा लोड हो गया। समीक्षा करके एआई जांच के लिए फसल दर्ज करें।",
        noWeatherWarnings: "अभी कोई नियम-आधारित मौसम चेतावनी नहीं है।",
        weatherUnavailable: "इस समय आपके स्थान के लिए वास्तविक मौसम डेटा उपलब्ध नहीं है।",
        weatherNeedsGps: "मौसम देखने के लिए GPS स्थान आवश्यक है।"
    }
};

function t(key) {
    return translations[currentLang][key] || translations.en[key] || key;
}

document.addEventListener("DOMContentLoaded", () => {
    try {
        const today = new Date().toISOString().split('T')[0];
        const h = document.getElementById("harvest_date");
        const s = document.getElementById("selling_date");
        if (h) h.value = today;
        if (s) s.value = today;
    } catch (e) {}

    loadBatches();
    loadProfile().finally(() => requestWeatherFromGps());
    fetchMandiRates();
    handlePreCostCalculation();
});

async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/auth";
}

async function loadProfile() {
    const response = await fetch("/api/profile");
    if (response.status === 401) {
        window.location.href = "/auth";
        return;
    }
    if (!response.ok) throw new Error(`Profile request failed (${response.status})`);

    const data = await response.json();
    farmerProfile = data.profile || null;
    const displayName = document.getElementById("display-farmer");
    if (displayName && farmerProfile?.full_name) displayName.innerText = farmerProfile.full_name;
}

function openProfile() {
    const modal = document.getElementById("profile-modal");
    if (!modal) return;

    document.getElementById("profile-name").value = farmerProfile?.full_name || "";
    document.getElementById("profile-latitude").value = farmerProfile?.latitude ?? "";
    document.getElementById("profile-longitude").value = farmerProfile?.longitude ?? "";
    document.getElementById("profile-location-name").value = farmerProfile?.location_name || "";
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
}

function closeProfile() {
    const modal = document.getElementById("profile-modal");
    if (modal) modal.classList.add("hidden");
    document.body.style.overflow = "";
}

function useProfileLocation() {
    if (!navigator.geolocation) {
        showToast("Location is not supported by this browser.", "error");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        position => {
            document.getElementById("profile-latitude").value = position.coords.latitude.toFixed(6);
            document.getElementById("profile-longitude").value = position.coords.longitude.toFixed(6);
            showToast("Farm location detected.", "success");
        },
        () => showToast("Could not access your location. Please enter coordinates manually.", "error"),
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

async function saveProfile(event) {
    event.preventDefault();
    const payload = {
        full_name: document.getElementById("profile-name").value.trim(),
        latitude: document.getElementById("profile-latitude").value,
        longitude: document.getElementById("profile-longitude").value,
        location_name: document.getElementById("profile-location-name").value.trim()
    };

    try {
        const response = await fetch("/api/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Profile could not be saved.");

        farmerProfile = data.profile;
        const displayName = document.getElementById("display-farmer");
        if (displayName) displayName.innerText = farmerProfile.full_name || "Signed in";
        closeProfile();
        showToast("Profile saved successfully.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

function useFarmLocation() {
    if (!navigator.geolocation) {
        showToast("Location is not supported by this browser.", "error");
        return;
    }

    const status = document.getElementById("weather-status");
    if (status) status.textContent = "Getting your farm location...";
    navigator.geolocation.getCurrentPosition(
        async position => {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;
            farmerProfile = {
                ...(farmerProfile || {}),
                latitude,
                longitude
            };
            await fetchWeather(latitude, longitude);
        },
        error => {
            if (status) status.textContent = error.code === error.PERMISSION_DENIED
                ? "Location permission was denied. Enter coordinates in Profile."
                : "Could not access your location. Try again or use Profile coordinates.";
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
}

async function requestWeatherFromGps() {
    if (weatherRequestPromise) return weatherRequestPromise;

    const latitude = Number(farmerProfile?.latitude);
    const longitude = Number(farmerProfile?.longitude);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) {
        weatherRequestPromise = fetchWeather(latitude, longitude).finally(() => {
            weatherRequestPromise = null;
        });
        return weatherRequestPromise;
    }

    const status = document.getElementById("weather-status");
    if (status) status.textContent = "Save your farm location in Profile or use your current location.";
    return null;
}

async function deleteAllProduce() {
    const confirmed = window.confirm("Delete all your registered crop data from Supabase? This cannot be undone.");
    if (!confirmed) return;

    try {
        const response = await fetch("/api/produce/delete-all", { method: "DELETE" });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.error || `Delete failed (${response.status})`);
        }
        produceBatches = [];
        renderAllViews();
        showToast("All your crop data was permanently deleted.", "success");
    } catch (error) {
        showToast(error.message, "error");
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));

    const target = document.getElementById(`tab-${tabId}`);
    if (target) target.classList.add('active');

    document.querySelectorAll('.nav-item').forEach(btn => {
        const attr = btn.getAttribute('onclick') || '';
        if (attr.includes(`switchTab('${tabId}')`)) {
            btn.classList.add('active');
        }
    });
}

function showToast(msg, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = msg;
    container.appendChild(toast);
    setTimeout(() => {
        if (toast && toast.parentNode) toast.remove();
    }, 3500);
}

function setLanguage(lang) {
    currentLang = lang;
    const btnEn = document.getElementById('btn-en');
    const btnHi = document.getElementById('btn-hi');
    if (btnEn) btnEn.classList.toggle('active', lang === 'en');
    if (btnHi) btnHi.classList.toggle('active', lang === 'hi');

    document.querySelectorAll('[data-en]').forEach(el => {
        const text = el.getAttribute(`data-${lang}`);
        if (text) el.textContent = text;
    });

    const chatLangIndicator = document.getElementById("chat-lang-indicator");
    if (chatLangIndicator) {
        chatLangIndicator.innerText = (currentLang === 'hi') ? 'EN' : 'HI';
    }

    const weatherAction = document.getElementById('weather-action-result');
    if (weatherAction && !weatherCache?.data) weatherAction.textContent = currentLang === 'hi' ? 'पहले GPS मौसम लोड करें, फिर जांचें।' : 'Load your GPS weather first, then analyze.';
    const weatherStatus = document.getElementById('weather-status');
    if (weatherStatus && (!weatherStatus.textContent || weatherStatus.textContent.includes('Waiting'))) {
        weatherStatus.textContent = currentLang === 'hi' ? 'आपके GPS स्थान की प्रतीक्षा है...' : 'Waiting for your GPS location...';
    }

    renderAllViews();
    handlePreCostCalculation();
}

async function toggleChatLanguage() {
    const nextLang = (currentLang === 'en') ? 'hi' : 'en';
    setLanguage(nextLang);
    const messages = Array.from(document.querySelectorAll('#chat-messages .bot-msg, #chat-messages .user-msg'));
    const originalMessages = messages.map(message => {
        if (!message.dataset.originalText) message.dataset.originalText = message.innerText;
        return message.dataset.originalText;
    });

    if (messages.length === 0) return;
    try {
        const response = await fetch('/api/assistant/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: originalMessages, target_lang: nextLang })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Translation failed.');
        (data.translations || []).forEach((translation, index) => {
            if (messages[index] && translation) messages[index].innerText = translation;
        });
        showToast(nextLang === 'hi' ? 'चैट हिंदी में बदल गई।' : 'Chat switched to English.', 'info');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function loadBatches() {
    try {
        const res = await fetch("/api/produce/list");
        if (res.status === 401) {
            window.location.href = "/auth";
            return;
        }
        const data = await res.json();
        produceBatches = data.batches || [];
    } catch (e) {
        console.warn("Offline batch fallback active");
    }
    renderAllViews();
}

function renderAllViews() {
    renderStoredProduce();
    populateSettlementDropdown();
    renderHistoryProduce();
    updateTallyStrip();
}

function updateTallyStrip() {
    let activeQty = 0;
    let highRiskCount = 0;
    let totalRevenue = 0;
    let totalProfit = 0;

    produceBatches.forEach(b => {
        if (b.status === "active") {
            activeQty += parseFloat(b.quantity_kg) || 0;
            if (b.spoilage_risk === "High") highRiskCount++;
        } else if (b.status === "sold") {
            totalRevenue += parseFloat(b.total_revenue) || 0;
            totalProfit += parseFloat(b.net_profit_loss) || 0;
        }
    });

    const statActive = document.getElementById("stat-active-qty");
    const statRisk = document.getElementById("stat-high-risk");
    const statRev = document.getElementById("stat-total-revenue");
    const statProfit = document.getElementById("stat-total-profit");

    if (statActive) statActive.innerHTML = `${activeQty.toLocaleString()} <small>KG</small>`;
    if (statRisk) statRisk.innerHTML = `${highRiskCount} <small>${currentLang === 'hi' ? 'बैच' : 'BATCH'}</small>`;
    if (statRev) statRev.innerText = `₹ ${totalRevenue.toLocaleString()}`;
    if (statProfit) statProfit.innerText = `₹ ${totalProfit.toLocaleString()}`;
}

// ============================================================
// PRE-COST CALCULATOR LOGIC
// ============================================================

async function handlePreCostCalculation(e) {
    if (e && e.preventDefault) e.preventDefault();

    const crop = document.getElementById("calc_crop")?.value || "Wheat";
    const area = parseFloat(document.getElementById("calc_area")?.value) || 1.0;
    const unit = document.getElementById("calc_area_unit")?.value || "Acre";
    const customYield = parseFloat(document.getElementById("calc_custom_yield")?.value) || 0;

    const payload = {
        crop_name: crop,
        land_area: area,
        area_unit: unit,
        cost_seeds: parseFloat(document.getElementById("calc_seed")?.value) || 0,
        cost_fertilizer: parseFloat(document.getElementById("calc_fert")?.value) || 0,
        cost_pesticide: parseFloat(document.getElementById("calc_pest")?.value) || 0,
        cost_irrigation: parseFloat(document.getElementById("calc_irrig")?.value) || 0,
        cost_labor: parseFloat(document.getElementById("calc_labour")?.value) || 0,
        cost_machinery: parseFloat(document.getElementById("calc_mach")?.value) || 0,
        cost_fuel: parseFloat(document.getElementById("calc_fuel")?.value) || 0,
        cost_misc: parseFloat(document.getElementById("calc_misc")?.value) || 0,
        custom_yield_kg: customYield
    };

    try {
        const res = await fetch("/api/calculator/pre-cost", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const d = await res.json();

        if (d.success) {
            const totalCostEl = document.getElementById("res-total-cost");
            const yieldEl = document.getElementById("res-yield");
            const rateEl = document.getElementById("res-rate");
            const revenueEl = document.getElementById("res-revenue");
            if (totalCostEl) totalCostEl.innerText = `₹ ${d.total_production_cost.toLocaleString()}`;
            if (yieldEl) yieldEl.innerText = `${d.expected_yield_kg.toLocaleString()} KG (${d.expected_yield_quintals} Qt)`;
            if (rateEl) rateEl.innerHTML = `₹ ${d.mandi_modal_price_per_quintal.toLocaleString()} / Qt <small id="res-rate-date">(${d.rate_date})</small>`;
            if (revenueEl) revenueEl.innerText = `₹ ${d.estimated_revenue.toLocaleString()}`;

            const profitEl = document.getElementById("res-net-profit");
            const profitVal = d.expected_profit_loss;
            if (profitEl) {
                profitEl.innerText = `${profitVal >= 0 ? '+' : '-'} ₹ ${Math.abs(profitVal).toLocaleString()}`;
                profitEl.className = `res-val ${profitVal >= 0 ? 'text-green' : 'text-risk'}`;
            }

            const unitEl = document.getElementById("res-profit-unit");
            if (unitEl) unitEl.innerText = `${d.profit_per_selected_unit >= 0 ? '+' : '-'} ₹ ${Math.abs(d.profit_per_selected_unit).toLocaleString()} / ${unit}`;
        }
    } catch (err) {
        console.error("Calculator error:", err);
    }
}

function autoFetchMandiBenchmark() {
    handlePreCostCalculation();
}

// ============================================================
// MANDI DATA LOGIC
// ============================================================

async function fetchMandiRates() {
    const tbody = document.getElementById("mandi-tbody");
    const alertBox = document.getElementById("mandi-alert-box");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 24px;">⏳ Loading government APMC market data...</td></tr>`;

    try {
        const res = await fetch("/api/market/mandi-rates");
        const data = await res.json();
        mandiRecordsCache = data.records || [];

        if (alertBox) {
            if (data.source === "live_mandi_api") {
                alertBox.className = "mandi-alert live";
                alertBox.innerText = "🟢 Displaying fresh daily mandi rates from the keyless Mandi API.";
            } else if (data.source === "live_datagov") {
                alertBox.className = "mandi-alert live";
                alertBox.innerText = "🟢 Displaying live Data.gov.in APMC mandi records.";
            } else if (data.source === "secondary_gov") {
                alertBox.className = "mandi-alert live";
                alertBox.innerText = "🟢 Displaying live secondary government mandi records.";
            } else {
                alertBox.className = "mandi-alert fallback";
                alertBox.innerText = "🟡 Live government mandi data is unavailable right now. No stale benchmark rates are being shown.";
            }
            alertBox.classList.remove("hidden");
        }

        renderMandiTable(mandiRecordsCache);
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" style="color:var(--risk-red); text-align:center;">Failed to load mandi data. Please refresh.</td></tr>`;
    }
}

function renderMandiTable(records) {
    const tbody = document.getElementById("mandi-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 20px; color: var(--text-muted);">${currentLang === 'hi' ? 'इस फिल्टर के लिए कोई मंडी भाव नहीं मिला।' : 'No mandi records found matching criteria.'}</td></tr>`;
        return;
    }

    records.forEach(r => {
        const isToday = r.is_today;
        const statusBadge = isToday
            ? `<span class="badge-live">🟢 Today's Rate (${r.arrival_date})</span>`
            : `<span class="badge-latest">📅 Rate Date: ${r.arrival_date}</span>`;

        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>${r.state}</strong><br><small style="color:var(--text-muted);">${r.district || '-'}</small></td>
            <td><strong>${r.market}</strong></td>
            <td>${r.commodity} <small style="color:var(--text-muted);">(${r.variety || 'Desi'})</small></td>
            <td>₹ ${r.min_price}</td>
            <td>₹ ${r.max_price}</td>
            <td><strong style="color: var(--leaf-green); font-size:14px;">₹ ${r.modal_price}</strong></td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });
}

function filterMandi() {
    const crop = document.getElementById("mandi-search-crop")?.value.toLowerCase().trim() || "";
    const state = document.getElementById("mandi-filter-state")?.value.toLowerCase().trim() || "";
    const market = document.getElementById("mandi-search-market")?.value.toLowerCase().trim() || "";

    const filtered = mandiRecordsCache.filter(r => {
        const matchCrop = !crop || r.commodity.toLowerCase().includes(crop);
        const matchState = !state || r.state.toLowerCase().includes(state);
        const matchMarket = !market || r.market.toLowerCase().includes(market) || (r.district && r.district.toLowerCase().includes(market));
        return matchCrop && matchState && matchMarket;
    });

    renderMandiTable(filtered);
}

// ============================================================
// BATCHES & STORED PRODUCE
// ============================================================

function renderStoredProduce() {
    const container = document.getElementById("stored-batches-list");
    if (!container) return;
    container.innerHTML = "";

    const activeList = produceBatches.filter(b => b.status === "active");
    const storedCount = document.getElementById("stored-count");
    if (storedCount) storedCount.innerText = `${activeList.length} ${t('batches')}`;

    if (activeList.length === 0) {
        container.innerHTML = `<div style="padding: 20px; color: var(--text-muted); font-size: 14px;">${t('noStored')}</div>`;
        return;
    }

    activeList.forEach(b => {
        const isGrowing = b.crop_status === "growing";
        const riskClass = b.spoilage_risk === "High" ? "risk-high" : (b.spoilage_risk === "Medium" ? "risk-medium" : "risk-low");
        const nextCropHtml = !isGrowing && b.next_crop_recommendation?.length ? `
            <div class="next-crop-container stored-next-crop">
                <div class="next-crop-title">🌱 ${t('nextCropTitle')}</div>
                <div class="next-crop-items">
                    ${b.next_crop_recommendation.slice(0, 3).map(rec => `
                        <div class="crop-plan-item">
                            <strong>${rec.crop}</strong> <small style="color:var(--turmeric-dark);">[ROI: ${rec.roi_potential} | ${currentLang === 'hi' ? 'पानी' : 'Water'}: ${rec.water_need}]</small>
                            <p style="margin-top:4px; font-size:11.5px; color:var(--text-muted);">${rec.reason}</p>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';
        const card = document.createElement("div");
        card.className = `batch-card ${riskClass}`;
        card.innerHTML = `
            <div>
                <span class="crop-title">${b.crop_name}</span>
                <small style="display: block; color: var(--text-muted);">${b.variety || ''} | ${b.field_name || ''}</small>
                <span class="detail-lbl" style="margin-top: 4px;">${isGrowing ? 'Current Growing Crop' : b.storage_type}</span>
            </div>
            <div>
                <span class="detail-lbl">${t('storedVolume')}</span>
                <span class="detail-val">${parseFloat(b.quantity_kg).toLocaleString()} KG</span>
                <small style="color: var(--text-muted);">Grade: <strong>${b.quality_grade || 'A'}</strong></small>
            </div>
            <div>
                <span class="detail-lbl">${t('spoilageRisk')}</span>
                <span class="detail-val text-${b.spoilage_risk === 'High' ? 'risk' : 'green'}">
                    ${isGrowing ? `${t('suggestedHarvest')}: ${b.suggested_harvest_date || (currentLang === 'hi' ? 'एआई जांच बाकी' : 'Pending AI analysis')}` : `${b.spoilage_risk} (${b.shelf_life_days} ${t('daysLeft')})`}
                </span>
                <small style="display:block; font-size:11px; color:var(--text-muted);">${b.defect_summary || ''}</small>
            </div>
            <div class="batch-advisory">
                <strong>💡 ${t('storage')}:</strong> ${b.recommendation}<br>
                <strong>⚙️ ${t('processing')}:</strong> ${b.processing_idea}
            </div>
            ${nextCropHtml}
            <div>
                <button type="button" class="btn-secondary" onclick="openSettlementForBatch('${b.id}')">
                    ${t('sale')}
                </button>
                <button type="button" class="btn-secondary" onclick="openStorageFinder('${b.id}')">
                    📍 Find Storage
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

function populateSettlementDropdown() {
    const select = document.getElementById("settle_batch_id");
    if (!select) return;
    select.innerHTML = `<option value="">-- ${t('activeBatch')} --</option>`;
    
    const activeList = produceBatches.filter(b => b.status === "active");
    activeList.forEach(b => {
        select.innerHTML += `<option value="${b.id}">${b.crop_name} (${b.variety}) - ${b.quantity_kg} KG in ${b.field_name}</option>`;
    });
}

function openSettlementForBatch(batchId) {
    switchTab('ledger-sold');
    const select = document.getElementById("settle_batch_id");
    if (select) {
        select.value = batchId;
        handleSettleBatchChange();
    }
}

function handleSettleBatchChange() {
    const select = document.getElementById("settle_batch_id");
    if (!select) return;
    const batchId = select.value;
    const batch = produceBatches.find(b => b.id === batchId);
    const qtyInput = document.getElementById("sold_quantity_kg");
    if (batch && qtyInput) {
        qtyInput.value = batch.quantity_kg;
    }
}

function renderHistoryProduce() {
    const container = document.getElementById("history-batches-list");
    if (!container) return;
    container.innerHTML = "";

    const soldList = produceBatches.filter(b => b.status === "sold");
    const histCount = document.getElementById("history-count");
    if (histCount) histCount.innerText = `${soldList.length} ${t('records')}`;

    if (soldList.length === 0) {
        container.innerHTML = `<div style="padding: 20px; color: var(--text-muted); font-size: 14px;">${t('noHistory')}</div>`;
        return;
    }

    soldList.forEach(b => {
        const isProfit = (b.net_profit_loss >= 0);
        const card = document.createElement("div");
        card.className = "history-card";
        
        const nextCropPlans = b.next_crop_recommendation?.length ? b.next_crop_recommendation : [
            { crop: b.crop_name === 'Tomato' ? 'Potato' : 'Tomato', reason: currentLang === 'hi' ? 'फसल चक्र से मिट्टी का संतुलन बनाए रखने और जोखिम कम करने में मदद मिलती है।' : 'Crop rotation can help maintain soil balance and reduce production risk.', roi_potential: 'Medium', water_need: 'Medium' },
            { crop: 'Pulses', reason: currentLang === 'hi' ? 'दलहनी फसल मिट्टी में नाइट्रोजन बढ़ाने और अगली फसल की लागत घटाने में मदद कर सकती है।' : 'A pulse crop can improve soil nitrogen and reduce input costs for the next cycle.', roi_potential: 'Medium', water_need: 'Low' }
        ];
        let rotationHtml = "";
        if (nextCropPlans.length > 0) {
            rotationHtml = `
                <div class="next-crop-container">
                    <div class="next-crop-title">🌱 ${b.next_crop_recommendation?.length ? t('nextCropTitle') : t('nextCropFallbackTitle')}</div>
                    <div class="next-crop-items">
                        ${nextCropPlans.map(rec => `
                            <div class="crop-plan-item">
                                <strong>${rec.crop}</strong> <small style="color:var(--turmeric-dark);">[ROI: ${rec.roi_potential} | Water: ${rec.water_need}]</small>
                                <p style="margin-top:4px; font-size:11.5px; color:var(--text-muted);">${rec.reason}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="history-card-header">
                <div>
                    <h4>${b.crop_name} <small>(${b.variety || 'Desi'})</small></h4>
                    <span style="font-size:12px; color:var(--text-muted);">${b.field_name} | Harvest: ${b.harvest_date} ➔ Sold: ${b.selling_date}</span>
                </div>
                <div>
                    <span style="font-size:16px; font-weight:700; color: ${isProfit ? 'var(--leaf-green)' : 'var(--risk-red)'};">
                        ${isProfit ? 'PROFIT' : 'LOSS'}: ₹ ${Math.abs(b.net_profit_loss).toLocaleString()}
                    </span>
                </div>
            </div>

            <div class="history-financial-grid">
                <div>
                    <span class="detail-lbl">${t('qtyProducedSold')}</span>
                    <span class="detail-val">${b.quantity_kg} / ${b.sold_quantity_kg} KG</span>
                </div>
                <div>
                    <span class="detail-lbl">${t('sellingPrice')}</span>
                    <span class="detail-val">₹ ${b.selling_price_per_kg} / KG</span>
                </div>
                <div>
                    <span class="detail-lbl">${t('totalRevenue')}</span>
                    <span class="detail-val text-green">₹ ${b.total_revenue.toLocaleString()}</span>
                </div>
                <div>
                    <span class="detail-lbl">${t('totalCost')}</span>
                    <span class="detail-val">₹ ${b.total_combined_cost.toLocaleString()}</span>
                </div>
            </div>
            ${rotationHtml}
        `;
        container.appendChild(card);
    });
}

async function handleSaleSettlement(e) {
    if (e && e.preventDefault) e.preventDefault();
    const btn = document.getElementById("btn-settle-sale");
    if (btn) {
        btn.innerText = translations[currentLang].settling;
        btn.disabled = true;
    }

    const sellingCosts = {};
    document.querySelectorAll(".selling-cost-val").forEach(input => {
        const cat = input.getAttribute("data-cat") || "misc";
        sellingCosts[cat] = parseFloat(input.value) || 0;
    });

    const batchIdInput = document.getElementById("settle_batch_id");
    const soldQuantityInput = document.getElementById("sold_quantity_kg");
    const sellingPriceInput = document.getElementById("selling_price_per_kg");
    const sellingDateInput = document.getElementById("selling_date");
    if (!batchIdInput || !soldQuantityInput || !sellingPriceInput || !sellingDateInput) {
        showToast(translations[currentLang].toastError, "error");
        if (btn) {
            btn.innerText = translations[currentLang].settleBtn;
            btn.disabled = false;
        }
        return;
    }

    const payload = {
        batch_id: batchIdInput.value,
        sold_quantity_kg: soldQuantityInput.value,
        selling_price_per_kg: sellingPriceInput.value,
        selling_date: sellingDateInput.value,
        selling_costs: sellingCosts
    };

    try {
        const res = await fetch("/api/produce/settle-sale", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            const idx = produceBatches.findIndex(b => b.id === result.batch.id);
            if (idx !== -1) produceBatches[idx] = result.batch;
            renderAllViews();
            showToast(translations[currentLang].toastSettled, "success");
            switchTab('ledger-history');
        } else {
            showToast(translations[currentLang].toastError, "error");
        }
    } catch (e) {
        showToast(translations[currentLang].toastError, "error");
    } finally {
        if (btn) {
            btn.innerText = translations[currentLang].settleBtn;
            btn.disabled = false;
        }
    }
}

function addCustomSellingCost() {
    const name = prompt(translations[currentLang].customCostPrompt);
    if (name && name.trim()) {
        const container = document.getElementById("selling-costs-container");
        if (!container) return;
        const item = document.createElement("div");
        item.className = "cost-item";
        item.innerHTML = `
            <label>${name.trim()} (₹)</label>
            <input type="number" class="selling-cost-val" data-cat="${name.toLowerCase().replace(/\s+/g, '_')}" placeholder="0" value="0">
        `;
        container.appendChild(item);
    }
}

function handleImageSelected(e) {
    const file = e.target.files && e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(evt) {
            selectedImageBase64 = evt.target.result;
            const preview = document.getElementById("preview-img");
            const wrapper = document.getElementById("image-preview-wrapper");
            if (preview) preview.src = selectedImageBase64;
            if (wrapper) wrapper.classList.remove("hidden");
        };
        reader.readAsDataURL(file);
    }
}

function removeImage() {
    selectedImageBase64 = null;
    const input = document.getElementById("crop_image");
    const wrapper = document.getElementById("image-preview-wrapper");
    const preview = document.getElementById("preview-img");
    if (input) input.value = "";
    if (wrapper) wrapper.classList.add("hidden");
    if (preview) preview.src = "";
}

function triggerFileInput() {
    const input = document.getElementById("crop_image");
    if (input) input.click();
}

function toggleCropRegistrationMode() {
    const mode = document.querySelector('input[name="crop_status"]:checked')?.value || "harvested";
    document.querySelectorAll(".growing-only").forEach(field => field.classList.toggle("hidden", mode !== "growing"));
    const harvestDate = document.getElementById("harvest_date");
    const harvestLabel = document.querySelector('label[for="harvest_date"]');
    if (harvestDate) harvestDate.required = mode === "harvested";
    if (harvestLabel) harvestLabel.textContent = mode === "growing" ? "Expected Harvest Date (optional)" : "Harvest Date";
}

async function handleProduceSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    const btn = document.getElementById("btn-submit-produce");
    const label = document.getElementById("submit-text");
    if (label) label.innerText = translations[currentLang].analyzing;
    if (btn) btn.disabled = true;

    const prodCosts = {};
    document.querySelectorAll(".prod-cost-val").forEach(input => {
        const cat = input.getAttribute("data-cat") || "misc";
        prodCosts[cat] = parseFloat(input.value) || 0;
    });

    const cropNameInput = document.getElementById("crop_name");
    const varietyInput = document.getElementById("crop_variety");
    const fieldNameInput = document.getElementById("field_name");
    const quantityInput = document.getElementById("quantity");
    const weightUnitInput = document.getElementById("weight_unit");
    const harvestDateInput = document.getElementById("harvest_date");
    const plantingDateInput = document.getElementById("planting_date");
    const storageTypeInput = document.getElementById("storage_type");
    if (!cropNameInput || !varietyInput || !fieldNameInput || !quantityInput || !weightUnitInput || !harvestDateInput || !storageTypeInput) {
        showToast(translations[currentLang].toastError, "error");
        if (label) label.innerText = translations[currentLang].analyzeBtn;
        if (btn) btn.disabled = false;
        return;
    }

    const payload = {
        crop_name: cropNameInput.value,
        crop_status: document.querySelector('input[name="crop_status"]:checked')?.value || "harvested",
        variety: varietyInput.value,
        field_name: fieldNameInput.value,
        quantity: quantityInput.value,
        unit: weightUnitInput.value,
        harvest_date: harvestDateInput.value,
        planting_date: plantingDateInput?.value || null,
        storage_type: storageTypeInput.value,
        image_base64: selectedImageBase64,
        production_costs: prodCosts
    };

    try {
        const res = await fetch("/api/produce/analyze-and-add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
            produceBatches.unshift(result.batch);
            renderAllViews();
            document.getElementById("produce-form").reset();
            removeImage();
            showToast(translations[currentLang].toastSaved, "success");
            switchTab('ledger-stored');
        } else {
            showToast(result.error || "Could not save this crop.", "error");
        }
    } catch (e) {
        showToast(`Crop registration failed: ${e.message}`, "error");
    } finally {
        if (label) label.innerText = translations[currentLang].analyzeBtn;
        if (btn) btn.disabled = false;
    }
}

function fillDemoBatch() {
    const activePanel = document.querySelector('.tab-panel.active')?.id;
    const crop = document.getElementById("crop_name");
    const variety = document.getElementById("crop_variety");
    const field = document.getElementById("field_name");
    const qty = document.getElementById("quantity");
    const unit = document.getElementById("weight_unit");
    const storage = document.getElementById("storage_type");

    if (crop) crop.value = "Tomato";
    if (variety) variety.value = "Hybrid Red";
    if (field) field.value = "South Polyhouse Plot 1";
    if (qty) qty.value = "1500";
    if (unit) unit.value = "kg";
    if (storage) storage.value = "Open Air Jute Bags";

    const calcCrop = document.getElementById("calc_crop");
    const calcArea = document.getElementById("calc_area");
    if (calcCrop) calcCrop.value = "Tomato";
    if (calcArea) calcArea.value = "2";
    const calculatorCosts = {
        calc_seed: 8000,
        calc_fert: 6500,
        calc_pest: 3500,
        calc_irrig: 4500,
        calc_labour: 9000,
        calc_mach: 5000,
        calc_fuel: 3500,
        calc_misc: 2000
    };
    Object.entries(calculatorCosts).forEach(([id, value]) => {
        const input = document.getElementById(id);
        if (input) input.value = value;
    });
    handlePreCostCalculation();
    
    if (activePanel !== 'tab-pre-cost') switchTab('add-batch');
    showToast(t('demoLoaded'), 'info');
}

// ============================================================
// CHAT & VOICE ENGINE (REFINED WAIT & DEBOUNCE LOGIC)
// ============================================================

function toggleAssistant() {
    const panel = document.getElementById("assistant-panel");
    if (panel) panel.classList.toggle("open");
}

function handleAssistantKey(e) {
    if (e.key === "Enter") sendAssistantMessage();
}

function handleChatImageUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(evt) {
            const source = new Image();
            source.onload = function() {
                const maxDimension = 1600;
                const scale = Math.min(1, maxDimension / Math.max(source.width, source.height));
                const canvas = document.createElement("canvas");
                canvas.width = Math.max(1, Math.round(source.width * scale));
                canvas.height = Math.max(1, Math.round(source.height * scale));
                canvas.getContext("2d").drawImage(source, 0, 0, canvas.width, canvas.height);
                chatImageBase64 = canvas.toDataURL("image/jpeg", 0.82);

                const thumb = document.getElementById("chat-img-thumb");
                const preview = document.getElementById("chat-media-preview");
                if (thumb) thumb.src = chatImageBase64;
                if (preview) preview.classList.remove("hidden");
            };
            source.onerror = function() {
                showToast("Could not read this image. Please choose another photo.", "error");
            };
            source.src = evt.target.result;
        };
        reader.readAsDataURL(file);
    }
}

function removeChatMedia() {
    chatImageBase64 = null;
    const fileInput = document.getElementById("chat-file-input");
    const preview = document.getElementById("chat-media-preview");
    if (fileInput) fileInput.value = "";
    if (preview) preview.classList.add("hidden");
}

let globalRecognizer = null;

function stopRecording() {
    if (globalRecognizer && isRecognizing) {
        try {
            globalRecognizer.stop();
        } catch (e) {}
        isRecognizing = false;
    }
}

function recordAudioMessage() {
    if (isRecognizing) return;
    
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
        return; 
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast(translations[currentLang].voiceNotSupported, "error");
        return;
    }

    try {
        globalRecognizer = new SpeechRecognition();
        globalRecognizer.lang = (currentLang === 'hi') ? 'hi-IN' : 'en-IN';
        globalRecognizer.interimResults = false;
        
        // If Live Voice is ON, keep mic continuous to build the sentence naturally
        globalRecognizer.continuous = isLiveVoiceActive; 

        const input = document.getElementById("assistant-query");
        const micBtn = document.getElementById("btn-mic-input");

        globalRecognizer.onstart = function() {
            isRecognizing = true;
            if (micBtn) micBtn.style.backgroundColor = "#FCD7D7";
            if (input) input.placeholder = translations[currentLang].voiceListening;
        };

        globalRecognizer.onresult = function(event) {
            // Rebuild the final transcript cleanly from all segments
            let finalTranscript = '';
            for (let i = 0; i < event.results.length; i++) {
                finalTranscript += event.results[i][0].transcript + " ";
            }
            
            if (input) {
                input.value = finalTranscript.trim();
            }
            
            // Only auto-send if Live Voice is ON
            if (isLiveVoiceActive) {
                clearTimeout(voiceDebounceTimer);
                voiceDebounceTimer = setTimeout(() => {
                    sendAssistantMessage();
                }, 1500); // 1.5 seconds of pure silence triggers the send
            }
            // If Live Voice is OFF, the user must click the 'Send' button manually
        };

        globalRecognizer.onerror = function(event) {
            console.error("Speech Recognition Error:", event.error);
            if (event.error === 'not-allowed') {
                showToast(translations[currentLang].micBlocked, "error");
            }
        };

        globalRecognizer.onend = function() {
            isRecognizing = false;
            if (micBtn) micBtn.style.backgroundColor = "";
            if (input) input.placeholder = (currentLang === 'hi') ? "यहाँ लिखें या प्रश्न पूछें..." : "Type or ask a farming question...";
        };

        globalRecognizer.start();
    } catch (err) {
        console.error("Recognizer start exception:", err);
        isRecognizing = false;
    }
}

async function toggleLiveVoiceConversation() {
    isLiveVoiceActive = !isLiveVoiceActive;
    const btn = document.getElementById("btn-live-voice");
    const statusText = document.getElementById("voice-chat-status");
    if (btn) btn.classList.toggle("active", isLiveVoiceActive);

    if (isLiveVoiceActive) {
        if (statusText) statusText.innerText = translations[currentLang].voiceActive;
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        try {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                permissionStream.getTracks().forEach(track => track.stop());
            }
            recordAudioMessage();
        } catch (error) {
            console.error("Microphone permission error:", error);
            isLiveVoiceActive = false;
            if (btn) btn.classList.remove("active");
            if (statusText) statusText.innerText = translations[currentLang].voiceChatStatus;
            if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
                showToast(translations[currentLang].micBlocked, "error");
            } else {
                showToast(translations[currentLang].voiceError, "error");
            }
        }
    } else {
        if (statusText) statusText.innerText = translations[currentLang].voiceChatStatus;
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        stopRecording();
        clearTimeout(voiceDebounceTimer);
    }
}

function speakAssistantResponse(text) {
    if (!('speechSynthesis' in window)) return;
    
    stopRecording(); 
    window.speechSynthesis.cancel();

    const cleanText = text.replace(/[*_#`]/g, '').trim();
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = (currentLang === 'hi') ? 'hi-IN' : 'en-IN';
    utterance.rate = 1.0;

    utterance.onend = function() {
        if (isLiveVoiceActive) {
            setTimeout(() => recordAudioMessage(), 800); 
        }
    };

    window.speechSynthesis.speak(utterance);
}

async function sendAssistantMessage() {
    clearTimeout(voiceDebounceTimer);
    stopRecording(); 

    const input = document.getElementById("assistant-query");
    if (!input) return;
    const text = input.value.trim();
    if (!text && !chatImageBase64) return;

    const chatBody = document.getElementById("chat-messages");
    if (!chatBody) return;

    const userBubble = document.createElement("div");
    userBubble.className = "user-msg";
    if (text) {
        userBubble.innerText = text;
    } else {
        const attachmentLabel = document.createElement("em");
        attachmentLabel.innerText = "[Photo Attached for AI Diagnosis]";
        userBubble.appendChild(attachmentLabel);
    }
    chatBody.appendChild(userBubble);
    
    // Clear the input box instantly so it doesn't double-send
    input.value = "";
    chatBody.scrollTop = chatBody.scrollHeight;

    const botBubble = document.createElement("div");
    botBubble.className = "bot-msg";
    botBubble.innerText = (currentLang === 'hi') ? "कृषि डेटा का विश्लेषण हो रहा है..." : "Analyzing crop data & financial benchmarks...";
    chatBody.appendChild(botBubble);
    chatBody.scrollTop = chatBody.scrollHeight;

    const payload = {
        message: text,
        image_base64: chatImageBase64,
        lang: currentLang
    };
    removeChatMedia();

    try {
        const res = await fetch("/api/assistant/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok || data.error) {
            throw new Error(data.error || `Chat request failed (${res.status})`);
        }
        botBubble.innerText = data.reply || "The assistant returned no response. Please try again.";
        
        if (data.updated_batches) {
            produceBatches = data.updated_batches;
            renderAllViews();
        }

        if (isLiveVoiceActive) {
            speakAssistantResponse(data.reply);
        }
    } catch (e) {
        botBubble.innerText = `AI error: ${e.message}`;
        if (isLiveVoiceActive) {
            setTimeout(() => recordAudioMessage(), 1000); 
        }
    }
    chatBody.scrollTop = chatBody.scrollHeight;
}

async function fetchWeather(latitude, longitude) {
    const status = document.getElementById("weather-status");
    const metrics = document.getElementById("weather-metrics");
    const forecast = document.getElementById("weather-forecast");
    if (!status || !metrics || !forecast) return;

    status.textContent = "Loading weather for your GPS location...";
    try {
        const response = await fetch(`/api/weather?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Weather request failed");

        const current = data.current;
        status.textContent = `${data.location.latitude.toFixed(4)}, ${data.location.longitude.toFixed(4)} · ${data.location.timezone} · ${current.condition}`;
        const alerts = document.getElementById("weather-alerts");
        if (alerts) {
            alerts.innerHTML = (data.alerts || []).map(alert => `<div class="weather-alert ${alert.level}">⚠️ ${alert.message}</div>`).join("") || `<div class="weather-alert clear">✓ ${t('noWeatherWarnings')}</div>`;
        }
        metrics.innerHTML = [
            ["Temperature", `${current.temperature_c ?? "-"} °C`, "🌡️"],
            ["Humidity", `${current.relative_humidity_percent ?? "-"} %`, "💧"],
            ["Wind speed", `${current.wind_speed_kmh ?? "-"} km/h`, "💨"],
            ["Rain now", `${current.rainfall_mm ?? "-"} mm`, "🌧️"],
            ["Weather condition", current.condition, "☀️"],
            ["Rain probability today", `${data.forecast[0]?.rain_probability_percent ?? "-"} %`, "🌧️"]
        ].map(([label, value, icon]) => `<div class="weather-metric"><span class="weather-metric-icon">${icon}</span><span class="weather-metric-label">${label}</span><strong>${value}</strong></div>`).join("");
        forecast.innerHTML = data.forecast.map(day => `<tr><td>${day.date}</td><td>${day.condition}</td><td>${day.temperature_min_c ?? "-"} / ${day.temperature_max_c ?? "-"} °C</td><td>${day.precipitation_mm ?? "-"} mm</td><td>${day.rain_probability_percent ?? "-"} %</td><td>${day.sunrise?.slice(11, 16) ?? "-"}</td><td>${day.sunset?.slice(11, 16) ?? "-"}</td></tr>`).join("");
        weatherCache = { latitude, longitude, data, storedAt: Date.now() };
    } catch (error) {
        status.textContent = `Weather unavailable: ${error.message}`;
        metrics.innerHTML = "";
        forecast.innerHTML = `<tr><td colspan="7">${t('weatherUnavailable')}</td></tr>`;
    }
}

async function generateWeatherAction() {
    const result = document.getElementById("weather-action-result");
    const button = document.getElementById("weather-action-button");
    if (!result || !button) return;
    if (!weatherCache?.data) {
        result.textContent = "Load your GPS weather first, then analyze.";
        return;
    }
    const crop = document.getElementById("calc_crop")?.value || "the crop";
    button.disabled = true;
    result.textContent = "Gemini is analyzing today and tomorrow...";
    try {
        const response = await fetch("/api/weather/action-suggestion", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                latitude: weatherCache.latitude,
                longitude: weatherCache.longitude,
                current: weatherCache.data.current,
                forecast: weatherCache.data.forecast.slice(0, 2),
                crop
            })
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Could not generate action.");
        result.textContent = data.suggestion;
    } catch (error) {
        result.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

function haversineKm(lat1, lon1, lat2, lon2) {
    const earthRadiusKm = 6371;
    const deltaLat = (lat2 - lat1) * Math.PI / 180;
    const deltaLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(deltaLon / 2) ** 2;
    return earthRadiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function openStorageFinder(batchId) {
    const modal = document.getElementById('storage-finder-modal');
    const statusEl = document.getElementById('storage-finder-status');
    const resultsEl = document.getElementById('storage-finder-results');
    if (!modal) return;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    if (statusEl) statusEl.innerText = batchId ? 'Preparing storage search...' : '';
    if (resultsEl) resultsEl.innerHTML = '';
    findNearestStorage();
}

function closeStorageFinder() {
    const modal = document.getElementById('storage-finder-modal');
    if (storageFinderMap) {
        storageFinderMap.remove();
        storageFinderMap = null;
        storageFinderLayer = null;
    }
    if (modal) modal.classList.add('hidden');
    document.body.style.overflow = '';
}

function renderStorageResults(facilities, userLat, userLng, radiusKm = 100) {
    const resultsEl = document.getElementById('storage-finder-results');
    const mapEl = document.getElementById('storage-finder-map');

    if (storageFinderMap) storageFinderMap.remove();
    storageFinderMap = L.map(mapEl).setView([userLat, userLng], 11);
    storageFinderLayer = L.layerGroup().addTo(storageFinderMap);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(storageFinderMap);

    const farmIcon = L.divIcon({ className: 'farm-location-marker', html: '<span></span>', iconSize: [18, 18], iconAnchor: [9, 9] });
    L.marker([userLat, userLng], { icon: farmIcon }).addTo(storageFinderLayer).bindPopup('<strong>Your Farm</strong>');
    const withDistance = facilities.map(facility => ({
        facility,
        distanceKm: Number(facility.distance_km || facility.distance_meters / 1000 || 0)
    })).sort((a, b) => a.distanceKm - b.distanceKm);

    if (withDistance.length === 0) return false;
    document.getElementById('storage-finder-status').innerText = `Found ${withDistance.length} storage facilities within ${radiusKm} km, sorted by distance:`;
    resultsEl.innerHTML = withDistance.map(({ facility, distanceKm }) => {
        const lat = Number(facility.latitude);
        const lng = Number(facility.longitude);
        const directionsUrl = `https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${userLat}%2C${userLng}%3B${lat}%2C${lng}`;
        L.marker([lat, lng]).addTo(storageFinderLayer).bindPopup(`
            <strong>${facility.name}</strong><br>
            Type: ${facility.category}<br>
            Address: ${facility.address}<br>
            Distance: ${distanceKm.toFixed(1)} km
        `);
        return `
            <div class="batch-card">
                <div><span class="crop-title">${facility.name}</span><small style="display:block; color: var(--text-muted);">${facility.address || 'Location details not listed'}</small></div>
                <div><span class="detail-lbl">${facility.category || 'Storage facility'}</span><span class="detail-val">${distanceKm.toFixed(1)} km</span></div>
                <div><a class="btn-secondary" style="display:inline-block; text-decoration:none; text-align:center;" href="${directionsUrl}" target="_blank" rel="noopener">Get Directions</a></div>
            </div>`;
    }).join('');
    return true;
}

async function findNearestStorage() {
    const statusEl = document.getElementById('storage-finder-status');
    const resultsEl = document.getElementById('storage-finder-results');
    const btn = document.getElementById('storage-finder-locate-btn');

    btn.disabled = true;
    statusEl.innerText = 'Getting your farm location...';
    resultsEl.innerHTML = '';

    (async () => {
        if (!window.L) {
            statusEl.innerText = 'The map service is still loading. Please try again.';
            btn.disabled = false;
            return;
        }
        try {
            let userLat = Number(farmerProfile?.latitude);
            let userLng = Number(farmerProfile?.longitude);
            if (!Number.isFinite(userLat) || !Number.isFinite(userLng)) {
                if (!navigator.geolocation) throw new Error('Location is not supported by this browser.');
                statusEl.innerText = 'Detecting your location automatically...';
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 300000
                    });
                });
                userLat = position.coords.latitude;
                userLng = position.coords.longitude;
                farmerProfile = { ...(farmerProfile || {}), latitude: userLat, longitude: userLng };
            }

            statusEl.innerText = 'Finding the nearest storage facility...';
            const response = await fetch(`/api/storage/search?latitude=${encodeURIComponent(userLat)}&longitude=${encodeURIComponent(userLng)}`);
            const contentType = response.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) throw new Error(`Storage search server error (${response.status}).`);
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'OpenStreetMap search failed.');
            if (!renderStorageResults(data.facilities || [], userLat, userLng, data.radius_km)) {
                statusEl.innerText = data.message || `No storage facility found nearby within ${data.radius_km || 50} km.`;
            }
        } catch (error) {
            statusEl.innerText = error.code === 1
                ? 'Location permission was denied. Allow location access or save coordinates in Profile.'
                : (error.message || 'Could not determine your farm location.');
            resultsEl.innerHTML = '<div class="empty-admin">OpenStreetMap search failed. Please try again.</div>';
        } finally {
            btn.disabled = false;
        }
    })();
}