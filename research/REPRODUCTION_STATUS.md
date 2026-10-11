# 연구 재현 상태 (2026-10-11 감사)

**기술적 종료(closure)** 와 **가설 입증(validation)** 은 별개 열이다. 재현 = 같은 입력 해시·코드로 다시 실행해 결과표가 일치함.
감사 환경: WSL2 Ubuntu 24.04 · Python 3.12.3 · numpy 2.4.6 · pandas 3.0.3 · scipy 1.18.0 · scikit-learn 1.9.0 · statsmodels 0.14.6 · 24 cores.

| 연구 | 원본 | 입력 해시 확인 | 재실행 결과 | Closure | Validation |
|---|---|---|---|---|---|
| ETF Domain EDA (Phase 00/00.5) | SA_ETF `d5c2f79` | raw 20/20 = `MANIFEST.csv` | 별도 clone 에서 테스트 4/4, `run_all_final.sh` 6개 STEP 모두 exit 0 (78 s). tracked csv·png **309/309 재생성** 후 **변경 0 (바이트 동일)**, 노트북 21개는 메타데이터만 변경 (출력 내용 차이 0) | CLOSED (재현 확인) | claim 16건: CONFIRMED 10 · WITH_LIMITATION 2 · REVISED 2 · CORRECTED 1 · DOWNGRADED 1 (원본 판정 유지) |
| Track A — Cross-Asset 상관 전환 vs 가격 사건 | SA_ETF `codex/r2h-track-a@a3f9e9b` (LOCAL_ONLY) | raw 20/20 (EDA 와 같은 MANIFEST) | 테스트 35/35. A1→A2→A3 **독립 2회** 실행: 파이프라인 결과표 43종 재생성(새 run_id) × 2 → 원본과 내용 동일 (`run_id` 열 제외). 집계표 `final_research_metrics.csv` 38값은 재생성된 RUN_MANIFEST 와 일치. 보고서 claim 29개 중 27 MATCH, 2 MISMATCH (아래) | CLOSED | **부정적 결과**: 상관 전환과 급등·급락의 근접은 같은 날 기계적 중복을 빼면 우연 수준. 상관 전환을 정답·조기경보로 쓸 근거 없음 |
| Track B — Lee·Kim·Lee (2020) SVR–GARCH CUSUM | 로컬 미커밋 패키지 (LOCAL_ONLY) | Yahoo 대체 3종 3/3 = `data_manifest.json` | 테스트 84/84. 실증 재실행 → `empirical_summary.json`·실증 csv·Figure 2–4 재생성, **바이트 동일** (Figure 1 3패널은 별도 스크립트라 미재실행). MC chunk 9개(400 반복, clip·raise·recursive 레인) 재생성 → 통계량·기각·위치 **완전 일치** | CLOSED (감사 종결) | **METHOD_FIDELITY_UNRESOLVED**: 원문 Tables 1–6 과 실증 통계량 미재현. 원문 값이 재현 95% CI 안에 든 셀: clip 1/45 · raise 9/45 · recursive 10/45 (jsonl 에서 독립 재계산 일치) |
| R2H Features/Contracts (이 브랜치) | 이 저장소 | 합성 데이터만 | `docs/provenance/PARITY.md` — 이식 함수 원본과 비트 동일 | 이 표의 상태는 CI·리뷰 후 갱신 | 탐지 성능 수치 없음 (정답 미승인) |

## Track A 보고서 수치 대조 — MISMATCH 2건

| claim | 보고서 | 재계산 | 판정 |
|---|---|---|---|
| "C3 확정까지 평균 11.1 달력일" (§Q9) | 11.1 | primary C3(b0.1, k10, Pearson) 기준 **13.4**; C3 전 변형(k5/k10/k20, 양 method) 평균이 11.1 | 문구 범위 불명확 → primary 로 읽으면 MISMATCH. 거래일 기준 확인 지연은 정의상 항상 k−1 = **9 거래일** (MATCH) |
| "모든 자산에서 lag 0 상관이 최대" (§Q7) | 모든 자산 | 261220(원유)은 lag 0 ρ 0.060 < lag +2 ρ 0.093 (\|lag −3..+3\| 전체표본) | MISMATCH — 모든 값이 0.1 미만이라 "선행·지연 관계 없음" 결론은 유지. \|ρ(±1)\| ≤ 0.11 은 MATCH |

lookahead 기계 검사 (MATCH): C·P 사건 전 행 `available_at ≥ candidate_at` · P4·P2_full·P5_q99 2,775행 모두 `parameter_set` 에 사후/look-ahead 표시 · P4 는 `available_at > candidate_at`.

나머지 MATCH 예: 148070 60일 C3 = 13건 · primary C3 111건 · 사건일 제거 재검정 L=0 근접 18→1, p<0.05 9→0/48 · 귀무검정 46,000행(검정 가능 45,280) ·
p<0.05 비율 L=0/5/10/20 = 11.2/8.0/6.8/5.1% · global BH q<0.10 = 299 · 1차 가족 586 중 3 · 148070 Pearson 전체 0.134, 2019 −0.404, 2026 0.369.

## EDA 오류 판정의 역류 검사

DX-13 (달러 폭락일 상승 "86%" → 정의에 따라 72–91% REVISED), DX-14 (148070 β 1.87 → 069500 기준 β 0.029 CORRECTED) 의
원래 수치(86%, β 1.87) 가 Track A·B 보고서·코드에 다시 쓰인 곳: **0건** (grep 결과 우연한 숫자 일치만 있음).

## 알려진 문서 불일치 (원본 수정 없이 기록)

- Track B README 는 "25 tests", 최종 보고서는 "84 passed" — 실제 재실행 84.
- Track A README 는 "34 tests" — 실제 35.
- Track A 보고서는 `event_null_tests.csv` 를 gitignored 라고 적었으나 원 브랜치 `.gitignore` 에 해당 규칙 없음 (워크트리에 untracked 로 존재).
