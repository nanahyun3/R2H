# REPRODUCIBILITY_AUDIT — T11 SVR–GARCH CUSUM 최종 재평가

감사일 2026-10-12 · 기준 커밋 `a346faf78ff47b2695fab438f7397d7958b8d655` (R2H `1012`, 이 브랜치 `1012_SVR-GARCH-CUSUM` 의 분기점)

## 1. 데이터 버전

| 항목 | 값 | 확인 방법 | 상태 |
|---|---|---|---|
| 원시 시세 | FinanceDataReader 0.9.202 KRX 일봉 20종, `SA/ETF_EDA_SCAFFOLD/data/raw/*.csv` (저장소 밖) | `ETF_RAW_DIR` 로 로드 | — |
| 종가 해시 | 20/20 일치 (`research/svr_garch_cusum_etf/reference_close_sha256.csv`) | `load_close_panel` 이 `Date,Close` 원문 sha256 대조, 불일치 시 `DataVersionDiffers` | VERIFIED (재실행 2회 모두 통과) |
| data_version | `5f20e3e0073b521a` | `results/run_manifest.json` | VERIFIED |
| 수익률 | 1,902 공통 거래일 (2019-01-03 ~ 2026-10-02), 261240 DQ 2일 NaN | `t11_state.npz` | VERIFIED |

## 2. 실행 환경

| 항목 | 환경 1 — 루트 `.venv` | 환경 2 — R2H `uv.lock` (`uv sync --frozen`) |
|---|---|---|
| Python | 3.12.3 | 3.12.3 |
| numpy / pandas | 2.4.6 / 3.0.3 | 2.5.4 / 3.0.6 |
| scikit-learn / scipy | 1.9.0 / 1.18.0 | 1.9.1 / 1.18.1 |
| OS | WSL2 Ubuntu 24.04, 24 cores | 같은 머신 |

보고서 제작 도구: python-docx 1.2.0 · latex2mathml 3.81.1 · pymupdf 1.28.2 (루트 `.venv`, `requirements-report.txt`) · Microsoft Word (Windows, COM — PDF 내보내기와 목차·쪽 번호 필드 갱신) · Office `MML2OMML.XSL` (수식 변환).

## 3. 실행 명령과 결과

| # | 명령 (R2H 루트) | 결과 | 증거 | 상태 |
|---|---|---|---|---|
| 1 | `ETF_RAW_DIR=… PYTHONPATH=src .venv/bin/python scripts/run_svr_garch_cusum_etf.py --out <tmp>` (환경 1) | 결과표 9종 **바이트 동일** · `run_manifest.json` 은 패키지 버전·실행 시간 필드만 다름 · `t11_state.npz` 바이트 동일 · 155 s | `analysis/repro_logs/rerun1_*` | VERIFIED |
| 2 | `uv run --frozen python scripts/run_svr_garch_cusum_etf.py --out <tmp>` (환경 2) | 결과표 9종 **바이트 동일** · manifest 는 실행 시간만 다름 · 143 s | `analysis/repro_logs/rerun2_*` | VERIFIED |
| 3 | `uv run --frozen pytest -q` (환경 2) | **98 passed** | `analysis/repro_logs/pytest_uvlock.txt` | VERIFIED |
| 4 | `pytest -q` (환경 1) | 수집 실패 — `hypothesis` 미설치 (환경 문제, 코드 문제 아님) | `analysis/repro_logs/pytest_rootvenv_FAILED_import.txt` | 기록 |
| 5 | `scripts/01_recompute.py` | 사후 검정 60행·임계값 200행·이동창 200열·연도 블록 320행 재계산, 결과표와 차이 최대 5×10⁻⁶ (CSV 6자리 반올림) · k̂ 60/60 · 기각 60/60 일치 | `analysis/*.csv`, `recompute_claims.json` | VERIFIED |
| 6 | 귀무 경보율 재계산 (같은 seed·salt·sims=100) | 차이 최대 0.0013 회/년 — CSV 로 반올림된 임계값을 다시 쓰면서 경계 사례가 바뀐 것 | `analysis/zone_rates.csv` `null_diff` | VERIFIED (반올림 효과로 설명) |
| 7 | `scripts/02_extension.py E1 … E6` | E1–E6 완료 (E2 1,000회 57 s, 20 프로세스) | `extension/`, `extension_run_log.json` | VERIFIED (EXTENSION) |
| 8 | `scripts/03_claims.py` → `04_figures.py` → `05_build_docx.py` → `06_export_pdf.ps1` | 그림 11종 + 재사용 2종, DOCX (표 19 · 그림 13 · OMML 수식 6) → Word 로 필드 갱신 → PDF 32쪽 | 이 폴더 | VERIFIED |
| 9 | `scripts/07_check_consistency.py` | claim 값 186개 DOCX·PDF 모두 존재 · 장·절 52개 순서 일치 · 그림 1–13·표 1–19 연속 · PDF 글꼴 전부 임베드 (맑은 고딕, Cambria Math 등) → **PASS** | `analysis/consistency_check.json` | VERIFIED |

그림 생성은 matplotlib 글리프 누락 경고를 오류로 처리(`-W error::UserWarning`)해 통과했다. PDF 는 전 쪽을 110 dpi 이미지로 렌더해 잘림·글꼴·수식·표·캡션을 육안 확인했다.

## 4. 시점 무결성 (E4)

069500, 검정 구간 t₀ = 2025-08-22 이후 수익률만 ×3 → ĝ 동일, t₀ 이전 정책 A·B 잔차·기준선 잔차·5개 창 이동창 통계량 **17/17 비트 동일**.
대조: 적합 구간 교란 시 ĝ 와 검정 구간 잔차 모두 변경 — 적합 구간 정책 A 값은 설계상 in-sample (파라미터 look-ahead).

## 5. 재실행하지 않은 범위 (NOT_REEXECUTED)

| 범위 | 이유 | 보고서 처리 |
|---|---|---|
| Track B 원 논문 Monte Carlo 전체 (n=1000/2000, raise·recursive 1,000회) | 원 감사(2026-10-11) 범위 밖, 계산량 | REPORTED 로 인용 (원문 값 CI 포함 셀 clip 1/45 · raise 9/45 · recursive 10/45) |
| Track B 실증 3종 (S&P500·KOSPI·KRW/USD) | 원 감사에서 바이트 동일 재현 확인됨 | REPORTED |
| T11 노트북 실행 | 결과표가 바이트 동일하므로 노트북 출력은 같은 입력 — 이번 보고서는 노트북을 쓰지 않음 | 해당 없음 |
| 기존 사건 근접 결과 (`overlap_metrics.csv` 등) | 이번 보고서의 판단 근거에서 제외 (재현 자체는 #1·#2 바이트 동일에 포함) | 제외 사유만 기술 |

## 6. 결정성과 원문 재현의 구분

- **결정성 (VERIFIED)**: 같은 코드·같은 자료·같은 seed → 같은 결과표 (2개 환경).
- **원 논문 수치 재현 (UNRESOLVED)**: Track B `METHOD_FIDELITY_UNRESOLVED`. 이 보고서의 ETF 결과는 "원 논문 방법의 결과" 가 아니라 "T11 프로토콜의 결과" 다.

## 7. 다시 만들기

```bash
cd R2H                                    # 이 브랜치 체크아웃
uv sync --frozen --extra dev --extra notebook --extra research
ETF_RAW_DIR=<원시 시세 폴더> uv run python scripts/run_svr_garch_cusum_etf.py   # outputs/cache/t11_state.npz 생성
D=deliverables/R2H_T11_CUSUM_Final_Review/scripts
uv run python $D/01_recompute.py && uv run python $D/02_extension.py
uv pip install python-docx==1.2.0 latex2mathml==3.81.1 pymupdf==1.28.2   # 보고서 도구 (R2H 의존성에는 넣지 않음)
uv run python $D/03_claims.py && uv run python $D/04_figures.py && uv run python $D/05_build_docx.py
# Windows Word 가 있는 환경에서: powershell.exe -ExecutionPolicy Bypass -File 06_export_pdf.ps1 -Docx <docx> -Pdf <pdf>
uv run python $D/07_check_consistency.py
```

`05_build_docx.py` 는 `MML2OMML.XSL` 경로가 필요하다 (`MML2OMML_XSL` 환경변수, 기본값은 WSL 에서 본 Office 설치 경로).
