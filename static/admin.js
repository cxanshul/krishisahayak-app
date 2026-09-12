let adminData = null;
let adminLang = localStorage.getItem('hackbhoomi-language') || 'en';

const adminTranslations = {
    en: {
        updated: 'Updated', unknownDate: 'Unknown date', noRecords: 'No records yet.',
        noQualityFlags: 'No quality flags yet.', noFarmers: 'No farmers match this search.',
        noActivity: 'No crop activity yet.', profiles: 'profiles with farm records',
        active: 'active', sold: 'sold', kg: 'kg', systemReady: 'System healthy · snapshot loaded',
        systemPending: 'System check pending', highRisk: 'High-risk activity',
        csvFarmer: 'Farmer', csvLocation: 'Location', csvBatches: 'Batches', csvActiveKg: 'Active kg',
        csvRevenue: 'Revenue', csvProfit: 'Profit',
        statusActive: 'active', statusSold: 'sold', riskHigh: 'High', riskMedium: 'Medium', riskLow: 'Low', riskNa: 'Not applicable'
    },
    hi: {
        updated: 'अपडेट', unknownDate: 'अज्ञात तारीख', noRecords: 'अभी कोई रिकॉर्ड नहीं है।',
        noQualityFlags: 'अभी कोई गुणवत्ता संकेत नहीं है।', noFarmers: 'इस खोज से कोई किसान नहीं मिला।',
        noActivity: 'अभी कोई फसल गतिविधि नहीं है।', profiles: 'खेत रिकॉर्ड वाले प्रोफाइल',
        active: 'सक्रिय', sold: 'बिके हुए', kg: 'किलो', systemReady: 'सिस्टम ठीक है · स्नैपशॉट लोड हुआ',
        systemPending: 'सिस्टम जांच लंबित', highRisk: 'उच्च जोखिम गतिविधि',
        csvFarmer: 'किसान', csvLocation: 'स्थान', csvBatches: 'बैच', csvActiveKg: 'सक्रिय किलो',
        csvRevenue: 'आय', csvProfit: 'लाभ',
        statusActive: 'सक्रिय', statusSold: 'बिका', riskHigh: 'उच्च', riskMedium: 'मध्यम', riskLow: 'कम', riskNa: 'लागू नहीं'
    }
};

function at(key) {
    return adminTranslations[adminLang][key] || adminTranslations.en[key] || key;
}

function setAdminLanguage(lang) {
    adminLang = lang;
    localStorage.setItem('hackbhoomi-language', lang);
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-en]').forEach(element => {
        const value = element.getAttribute(`data-${lang}`);
        if (value) element.textContent = value;
    });
    document.querySelectorAll('[data-placeholder-en]').forEach(element => {
        element.placeholder = element.getAttribute(`data-placeholder-${lang}`) || element.placeholder;
    });
    document.getElementById('admin-btn-en')?.classList.toggle('active', lang === 'en');
    document.getElementById('admin-btn-hi')?.classList.toggle('active', lang === 'hi');
    if (adminData) renderAdminDashboard(adminData);
}

const money = value => `₹ ${Math.round(Number(value) || 0).toLocaleString('en-IN')}`;
const number = value => Math.round(Number(value) || 0).toLocaleString('en-IN');
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));

async function loadAdminOverview() {
    const errorBox = document.getElementById('admin-error');
    errorBox.classList.add('hidden');
    try {
        const response = await fetch('/api/admin/overview');
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Admin data could not be loaded.');
        adminData = data;
        renderAdminDashboard(data);
    } catch (error) {
        errorBox.textContent = error.message;
        errorBox.classList.remove('hidden');
    }
}

function renderAdminDashboard(data) {
    const summary = data.summary;
    document.getElementById('admin-refreshed-at').textContent = `${at('updated')} ${formatDate(data.refreshed_at)}`;
    document.getElementById('kpi-farmers').textContent = number(summary.farmer_count);
    document.getElementById('kpi-profiles').textContent = `${number(summary.profile_count)} ${at('profiles')}`;
    document.getElementById('kpi-batches').textContent = number(summary.batch_count);
    document.getElementById('kpi-active').textContent = number(summary.active_batches);
    document.getElementById('kpi-sold').textContent = number(summary.sold_batches);
    document.getElementById('kpi-quantity').textContent = `${number(summary.total_quantity_kg)} ${at('kg')}`;
    document.getElementById('kpi-risk').textContent = number(summary.high_risk_batches);
    document.getElementById('kpi-revenue').textContent = money(summary.revenue);
    document.getElementById('kpi-profit').textContent = money(summary.profit);
    document.getElementById('kpi-cost').textContent = money(summary.production_cost);
    document.getElementById('kpi-margin').textContent = summary.revenue ? `${((summary.profit / summary.revenue) * 100).toFixed(1)}%` : '—';
    renderBars('crop-mix-chart', data.crop_mix, 'crop');
    renderBars('state-mix-chart', data.state_mix, 'state');
    renderRisks(data.risk_mix);
    renderFarmers(data.farmers);
    renderActivity(document.getElementById('risk-only')?.checked ? data.recent_batches.filter(batch => batch.spoilage_risk === 'High') : data.recent_batches);
    document.getElementById('admin-health').textContent = summary.high_risk_batches ? `${at('systemReady')} · ${number(summary.high_risk_batches)} ${at('highRisk')}` : at('systemReady');
}

function renderBars(targetId, entries, type) {
    const target = document.getElementById(targetId);
    if (!entries.length) {
        target.innerHTML = `<p class="empty-admin">${at('noRecords')}</p>`;
        return;
    }
    const max = Math.max(...entries.map(entry => entry.value), 1);
    target.innerHTML = entries.slice(0, 7).map(entry => `<div class="bar-row"><div class="bar-label"><span>${escapeHtml(entry.label)}</span><b>${number(entry.value)}</b></div><div class="bar-track"><i class="bar-fill ${type}" style="width:${Math.max(8, (entry.value / max) * 100)}%"></i></div></div>`).join('');
}

function renderRisks(entries) {
    const target = document.getElementById('risk-mix-chart');
    const colors = { High: 'risk-high', Medium: 'risk-medium', Low: 'risk-low', 'Not applicable': 'risk-na' };
    target.innerHTML = entries.length ? entries.map(entry => `<div class="risk-row"><span class="risk-key"><i class="risk-dot ${colors[entry.label] || 'risk-low'}"></i>${escapeHtml(translateRisk(entry.label))}</span><strong>${number(entry.value)}</strong></div>`).join('') : `<p class="empty-admin">${at('noQualityFlags')}</p>`;
}

function renderFarmers(farmers) {
    const target = document.getElementById('farmers-table');
    const filter = document.getElementById('farmer-filter').value.toLowerCase().trim();
    const visible = farmers.filter(farmer => `${farmer.full_name} ${farmer.location}`.toLowerCase().includes(filter));
    target.innerHTML = visible.length ? visible.map(farmer => `<tr><td><strong>${escapeHtml(farmer.full_name)}</strong><small>${escapeHtml(farmer.farmer_id || '')}</small></td><td>${escapeHtml(farmer.location)}</td><td>${number(farmer.crop_count)}</td><td>${number(farmer.active_quantity_kg)}</td><td>${money(farmer.revenue)}</td><td class="${farmer.profit < 0 ? 'negative' : 'positive'}">${money(farmer.profit)}</td></tr>`).join('') : `<tr><td colspan="6" class="empty-admin">${at('noFarmers')}</td></tr>`;
}

function filterFarmers() {
    if (adminData) renderFarmers(adminData.farmers);
}

function renderActivity(batches) {
    const target = document.getElementById('recent-activity');
    target.innerHTML = batches.length ? batches.map(batch => `<div class="activity-item"><div class="activity-mark ${batch.spoilage_risk === 'High' ? 'high' : ''}"></div><div><strong>${escapeHtml(batch.crop_name)}</strong><span>${escapeHtml(batch.farmer_name)} · ${number(batch.quantity_kg)} ${at('kg')}</span><small>${escapeHtml(translateStatus(batch.status))} · ${formatDate(batch.created_at)}</small></div><em>${escapeHtml(translateRisk(batch.spoilage_risk))}</em></div>`).join('') : `<p class="empty-admin">${at('noActivity')}</p>`;
}

function translateRisk(value) {
    return { High: at('riskHigh'), Medium: at('riskMedium'), Low: at('riskLow'), 'Not applicable': at('riskNa') }[value] || value;
}

function translateStatus(value) {
    return { active: at('statusActive'), sold: at('statusSold') }[value] || value;
}

function formatDate(value) {
    if (!value) return at('unknownDate');
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString(adminLang === 'hi' ? 'hi-IN' : 'en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function exportAdminCsv() {
    if (!adminData?.farmers?.length) return;
    const headers = [at('csvFarmer'), at('csvLocation'), at('csvBatches'), at('csvActiveKg'), at('csvRevenue'), at('csvProfit')];
    const rows = adminData.farmers.map(farmer => [farmer.full_name, farmer.location, farmer.crop_count, farmer.active_quantity_kg, farmer.revenue, farmer.profit]);
    const csv = [headers, ...rows].map(row => row.map(value => `"${String(value ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    link.download = `hackbhoomi-farmer-report-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
}

async function logoutAdmin() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/auth';
}

document.addEventListener('DOMContentLoaded', () => {
    setAdminLanguage(adminLang);
    loadAdminOverview();
});
