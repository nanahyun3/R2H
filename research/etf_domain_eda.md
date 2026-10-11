# ETF Domain EDA — Phase 00 / 00.5 (SA_ETF)

- 원본: [Siegfriex/SA_ETF](https://github.com/Siegfriex/SA_ETF) `main` = `d5c2f79` · `reports/EDA_EVIDENCE_CLOSURE.md`, `reports/CLOSURE_MANIFEST.json`, `reports/CANONICAL_PATCH_NOTE.md`
- 입력: 국내 상장 ETF 20종 일봉, 2019-01-02 ~ 2026-10-02 (각 1,903행), FinanceDataReader 0.9.202. sha256 은 SA_ETF `data/raw/MANIFEST.csv`. 원시 파일은 공개하지 않는다.
- 상태: **CLOSED** · 2026-10-11 별도 clone 재실행에서 csv·png 바이트 동일 (REPRODUCTION_STATUS.md).

## 결론 중 R2H 가 쓰는 것

| 항목 | 내용 | 판정 |
|---|---|---|
| 동일 지수 중복 | KOSPI200 추종 069500·102110·122630·114800 은 독립 신호가 아님 → 사건 1건으로 셈 | 계약에 반영 (HANDOFF) |
| 변동성 스케일 | ETF 간 변동성 차이가 커 고정 % 임계값은 자산마다 의미가 다름 → r/σ 같은 스케일 정규화 점수 사용 | `vol_scaled_return` |
| 수정 판정 DX-13 | "달러는 주식 폭락일 86% 상승" → 폭락일 정의에 따라 72–91% (REVISED) | 원 86% 미사용 확인 |
| 수정 판정 DX-14 | 148070 β 1.87 은 proxy(153130) 분모 극소 artifact → 069500 기준 β 0.029, ρ 0.134 (CORRECTED) | 원 1.87 미사용 확인 |
| 강건성 (원 `CLOSURE_MANIFEST.json` 판정, 재실행으로 표 바이트 동일 확인) | 측정 80건: ROBUST 54 · DEFINITION_DEPENDENT 12 · FRAGILE 4 · COUNTEREXAMPLE 3 · SECONDARY 2 (+ addendum) | 원본 판정 |

## 한계 (원본 §5 요약)

유니버스는 현재 상장·규모 기준 PROVISIONAL 20종 (survivorship) · FDR Close 의 분배 조정은 추정 · 2026 은 탐색에 이미 쓰인 구간 · 범위 밖: 뉴스, PELT, 예측, 트레이딩 에이전트.
