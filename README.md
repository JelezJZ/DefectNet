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

# При необходимости: обучайте через Jupyter (notebooks/)
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
🚀 Быстрый статус env-настроек: [ENV_SETUP.md](ENV_SETUP.md)

## Запуск

### Backend (API)

```bash
python -m src.api.main
```

API доступен по адресу: http://localhost:8000  
Документация Swagger: http://localhost:8000/docs

### Frontend

Frontend отдается самим FastAPI-приложением:
- Главная: `http://localhost:8000/`
- Дашборд: `http://localhost:8000/dashboard`

## API Endpoints

| Endpoint | Описание |
|----------|----------|
| `POST /auth/register` | Регистрация пользователя |
| `POST /auth/login` | Вход и получение JWT |
| `GET /auth/me` | Данные текущего пользователя |
| `POST /detect` | Детекция дефектов на изображении |
| `POST /batch-detect` | Синхронная пакетная детекция |
| `POST /batch/upload` | Асинхронная пакетная обработка (Celery) |
| `GET /batch/status/{batch_id}` | Статус Celery batch-задачи |
| `GET /history/{inspection_id}` | Детали конкретной проверки |
| `GET /health` | Проверка статуса API |
| `GET /history` | История проверок |
| `GET /analytics/dashboard` | Дашборд статистики |
| `GET /statistics` | Базовая сводная статистика |
| `GET /defect-info` | Информация о типах дефектов |
| `GET /models/available` | Модели для `detect` |
| `GET /models/list` | Подробная информация по моделям |
| `POST /models/compare` | Сравнение моделей на одном изображении |
| `GET /export/pdf/{inspection_id}` | Экспорт отчета PDF |
| `GET /export/json/{inspection_id}` | Экспорт одной проверки в JSON-файл |
| `GET /export/image/{inspection_id}?format=png|jpeg` | Экспорт изображения результата |
| `GET /export/csv` | Экспорт истории в CSV |
| `GET /results/{file_path:path}` | Доступ к изображениям результата |
| `GET /uploads/{file_path:path}` | Доступ к исходным изображениям |
| `GET /dashboard` | HTML-дашборд аналитики |
| `GET /` | HTML-интерфейс детекции |

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

## Важно

- В продакшене `ALLOWED_ORIGINS=*` запрещен (приложение завершится при `ENVIRONMENT=production`).
- Для запуска нужны рабочие `DATABASE_URL` и `MODEL_PATH` в `.env`.

## Лицензия

MIT
