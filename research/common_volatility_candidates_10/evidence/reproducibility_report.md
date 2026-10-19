# 10번 재현성 보고 (`10-lock-1`)

| 비교 | 대상 | 결과 |
|---|---|---|
| 경로 A: 노트북 10 새 커널 실행 (`scripts/run_t19_notebook.py`) vs 경로 B: `scripts/run_t19_pipeline.py` | `results/` CSV 17개 + `figures/` PNG 16·SVG 16 (49개, `figure_captions.json` 제외) | 바이트 동일 |
| 경로 A 2회차 vs 경로 B | 같은 49개 | 바이트 동일 |
| 09 노트북·W4 `results/` | 10번 실행 전후 SHA256 | 동일 (노트북 마지막 셀 assert) |

- 환경: R2H `.venv` (Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scipy 1.18.1 · matplotlib 3.11.2), BLAS 스레드 1, `PYTHONNOUSERSITE=1`.
- 노트북 CLAIMS 58/58 일치. pytest 전체 242 통과 (신규 `tests/unit/test_common_vol_10.py` 18개 포함).
- 실행 기록: `evidence/execution_record.json`, 로그 `evidence/10_execution.log`.

## v2 (`10-lock-2`)

| 비교 | 대상 | 결과 |
|---|---|---|
| 노트북 10 v2 새 커널 2회 vs `run_t19_pipeline.py` (+ 인포그래픽 스크립트) | `results/` CSV 28 + `figures/` 22 PNG·22 SVG + `infographics/` 2 PNG·2 SVG (76개) | 바이트 동일 (3회) |
| lock-1 결과 CSV 17개 | 커밋 `20f19fb` 대비 | 변경 없음 |
| 09·W4 results | 실행 전후 | 동일 |

CLAIMS 72/72 (lock-1 58 + lock-2 14). pytest 245 통과 (`tests/unit/test_common_vol_10.py` 21개).

## PART R (모델 입력)

| 비교 | 대상 | 결과 |
|---|---|---|
| 노트북 10 (PART R 포함) 새 커널 2회 vs `run_t19_pipeline.py` + 인포그래픽 | `results/` CSV 34 + JSON + 그림 25 PNG·25 SVG + 인포그래픽 3 PNG·3 SVG (92개) | 바이트 동일 (3회) |
| lock-1 CSV 17 · lock-2 CSV 11 | 커밋 `20f19fb` · `78d136d` 대비 | 변경 없음 |

CLAIMS 84/84. pytest 250 통과. 텐서 `outputs/t19/*.npz` 는 Git 제외 (색인·정규화 통계로 재현).
