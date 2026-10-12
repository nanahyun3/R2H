"""T12 v2 — 연간 expanding SVR–GARCH CUSUM × ETF 20종 다축 진단 (V/M/N/C/H).

T11(``r2h.svrgarch_etf``) 과 Track B(``r2h.paper2020``) 원본은 수정하지 않고 import 만 한다.
프로토콜: ``research/t12_annual_expanding_v2/PROTOCOL_LOCK.md`` · 설정: ``configs/t12_annual_expanding_v2.json``.
"""

from .config import config_hash, derive_seed, load_config
from .folds import STRATEGIES, AnnualFold, build_fold

__all__ = ["STRATEGIES", "AnnualFold", "build_fold", "config_hash", "derive_seed", "load_config"]
