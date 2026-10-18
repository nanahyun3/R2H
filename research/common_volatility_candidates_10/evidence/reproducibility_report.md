# 10번 재현성 보고 (`10-lock-1`)

| 비교 | 대상 | 결과 |
|---|---|---|
| 경로 A: 노트북 10 새 커널 실행 (`scripts/run_t19_notebook.py`) vs 경로 B: `scripts/run_t19_pipeline.py` | `results/` CSV 17개 + `figures/` PNG 16·SVG 16 (49개, `figure_captions.json` 제외) | 바이트 동일 |
| 경로 A 2회차 vs 경로 B | 같은 49개 | 바이트 동일 |
| 09 노트북·W4 `results/` | 10번 실행 전후 SHA256 | 동일 (노트북 마지막 셀 assert) |

- 환경: R2H `.venv` (Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scipy 1.18.1 · matplotlib 3.11.2), BLAS 스레드 1, `PYTHONNOUSERSITE=1`.
- 노트북 CLAIMS 58/58 일치. pytest 전체 242 통과 (신규 `tests/unit/test_common_vol_10.py` 18개 포함).
- 실행 기록: `evidence/execution_record.json`, 로그 `evidence/10_execution.log`.
