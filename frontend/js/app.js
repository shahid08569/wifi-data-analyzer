/**
 * WiFi & Hotspot Data Analyzer - Frontend Controller
 */

let currentFilter = '30days';
let customStartDate = null;
let customEndDate = null;
let allDevices = [];
let totalNetworkBytes = 0;

document.addEventListener('DOMContentLoaded', () => {
  setupFilterPills();
  loadAllData();
  // Auto-refresh every 5 seconds for live bandwidth & hotspot updates
  setInterval(loadAllData, 5000);
});

function setupFilterPills() {
  const pills = document.querySelectorAll('.pill');
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const filter = pill.getAttribute('data-filter');
      const customBox = document.getElementById('custom-date-box');

      if (filter === 'custom') {
        customBox.style.display = 'flex';
        // Set default dates if empty
        const today = new Date().toISOString().split('T')[0];
        if (!document.getElementById('date-to').value) {
          document.getElementById('date-to').value = today;
        }
        if (!document.getElementById('date-from').value) {
          const past = new Date();
          past.setDate(past.getDate() - 30);
          document.getElementById('date-from').value = past.toISOString().split('T')[0];
        }
      } else {
        customBox.style.display = 'none';
        currentFilter = filter;
        customStartDate = null;
        customEndDate = null;
        loadAllData();
      }
    });
  });
}

function applyCustomDateFilter() {
  const from = document.getElementById('date-from').value;
  const to = document.getElementById('date-to').value;
  if (!from || !to) {
    alert('कृपया दोनों तारीखें (From और To) चुनें!');
    return;
  }
  currentFilter = 'custom';
  customStartDate = from;
  customEndDate = to;
  loadAllData();
}

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.style.display = 'none';
    pane.classList.remove('active');
  });

  const activePane = document.getElementById(tabId);
  if (activePane) {
    activePane.style.display = 'block';
    activePane.classList.add('active');
  }

  // Set active tab button
  const clickedBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => 
    (tabId === 'devices-tab' && b.innerText.includes('Device Data')) ||
    (tabId === 'hotspot-tab' && b.innerText.includes('Hotspot Tracking'))
  );
  if (clickedBtn) clickedBtn.classList.add('active');
}

async function loadAllData() {
  await Promise.all([
    fetchNetworkInfo(),
    fetchSummary(),
    fetchDevices(),
    fetchHotspot()
  ]);
}

function buildQueryString() {
  let url = `filter=${currentFilter}`;
  if (currentFilter === 'custom' && customStartDate && customEndDate) {
    url += `&start_date=${customStartDate}&end_date=${customEndDate}`;
  }
  return url;
}

async function fetchNetworkInfo() {
  try {
    const res = await fetch('/api/network-info');
    if (!res.ok) return;
    const data = await res.json();
    
    // SSID
    const ssidElem = document.getElementById('current-ssid');
    if (ssidElem) {
      ssidElem.textContent = data.network.ssid || 'Connected';
    }

    // Hotspot status pill
    const hsDot = document.getElementById('hotspot-dot');
    const hsText = document.getElementById('hotspot-status-text');
    if (data.hotspot && data.hotspot.is_active) {
      hsDot.className = 'hotspot-dot active';
      hsText.textContent = `ON (${data.hotspot.client_count} devices)`;
      hsText.style.color = '#fbbf24';
    } else {
      hsDot.className = 'hotspot-dot';
      hsText.textContent = 'OFF';
      hsText.style.color = 'var(--text-muted)';
    }
  } catch (err) {
    console.warn('Network info error:', err);
  }
}

async function fetchSummary() {
  try {
    const res = await fetch(`/api/summary?${buildQueryString()}`);
    if (!res.ok) return;
    const data = await res.json();

    totalNetworkBytes = data.total_bytes || 0;

    // Total traffic
    document.getElementById('val-total-traffic').textContent = formatBytes(data.total_bytes);
    document.getElementById('val-total-down').textContent = formatBytes(data.total_download_bytes);
    document.getElementById('val-total-up').textContent = formatBytes(data.total_upload_bytes);

    // Active devices
    document.getElementById('val-active-devices').textContent = `${data.active_devices} Active`;
    document.getElementById('val-total-devices').textContent = `Total Discovered: ${data.total_devices}`;

    // Hotspot duration
    document.getElementById('val-hotspot-time').textContent = formatDuration(data.hotspot_total_seconds);
    document.getElementById('val-hotspot-sessions').textContent = `Sessions: ${data.hotspot_sessions_count} recorded`;

    // Hotspot data
    document.getElementById('val-hotspot-data').textContent = formatBytes(data.hotspot_traffic_bytes);
  } catch (err) {
    console.warn('Summary error:', err);
  }
}

async function fetchDevices() {
  try {
    const res = await fetch(`/api/devices?${buildQueryString()}`);
    if (!res.ok) return;
    const data = await res.json();
    allDevices = data.devices || [];
    filterDevicesList();
  } catch (err) {
    console.warn('Devices error:', err);
  }
}

function filterDevicesList() {
  const query = (document.getElementById('device-search').value || '').toLowerCase().trim();
  const filtered = allDevices.filter(d => {
    return (
      (d.hostname && d.hostname.toLowerCase().includes(query)) ||
      (d.ip && d.ip.includes(query)) ||
      (d.mac && d.mac.toLowerCase().includes(query)) ||
      (d.vendor && d.vendor.toLowerCase().includes(query))
    );
  });

  renderDevicesTable(filtered);
}

function renderDevicesTable(devices) {
  const tbody = document.getElementById('devices-table-body');
  const countLabel = document.getElementById('devices-count-label');

  if (countLabel) {
    countLabel.textContent = `Showing ${devices.length} of ${allDevices.length} devices`;
  }

  if (!devices || devices.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="loading-cell">No devices found. Turn on network scanning or connect devices.</td></tr>`;
    return;
  }

  let html = '';
  devices.forEach(dev => {
    const totalBytes = dev.total_bytes || 0;
    const downBytes = dev.bytes_down || 0;
    const upBytes = dev.bytes_up || 0;
    const percentage = totalNetworkBytes > 0 ? ((totalBytes / totalNetworkBytes) * 100).toFixed(1) : 0;

    const deviceIcon = dev.device_type.includes('Mobile') ? '📱' :
                       dev.device_type.includes('Laptop') ? '💻' :
                       dev.device_type.includes('Gateway') ? '📡' : '🌐';

    const statusBadge = dev.is_active 
      ? `<span class="badge-online"><span class="pulse-dot"></span> Online</span>`
      : `<span class="badge-offline">Last seen</span>`;

    const hotspotPill = dev.is_hotspot_client 
      ? `<span class="hotspot-tag">🔥 Hotspot</span>`
      : '';

    html += `
      <tr>
        <td>
          <div style="font-weight: 700; display: flex; align-items: center; gap: 0.4rem;">
            <span>${deviceIcon}</span>
            <span>${escapeHtml(dev.hostname)}</span>
            ${hotspotPill}
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.15rem;">
            Type: ${escapeHtml(dev.device_type)}
          </div>
        </td>
        <td class="mono-cell">${escapeHtml(dev.ip)}</td>
        <td class="mono-cell">${escapeHtml(dev.mac)}</td>
        <td>${escapeHtml(dev.vendor)}</td>
        <td>${statusBadge}</td>
        <td>${formatBytes(downBytes)}</td>
        <td>${formatBytes(upBytes)}</td>
        <td>
          <strong style="font-size: 0.95rem; color: var(--primary);">${formatBytes(totalBytes)}</strong>
        </td>
        <td>
          <div class="usage-bar-wrapper">
            <div class="usage-bar-track">
              <div class="usage-bar-fill" style="width: ${Math.min(100, Math.max(3, percentage))}%;"></div>
            </div>
            <span style="font-size: 0.8rem; font-weight: 600; min-width: 42px;">${percentage}%</span>
          </div>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

async function fetchHotspot() {
  try {
    const res = await fetch('/api/hotspot');
    if (!res.ok) return;
    const data = await res.json();

    const curr = data.current || {};
    const sessions = data.sessions || [];

    // Live status
    const circle = document.getElementById('hs-status-circle');
    const title = document.getElementById('hs-live-title');
    const sub = document.getElementById('hs-live-subtitle');
    const clients = document.getElementById('hs-current-clients');
    const adapter = document.getElementById('hs-adapter-name');

    if (curr.is_active) {
      circle.className = 'hs-indicator on';
      title.textContent = 'Mobile Hotspot: ACTIVE (चालू है)';
      title.style.color = '#fbbf24';
      sub.textContent = `Connected mobile & PC devices are currently using this laptop's hotspot.`;
      clients.textContent = curr.client_count || 0;
      adapter.textContent = curr.adapter_name || 'Virtual Direct';
    } else {
      circle.className = 'hs-indicator';
      title.textContent = 'Mobile Hotspot: Inactive (बंद है)';
      title.style.color = 'var(--text-main)';
      sub.textContent = 'Windows Mobile Hotspot is currently turned off in Settings.';
      clients.textContent = '0';
      adapter.textContent = 'None';
    }

    renderHotspotSessions(sessions);
  } catch (err) {
    console.warn('Hotspot error:', err);
  }
}

function renderHotspotSessions(sessions) {
  const tbody = document.getElementById('hotspot-table-body');
  if (!sessions || sessions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="loading-cell">No hotspot sessions recorded yet. Turn on Windows Mobile Hotspot to record.</td></tr>`;
    return;
  }

  let html = '';
  sessions.forEach(s => {
    const startTime = new Date(s.started_at).toLocaleString();
    const endTime = s.ended_at ? new Date(s.ended_at).toLocaleString() : 'In Progress';
    const statusBadge = s.status === 'active' 
      ? `<span class="badge-online">Active Now</span>`
      : `<span class="badge-offline">Completed</span>`;

    html += `
      <tr>
        <td class="mono-cell">#${s.id}</td>
        <td>${startTime}</td>
        <td>${endTime}</td>
        <td><strong style="color: var(--amber);">${formatDuration(s.duration_seconds)}</strong></td>
        <td><strong style="color: var(--primary);">${formatBytes(s.total_bytes)}</strong></td>
        <td>⬇️ ${formatBytes(s.bytes_down)} / ⬆️ ${formatBytes(s.bytes_up)}</td>
        <td>${s.clients_count} Device(s)</td>
        <td>${statusBadge}</td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
}

async function triggerManualScan() {
  const btn = document.getElementById('btn-scan');
  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = `<span>Scanning...</span>`;

  try {
    await fetch('/api/scan', { method: 'POST' });
    await loadAllData();
  } catch (err) {
    console.error('Scan error:', err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalHtml;
  }
}

// Helpers
function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 MB';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  if (i === 0) return bytes + ' B';
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return '0m';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
