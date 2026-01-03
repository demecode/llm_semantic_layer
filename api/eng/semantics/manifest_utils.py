from pathlib import Path
import hashlib
from eng.config import DBT_MANIFEST_PATH

def manifest_hash() -> str:
    p = Path(DBT_MANIFEST_PATH)
    b = p.read_bytes()
    return hashlib.sha256(b).hexdigest()[:12]