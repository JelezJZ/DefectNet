const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/monitor';

let ws;
let defectsChart, timelineChart;

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connectWebSocket();
    loadInitialData();

    setInterval(loadAnalytics, 10000);
});

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
        const response = await fetch(`${API_URL}/analytics/dashboard`);
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
        const response = await fetch(`${API_URL}/history?limit=20`);
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