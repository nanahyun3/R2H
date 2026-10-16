# REQUESTS_TO_B — A → B 수정 요청 (C 중계)

형식: `RQ-n · 대상 파일:줄 · 반례/실패조건 · 요청`. 줄 번호는 base `8414678` 기준이다.
A 는 `src/`·`research/`·`notebooks/`·`scripts/` 를 수정하지 않는다.
"코드 변경" 요청은 결과 수치를 바꿀 수 있다. 그런 요청은 **lock 이후 변경**이므로 `PROTOCOL_CHANGELOG.md` 에 run ID 와 함께 기록해야 한다. 원 결과(seq_golden)와 섞지 않는다.

| RQ | 대상 파일:줄 | 반례 / 실패조건 | 요청 | 결과 영향 |
|---|---|---|---|---|
| RQ-1 | `src/r2h/annual_expanding/worker.py:75-90` · `PROTOCOL_CHANGELOG.md` | 주석이 `C-11` 을 인용하지만 CHANGELOG 는 C-10 에서 끝난다. normal_mc·asymptotic 귀무 표본 seed 키에 ticker·year·policy 가 없다. 이는 `LOCK:58` seed 규칙과 다르다 (계약 K-2) | 코드는 바꾸지 않는다. CHANGELOG 에 C-11 행을 추가한다 (내용: 정규 참조 표본은 풀과 무관하므로 (n, reps, 용도) 로 공유, 그 결과 ETF 간 MC 오차가 공통). 노트북 방법 절에도 한 줄 적는다 | 없음 (문서) |
| RQ-2 | `research/t12_annual_expanding_v2/report/methods_part.md` II.5 표 · 노트북 방법 절 | 1.3397 을 "대표본 점근" 이라고 부른다. sup\|Brownian bridge\| 의 정확한 95% 분위는 1.3581 이고, 극한에서 `P(>1.3397)=0.0552` 다. n≈245 iid 정규에서는 size 가 0.040 이고, 1.3397 은 n=5000 유한표본 95% (1.3396) 와 거의 같다 (감사 Q4) | "원문(Lee·Kim·Lee 2020) 표기 임계값. 점근 5% 정확값(1.358)이 아니며 n≈245 에서 보수적" 으로 고친다. 열 이름 `asymptotic` 은 유지해도 된다 | 없음 (서술) |
| RQ-3 | `worker.py:387,390` | `LOCK:57` 은 귀무 표본 길이를 `n_test` 로 정의하는데, 코드는 `n_days` 를 쓴다 (계약 K-1) | 노트북·CHANGELOG 에 "귀무 표본 길이 = 검정연도 공통 거래일 수 (비양수 분산일 포함)" 로 정의를 명시한다. 이번 자료에서는 수치가 같다 | 없음 |
| RQ-4 | `worker.py:397-463` · `PROTOCOL_CHANGELOG.md` | `SPEC B§5` 는 `CROSS_YEAR_EPISODE` 표시와 2020 `w=252` 의 `INSUFFICIENT_CALIBRATION` 표시를 요구한다. 둘 다 구현되지 않았다 (계약 K-3, K-4) | 코드는 바꾸지 않는다. CHANGELOG 에 "명세 대비 미구현" 행 2개를 추가하고, 노트북 제한사항에 적는다 (CARRY 연말-연초 에피소드는 두 해에 각각 1건으로 셀 수 있다. 2020 w=252 보정 풀은 244–245개로 252보다 짧다) | 없음 (주 분석은 w60 PURE) |
| RQ-5 | `report/methods_part.md` II.2 | "2019 한 해(245일)도 172/73" 이라고 적었다. 그러나 261240 은 DQ 결측 2일 때문에 243일, 170/73 이다 | 노트북에 261240 예외를 적는다 | 없음 |
| RQ-6 | `research/t12_annual_expanding_v2/results/summary_by_year_policy.csv` (생성: `scripts/t12_*`) · 노트북 표 | 2020 은 iid_prequential 이 `NOT_ESTIMABLE` 인데 `n_reject_iid_prequential = 0` 으로 나온다 (감사 Q5, R-10) | 노트북 표에서 `n_prequential_estimable = 0` 인 칸은 NA 로 표시한다. 원 CSV 는 바꾸지 않는다 | 없음 (표시) |
| RQ-7 | `src/r2h/annual_expanding/profile.py:127-138` · 노트북 종합 상태 절 | 신호 게이트 = 연간 기각 OR w60 PURE 에피소드 ≥1. 귀무에서 w60 쪽이 셀당 약 0.68 의 확률로 켜진다. 실제 신호 290개 중 217개가 w60 단독이다 (Q3, R-2) | 코드는 바꾸지 않는다 (사전 고정). 노트북에 이 수치를 적고, `MULTIFACTOR` 등 라벨이 "귀무에서도 흔한 신호" 에 붙는다는 점을 명시한다. 연간 기각만으로 켜진 셀 수(A 11·B 28·base 34)도 함께 보인다 | 없음 |
| RQ-8 | 노트북 제한사항 · 재현성 절 | proxy 를 수학적으로 같은 다른 연산 순서로 계산하면 (ULP 수준 차이) 305540 2022 의 하이퍼파라미터가 바뀐다. B 판정은 1/140 뒤집힌다 (133690 2020) (Q2 RISK-N1, `out/a2_independent_svr.txt`) | 바이트 결정성은 같은 코드·같은 연산 순서에서만 성립한다고 적는다. B 개별 판정 (특히 T≈1.34) 의 수치 불안정성을 적는다. 튜닝 근거로 쓰지 않는다 | 없음 |
| RQ-9 | `PROTOCOL_CHANGELOG.md` | lock 이후 실데이터 파일럿 `pilot_g3` (069500·102110·148070, 11:16, `cb9e9ca+dirty`, code_sha `204efe33`) 이 실행됐다. 그 뒤 코드가 바뀌었는데 (`eb612bf6`) 기록이 없다. 결과표는 바이트 동일하다 (부기 V-2) | CHANGELOG 에 사실 행을 추가한다 (실행·코드 해시 변화·결과 동일 확인) | 없음 |
| RQ-10 | 노트북 해석 절 | A 비기각을 안정성으로, base 기각을 구조변화로 읽을 위험이 있다 (Q6, R-3·R-4) | 다음을 명시한다: A 파이프라인 검정력 0.085 (×2), base 는 군집 귀무 size 0.51–0.58, 정책 비교는 같은 숫자 임계값 아래의 비교일 뿐이다 | 없음 |
| RQ-11 | 노트북 T11 비교 절 | base 연간 T 는 T11 `yearly_blocks` 와 같은 계산이다 (140/140 일치, `T11_T12_COMPARISON_CONTRACT.md §2`) | "T11 과 일치 = 재현/확인" 이라고 쓰지 않는다. 비교 불가 목록 N-1..N-8 을 따른다 | 없음 |
