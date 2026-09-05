let currentLang = 'en';
let produceBatches = [];
let mandiRecordsCache = [];
let selectedImageBase64 = null;
let chatImageBase64 = null;
let isLiveVoiceActive = false;
let isRecognizing = false;
let voiceDebounceTimer = null; // New timer to wait before sending

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
        voiceError: "Voice input failed. Please try again or type your message."
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
        voiceError: "आवाज पहचान में त्रुटि हुई। कृपया पुनः प्रयास करें।"
    }
};

document.addEventListener("DOMContentLoaded", () => {
    try {
        const today = new Date().toISOString().split('T')[0];
        const h = document.getElementById("harvest_date");
        const s = document.getElementById("selling_date");
        if (h) h.value = today;
        if (s) s.value = today;
    } catch (e) {}

    loadBatches();
    loadProfile().finally(() => fetchWeather());
    fetchMandiRates();
    handlePreCostCalculation();
});

async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/auth";
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

    renderAllViews();
    handlePreCostCalculation();
}

function toggleChatLanguage() {
    const nextLang = (currentLang === 'en') ? 'hi' : 'en';
    setLanguage(nextLang);
    showToast(nextLang === 'hi' ? 'चैट भाषा हिंदी में बदली गई।' : 'Chat language switched to English.', 'info');
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
            if (data.source === "live_datagov") {
                alertBox.className = "mandi-alert live";
                alertBox.innerText = "🟢 Displaying live Data.gov.in APMC mandi records.";
            } else {
                alertBox.className = "mandi-alert fallback";
                alertBox.innerText = "🟡 Data.gov.in is unavailable right now. Displaying fallback benchmark rates, not live prices.";
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
    if (storedCount) storedCount.innerText = `${activeList.length} ${currentLang === 'hi' ? 'बैच' : 'Batches'}`;

    if (activeList.length === 0) {
        container.innerHTML = `<div style="padding: 20px; color: var(--text-muted); font-size: 14px;">${currentLang === 'hi' ? 'कोई सक्रिय भंडारित फसल नहीं है।' : 'No active stored produce batches.'}</div>`;
        return;
    }

    activeList.forEach(b => {
        const riskClass = b.spoilage_risk === "High" ? "risk-high" : (b.spoilage_risk === "Medium" ? "risk-medium" : "risk-low");
        const card = document.createElement("div");
        card.className = `batch-card ${riskClass}`;
        card.innerHTML = `
            <div>
                <span class="crop-title">${b.crop_name}</span>
                <small style="display: block; color: var(--text-muted);">${b.variety || ''} | ${b.field_name || ''}</small>
                <span class="detail-lbl" style="margin-top: 4px;">${b.storage_type}</span>
            </div>
            <div>
                <span class="detail-lbl">${currentLang === 'hi' ? 'भंडारित मात्रा' : 'Stored Volume'}</span>
                <span class="detail-val">${parseFloat(b.quantity_kg).toLocaleString()} KG</span>
                <small style="color: var(--text-muted);">Grade: <strong>${b.quality_grade || 'A'}</strong></small>
            </div>
            <div>
                <span class="detail-lbl">${currentLang === 'hi' ? 'सड़न जोखिम' : 'Spoilage Risk'}</span>
                <span class="detail-val text-${b.spoilage_risk === 'High' ? 'risk' : 'green'}">
                    ${b.spoilage_risk} (${b.shelf_life_days} ${currentLang === 'hi' ? 'दिन शेष' : 'Days'})
                </span>
                <small style="display:block; font-size:11px; color:var(--text-muted);">${b.defect_summary || ''}</small>
            </div>
            <div class="batch-advisory">
                <strong>💡 ${currentLang === 'hi' ? 'भंडारण निर्देश' : 'Storage'}:</strong> ${b.recommendation}<br>
                <strong>⚙️ ${currentLang === 'hi' ? 'प्रसंस्करण' : 'Processing'}:</strong> ${b.processing_idea}
            </div>
            <div>
                <button type="button" class="btn-secondary" onclick="openSettlementForBatch('${b.id}')">
                    ${currentLang === 'hi' ? 'बिक्री दर्ज करें ➔' : 'Settle Sale ➔'}
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

function populateSettlementDropdown() {
    const select = document.getElementById("settle_batch_id");
    if (!select) return;
    select.innerHTML = `<option value="">-- ${currentLang === 'hi' ? 'सक्रिय बैच चुनें' : 'Select Active Batch'} --</option>`;
    
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
    if (histCount) histCount.innerText = `${soldList.length} ${currentLang === 'hi' ? 'रिकॉर्ड' : 'Records'}`;

    if (soldList.length === 0) {
        container.innerHTML = `<div style="padding: 20px; color: var(--text-muted); font-size: 14px;">${currentLang === 'hi' ? 'कोई पुराना बिक्री रिकॉर्ड उपलब्ध नहीं है।' : 'No completed sales history recorded yet.'}</div>`;
        return;
    }

    soldList.forEach(b => {
        const isProfit = (b.net_profit_loss >= 0);
        const card = document.createElement("div");
        card.className = "history-card";
        
        let rotationHtml = "";
        if (b.next_crop_recommendation && b.next_crop_recommendation.length > 0) {
            rotationHtml = `
                <div class="next-crop-container">
                    <div class="next-crop-title">🌱 ${currentLang === 'hi' ? 'एआई अगली फसल सुझाव (भूमि एवं मौसम अनुसार):' : 'AI Next Crop Recommendations for this Field:'}</div>
                    <div class="next-crop-items">
                        ${b.next_crop_recommendation.map(rec => `
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
                    <span class="detail-lbl">${currentLang === 'hi' ? 'उत्पादित / बेची मात्रा' : 'Qty Produced / Sold'}</span>
                    <span class="detail-val">${b.quantity_kg} / ${b.sold_quantity_kg} KG</span>
                </div>
                <div>
                    <span class="detail-lbl">${currentLang === 'hi' ? 'विक्रय मूल्य' : 'Selling Price'}</span>
                    <span class="detail-val">₹ ${b.selling_price_per_kg} / KG</span>
                </div>
                <div>
                    <span class="detail-lbl">${currentLang === 'hi' ? 'कुल आय (Revenue)' : 'Total Revenue'}</span>
                    <span class="detail-val text-green">₹ ${b.total_revenue.toLocaleString()}</span>
                </div>
                <div>
                    <span class="detail-lbl">${currentLang === 'hi' ? 'कुल लागत (Combined)' : 'Total Cost'}</span>
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
    const storageTypeInput = document.getElementById("storage_type");
    if (!cropNameInput || !varietyInput || !fieldNameInput || !quantityInput || !weightUnitInput || !harvestDateInput || !storageTypeInput) {
        showToast(translations[currentLang].toastError, "error");
        if (label) label.innerText = translations[currentLang].analyzeBtn;
        if (btn) btn.disabled = false;
        return;
    }

    const payload = {
        crop_name: cropNameInput.value,
        variety: varietyInput.value,
        field_name: fieldNameInput.value,
        quantity: quantityInput.value,
        unit: weightUnitInput.value,
        harvest_date: harvestDateInput.value,
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
    
    switchTab('add-batch');
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

async function fetchWeather() {
    const status = document.getElementById("weather-status");
    const metrics = document.getElementById("weather-metrics");
    const forecast = document.getElementById("weather-forecast");
    if (!status || !metrics || !forecast) return;

    const latitude = document.getElementById("weather-latitude")?.value || "28.6139";
    const longitude = document.getElementById("weather-longitude")?.value || "77.2090";
    status.textContent = "Loading weather and soil indicators...";
    try {
        const response = await fetch(`/api/weather?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Weather request failed");

        const current = data.current;
        const agronomy = data.agronomy;
        const place = [data.location.district, data.location.state].filter(Boolean).join(", ");
        status.textContent = `${place || `${data.location.latitude.toFixed(4)}, ${data.location.longitude.toFixed(4)}`} · ${data.observed_at || "Latest observation"} IST · ${current.condition}`;
        const alerts = document.getElementById("weather-alerts");
        if (alerts) {
            alerts.innerHTML = (data.alerts || []).map(alert => `<div class="weather-alert ${alert.level}">⚠️ ${alert.message}</div>`).join("") || `<div class="weather-alert clear">✓ No rule-based weather warnings right now.</div>`;
        }
        metrics.innerHTML = [
            ["Temperature", `${current.temperature_c ?? "-"} °C`, "🌡️"],
            ["Humidity", `${current.relative_humidity_percent ?? "-"} %`, "💧"],
            ["Wind speed", `${current.wind_speed_kmh ?? "-"} km/h`, "💨"],
            ["Rain now", `${current.rainfall_mm ?? "-"} mm`, "🌧️"],
            ["Solar radiation", `${current.shortwave_radiation_w_m2 ?? "-"} W/m²`, "☀️"],
            ["Direct normal irradiance", `${current.direct_normal_irradiance_w_m2 ?? "-"} W/m²`, "🔆"],
            ["ET0 today", `${agronomy.et0_mm ?? "-"} mm`, "☀️"],
            ["Soil at 6 cm", `${agronomy.soil_temperature_6cm_c ?? "-"} °C`, "🌱"],
            ["Root-zone moisture", `${agronomy.soil_moisture_3_to_9cm_m3_m3 ?? "-"} m³/m³`, "🪴"]
        ].map(([label, value, icon]) => `<div class="weather-metric"><span class="weather-metric-icon">${icon}</span><span class="weather-metric-label">${label}</span><strong>${value}</strong></div>`).join("");
        forecast.innerHTML = data.forecast.map(day => `<tr><td>${day.date}</td><td>${day.condition}</td><td>${day.rainfall_mm ?? "-"} mm</td><td>${day.et0_mm ?? "-"} mm</td></tr>`).join("");
        fetchSeasonalWeather();
    } catch (error) {
        status.textContent = error.message;
        metrics.innerHTML = "";
        forecast.innerHTML = "<tr><td colspan=\"4\">Weather data could not be loaded. Please try again.</td></tr>";
    }
}

function useFarmLocation() {
    if (!navigator.geolocation) {
        showToast("Location is not supported by this browser.", "error");
        return;
    }
    navigator.geolocation.getCurrentPosition(position => {
        document.getElementById("weather-latitude").value = position.coords.latitude.toFixed(6);
        document.getElementById("weather-longitude").value = position.coords.longitude.toFixed(6);
        fetchWeather();
    }, () => showToast("Could not read your location. Enter coordinates manually.", "error"));
}

async function fetchSeasonalWeather() {
    const status = document.getElementById("seasonal-status");
    const table = document.getElementById("seasonal-forecast");
    if (!status || !table) return;
    const latitude = document.getElementById("weather-latitude")?.value || "28.6139";
    const longitude = document.getElementById("weather-longitude")?.value || "77.2090";
    status.textContent = "Loading seasonal ensemble trends...";
    try {
        const response = await fetch(`/api/weather/seasonal?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`);
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || "Seasonal request failed");
        status.textContent = `${data.source} · monthly precipitation guidance, not an official IMD warning.`;
        table.innerHTML = data.monthly.map(month => `<tr><td>${month.month}</td><td>${month.precipitation_mm ?? "-"} mm</td><td>${month.temperature_c ?? "-"} °C</td></tr>`).join("");
    } catch (error) {
        status.textContent = error.message;
        table.innerHTML = "<tr><td colspan=\"3\">Seasonal data could not be loaded.</td></tr>";
    }
}

async function loadProfile() {
    try {
        const response = await fetch("/api/profile");
        if (!response.ok) return;
        const data = await response.json();
        const profile = data.profile || {};
        document.getElementById("display-farmer").textContent = profile.full_name || "Farmer profile";
        if (profile.latitude && profile.longitude) {
            document.getElementById("weather-latitude").value = profile.latitude;
            document.getElementById("weather-longitude").value = profile.longitude;
        }
    } catch (error) { console.warn("Profile unavailable", error); }
}

async function openProfile() {
    const response = await fetch("/api/profile");
    const data = await response.json();
    const profile = data.profile || {};
    document.getElementById("profile-name").value = profile.full_name || "";
    document.getElementById("profile-latitude").value = profile.latitude || "";
    document.getElementById("profile-longitude").value = profile.longitude || "";
    document.getElementById("profile-location-name").value = profile.location_name || "";
    document.getElementById("profile-modal").classList.remove("hidden");
}

function closeProfile() { document.getElementById("profile-modal").classList.add("hidden"); }

function useProfileLocation() {
    navigator.geolocation?.getCurrentPosition(position => {
        document.getElementById("profile-latitude").value = position.coords.latitude.toFixed(6);
        document.getElementById("profile-longitude").value = position.coords.longitude.toFixed(6);
    });
}

async function saveProfile(event) {
    event.preventDefault();
    const payload = { full_name: document.getElementById("profile-name").value, latitude: document.getElementById("profile-latitude").value, longitude: document.getElementById("profile-longitude").value, location_name: document.getElementById("profile-location-name").value };
    const response = await fetch("/api/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok || !data.success) { showToast(data.error || "Profile could not be saved.", "error"); return; }
    closeProfile();
    document.getElementById("display-farmer").textContent = payload.full_name;
    document.getElementById("weather-latitude").value = payload.latitude;
    document.getElementById("weather-longitude").value = payload.longitude;
    fetchWeather();
    showToast("Profile and farm location updated.", "success");
}

async function deleteMyAccountData() {
    if (!window.confirm("Delete only your crop records and profile data? This cannot be undone.")) return;
    const response = await fetch("/api/profile", { method: "DELETE" });
    const data = await response.json();
    if (!response.ok || !data.success) { showToast(data.error || "Deletion failed.", "error"); return; }
    window.location.href = "/auth";
}