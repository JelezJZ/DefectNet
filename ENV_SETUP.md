# Environment Setup (Current)

Этот файл отражает текущее состояние проекта и дополняет `CONFIG.md`.

## Быстрый запуск

```bash
cp .env.example .env
python -m src.api.main
```

## Критичные переменные

- `DATABASE_URL` — обязателен, без него backend не стартует.
- `MODEL_PATH` — должен указывать на существующий `.pt` файл, иначе startup завершится ошибкой.
- `JWT_SECRET_KEY` — замените дефолт перед любым публичным запуском.

## Что уже поддерживается через env

- Сервер/окружение: `HOST`, `PORT`, `DEBUG`, `ENVIRONMENT`
- БД: `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`
- Детекция: `MODEL_PATH`, `IMAGE_SIZE`, `IOU_THRESHOLD`, `AUGMENT`
- Загрузка файлов: `MAX_UPLOAD_SIZE_MB`, `ALLOWED_IMAGE_TYPES`
- CORS: `ALLOWED_ORIGINS`
- Rate limiting: `RATE_LIMIT_PER_MINUTE`
- Celery/Redis: `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TIMEZONE`
- Пакетная обработка: `MAX_BATCH_SIZE`, `TASK_TIME_LIMIT`
- Логи: `LOG_LEVEL`, `LOG_FORMAT`, `LOG_DIR`, `LOG_FILE`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT`
- Очистка временных файлов: `CLEANUP_MAX_AGE_HOURS`, `CLEANUP_SCHEDULE_HOUR`, `CLEANUP_SCHEDULE_MINUTE`

## Важные ограничения

- При `ENVIRONMENT=production` нельзя использовать `ALLOWED_ORIGINS=*`.
- Frontend отдается backend-ом (`/` и `/dashboard`), отдельный `frontend/env-config.js` сейчас не подключен рантаймом.
