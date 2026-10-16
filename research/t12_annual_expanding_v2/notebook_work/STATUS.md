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

1. 지시서의 "진단 순서 1–7" 원문을 받은 문서에서 찾지 못했다. REPRO_HASHES §3 에 B 가 쓴 7단계를 적었다. 원문과 다르면 알려 달라.
2. D-C02 정정 제안: `+dirty` 원인은 untracked 파일 **2개** (`scripts/t12_figures.py` 11:23:48 생성이 먼저, `scripts/t12_compare_runs.py` 11:25:19).
   결론은 같다.
3. pipeline.py:198 의 code_sha 검사는 동어반복 (worker 가 부모 값을 되돌려줌). 결과 무영향. 고칠지 C 판단 (src 변경이라 B 는 손대지 않음).
4. `src/r2h/annual_expanding/**` 은 수정하지 않았다.
