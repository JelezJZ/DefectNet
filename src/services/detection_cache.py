import hashlib
import os
from collections import OrderedDict
from threading import Lock


_CACHE = OrderedDict()
_LOCK = Lock()
_MAX_ITEMS = int(os.getenv("DETECTION_CACHE_MAX_ITEMS", "500"))


def build_cache_key(
    image_bytes: bytes,
    model_name: str,
    confidence: float,
    iou: float,
    imgsz: int,
) -> str:
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    return f"{image_hash}:{model_name}:{confidence:.4f}:{iou:.4f}:{imgsz}"


def get_cached_result(cache_key: str):
    with _LOCK:
        value = _CACHE.get(cache_key)
        if value is None:
            return None
        _CACHE.move_to_end(cache_key)
        return value


def set_cached_result(cache_key: str, value: dict) -> None:
    with _LOCK:
        _CACHE[cache_key] = value
        _CACHE.move_to_end(cache_key)

        while len(_CACHE) > _MAX_ITEMS:
            _CACHE.popitem(last=False)
