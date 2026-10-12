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
