"""T11 — Lee·Kim·Lee (2020) SVR–GARCH CUSUM 을 ETF 20종에 적용 (sensitivity 적용, 원문 재현 아님).

``pipeline.run()`` 이 오토런 진입점이다. 설계·사전 고정 결정은 ``research/svr_garch_cusum_etf/README.md``.
"""

from .pipeline import PRIMARY, run

__all__ = ["PRIMARY", "run"]
