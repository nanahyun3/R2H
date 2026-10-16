# 재실행 사전 기대 (Claude 인수, 03·04 재실행 전에 작성 · 2026-10-16)

## 인수 시점 사실 (직접 확인)

- Codex 의 03 실행(2026-10-16T10:23–10:26Z, 190 s)은 **R2H `.venv` 가 아닌 인터프리터**에서 돌았다. 03 첫 셀 출력은 `NumPy 2.5.0 · pandas 3.0.3 · scikit-learn 1.9.0` 이고, 이는 `~/.local/lib/python3.12/site-packages` 의 user-site 버전이다. R2H `.venv` 는 `numpy 2.5.4 · pandas 3.0.6 · scikit-learn 1.9.1` 이다.
  - 원인: 커널 명세 `R2H/.venv/share/jupyter/kernels/python3/kernel.json` 의 argv 가 `"python"` 이다. 그래서 커널이 PATH 에서 먼저 잡히는 python 을 쓴다.
- 04 실행은 7 s 만에 03/04 대표 4종 동등성 assert 에서 실패했다 (`first_pure_valid` NA mask). 실행된 04 노트북은 19:23 생성기 출력이고, 생성기는 19:25 에 수정됐다.
  - 현재 디스크의 03_real·04_real CSV 로 같은 비교를 다시 해 보면 PASS 다.
- 실행된 03 노트북에는 폰트 등록 셀과 코드 줄 주석이 없다 (옛 생성기 출력). 그래서 노트북 규칙 테스트 4건이 실패했다.
- Codex 상태는 `outputs/t13/codex_snapshot_20261016T_codex/` (SHA256SUMS 44개) 에 보존했다.

## 재실행 조건

R2H `.venv` 를 강제한다 (PATH 앞, `PYTHONNOUSERSITE=1`, 첫 셀 버전 assert). 설정·시드·반복 수·판정 규칙은 바꾸지 않는다. 생성기 변경은 주석·import 정렬·미사용 import 제거·버전 assert·그림 표현에 한한다.

## 기대

1. **검출기 합성** (numpy RNG·rolling_cusum 만 사용): `detector_*.csv` 4개가 Codex 스냅샷과 바이트 동일.
2. **적합 포함 합성** (scikit-learn SVR 1.9.0 → 1.9.1): 바이트가 다를 수 있다. 다르면 최대 수치 차이와 판정 열(any_alarm, detected_60d)의 변화를 보고한다.
3. **판정** `최적창_판정과_보류사유.csv`: 4개 창 모두 `비적격` 유지 (적격 0/4). 바뀌면 원인을 기록하되 규칙은 고치지 않는다.
4. **실측** 03_real·04_real: 임계값 입력(pipeline_thresholds)이 같으면 바이트 동일. 다르면 2 의 차이가 전파된 것으로 본다.
5. 04 의 03/04 대표 4종 동등성: PASS.
