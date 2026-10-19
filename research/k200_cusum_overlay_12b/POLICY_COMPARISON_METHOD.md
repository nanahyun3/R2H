# 정책 비교 방법 (12B)

- 쌍: 등록부의 모든 (parent_experiment_id → experiment_id) 쌍 (463 − 루트 1 + 사후 제외 = 등록부 기준 전수). 쌍마다 `changed_variable` 과
  부모·자식 원장 열(policy_id, detector_type, window_w, reset_rule)을 대조해 실제로 바뀐 열이 하나인지 기록 (G4, `ofat_observed`).
- 쌍별 지표: 공통 유효일 · 부모만 · 자식만 유효일 · 공통일 원시 T 차이(중앙값·최대 절댓값) · 과거 전용 백분위 차이 · Spearman ρ ·
  이벤트 단계별 백분위 차이 · 앵커 EXPANDING / CONTRACTING 국면의 백분위 차이 · 경보일(α=0.05) 차이.
- 공식이 다른 쌍(detector 변경): 원시 차이는 `RAW_NOT_COMPARABLE` 표시, 백분위 척도로만 비교.
- 초기화 쌍: 추가된 NA 일수(자식만 결측)와 공통일 통계량 차이를 분리 — "관측 공백 추가" 와 "정보 변화" 를 구별.
- 모든 결과는 관측 서술 (`NULL_MODEL_INVALID_DESCRIPTIVE`). 대표 쌍 그림은 원장 배열과 수치 일치 검사(G6).
