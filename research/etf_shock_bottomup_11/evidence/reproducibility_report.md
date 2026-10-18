# 11번 재현성 보고 (`11-lock-1`)

| 비교 | 대상 | 결과 |
|---|---|---|
| 노트북 11 새 커널 실행 (`run_t20_notebook.py`) vs `run_t20_pipeline.py` | `results/` CSV 6 + `figures/` PNG 34·SVG 34 (74개, `figure_captions.json` 제외) | 바이트 동일 |
| 노트북 2회차 vs 스크립트 | 같은 74개 | 바이트 동일 |
| 09·10·W3 결과 폴더 | 실행 전후 SHA256 | 동일 (노트북 마지막 셀 assert) |
| W3 CUSUM 재실행 | `individual_cusum_summary.csv` 72셀 (최대 T·경보일·유효일) | 일치 |

환경: R2H `.venv` (Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scipy 1.18.1 · matplotlib 3.11.2), BLAS 1 스레드. CLAIMS 47/47. pytest 252 통과 (신규 `tests/unit/test_etf_shock_11.py` 8개 포함).
