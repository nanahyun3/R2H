# DECISION_LOG — C (오케스트레이터)

| # | 날짜 | 결정 | 근거 |
|---|---|---|---|
| D-C01 | 2026-10-16 | canonical base = `8414678` (ccd60d4 + 10/12 untracked 산출물 바이트 보존 커밋). 원본 트리 `R2H/` 는 손대지 않음 | 1차 증거(outputs/t12/work) 보존, 세 레인 동일 출발점 |
| D-C02 | 2026-10-16 | seq/par 비교 판정 = Byte FAIL / Semantic PASS, 원인 후보 = `fold_manifest.git_sha` 의 `+dirty` (untracked `scripts/t12_compare_runs.py`) | 8/9 표 바이트 동일, fold_manifest 앞 15열 동일, code_sha 동일, 파일 생성 시각 |
| D-C03 | 2026-10-16 | 비교 기준 = Semantic Fingerprint (provenance 열 제외, 전체 정밀도). 기각 판정이 바뀌면 FAIL | git_sha 가 결과표에 들어가므로 새 실행은 바이트가 다를 수밖에 없음 |
| D-C04 | 2026-10-16 | 노트북·스크립트는 로컬 `data/raw` 만 사용 (네트워크 경로 금지) | 10/16 FinanceDataReader 조회본에서 153130 종가 수정 → DataVersionDiffers |
| D-C05 | 2026-10-16 | canonical 노트북 위치 `notebooks/T12_Annual_Expanding_Reproduction.ipynb` (노트북 규칙 테스트 적용 범위), 실행 `jupyter execute` (nbclient), 계산은 순차(workers=1) | 지시서 B-2 우선순위, R2H .venv 에 nbconvert 없음·nbclient 있음 |
