# research/ — 감사를 거친 연구 근거 요약

원 연구 코드·노트북·데이터는 SA_ETF 에 있다. 여기에는 팀이 판단에 쓸 **요약과 재현 상태**만 둔다. 수치는 모두 원 결과표에서 재계산해 대조한 값이다.

| 파일 | 내용 |
|---|---|
| `REPRODUCTION_STATUS.md` | 세 연구의 재현·종결·검증 상태 표, 보고서 수치 대조 |
| `etf_domain_eda.md` | ETF 20종 Domain EDA (Phase 00/00.5) 요약 |
| `cross_asset_track_a.md` | Track A — KOSPI200 대비 상관 전환과 가격 사건 (부정적 결과) |
| `svr_garch_cusum_track_b.md` | Track B — Lee·Kim·Lee (2020) 재현 감사 (METHOD_FIDELITY_UNRESOLVED) |
| `SOURCE_TO_TARGET_MANIFEST.csv` | 이식 파일 단위 출처·해시·테스트 |
| `svr_garch_cusum_etf/` | **T11** — SVR–GARCH CUSUM 을 ETF 20종에 적용 (설계·데이터 카드·결과표·재현) |
| `window_study_w1/` | **W1** — CUSUM 검정창 선정 (03 대표 4종 · 04 전체 20종): 적격 0/4, 최적창 없음 · 종결 보고 `FINAL_03_04_RESEARCH_CLOSURE.md` |
| `03_04_연구계약.md` | W1 사전 연구계약 (실험 전 동결) |
| `proposals/` | 구현되지 않은 후속 연구 제안 (성과 없음) |
