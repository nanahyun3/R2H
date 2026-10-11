# 코드 출처 (provenance)

원본은 개인 연구 저장소 [Siegfriex/SA_ETF](https://github.com/Siegfriex/SA_ETF) (MIT, © 2026 Siegfriex — 이식자 본인) 와 그 로컬 작업물이다.
저장소 전체를 복제하지 않고 아래 함수만 옮겼다. 파일별 행 단위 목록: `research/SOURCE_TO_TARGET_MANIFEST.csv`.

## 원본 식별

| 출처 | 식별자 | 원격 공개 여부 (2026-10-11) |
|---|---|---|
| ETF Domain EDA (Phase 00/00.5) | SA_ETF `main` = `d5c2f792022d3c8efdbc52bdecd246b04bf32c45` | 공개 |
| Track A (Cross-Asset) | SA_ETF 브랜치 [`codex/r2h-track-a`](https://github.com/Siegfriex/SA_ETF/tree/codex/r2h-track-a) @ `a3f9e9b14a6980c84d2d417c7024e97c3e0eeee5` | 공개 (2026-10-12 push, 커밋 그대로) |
| Track B (SVR–GARCH CUSUM 재현) | SA_ETF 브랜치 [`research/track-b-paper2020`](https://github.com/Siegfriex/SA_ETF/tree/research/track-b-paper2020/research/track_b_paper2020) @ `031157d27a715f108acee55d1dac30bd69fac78e`, 경로 `research/track_b_paper2020/` | 공개 (2026-10-12) — 원래 미커밋이던 로컬 패키지를 정리해 커밋. 반복별 MC·ablation 결과와 Yahoo 원시 시계열은 제외 (`EXCLUDED_ARTIFACTS.md` 에 digest) |

두 출처 모두 2026-10-12 에 SA_ETF 원격 브랜치로 공개했다 (`main` 은 그대로). 아래 sha256 은 공개 브랜치의 같은 파일과 일치한다.

## 파일 대응

| R2H 파일 | 원본 파일 (sha256) | 변경 |
|---|---|---|
| `src/r2h/detection/paper2020_cusum.py` | Track B `research/track_b_paper2020/src/paper2020/cusum.py` (`bb686701639743abb1e6e36f31ae1223bc04b03ad419db1f48bc910374aac0fd`) | **없음 — 바이트 동일** (ruff format·일부 lint 제외 설정) |
| `src/r2h/features/correlation.py` | Track A `src/r2h/research_a/rolling_correlation.py` (`2ad8df279d5bd4ef4031f620cf599076c56e1b9ee4474a3f2dbf6660cc6b20d6`, = `a3f9e9b` 의 blob) | `rolling_corr`·`RegimeRule`·`sign_regimes`·`null_band` 만. 빈 창 경고 회피용 마스크 합, `confirm_lag_days` 직접 계산, 입력 검사 추가 — 수치 동일 (PARITY.md) |
| `src/r2h/evaluation/null_tests.py` | Track A `src/r2h/research_a/event_matching.py` (`f1dda08a6f7ab5d3ddfdc021e2a15ac618de8dfe8e8e4d732e438cf12b80f5e5`) | `proximity_count`·`circular_shift_test_fast`·`bh_qvalues` — 계산식 변경 없음, 서식만 |
| `src/r2h/features/price.py` | Track A `data.py::log_returns` (`a12b2542…`), `price_events.py` P1 점수 (`2fb4ccab…`) | 재작성 (행 보존형 `log_returns`, 일반화한 `vol_scaled_return`). 수치 동일 (PARITY.md) |
| `tests/unit/test_detection.py::test_paper_cusum_golden_vector` | Track B `tests/test_core.py::test_cusum_golden` (`650e1885…`) | 같은 golden 값 |
| 그 밖의 `src/r2h/**` | — | 1012 신규 작성 (계약·매칭·지표·분할·백테스트 스키마·참조 탐지기·합성 데이터) |

## 옮기지 않은 것과 이유

- SVR–GARCH 적합(`svr_garch.py`, scikit-learn), DGP·Monte Carlo 러너: 원문 수치 미재현 상태(METHOD_FIDELITY_UNRESOLVED)라 팀 기준선에 넣지 않음. SA_ETF 쪽 원본 참조.
- Track A 파이프라인(a1/a2/a3)·노트북·사건 정의 전체(C1–C5, P1–P5): 연구 재현용이며 결론이 부정적. 재사용 가능한 함수만 옮김.
- ETF EDA 노트북 20종·그림 243장·보고서 DOCX/PDF: SA_ETF 에 공개되어 있으므로 링크만.
- 원시 시세 (FinanceDataReader 20종, Yahoo 3종), 논문 PDF: 재배포 권리 미확인 → 해시·DOI 만.
