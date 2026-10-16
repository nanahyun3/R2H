# STATUS — A 레인 (Scientific Methodology & Independent Assurance)

| 항목 | 값 |
|---|---|
| 브랜치 | `research/annual-a-method` (base `8414678`) |
| 인터프리터 | `SA/1012_Annual_SVR–GARCH-CUSUM/R2H/.venv/bin/python` + `PYTHONPATH=$W/src` (시작 게이트 통과: `r2h.__file__` = `$W/src/r2h/__init__.py`) |
| 현재 단계 | A-1 완료 → A-3 → A-2 |
| 갱신 | 2026-10-16 |

## 완료 산출물

| 단계 | 산출물 | 상태 |
|---|---|---|
| A-1 | `docs/annual_assurance/ANNUAL_METHOD_CONTRACT.md` | 완료 |
| A-1 검증 | `tests/assurance/test_fold_contract_real.py` (fold 420행·history_hash 360행 독립 대조), `tests/assurance/test_boundary_leakage_real.py` (실데이터 경계 누수) | 8 passed (6 s) |
| 실행 | `a_seq_1` (workers=1, `$W/outputs/t12/work/a_seq_1`) — 일별 잔차 독립 재계산용. 순차 실행 2회째 증거 후보 | 진행 중 |

## 발견 (A-1 단계)

- 충돌 K-1..K-4, 문서 D-1..D-2 → `ANNUAL_METHOD_CONTRACT.md §12`
- 1.3397 은 정확한 점근 5% 값이 아니다 (정확값 1.3581). 원문 표기값이다

## B 에게 필요한 수정 요청

`REQUESTS_TO_B.md` RQ-1..RQ-5 (모두 문서·서술 요청이다. 코드 변경 요청은 없음)

## 주의

- 지시서 §5 의 "10개 질문" 원문은 A 가 볼 수 있는 경로(C 워크트리, 상위 명세 폴더)에서 찾지 못했다
  - A 는 C 가 보낸 과제 지시에 열거된 항목으로 10개 질문을 재구성했다 (`ANNUAL_SCIENTIFIC_AUDIT.md` 머리말)
  - **C 확인 필요**
