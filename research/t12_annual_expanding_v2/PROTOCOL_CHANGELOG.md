# T12 v2 — PROTOCOL CHANGELOG

명세(v1·v2)와 다르게 정한 것, 그리고 lock 이후의 변경을 기록한다. 지우지 않으며, 정정할 때는 새 행을 추가한다.

| ID | 날짜 | 구분 | 내용 | 이유 |
|---|---|---|---|---|
| C-01 | 2026-10-12 | 명세 대비 | 작업 브랜치는 `research/t12-annual-expanding` 이 아니라 `1012_Annual_SVR–GARCH-CUSUM` 이다 (원격에 이미 있고, `main` 과 같다. `origin/1012` 에서 fast-forward 로 시작한다) | 사용자 지정 |
| C-02 | 2026-10-12 | 명세 간 충돌 | 결과 폴더: v1 명세의 `research/t12_annual_expanding` 대신 v2 config 의 `research/t12_annual_expanding_v2` 를 쓴다 | v2 가 v1 보다 우선 |
| C-03 | 2026-10-12 | 명세 대비 | 설정 파일을 YAML 이 아니라 JSON 으로 둔다 (`configs/t12_annual_expanding_v2.json`) | R2H lock 에 PyYAML 이 없다. 의존성과 `uv.lock` 을 바꾸지 않기 위해서다 |
| C-04 | 2026-10-12 | 명세 대비 | 모듈 경로는 `src/r2h/annual_expanding/` 그대로 쓰되, 파일 분할은 명세 제안과 다르다 (folds·fit·diagnostics·calibration·worker·pipeline·synthetic·profile) | 기능 단위로 묶었다 |
| C-05 | 2026-10-12 | 명세 미정 → 결정 | B 정책의 warm 문맥·in-sample 보정 풀은 A 의 사전 연도 재표준화 잔차를 쓴다 | T11 `residuals("B")` 관례와 같다. B 재귀를 과거 전체에 다시 돌리면 정의가 하나 더 생긴다 |
| C-06 | 2026-10-12 | 명세 미정 → 결정 | 이력 전략은 학습 표본만 바꾸고, 특징 문맥(lag 입력)은 실제 직전 관측으로 통일한다 | frozen2019 를 CARRY 로 그대로 쓰면 2019 말과 y 초가 붙는 잘못된 문맥이 생긴다 |
| C-07 | 2026-10-12 | 명세 미정 → 결정 | 정책 간 M 축 비교는 세 정책이 모두 유효한 날의 교집합에서 한다. 자기 coverage 는 따로 적는다 | 명세 §8.1 #5 |
| C-08 | 2026-10-12 | 명세 미정 → 결정 | Ljung–Box·ARCH-LM 은 numpy/scipy 로 직접 구현한다. statsmodels 0.14.6 과의 대조는 1회만 하고 로그로 남긴다 (CI 제외) | 의존성 불변 |
| C-09 | 2026-10-12 | 명세 미정 → 결정 | 블록 부트스트랩(순환, L=10)은 **다른 귀무**(단기 의존 보존)의 민감도로만 보고한다 | 명세 §2.5-3: iid 귀무와 같은 H0 가 아니다 |
| C-10 | 2026-10-12 | 명세 대비 | oracle(`LOOKAHEAD_DIAGNOSTIC_ONLY`)은 만들지 않는다 | 명세에서 선택 사항이고, 주 결과에서도 금지다 |
| C-11 | 2026-10-16 | lock 이후 문서 정정, 수치 무영향 | `normal_mc`·`asymptotic` 용 정규 참조 표본(`worker.py:75–90`)의 seed 키는 풀과 무관하므로 `(study_id, n, reps, 용도)` 뿐이다 (ticker·year·policy 없음). LOCK L5 의 seed 규칙과 달리 이 표본은 ETF 간에 공유되고, 그 결과 MC 오차가 ETF 간에 공통이다. 코드는 바꾸지 않는다 | A RQ-1 (계약 K-2). 코드 주석이 이미 C-11 을 인용하고 있었다 |
| C-12 | 2026-10-16 | lock 이후 문서 정정, 수치 무영향 | 귀무 기대 에피소드의 귀무 표본 길이 = **검정연도 공통 거래일 수** (비양수 분산일 포함; `worker.py:387,390` 의 `n_days`). LOCK L5 의 `n_test` 표기를 이 정의로 읽는다. 이번 자료에서 두 값은 같다 | A RQ-3 (계약 K-1) |
| C-13 | 2026-10-16 | 명세 대비 미구현 (lock 이후 기록, 수치 무영향) | `SPEC B§5` 의 `CROSS_YEAR_EPISODE` 표시가 구현되지 않았다. CARRY 모드에서 연말–연초에 걸친 에피소드는 두 해에 각각 1건으로 셀 수 있다. 주 분석(w60 PURE)은 연도 안에서만 세므로 영향이 없다 | A RQ-4 (계약 K-3) |
| C-14 | 2026-10-16 | 명세 대비 미구현 (lock 이후 기록, 수치 무영향) | `SPEC B§5` 의 2020 `w=252` `INSUFFICIENT_CALIBRATION` 표시가 구현되지 않았다. 2020 의 보정 풀은 244–245개로 252보다 짧다. w=252 는 PURE 가 구조적으로 불가(L4)하고 주 분석이 아니다 | A RQ-4 (계약 K-4) |
| C-15 | 2026-10-16 | lock 이후 문서 정정, 수치 무영향 | 1.3397 은 원문(Lee·Kim·Lee 2020) 표기 임계값이다. 점근 5% 정확값(sup\|Brownian bridge\| 95% 분위 1.3581)이 아니다. 극한에서 P(>1.3397)≈0.055 이고, n≈245 iid 정규에서 size≈0.040 이므로 이 표본 크기에서는 보수적이다. 설정 키 `asymptotic_critical_5pct`·결과표 열 `asymptotic` 이름은 유지한다. methods_part.md II.5 를 고쳤다 | A RQ-2 (감사 Q4) |
