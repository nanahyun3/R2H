# Autoencoder 피처 인계 계약 (12번 → AE)

- 원장: `outputs/t21/feature_store_n1/daily_cusum_features.parquet` (long, 키 ticker·date·experiment_id, 681,999 행, Git 제외) · 후보 wide: `ae_candidate_wide.parquet` (1,473일 × 28 열). 해시: `results/data_artifact_manifest.csv`. 스키마: `FEATURE_SCHEMA.json`.
- 결정표: `results/feature_catalog.csv` (KEEP · KEEP_WITH_CAVEAT · OPTIONAL · DROP_DUPLICATE · EXCLUDE_NONSTATIONARY · POSTHOC_ONLY).

## 규칙
1. **시점**: 모든 입력은 t 종가까지 관측 가능 (예측분산은 t−1 종가에 t 를 예측). `POSTHOC_*`·사후 CUSUM·k̂·11번 사건 라벨·미래 RV 는 입력 금지.
2. **연속값으로 넘긴다**: CUSUM 경보(이진)·p 값·`SIGNIFICANT` 표시는 넘기지 않는다 — 관측 귀무 부적합이고 합성 검출력이 크기 수준이다.
3. **결측은 결측으로**: `WINDOW_NOT_AVAILABLE`·`INSUFFICIENT_HISTORY` 날은 NaN + 마스크 채널. 0 이나 p=1 로 채우지 않는다.
4. **이월 길이 명시**: 긴 창 CoS(w120·w252) 는 '최근 w 일 안 변화' 기억 채널 — 창 길이를 메타로 함께 넘긴다.
5. **재학습 경계**: SVR 기반 피처는 `model_fit_id` 를 함께 넘기고, 재적합 직후 w 일의 CoS 는 모형 혼합 창임을 표시한다 (X-D6).
6. **척도**: e² 는 1 이 아닌 연도별 척도를 가진다 — AE 쪽에서 과거 기준 정규화 여부를 사전 등록한다.

## 1차 후보 (KEEP)
ret · rv5 · rv20 · rv60 · vhat_B1 · e2_B1 · cos_w20_B1 · cos_w60_B1 · cos_w120_B1 · cos_w252_B1(주의) · cos_raw_w60 · page_dn_B1 · P20_score · V20_two_score · M20_60_score · K60_score

## 급변 구간 정의 후보 (AE 학습 라벨 아님 — 사전 등록 대상)
- 11번 q20 실현변동성 구간(관측) 은 서술 참조로만. CUSUM 기반 정의는 검출력 부족으로 제안하지 않는다.
- 사전 등록 후보: (a) X1 자기정규화 Page 상방 경보(하루 극단형), (b) Page 하방 경보(분산 감소형), (c) 변화점 V20 q0.99 트리거 — 각각 2026 이후 맹검 확인 필요.
