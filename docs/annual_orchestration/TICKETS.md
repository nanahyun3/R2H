# TICKETS — A/B/C 조정 (C 소유)

형식: `ID · 발신→수신 · 상태(OPEN/IN_PROGRESS/DONE/BLOCKED/REJECTED) · 내용 · 근거 · 해소`

| ID | 발신→수신 | 상태 | 내용 | 해소 |
|---|---|---|---|---|
| T-A1 | C→A | OPEN | A-1 `ANNUAL_METHOD_CONTRACT.md` — 지시서 §5 A-1 의 모든 항목에 코드 `파일:줄`·문서 근거 연결 | |
| T-A2 | C→A | OPEN | A-2 `ANNUAL_SCIENTIFIC_AUDIT.md` — 10개 질문, 반례·독립 테스트 | |
| T-A3 | C→A | OPEN | A-3 `T11_T12_COMPARISON_CONTRACT.md` | |
| T-B1 | C→B | OPEN | B-1 실행 DAG 복원 (`PIPELINE_DAG.md`) — 집계·그림 스크립트 포함 | |
| T-B2 | C→B | OPEN | B-2 seq/par 불일치 독립 확인 + Semantic Fingerprint 구현 + 새 순차 실행 `b_seq_1` 대비 seq_golden | |
| T-B3 | C→B | OPEN | B-3 재현 환경 기록 (인터프리터·버전·스레드·명령·데이터 해시, 네트워크 경로 차단) | |
| T-B4 | C→B | OPEN | B-4 `notebooks/T12_Annual_Expanding_Reproduction.ipynb` (G3 조건) | |
| T-A4 | C→A | WAITING(B-4) | A-4 노트북 독립 리뷰 — 승인/조건부/반려 | |
