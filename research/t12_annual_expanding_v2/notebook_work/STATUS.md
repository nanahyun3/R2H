# STATUS — B (Notebook Engineering & Reproducibility)

브랜치 `research/annual-b-notebook` · base `8414678` · 워크트리 `.worktrees/b`

## 사전 예측 (b_seq_1 실행 전에 적음, 2026-10-16)

- `b_seq_1` (CLI, workers=1, 이 워크트리 `src`, `git status --porcelain -- src configs scripts` 가 빈 상태에서 시작) 은
  seq_golden 대비 **바이트가 다른 파일은 `fold_manifest.csv`(git_sha 열 = `8414678…`) 와 `run_manifest.json`(run_id·git_sha·runtime·aggregate_hash·uv.lock 경로 무관) 뿐**이고,
  나머지 9개 결과표(8 표 + diagnostic_profile + integrity)는 바이트 동일, Semantic Fingerprint 는 전 표 동일할 것이다.
- 다른 표가 바이트로 다르면 그대로 FAIL 로 적고 원인을 조사한다 (설명으로 덮지 않는다).
