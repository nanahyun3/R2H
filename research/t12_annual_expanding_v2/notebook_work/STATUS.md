# STATUS — B (Notebook Engineering & Reproducibility)

브랜치 `research/annual-b-notebook` · base `8414678` · 워크트리 `.worktrees/b`

## 사전 예측 (b_seq_1 실행 전에 적음, 2026-10-16 16:12)

- `b_seq_1` (CLI, workers=1, 이 워크트리 `src`, `git status --porcelain -- src configs scripts` 가 빈 상태에서 시작) 은
  seq_golden 대비 **바이트가 다른 파일은 `fold_manifest.csv`(git_sha 열 = `8414678…`) 와 `run_manifest.json` 뿐**이고,
  나머지 9개 결과표(8 표 + diagnostic_profile + integrity)는 바이트 동일, Semantic Fingerprint 는 전 표 동일할 것이다.
- 다른 표가 바이트로 다르면 그대로 FAIL 로 적고 원인을 조사한다 (설명으로 덮지 않는다).
- **결과 (16:22)**: 예측과 정확히 일치. 9/10 표 바이트 동일, fold_manifest 는 git_sha 열만 다름, Semantic·Verdict PASS. 609 s.

## 단계

| 단계 | 상태 | 산출물 |
|---|---|---|
| B-1 DAG | DONE | `notebook_work/PIPELINE_DAG.md` |
| B-2 seq/par 확인 · 지문 | DONE (b_seq_1 · b_par4_1 Semantic PASS) | `scripts/t12_semantic_fingerprint.py`, `tests/integration/test_t12_semantic_fingerprint.py`, `notebook_work/REPRO_HASHES.md` |
| B-3 환경 | DONE | `notebook_work/REPRO_ENV.md`, `notebook_work/raw_data_sha256.txt` |
| B-4 노트북 | IN_PROGRESS | `notebooks/T12_Annual_Expanding_Reproduction.ipynb` (생성기 `scripts/t12_build_reproduction_notebook.py`) |

## 장애물

- (없음 — BLOCKER 없음)

## C 에 대한 질문 · 보고

1. (해소, D-C06/07/08) 진단 순서 원문 → REPRO_HASHES §3 을 원문 1–7 로 다시 썼다. D-C02 정정 반영 확인. code_sha 검사는 "무효, 결과 무영향" 으로만 기록 (REPRO_HASHES §5, 노트북 제한사항 10).
2. A RQ-1–5 (C 승인분) 반영: `PROTOCOL_CHANGELOG.md` C-11–C-15 ("lock 이후 문서 정정/명세 대비 미구현, 수치 무영향"), `report/methods_part.md` II.2·II.5,
   노트북 2절(1.3397 = 원문 표기 임계값, 정확 점근 5% 1.3581 아님, n≈245 보수적; C-11 seed 공유; 귀무 표본 길이) · 3절(261240 243일·170/73) · 11절 제한사항.
   노트북에서 1.3397 을 "점근 5%" 라고 부르지 않는다 (부정문 "점근 5% 정확값이 아니다" 한 곳만 있음).
   남은 표현: `scripts/t12_figures.py` 그림 6 의 x 눈금 "점근\n1.3397" (그림 PNG 를 바꾸므로 손대지 않음 — 필요하면 C 지시).
3. A 의 `REQUESTS_TO_B.md` 에 RQ-6–RQ-11 이 새로 생겼다. C 승인 범위(RQ-1–5) 밖이라 **반영하지 않았다**. 승인하면 노트북 표시·서술만 바꾸고 재실행한다.
4. 중단 run: `outputs/t12/work/b_nb_20261016T162756` 은 RQ 반영을 위해 B 가 일부러 중단한 노트북 실행의 잔여물이다 (merged 없음, 사용 금지).
5. 합성 재실행 측정 (B, 2026-10-16): workers=4 146.9 s, sha256 `43de7bca9b42…` 저장본과 동일 (`outputs/t12/synthetic_b_1`). 4회째 일치.
6. `src/r2h/annual_expanding/**` 은 수정하지 않았다.
