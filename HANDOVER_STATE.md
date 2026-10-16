# T12 인수 상태 (2026-10-16, 로컬 재현 검증 완료)

## 직접 확인한 근거

- Git root: `/home/sieg/projects-wsl/hongik_univ_26_2/SA/1012_Annual_SVR–GARCH-CUSUM/R2H`. 상위 `SA/`는 별도 Git root이고, 수업 루트는 Git 저장소가 아니다.
- 인수 기준: C 통합 `76e8b03b65e1e44e79cc41d3344b976f98c9c177`; 새 브랜치 `1016_Annual_SVR-GARCH-CUSUM_Final`은 이 커밋에서 분기했다. A의 `c33f700`은 C 이후 조건부 노트북 리뷰와 숫자 대조 문서를 추가했다. B의 최종 `871dc62`는 C에 포함되어 있다.
- 기존 A/B/C 작업트리는 보존했다. C 작업트리는 실행 출력이 저장된 노트북 한 파일이 수정 상태다. 이 파일은 새 브랜치로 복사하거나 덮어쓰지 않는다.
- C 노트북 JSON은 56셀, 코드 셀 실행번호 1~27 및 출력이 저장돼 있고 오류 출력은 0개다. C `c_nb_1`의 `notebook_summary.json`은 `EXECUTED`, 파이프라인 648.3초, `76e8b03`, code SHA `eb612bf6c11f15f8`을 기록한다. 현재 세션에서 `scripts/t12_semantic_fingerprint.py`로 C 병합 결과를 동결표와 직접 대조해 Semantic·Verdict **PASS**, Byte **FAIL**(fold_manifest의 `git_sha`, run_manifest)를 확인했다. C 그림 manifest는 32행이다. 따라서 C의 최종 full 계산·저장 상태는 **PASS WITH LIMITATIONS**다. C 그림 픽셀 품질은 별도 최종 그림 검수 대상이다.
- 원본 프로토콜 `PROTOCOL_LOCK.md` SHA256: `e92fae99ed05e0135b10a2a692cf703214951ae5c8036cc02a66944ed3610abf`. 기존 `results/annual_posthoc.csv` SHA256: `5d8910821e20de5f2c16ccbcd48e98bed92c2c9de14160b89ca592df4867a3c`. 00 새 커널 실행에서 원자료 22개 SHA와 data version `5f20e3e0073b521a`를 모두 대조했다.
- 인수 시 A4의 RQ-12~16은 `scripts/t12_build_reproduction_notebook.py` 마크다운에 미반영이었다. 최종 브랜치 생성기에서는 size 0.036/0.035와 보정·블록 수치, `derive_seed`·`moving_square_proxy` 함수 위치, 원문값 1.3397 설명, 군집 0.39–0.58, 2020/2026 기간 표시를 정정했다. 정정판 00·01·02 저장 출력 및 02 새 커널 재실행을 확인했다.
- 새 01 full 순차 실행 `b_nb_20261016T181251`은 20/20 ETF를 완료했고, 635.5초가 manifest에 기록됐다. 기존 동결표 대비 Semantic·Verdict PASS, Byte 9/10 PASS·1/10 FAIL(provenance)다. 새 발표 그림은 6쌍 PNG/SVG를 별도 제작·픽셀 검수했다. 현재 테스트는 146 passed다.
- 새 작업트리에는 `data/raw`와 `.venv`가 없다. 기존 R2H `.venv` 및 원자료를 읽기 전용으로 연결하되 원본 산출물은 수정하지 않는다.

## 기존 로그의 주장 (현 세션의 PASS 아님)

- B 상태 문서는 `b_nb_20261016T163946` full run 663초, Semantic·Verdict 일치, PNG 32/32 바이트 일치, pytest 134 passed를 보고한다.
- A4는 B 노트북의 수치 24묶음 중 23묶음 일치, RQ-12 한 건의 범위 오류 및 RQ-13~16 표시·인용 문제로 조건부 승인했다.
- C 결정 로그는 순차·병렬 결과의 Byte 차이를 provenance 열(`git_sha`)과 manifest로 분리하고 Semantic·Verdict PASS라고 기록한다.

## 종결 계획과 경계

- `notebooks/00_환경과_데이터_검증.ipynb`, `01_연간확장_실험재현.ipynb`, `02_가설검증_강건성_심층해석.ipynb`가 최종 공식본이다. 기존 B 생성기의 코드와 출력은 재사용하며, 중복 계산 구현을 만들지 않는다. 이름 변경에 맞춰 생성기·실행 스크립트·README를 함께 정리한다.
- RQ-12~16은 문구·그림 표시 수정으로 처리 가능하다. 원본 수치·정책·귀무모형·임계값의 변경은 방법론 변경이며 이 릴리스에서 수행하지 않는다. 정확 점근값 1.3581은 설명용 비교이고 원 프로토콜의 1.3397 판정은 유지한다.
- 통계적 유효성은 계산 재현과 별도다. 원논문 충실 재현, 군집 귀무 크기, 2026 비블라인드, 온라인 급등 탐지는 미해결로 남긴다.
