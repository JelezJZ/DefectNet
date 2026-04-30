import logging
import os
import shutil
import time
from pathlib import Path

from src.tasks.celery_config import celery_app


logger = logging.getLogger(__name__)


def _is_older_than(path: Path, max_age_seconds: int, now: float) -> bool:
    try:
        modified_time = path.stat().st_mtime
    except FileNotFoundError:
        return False

    return (now - modified_time) > max_age_seconds


def _delete_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.is_file():
        try:
            path.unlink(missing_ok=True)
        except TypeError:
            if path.exists():
                path.unlink()


@celery_app.task(name="src.tasks.cleanup_tasks.cleanup_old_temp_files")
def cleanup_old_temp_files() -> dict:
    """Remove temp and batch artifacts older than configured TTL."""
    max_age_hours = int(os.getenv("CLEANUP_MAX_AGE_HOURS", "24"))
    max_age_seconds = max_age_hours * 3600
    now = time.time()

    base_dir = Path(__file__).resolve().parents[2]
    storage_dir = base_dir / os.getenv("STORAGE_DIR", "storage")

    targets = []

    targets.extend(path for path in base_dir.glob("batch_*") if path.is_dir())

    temp_dirs = [
        storage_dir / "tmp",
        storage_dir / "temp",
        storage_dir / "batch_tmp",
    ]

    for temp_dir in temp_dirs:
        if temp_dir.exists() and temp_dir.is_dir():
            targets.extend(temp_dir.iterdir())

    removed = []
    checked = 0

    for target in targets:
        checked += 1
        if not _is_older_than(target, max_age_seconds, now):
            continue

        try:
            _delete_path(target)
            removed.append(str(target))
        except Exception as error:
            logger.warning("Failed to cleanup path %s: %s", target, error)

    logger.info(
        "Cleanup task completed: checked=%s removed=%s max_age_hours=%s",
        checked,
        len(removed),
        max_age_hours,
    )

    return {
        "checked": checked,
        "removed_count": len(removed),
        "removed": removed,
        "max_age_hours": max_age_hours,
    }
