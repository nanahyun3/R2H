"""T12 설정 로드 · 해시 · 키 기반 seed.

설정 원본은 ``configs/t12_annual_expanding_v2.json`` (PROTOCOL_LOCK). seed 는 Python ``hash()`` 가 아니라
``sha256(study_id|키...)`` 앞 8바이트 → 실행 순서·프로세스·PYTHONHASHSEED 와 무관하다.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "t12_annual_expanding_v2.json"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as fh:
        cfg: dict[str, Any] = json.load(fh)
    return cfg


def config_hash(cfg: dict[str, Any]) -> str:
    """정렬된 JSON 직렬화의 sha256 앞 16자."""
    body = json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def derive_seed(*key: object) -> int:
    """키 튜플 → 64비트 seed (안정적)."""
    body = "|".join(str(k) for k in key)
    return int.from_bytes(hashlib.sha256(body.encode()).digest()[:8], "big")


def rng_for(*key: object) -> np.random.Generator:
    return np.random.default_rng(derive_seed(*key))


def array_hash(values: np.ndarray) -> str:
    """float 배열의 sha256 앞 16자 (NaN 포함, little-endian float64)."""
    arr = np.ascontiguousarray(np.asarray(values, dtype="<f8"))
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]
