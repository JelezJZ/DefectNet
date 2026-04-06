# DefectNet — Обнаружение дефектов PCB

Система автоматического обнаружения дефектов печатных плат на основе YOLO11.

## Возможности

- 🎯 Детекция 6 типов дефектов: missing_hole, short, open_circuit, mouse_bite, spur, spurious_copper
- 🚀 FastAPI backend с REST API
- 🖥️ Веб-интерфейс для загрузки изображений
- 📊 Статистика и история проверок
- 💾 SQLite для хранения результатов

## Установка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd DefectNet

# Установить зависимости
pip install -r requirements.txt

# Настроить переменные окружения
cp .env.example .env
# Отредактируйте .env под вашу среду (особенно JWT_SECRET_KEY!)

# Скачать модели
python scripts/download_models.py

# Обучить модель (опционально)
python notebooks/01_train_yolo.ipynb
```

### Конфигурация

⚠️ **ВАЖНО**: Перед запуском настройте `.env` файл:

```bash
# Сгенерировать безопасный JWT ключ
openssl rand -hex 32

# Скопировать результат в .env:
# JWT_SECRET_KEY=ваш_ключ_из_32_символов
```

📖 Подробное руководство: [CONFIG.md](CONFIG.md)  
🚀 Чеклист для продакшена: [ENV_SETUP.md](ENV_SETUP.md)

## Запуск

### Backend (API)

```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python -m src.api.main
```

API доступен по адресу: http://localhost:8000  
Документация Swagger: http://localhost:8000/docs

### Frontend

Откройте `frontend/index.html` в браузере или используйте простой сервер:

```bash
cd frontend && python -m http.server 3000
```

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /detect` | Детекция дефектов на изображении |
| `GET /health` | Проверка статуса API |
| `GET /history` | История проверок |
| `GET /analytics/dashboard` | Дашборд статистики |
| `GET /defect-info` | Информация о типах дефектов |

## Структура проекта

```
DefectNet/
├── src/              # Исходный код (API, модели, БД)
├── frontend/         # Веб-интерфейс
├── models/           # Претренированные модели
├── datasets/         # Датасеты (не в git)
├── storage/          # Загруженные файлы и результаты
├── runs/             # Результаты тренировок YOLO
├── notebooks/        # Jupyter ноутбуки для обучения
└── scripts/          # Скрипты (download_models.py)
```

## Требования

- Python 3.10+
- CUDA (опционально, для GPU)
- 4GB+ RAM

## Лицензия

MIT
