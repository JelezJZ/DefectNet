const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/monitor';

let ws;
let defectsChart, timelineChart;
let authToken = localStorage.getItem('authToken');
let currentUser = null;

const DEFECT_INFO = {
    'mouse_bite': { name_ru: 'Мышиный укус', severity: 'medium', description: 'Неровные края на печатной плате' },
    'spur': { name_ru: 'Выступ', severity: 'low', description: 'Выступ на проводнике' },
    'missing_hole': { name_ru: 'Отсутствующее отверстие', severity: 'critical', description: 'Отверстие не просверлено или отсутствует' },
    'short': { name_ru: 'Короткое замыкание', severity: 'critical', description: 'Нежелательное соединение проводников' },
    'open_circuit': { name_ru: 'Разрыв цепи', severity: 'critical', description: 'Разрыв проводника' },
    'spurious_copper': { name_ru: 'Лишняя медь', severity: 'medium', description: 'Остатки меди на плате' }
};

// Инициализация
document.addEventListener('DOMContentLoaded', async () => {
    const authenticated = await checkAuth();
    if (!authenticated) {
        alert('Please login first');
        window.location.href = '/';
        return;
    }
    
    initCharts();
    connectWebSocket();
    loadInitialData();

    setInterval(loadAnalytics, 10000);
});

async function checkAuth() {
    if (!authToken) {
        return false;
    }

    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            currentUser = await response.json();
            document.getElementById('userInfo').textContent = `👤 ${currentUser.username}`;
            return true;
        } else {
            localStorage.removeItem('authToken');
            return false;
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        return false;
    }
}

function logout() {
    localStorage.removeItem('authToken');
    window.location.href = '/';
}

function connectWebSocket() {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 5000);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleRealtimeUpdate(data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connectWebSocket, 3000);
    };
}

function handleRealtimeUpdate(data) {
    if (data.event === 'new_inspection') {
        addActivityItem(data.data);
        loadAnalytics();
    }
}

function addActivityItem(inspection) {
    const feed = document.getElementById('activityFeed');
    const statusClass = inspection.status === 'failed' ? 'failed' :
                        inspection.status === 'warning' ? 'warning' : '';

    const item = document.createElement('div');
    item.className = `activity-item ${statusClass}`;
    item.style.cursor = 'pointer';
    item.onclick = () => viewInspectionDetail(inspection.inspection_id);
    item.innerHTML = `
        <strong>New Inspection</strong><br>
        ID: ${inspection.inspection_id}<br>
        Status: ${inspection.status.toUpperCase()}<br>
        Defects: ${inspection.total_defects}<br>
        <small>${new Date().toLocaleTimeString()}</small>
    `;

    feed.insertBefore(item, feed.firstChild);

    while (feed.children.length > 20) {
        feed.removeChild(feed.lastChild);
    }
}

async function loadInitialData() {
    await loadAnalytics();
    await loadHistory();
}

async function loadAnalytics() {
    try {
        const response = await fetch(`${API_URL}/analytics/dashboard`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        const data = await response.json();
        
        // Обновление метрик
        document.getElementById('totalInspections').textContent = data.total_inspections;
        document.getElementById('totalDefects').textContent = data.total_defects_found;
        document.getElementById('passRate').textContent = data.pass_rate.toFixed(1) + '%';
        
        // Обновление графика дефектов
        updateDefectsChart(data.defect_breakdown);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

async function loadHistory() {
    try {
        const response = await fetch(`${API_URL}/history?limit=20`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        const data = await response.json();
        
        // Заполнить activity feed
        const feed = document.getElementById('activityFeed');
        feed.innerHTML = '';
        
        data.inspections.forEach(insp => {
            addActivityItem({
                inspection_id: insp.id,
                status: insp.status,
                total_defects: insp.total_defects
            });
        });
        
        // Обновить timeline
        updateTimelineChart(data.inspections);
        
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function initCharts() {
    // Таблица дефектов
    const defectsCtx = document.getElementById('defectsChart').getContext('2d');
    defectsChart = new Chart(defectsCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Count',
                data: [],
                backgroundColor: 'rgba(102, 126, 234, 0.8)',
                borderColor: 'rgba(102, 126, 234, 1)',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: { 
                    beginAtZero: true,
                    ticks: { color: '#eee' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                x: { 
                    ticks: { color: '#eee' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                }
            }
        }
    });

    // Временная шкала
    const timelineCtx = document.getElementById('timelineChart').getContext('2d');
    timelineChart = new Chart(timelineCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Inspections',
                data: [],
                borderColor: 'rgba(102, 126, 234, 1)',
                backgroundColor: 'rgba(102, 126, 234, 0.2)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#eee' } }
            },
            scales: {
                y: { 
                    beginAtZero: true,
                    ticks: { color: '#eee' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                x: { 
                    ticks: { color: '#eee' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                }
            }
        }
    });
}

function updateDefectsChart(breakdown) {
    defectsChart.data.labels = Object.keys(breakdown);
    defectsChart.data.datasets[0].data = Object.values(breakdown);
    defectsChart.update();
}

function updateTimelineChart(inspections) {
    // Группировка по часам
    const hourly = {};

    inspections.forEach(insp => {
        const hour = new Date(insp.timestamp).getHours();
        hourly[hour] = (hourly[hour] || 0) + 1;
    });

    timelineChart.data.labels = Object.keys(hourly).map(h => `${h}:00`);
    timelineChart.data.datasets[0].data = Object.values(hourly);
    timelineChart.update();
}

async function viewInspectionDetail(inspectionId) {
    // Создаём модальное окно динамически
    let modal = document.getElementById('dashboardInspectionModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'dashboardInspectionModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>📋 Детали инспекции</h3>
                    <span class="modal-close" onclick="this.closest('.modal').style.display='none'">&times;</span>
                </div>
                <div class="modal-body" id="dashboardInspectionBody">
                    <div style="text-align: center; padding: 40px;">
                        <div class="spinner"></div>
                        <p>Загрузка...</p>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.style.display = 'none';
        });
    }

    const body = document.getElementById('dashboardInspectionBody');
    modal.style.display = 'block';
    body.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="spinner"></div><p>Загрузка...</p></div>';

    try {
        const response = await fetch(`${API_URL}/history/${inspectionId}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        if (!response.ok) throw new Error('Failed to load inspection');

        const data = await response.json();
        renderInspectionInModal(data, body);
    } catch (error) {
        body.innerHTML = `<p style="color: #dc3545;">Ошибка: ${error.message}</p>`;
    }
}

function renderInspectionInModal(data, body) {
    const statusText = { 'passed': '✅ PASSED', 'warning': '⚠️ WARNING', 'failed': '❌ FAILED' };
    const date = new Date(data.timestamp);

    const severityHtml = data.severity_breakdown ? `
        <div class="meta-item"><label>🔴 Critical</label><span>${data.severity_breakdown.critical || 0}</span></div>
        <div class="meta-item"><label>🟡 Medium</label><span>${data.severity_breakdown.medium || 0}</span></div>
        <div class="meta-item"><label>🟢 Low</label><span>${data.severity_breakdown.low || 0}</span></div>
    ` : '';

    const originalImageHtml = data.original_image_path
        ? `<img src="${API_URL}/uploads/${data.original_image_path.split('/').pop()}" alt="Original">`
        : '<div style="min-height:200px;background:#333;display:flex;align-items:center;justify-content:center;border-radius:10px;color:#888;">Недоступно</div>';

    const resultImageHtml = data.result_image_path
        ? `<img src="${API_URL}/results/${data.result_image_path.split('/').pop()}" alt="Result">`
        : '<div style="min-height:200px;background:#333;display:flex;align-items:center;justify-content:center;border-radius:10px;color:#888;">Недоступно</div>';

    const defectsHtml = data.detections && data.detections.length > 0
        ? data.detections.map((d, i) => {
            const info = DEFECT_INFO[d.class] || { name_ru: d.class, description: '' };
            return `
                <div class="defect-card ${d.severity}">
                    <h4>#${i + 1}: ${info.name_ru} <span class="severity-${d.severity}" style="float:right">${d.severity.toUpperCase()}</span></h4>
                    <p>Confidence: ${(d.confidence * 100).toFixed(1)}%</p>
                    <p>${info.description}</p>
                </div>`;
        }).join('')
        : '<p style="text-align:center;color:#28a745;">🎉 Дефекты не обнаружены</p>';

    body.innerHTML = `
        <div class="inspection-detail-header">
            <h3>Инспекция: ${data.id}</h3>
            <span class="status-badge status-${data.status}">${statusText[data.status] || data.status}</span>
        </div>
        <div class="inspection-meta">
            <div class="meta-item"><label>Дата</label><span>${date.toLocaleString()}</span></div>
            <div class="meta-item"><label>Файл</label><span>${data.filename}</span></div>
            <div class="meta-item"><label>Дефектов</label><span>${data.total_defects}</span></div>
            <div class="meta-item"><label>Время</label><span>${data.processing_time} с</span></div>
            ${severityHtml}
        </div>
        <div class="inspection-images">
            <div><h4 style="margin-bottom:10px;color:#667eea;">📷 Оригинал</h4>${originalImageHtml}</div>
            <div><h4 style="margin-bottom:10px;color:#667eea;">✨ Результат</h4>${resultImageHtml}</div>
        </div>
        <div class="inspection-defects"><h4>🔎 Дефекты (${data.detections ? data.detections.length : 0})</h4>${defectsHtml}</div>
    `;
}