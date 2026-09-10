let adminData = null;

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
    document.getElementById('admin-refreshed-at').textContent = `Updated ${formatDate(data.refreshed_at)}`;
    document.getElementById('kpi-farmers').textContent = number(summary.farmer_count);
    document.getElementById('kpi-profiles').textContent = `${number(summary.profile_count)} profiles with farm records`;
    document.getElementById('kpi-batches').textContent = number(summary.batch_count);
    document.getElementById('kpi-active').textContent = number(summary.active_batches);
    document.getElementById('kpi-sold').textContent = number(summary.sold_batches);
    document.getElementById('kpi-quantity').textContent = `${number(summary.total_quantity_kg)} kg`;
    document.getElementById('kpi-risk').textContent = number(summary.high_risk_batches);
    document.getElementById('kpi-revenue').textContent = money(summary.revenue);
    document.getElementById('kpi-profit').textContent = money(summary.profit);
    document.getElementById('kpi-cost').textContent = money(summary.production_cost);
    document.getElementById('kpi-margin').textContent = summary.revenue ? `${((summary.profit / summary.revenue) * 100).toFixed(1)}%` : '—';
    renderBars('crop-mix-chart', data.crop_mix, 'crop');
    renderBars('state-mix-chart', data.state_mix, 'state');
    renderRisks(data.risk_mix);
    renderFarmers(data.farmers);
    renderActivity(data.recent_batches);
}

function renderBars(targetId, entries, type) {
    const target = document.getElementById(targetId);
    if (!entries.length) {
        target.innerHTML = '<p class="empty-admin">No records yet.</p>';
        return;
    }
    const max = Math.max(...entries.map(entry => entry.value), 1);
    target.innerHTML = entries.slice(0, 7).map(entry => `<div class="bar-row"><div class="bar-label"><span>${escapeHtml(entry.label)}</span><b>${number(entry.value)}</b></div><div class="bar-track"><i class="bar-fill ${type}" style="width:${Math.max(8, (entry.value / max) * 100)}%"></i></div></div>`).join('');
}

function renderRisks(entries) {
    const target = document.getElementById('risk-mix-chart');
    const colors = { High: 'risk-high', Medium: 'risk-medium', Low: 'risk-low', 'Not applicable': 'risk-na' };
    target.innerHTML = entries.length ? entries.map(entry => `<div class="risk-row"><span class="risk-key"><i class="risk-dot ${colors[entry.label] || 'risk-low'}"></i>${escapeHtml(entry.label)}</span><strong>${number(entry.value)}</strong></div>`).join('') : '<p class="empty-admin">No quality flags yet.</p>';
}

function renderFarmers(farmers) {
    const target = document.getElementById('farmers-table');
    const filter = document.getElementById('farmer-filter').value.toLowerCase().trim();
    const visible = farmers.filter(farmer => `${farmer.full_name} ${farmer.location}`.toLowerCase().includes(filter));
    target.innerHTML = visible.length ? visible.map(farmer => `<tr><td><strong>${escapeHtml(farmer.full_name)}</strong><small>${escapeHtml(farmer.farmer_id || '')}</small></td><td>${escapeHtml(farmer.location)}</td><td>${number(farmer.crop_count)}</td><td>${number(farmer.active_quantity_kg)}</td><td>${money(farmer.revenue)}</td><td class="${farmer.profit < 0 ? 'negative' : 'positive'}">${money(farmer.profit)}</td></tr>`).join('') : '<tr><td colspan="6" class="empty-admin">No farmers match this search.</td></tr>';
}

function filterFarmers() {
    if (adminData) renderFarmers(adminData.farmers);
}

function renderActivity(batches) {
    const target = document.getElementById('recent-activity');
    target.innerHTML = batches.length ? batches.map(batch => `<div class="activity-item"><div class="activity-mark ${batch.spoilage_risk === 'High' ? 'high' : ''}"></div><div><strong>${escapeHtml(batch.crop_name)}</strong><span>${escapeHtml(batch.farmer_name)} · ${number(batch.quantity_kg)} kg</span><small>${escapeHtml(batch.status)} · ${formatDate(batch.created_at)}</small></div><em>${escapeHtml(batch.spoilage_risk)}</em></div>`).join('') : '<p class="empty-admin">No crop activity yet.</p>';
}

function formatDate(value) {
    if (!value) return 'Unknown date';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

async function logoutAdmin() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/auth';
}

document.addEventListener('DOMContentLoaded', loadAdminOverview);
