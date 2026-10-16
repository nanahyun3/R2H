# STATUS — A 레인 (Scientific Methodology & Independent Assurance)

| 항목 | 값 |
|---|---|
| 브랜치 | `research/annual-a-method` (base `8414678`) |
| 인터프리터 | `SA/1012_Annual_SVR–GARCH-CUSUM/R2H/.venv/bin/python` + `PYTHONPATH=$W/src` (시작 게이트 통과) |
| 현재 단계 | A-1 · A-3 · A-2 완료. A-4 는 C 요청을 기다리는 중 (B-4 노트북 완료 후) |
| 갱신 | 2026-10-16 |

## 완료 산출물

| 단계 | 산출물 |
|---|---|
| A-1 | `ANNUAL_METHOD_CONTRACT.md` |
| A-3 | `T11_T12_COMPARISON_CONTRACT.md` · `scripts/a3_t11_t12_base_check.py` |
| A-2 | `ANNUAL_SCIENTIFIC_AUDIT.md` (질문 번호·문구 = `DIRECTIVE_EXCERPTS.md` §5 원문) · `scripts/a2_*.py` · `out/*` |
| 테스트 | `tests/assurance/` 8개 — `pytest tests` 전체 134 passed (22 s) |
| 실행 | `a_seq_1` (순차, 607 s, git `8414678`). 결과표 8/9 바이트 동일, `fold_manifest` 는 `git_sha` 열만 다르다 |

## 판정 요약

Q1 OK · Q2 OK (+RISK-N1 수치 취약성) · Q3 OK(조건부) · Q4–Q10 RISK · 부기(사후 튜닝) VIOLATION 절차·경미 3건 (V-1..V-3, 결과 영향 없음), 튜닝 증거 없음

## B 에게 필요한 수정 요청

- RQ-1..RQ-5: C 승인 완료, B 반영 중
- RQ-6..RQ-11: 신규 (A-2). 모두 문서·표시 요청이며 코드 변경은 없다
