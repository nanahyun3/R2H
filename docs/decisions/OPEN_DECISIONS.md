# 열린 결정 (1012 기준선)

코드는 아래 항목을 **확정하지 않은 채** 인자/config 로 받도록 만들었다. 결정되면 이 표와 `CONTRACT_v0.1.md` 를 같이 갱신하고 버전을 올린다.

| ID | 결정 사항 | 현재 상태 | 결정 주체 | 코드 영향 |
|---|---|---|---|---|
| D-01 | 급등 Ground Truth 정의 (가격 급등 / 자산 간 동행성 변화 / 변동성 변화; P1 실시간 vs P4 사후 vs 공통충격일) | 미정. Track A 결과상 상관 전환은 정답 후보로 근거 없음 | 교수 · 2조 · 4조 | `evaluation.ground_truth` 의 `label_version` |
| D-02 | 오탐 상한 (FP / ticker-year) · 최대 지연 · cooldown · pre_tolerance | 미정 | 교수 확인 | `MatchConfig`, `recall_at_fp_cap(fp_cap)` |
| D-03 | 개발 / 검증 / 관찰 구간 경계, 2026 처리 | 미정 (Track A 는 2019–24 / 2025 / 2026 을 썼으나 2026 은 blind 아님) | 교수 확인 | `chronological_split(bounds)` |
| D-04 | 유니버스 (공식 ETF 목록, exposure 중복 처리 — KOSPI200 계열 4종은 사건 1건) | PROVISIONAL 20종 | 2조 · 4조 | 입력 계약 `ticker` |
| D-05 | robust-z 정의 표준 (rz_D / rz_A / rz_eda — Jaccard 0.73~0.85) | unresolved | 2조 | 가격 사건 정의 |
| D-06 | 수정주가 정책 (FDR Close 분배 소급조정 추정) | ESTIMATED | 2조 W02 | `adj_close`, `source` |
| D-07 | 저장소 LICENSE | **없음** — 임의로 추가하지 않음 | 팀 전체 (저장소 소유자) | 공개 저장소 재사용 조건 |
| D-08 | 패키지 관리자 (uv + `uv.lock` 를 이 브랜치가 사용) | 제안 | 2조 · 4조 | `pyproject.toml`, `uv.lock` |
| D-09 | Track B 테스트 구간 분산 lag 정책 (관측 proxy A / 재귀 예측 B) | UNRESOLVED — 원문 미명시, 어느 쪽도 원문 Tables 재현 못 함 | 저자 문의 / 2조 W04 | `posthoc` 결과 해석 |

## 범위 밖 (이번 브랜치에서 구현하지 않음)

HMM 상태추론 · Dynamic Programming · Active Inference · LLM 에이전트 · PELT 사후 분할 · 뉴스 → `research/proposals/README.md`.
