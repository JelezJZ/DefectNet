const API_URL = 'http://localhost:8000';
let selectedFile = null;
let batchFiles = [];
let compareFile = null;
let currentInspectionId = null;
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
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    initEventListeners();
});

function initEventListeners() {
    // Single detection
    document.getElementById('fileInput').addEventListener('change', handleFileSelect);
    document.getElementById('confidenceSlider').addEventListener('input', updateConfidenceValue);
    document.getElementById('analyzeBtn').addEventListener('click', analyzeImage);

    // Drag & Drop
    const uploadSection = document.getElementById('uploadSection');
    uploadSection.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadSection.classList.add('drag-over');
    });
    uploadSection.addEventListener('dragleave', () => {
        uploadSection.classList.remove('drag-over');
    });
    uploadSection.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadSection.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFile(files[0]);
    });

    // Batch
    document.getElementById('batchFileInput').addEventListener('change', handleBatchFileSelect);

    // Compare
    document.getElementById('compareFileInput').addEventListener('change', handleCompareFileSelect);
}

// ============ AUTH ============
async function checkAuth() {
    if (!authToken) {
        updateUIForGuest();
        return;
    }

    try {
        const response = await fetch(`${API_URL}/auth/me`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (response.ok) {
            currentUser = await response.json();
            updateUIForUser(currentUser);
        } else {
            // Token invalid
            localStorage.removeItem('authToken');
            authToken = null;
            updateUIForGuest();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        updateUIForGuest();
    }
}

function updateUIForUser(user) {
    document.getElementById('username').textContent = user.username;
    document.getElementById('userAvatar').textContent = user.username[0].toUpperCase();
    document.getElementById('loginBtn').style.display = 'none';
    document.getElementById('logoutBtn').style.display = 'block';
    document.getElementById('mainContent').style.display = 'block';
    document.getElementById('loginFormContainer').style.display = 'none';
    document.getElementById('registerFormContainer').style.display = 'none';
}

function updateUIForGuest() {
    document.getElementById('username').textContent = 'Guest';
    document.getElementById('userAvatar').textContent = 'G';
    document.getElementById('loginBtn').style.display = 'block';
    document.getElementById('logoutBtn').style.display = 'none';
}

function showLoginForm() {
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('loginFormContainer').style.display = 'block';
    document.getElementById('registerFormContainer').style.display = 'none';
}

function showRegisterForm() {
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('loginFormContainer').style.display = 'none';
    document.getElementById('registerFormContainer').style.display = 'block';
}

async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const alertDiv = document.getElementById('loginAlert');

    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            currentUser = data.user;
            
            alertDiv.innerHTML = '<div class="alert alert-success">Login successful!</div>';
            setTimeout(() => {
                updateUIForUser(currentUser);
            }, 1000);
        } else {
            const error = await response.json();
            alertDiv.innerHTML = `<div class="alert alert-error">${error.detail}</div>`;
        }
    } catch (error) {
        alertDiv.innerHTML = '<div class="alert alert-error">Login failed. Please try again.</div>';
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const fullName = document.getElementById('regFullName').value;
    const password = document.getElementById('regPassword').value;
    const alertDiv = document.getElementById('registerAlert');

    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username,
                email,
                full_name: fullName,
                password
            })
        });

        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            currentUser = data.user;
            
            alertDiv.innerHTML = '<div class="alert alert-success">Registration successful!</div>';
            setTimeout(() => {
                updateUIForUser(currentUser);
            }, 1000);
        } else {
            const error = await response.json();
            alertDiv.innerHTML = `<div class="alert alert-error">${error.detail}</div>`;
        }
    } catch (error) {
        alertDiv.innerHTML = '<div class="alert alert-error">Registration failed. Please try again.</div>';
    }
}

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUser = null;
    updateUIForGuest();
    showLoginForm();
}

// ============ TAB SWITCHING ============
function switchTab(tabName) {
    // Скрыть все tabs
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

    // Показать выбранный
    document.querySelector(`.tab:nth-child(${getTabIndex(tabName)})`).classList.add('active');
    document.getElementById(`tab${capitalize(tabName)}`).classList.add('active');

    // Загрузить данные если нужно
    if (tabName === 'history') {
        loadHistory();
    }
}

function getTabIndex(tabName) {
    const tabs = { single: 1, batch: 2, history: 3, compare: 4 };
    return tabs[tabName] || 1;
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function switchPage(page) {
    // Обновить активный пункт меню
    document.querySelectorAll('.navbar-menu a').forEach(a => a.classList.remove('active'));
    event.target.classList.add('active');

    // Переключить соответствующую вкладку
    const pageToTab = {
        'detection': 'single',
        'batch': 'batch',
        'history': 'history',
        'models': 'compare',
        'analytics': 'single' // Можно создать отдельную вкладку для аналитики
    };

    switchTab(pageToTab[page] || 'single');
}

// ============ SINGLE DETECTION ============
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) handleFile(file);
}

function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        alert('Please select an image');
        return;
    }

    selectedFile = file;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('originalImage').src = e.target.result;
        document.getElementById('controls').style.display = 'block';
    };
    reader.readAsDataURL(file);
}

function updateConfidenceValue(e) {
    document.getElementById('confidenceValue').textContent = e.target.value;
}

async function analyzeImage() {
    if (!selectedFile) {
        alert('Please select an image first');
        return;
    }

    document.getElementById('loading').classList.add('active');
    document.getElementById('previewSection').classList.remove('active');
    document.getElementById('resultsSection').classList.remove('active');

    const formData = new FormData();
    formData.append('file', selectedFile);
    
    const confidence = document.getElementById('confidenceSlider').value;
    
    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_URL}/detect?confidence=${confidence}&save_image=true`, {
            method: 'POST',
            headers: headers,
            body: formData
        });

        if (!response.ok) {
            throw new Error('Analysis failed');
        }

        const data = await response.json();
        currentInspectionId = data.inspection_id;
        displayResults(data);
        
    } catch (error) {
        alert('Error: ' + error.message);
        console.error(error);
    } finally {
        document.getElementById('loading').classList.remove('active');
    }
}

function displayResults(data) {
    const results = data.results;
    
    // Показать изображение
    if (data.result_image) {
        document.getElementById('resultImage').src = API_URL + data.result_image;
        document.getElementById('previewSection').classList.add('active');
    }

    // Статус
    const statusBadge = document.getElementById('statusBadge');
    const statusClass = `status-${results.status}`;
    const statusText = {
        'passed': '✅ Inspection Passed',
        'warning': '⚠️ Minor Defects Detected',
        'failed': '❌ Critical Defects Detected'
    };
    
    statusBadge.innerHTML = `<div class="status-badge ${statusClass}">${statusText[results.status]}</div>`;

    // Статистика
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = `
        <div class="stat-card">
            <h2>${results.total_defects}</h2>
            <p>Total Defects</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">
            <h2>${results.severity_breakdown.critical || 0}</h2>
            <p>Critical</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);">
            <h2>${results.severity_breakdown.medium || 0}</h2>
            <p>Medium</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #28a745 0%, #218838 100%);">
            <h2>${results.severity_breakdown.low || 0}</h2>
            <p>Low</p>
        </div>
    `;

    // Дефекты
    const defectsList = document.getElementById('defectsList');
    
    if (results.detections.length === 0) {
        defectsList.innerHTML = '<p style="text-align: center; color: #28a745; font-size: 1.2em;">🎉 No defects detected!</p>';
    } else {
        defectsList.innerHTML = results.detections.map((defect, index) => `
            <div class="defect-card ${defect.severity}">
                <h4>
                    #${index + 1}: ${defect.class_ru}
                    <span class="severity-${defect.severity}" style="float: right;">
                        ${defect.severity.toUpperCase()}
                    </span>
                </h4>
                <p><strong>Type:</strong> ${defect.class}</p>
                <p><strong>Confidence:</strong> ${(defect.confidence * 100).toFixed(1)}%</p>
                <p><strong>Description:</strong> ${defect.description}</p>
                <p><strong>Coordinates:</strong> 
                    [${defect.bbox.x1.toFixed(0)}, ${defect.bbox.y1.toFixed(0)}] - 
                    [${defect.bbox.x2.toFixed(0)}, ${defect.bbox.y2.toFixed(0)}]
                </p>
            </div>
        `).join('');
    }

    document.getElementById('resultsSection').classList.add('active');
    document.getElementById('exportBtn').style.display = 'inline-block';
}

function reset() {
    selectedFile = null;
    currentInspectionId = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('controls').style.display = 'none';
    document.getElementById('previewSection').classList.remove('active');
    document.getElementById('resultsSection').classList.remove('active');
    document.getElementById('exportBtn').style.display = 'none';
    document.getElementById('originalImage').src = '';
    document.getElementById('resultImage').src = '';
}

async function exportPDF() {
    if (!currentInspectionId) {
        alert('No inspection to export');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/export/pdf/${currentInspectionId}`);
        
        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `inspection_${currentInspectionId}.pdf`;
        a.click();
        
    } catch (error) {
        alert('Export failed: ' + error.message);
    }
}

// ============ BATCH PROCESSING ============
function handleBatchFileSelect(e) {
    const files = Array.from(e.target.files);
    
    files.forEach(file => {
        if (file.type.startsWith('image/')) {
            batchFiles.push(file);
        }
    });

    displayBatchFiles();
}

function displayBatchFiles() {
    if (batchFiles.length === 0) {
        document.getElementById('batchFilesContainer').style.display = 'none';
        return;
    }

    document.getElementById('batchFilesContainer').style.display = 'block';
    document.getElementById('batchFileCount').textContent = batchFiles.length;

    const listHTML = batchFiles.map((file, index) => `
        <div class="batch-file-item">
            <div>
                <div class="file-name">${file.name}</div>
                <div class="file-size">${(file.size / 1024).toFixed(1)} KB</div>
            </div>
            <button class="remove-file-btn" onclick="removeBatchFile(${index})">Remove</button>
        </div>
    `).join('');

    document.getElementById('batchFilesList').innerHTML = listHTML;
}

function removeBatchFile(index) {
    batchFiles.splice(index, 1);
    displayBatchFiles();
}

function clearBatchFiles() {
    batchFiles = [];
    document.getElementById('batchFileInput').value = '';
    displayBatchFiles();
}

async function processBatch() {
    if (batchFiles.length === 0) {
        alert('No files selected');
        return;
    }

    document.getElementById('batchProgress').style.display = 'block';
    document.getElementById('batchResults').style.display = 'none';

    const formData = new FormData();
    batchFiles.forEach(file => {
        formData.append('files', file);
    });

    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_URL}/batch-detect?confidence=0.25`, {
            method: 'POST',
            headers: headers,
            body: formData
        });

        if (!response.ok) {
            throw new Error('Batch processing failed');
        }

        const data = await response.json();
        displayBatchResults(data);
        
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

function displayBatchResults(data) {
    document.getElementById('batchProgressBar').style.width = '100%';
    document.getElementById('batchProgressText').textContent = '100%';

    setTimeout(() => {
        document.getElementById('batchProgress').style.display = 'none';
        document.getElementById('batchResults').style.display = 'block';

        const resultsHTML = data.results.map((result, index) => {
            if (result.status === 'error') {
                return `
                    <div class="defect-card" style="border-left-color: #dc3545;">
                        <h4>${index + 1}. ${result.filename}</h4>
                        <p style="color: #dc3545;">Error: ${result.error}</p>
                    </div>
                `;
            }

            const inspectionData = result.data;
            return `
                <div class="defect-card" style="border-left-color: #28a745;">
                    <h4>${index + 1}. ${result.filename}</h4>
                    <p><strong>Status:</strong> ${inspectionData.results.status.toUpperCase()}</p>
                    <p><strong>Defects Found:</strong> ${inspectionData.results.total_defects}</p>
                    <p><strong>Critical:</strong> ${inspectionData.results.severity_breakdown.critical || 0}, 
                        <strong>Medium:</strong> ${inspectionData.results.severity_breakdown.medium || 0}, 
                        <strong>Low:</strong> ${inspectionData.results.severity_breakdown.low || 0}</p>
                </div>
            `;
        }).join('');

        document.getElementById('batchResultsContent').innerHTML = resultsHTML;
    }, 500);
}

// ============ HISTORY ============
async function loadHistory() {
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px;">Loading...</td></tr>';

    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_URL}/history?limit=50`, {
            headers: headers
        });

        if (!response.ok) {
            throw new Error('Failed to load history');
        }

        const data = await response.json();
        
        if (data.inspections.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px;">No inspections found</td></tr>';
            return;
        }

        const rowsHTML = data.inspections.map(insp => {
            const date = new Date(insp.timestamp);
            const statusClass = `status-${insp.status}`;
            
            return `
                <tr>
                    <td>${insp.id.substring(0, 8)}...</td>
                    <td>${date.toLocaleString()}</td>
                    <td>${insp.filename}</td>
                    <td>${insp.total_defects}</td>
                    <td><span class="status-badge ${statusClass}">${insp.status.toUpperCase()}</span></td>
                    <td>
                        <button class="btn" style="padding: 5px 15px; margin: 0;" 
                                onclick="viewInspection('${insp.id}')">View</button>
                        <button class="btn btn-success" style="padding: 5px 15px; margin: 0 0 0 5px;" 
                                onclick="exportPDFById('${insp.id}')">PDF</button>
                    </td>
                </tr>
            `;
        }).join('');

        tbody.innerHTML = rowsHTML;

    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 40px; color: #dc3545;">Error: ${error.message}</td></tr>`;
    }
}

async function viewInspection(inspectionId) {
    const modal = document.getElementById('inspectionModal');
    const body = document.getElementById('inspectionModalBody');

    modal.style.display = 'block';
    body.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="spinner"></div><p>Загрузка...</p></div>';

    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_URL}/history/${inspectionId}`, {
            headers: headers
        });

        if (!response.ok) {
            throw new Error('Failed to load inspection');
        }

        const data = await response.json();
        renderInspectionModal(data);

    } catch (error) {
        body.innerHTML = `<div class="alert alert-error">Ошибка: ${error.message}</div>`;
    }
}

function renderInspectionModal(data) {
    const body = document.getElementById('inspectionModalBody');

    const statusClass = `status-${data.status}`;
    const statusText = {
        'passed': '✅ PASSED',
        'warning': '⚠️ WARNING',
        'failed': '❌ FAILED'
    };

    const date = new Date(data.timestamp);

    const severityHtml = data.severity_breakdown ? `
        <div class="meta-item">
            <label>🔴 Critical</label>
            <span>${data.severity_breakdown.critical || 0}</span>
        </div>
        <div class="meta-item">
            <label>🟡 Medium</label>
            <span>${data.severity_breakdown.medium || 0}</span>
        </div>
        <div class="meta-item">
            <label>🟢 Low</label>
            <span>${data.severity_breakdown.low || 0}</span>
        </div>
    ` : '';

    const originalImageHtml = data.original_image_path
        ? `<img src="${API_URL}/uploads/${data.original_image_path.split('/').pop()}" alt="Original">`
        : '<div style="min-height:200px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;border-radius:10px;color:#888;">Изображение недоступно</div>';

    const resultImageHtml = data.result_image_path
        ? `<img src="${API_URL}/results/${data.result_image_path.split('/').pop()}" alt="Result">`
        : '<div style="min-height:200px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;border-radius:10px;color:#888;">Изображение недоступно</div>';

    const defectsHtml = data.detections && data.detections.length > 0
        ? data.detections.map((defect, index) => {
            const defectInfo = DEFECT_INFO[defect.class] || { name_ru: defect.class, description: '' };
            return `
                <div class="defect-card ${defect.severity}">
                    <h4>
                        #${index + 1}: ${defectInfo.name_ru || defect.class}
                        <span class="severity-${defect.severity}" style="float: right;">
                            ${defect.severity.toUpperCase()}
                        </span>
                    </h4>
                    <p><strong>Confidence:</strong> ${(defect.confidence * 100).toFixed(1)}%</p>
                    <p><strong>Description:</strong> ${defectInfo.description || defect.description || ''}</p>
                    <p><strong>Coordinates:</strong>
                        [${defect.bbox.x1.toFixed(0)}, ${defect.bbox.y1.toFixed(0)}] -
                        [${defect.bbox.x2.toFixed(0)}, ${defect.bbox.y2.toFixed(0)}]
                    </p>
                </div>
            `;
        }).join('')
        : '<p style="text-align: center; color: #28a745; font-size: 1.2em;">🎉 Дефекты не обнаружены</p>';

    body.innerHTML = `
        <div class="inspection-detail-header">
            <h3>Инспекция: ${data.id}</h3>
            <span class="status-badge ${statusClass}">${statusText[data.status] || data.status}</span>
        </div>

        <div class="inspection-meta">
            <div class="meta-item">
                <label>Дата и время</label>
                <span>${date.toLocaleString()}</span>
            </div>
            <div class="meta-item">
                <label>Файл</label>
                <span>${data.filename}</span>
            </div>
            <div class="meta-item">
                <label>Всего дефектов</label>
                <span>${data.total_defects}</span>
            </div>
            <div class="meta-item">
                <label>Время обработки</label>
                <span>${data.processing_time} с</span>
            </div>
            <div class="meta-item">
                <label>Порог уверенности</label>
                <span>${(data.confidence_threshold * 100).toFixed(0)}%</span>
            </div>
            <div class="meta-item">
                <label>Разрешение</label>
                <span>${data.image_width}x${data.image_height}</span>
            </div>
            ${severityHtml}
        </div>

        <div class="inspection-images">
            <div>
                <h4 style="margin-bottom: 10px; color: #667eea;">📷 Исходное изображение</h4>
                ${originalImageHtml}
            </div>
            <div>
                <h4 style="margin-bottom: 10px; color: #667eea;">✨ Результат анализа</h4>
                ${resultImageHtml}
            </div>
        </div>

        <div class="inspection-defects">
            <h4>🔎 Обнаруженные дефекты (${data.detections ? data.detections.length : 0})</h4>
            ${defectsHtml}
        </div>

        <div style="margin-top: 20px; text-align: right;">
            <button class="btn btn-success" onclick="exportPDFById('${data.id}')">📄 Экспорт PDF</button>
        </div>
    `;
}

function closeInspectionModal() {
    document.getElementById('inspectionModal').style.display = 'none';
}

// Закрытие модального окна при клике вне его
document.addEventListener('click', (e) => {
    const modal = document.getElementById('inspectionModal');
    if (e.target === modal) {
        closeInspectionModal();
    }
});

// Закрытие модального окна по Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeInspectionModal();
    }
});

async function exportPDFById(inspectionId) {
    try {
        const response = await fetch(`${API_URL}/export/pdf/${inspectionId}`);
        
        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `inspection_${inspectionId}.pdf`;
        a.click();
        
    } catch (error) {
        alert('Export failed: ' + error.message);
    }
}

async function exportHistoryCSV() {
    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const response = await fetch(`${API_URL}/export/csv`, {
            headers: headers
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'inspections_export.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

    } catch (error) {
        alert('Export failed: ' + error.message);
    }
}

// ============ MODEL COMPARISON ============
function handleCompareFileSelect(e) {
    const file = e.target.files[0];
    if (file && file.type.startsWith('image/')) {
        compareFile = file;
        document.getElementById('compareControls').style.display = 'block';
    }
}

async function compareModels() {
    if (!compareFile) {
        alert('Please select an image first');
        return;
    }

    document.getElementById('compareLoading').classList.add('active');
    document.getElementById('compareResults').style.display = 'none';

    const formData = new FormData();
    formData.append('file', compareFile);

    try {
        const response = await fetch(`${API_URL}/models/compare?confidence=0.25`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Comparison failed');
        }

        const data = await response.json();
        displayComparisonResults(data);

    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        document.getElementById('compareLoading').classList.remove('active');
    }
}

function displayComparisonResults(data) {
    const container = document.getElementById('comparisonContainer');
    
    const modelsHTML = Object.entries(data.comparison).map(([modelName, modelData]) => `
        <div class="model-result">
            <h4>${modelName} (v${modelData.version})</h4>
            <p><strong>Detections:</strong> ${modelData.count}</p>
            <div style="margin-top: 15px;">
                ${modelData.detections.slice(0, 5).map(det => `
                    <div style="padding: 8px; background: white; border-radius: 5px; margin-bottom: 5px;">
                        <strong>${det.class}</strong>: ${(det.confidence * 100).toFixed(1)}%
                    </div>
                `).join('')}
                ${modelData.count > 5 ? `<p style="margin-top: 10px; color: #666;">+ ${modelData.count - 5} more...</p>` : ''}
            </div>
        </div>
    `).join('');

    container.innerHTML = modelsHTML;

    // Agreement analysis
    const agreement = data.summary.detection_agreement;
    document.getElementById('agreementAnalysis').innerHTML = `
        <p><strong>Agreement Score:</strong> ${(agreement.agreement_score * 100).toFixed(1)}%</p>
        <p><strong>Average Detections:</strong> ${agreement.avg_detections}</p>
        <p><strong>Standard Deviation:</strong> ${agreement.std_detections}</p>
        ${data.summary.recommendations.length > 0 ? `
            <div style="margin-top: 15px;">
                <strong>Recommendations:</strong>
                <ul>
                    ${data.summary.recommendations.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
    `;

    document.getElementById('compareResults').style.display = 'block';
}

// Health check при загрузке
fetch(`${API_URL}/health`)
    .then(res => res.json())
    .then(data => console.log('API Status:', data))
    .catch(err => console.error('API not available:', err));