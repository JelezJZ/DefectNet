const API_URL = 'http://localhost:8000';
let selectedFile = null;

// Инициализация
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
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFile(file);
    }
}

function handleFile(file) {
    if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, выберите изображение');
        return;
    }

    selectedFile = file;
    
    // Показать превью
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
        alert('Сначала выберите изображение');
        return;
    }

    // Показать загрузку
    document.getElementById('loading').classList.add('active');
    document.getElementById('previewSection').classList.remove('active');
    document.getElementById('resultsSection').classList.remove('active');

    const formData = new FormData();
    formData.append('file', selectedFile);
    
    const confidence = document.getElementById('confidenceSlider').value;
    
    try {
        const response = await fetch(`${API_URL}/detect?confidence=${confidence}&save_image=true`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Ошибка при анализе изображения');
        }

        const data = await response.json();
        displayResults(data);
        
    } catch (error) {
        alert('Произошла ошибка: ' + error.message);
        console.error(error);
    } finally {
        document.getElementById('loading').classList.remove('active');
    }
}

function displayResults(data) {
    const results = data.results;
    
    // Показать изображение с результатами
    if (data.result_image) {
        document.getElementById('resultImage').src = API_URL + data.result_image;
        document.getElementById('previewSection').classList.add('active');
    }

    // Статус
    const statusBadge = document.getElementById('statusBadge');
    const statusClass = `status-${results.status}`;
    const statusText = {
        'passed': '✅ Проверка пройдена',
        'warning': '⚠️ Обнаружены незначительные дефекты',
        'failed': '❌ Обнаружены критические дефекты'
    };
    
    statusBadge.innerHTML = `<div class="status-badge ${statusClass}">${statusText[results.status]}</div>`;

    // Статистика
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = `
        <div class="stat-card">
            <h2>${results.total_defects}</h2>
            <p>Всего дефектов</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">
            <h2>${results.severity_breakdown.critical || 0}</h2>
            <p>Критических</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);">
            <h2>${results.severity_breakdown.medium || 0}</h2>
            <p>Средних</p>
        </div>
        <div class="stat-card" style="background: linear-gradient(135deg, #28a745 0%, #218838 100%);">
            <h2>${results.severity_breakdown.low || 0}</h2>
            <p>Низких</p>
        </div>
    `;

    // Список дефектов
    const defectsList = document.getElementById('defectsList');
    
    if (results.detections.length === 0) {
        defectsList.innerHTML = '<p style="text-align: center; color: #28a745; font-size: 1.2em;">🎉 Дефектов не обнаружено!</p>';
    } else {
        defectsList.innerHTML = results.detections.map((defect, index) => `
            <div class="defect-card ${defect.severity}">
                <h4>
                    #${index + 1}: ${defect.class_ru}
                    <span class="severity-${defect.severity}" style="float: right;">
                        ${defect.severity.toUpperCase()}
                    </span>
                </h4>
                <p><strong>Тип:</strong> ${defect.class}</p>
                <p><strong>Уверенность:</strong> ${(defect.confidence * 100).toFixed(1)}%</p>
                <p><strong>Описание:</strong> ${defect.description}</p>
                <p><strong>Координаты:</strong> 
                    [${defect.bbox.x1.toFixed(0)}, ${defect.bbox.y1.toFixed(0)}] - 
                    [${defect.bbox.x2.toFixed(0)}, ${defect.bbox.y2.toFixed(0)}]
                </p>
            </div>
        `).join('');
    }

    document.getElementById('resultsSection').classList.add('active');
}

function reset() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('controls').style.display = 'none';
    document.getElementById('previewSection').classList.remove('active');
    document.getElementById('resultsSection').classList.remove('active');
    document.getElementById('originalImage').src = '';
    document.getElementById('resultImage').src = '';
}

// Проверка доступности API при загрузке
fetch(`${API_URL}/health`)
    .then(res => res.json())
    .then(data => console.log('API Status:', data))
    .catch(err => console.error('API not available:', err));