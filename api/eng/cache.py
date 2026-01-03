import json, hashlib, time
from typing import Any, Dict, Optional

_CACHE: Dict[str, tuple[float, Any]] = {}

def _key(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def get(payload: Dict[str, Any]) -> Optional[Any]:
    k = _key(payload)
    item = _CACHE.get(k)
    if not item:
        return None
    expires_at, value = item
    if time.time() > expires_at:
        _CACHE.pop(k, None)
        return None
    return value

def set(payload: Dict[str, Any], value: Any, ttl_seconds: int = 300) -> Dict[str, Any]:
    k = _key(payload)
    _CACHE[k] = (time.time() + ttl_seconds, value)
    return {"cache_key": k, "ttl_seconds": ttl_seconds}