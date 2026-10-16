# T12 최종 재현 보고 — 2026-10-16

## 실행 계약과 시간

- 기준 브랜치: `1016_Annual_SVR-GARCH-CUSUM_Final`; 인수 기준 C `76e8b03b65e1e44e79cc41d3344b976f98c9c177`, A 후속 리뷰 cherry-pick `9afc63e95873063b980f57fe0a1f21cb5e251394`. 최종 릴리스 커밋은 이 보고가 작성된 뒤 생성되므로 `git rev-parse HEAD`로 확인한다.
- 프로토콜 `T12v2-lock-1`, 설정 해시 `0a9fbaa9c5776ebc`, 데이터 버전 `5f20e3e0073b521a`, 코드 해시 `eb612bf6c11f15f8`, 원본 run `b_nb_20261016T181251`, 순차 worker 1, BLAS 관련 스레드 1. `uv.lock` SHA256 `283c21139b79d94aa81c22fc553e71bca9dfc1546a11ba38e149bd2ca51e11e0`.
- 00은 새 커널에서 환경·원자료 22개 해시·날짜·폰트를 검사했다. 입력 종가는 2019-01-03~2026-10-02의 1,903행 × 20 ETF, 수익률은 1,902행이다. 외부 재다운로드는 하지 않았다.
- 01은 현지시각 18:12:51에 시작한 새 순차 full run으로 20/20 ETF를 모두 계산했다. 병합 `run_manifest.json`은 계산시간 635.5초, `integrity_pass=true`, 결과 파일 저장 시각 18:23:27을 기록한다. 01 저장 노트북 수정 시각은 18:23:36이다. 코드 셀은 12/12 실행 저장됐다.
- 02의 첫 새 커널 시도는 `ModuleNotFoundError: No module named 'scripts'`로 실패했다. 생성기 bridge에 저장소 루트를 `sys.path`로 추가하고 02를 다시 생성·새 커널 재실행했다. 재시도 코드 실행 메타데이터는 09:24:03~09:24:21 UTC(18:24:03~18:24:21 KST)이며 24/24 코드 셀 실행, 오류 출력 0이다. 00·01은 동일 코드 셀을 유지한 채 추가 한국어 마크다운을 생성기로 삽입했고 저장 출력을 보존했다. 각 노트북의 코드 셀 출처는 변경 전후 대조했다.
- 최종 노트북은 00/01/02 각각 20/26/53셀, 코드 실행번호 9/9·12/12·24/24, `nbformat.validate` 3/3 PASS, 오류 출력 0이다. 테스트는 현 브랜치·R2H `.venv`에서 `146 passed in 22.50s`다. 실행 스크립트 `scripts/run_t12_final_notebooks.py`는 동일한 00→01→02 순서를 새 커널로 자동화한다. 이번 보고의 3회 실행은 해당 스크립트의 각 명령을 수동으로 호출했으며, 스크립트 자체의 통합 호출은 별도 실행하지 않았다.

## 독립 대조와 판정

`scripts/t12_semantic_fingerprint.py`를 실행별 결과 10개 핵심표에 적용해 기준 동결표와 비교했다.

| 단위 | 결과 | 의미 |
|---|---|---|
| 입력 해시 | PASS | 고정 원자료 22개·20 ETF 종가 해시 및 데이터 버전 일치 |
| Byte | FAIL | 10개 핵심표 중 9개 동일, `fold_manifest.csv`는 `git_sha` provenance 값이 달라 바이트 불일치; `run_manifest.json` 메타데이터도 달라짐 |
| Semantic | PASS | 집계 지문 `a5dca934bee19e3d843d2914c465a330cdd9d8abcd5051c3ef212de47472f883` |
| Verdict | PASS | 판정 지문 `48c8de250f72e22bc3d880e37ee762ecdec9fa2e98cd4258143cdf5c570e710f` |
| 연간 핵심 결과 | PASS | 2021–2025 정책당 100 ETF-연도: A 0, B 12, 기준선 6 기각 |
| 이동창 핵심 결과 | PASS | w60 `PURE_OOS` 에피소드 A/B/기준선 26/171/346, iid 귀무 기대 132.220/132.975/135.675 |

Byte FAIL을 수치 PASS로 대체하지 않는다. 동일 환경·단일 스레드에서 이번에는 기각 경계 반전이 없었지만, 이전 병렬 실행 기록에는 연산 순서에 따라 1/140 판정이 뒤집힌 사례가 있다. 타 플랫폼·다른 스레드 수의 판정 안정성은 승인하지 않는다. ETF-연도는 독립 시행이 아니며 관측 기각은 실제 시장 구조변화의 정답이 아니다.

## 그림과 출처

02 실행은 원본 그림 manifest의 32행과 발표용 P01–P06 PNG/SVG 6쌍을 생성했다. 발표용 6개 PNG를 픽셀로 열어 한글 글리프·마이너스·제목/축/범례의 잘림·데이터 겹침·캡션 숫자를 확인했고 눈에 띄는 결함이 없었다. PNG의 해상도 메타데이터는 Pillow 표시 `(299.9994, 299.9994)` dpi로 300 dpi의 저장 반올림이다. SVG는 편집 가능한 벡터 파일이다. 발표 그림 함수를 독립 재호출했을 때 PNG 6/6개는 원본과 바이트 동일했다. SVG는 생성 시각과 자동 element ID가 달라 바이트 동일하지 않다(숫자·형상 차이 아님). 원본 32장에 대해서는 manifest·수치 대조를 수행했으나 **32장 전부의 픽셀 시각 감사는 하지 않았다**. 수정 표현은 `presentation/`로 분리하고 기존 F 그림을 원본으로 남겼다.

- 실행별 계산표: `outputs/t12/notebook/b_nb_20261016T181251/results/`.
- 실행별 그림·자료 SHA 인덱스: `outputs/t12/notebook/b_nb_20261016T181251/presentation/presentation_figure_index.csv`.
- 로컬 릴리스 그림: [presentation/](presentation/). 원본 고정 계산표와 그림은 기존 `results/`, `figures/`에 그대로 있다.
- 파일별 SHA256과 현재 새 실행의 run id·지문: `FINAL_RELEASE_MANIFEST.json`.

## 재현 명령과 제한

```bash
python scripts/run_t12_final_notebooks.py
env -u VIRTUAL_ENV -u LD_LIBRARY_PATH PYTHONPATH="$PWD/src" /home/sieg/projects-wsl/hongik_univ_26_2/SA/1012_Annual_SVR–GARCH-CUSUM/R2H/.venv/bin/python -m pytest -q tests
python scripts/t12_release_manifest.py
```

작업트리의 `data` symlink는 원자료의 로컬 위치를 가리키며 원자료 자체는 Git에 넣지 않는다. 다른 장소에서는 동일 해시 파일을 `data/raw`에 배치해야 한다. `T12_JUPYTER`로 호환 Jupyter 실행 파일을 지정할 수 있다. 계산 재현의 PASS는 원논문 방법 충실성, 합성 군집 귀무의 크기 보정, ETF 급등 시작 탐지의 타당성을 승인하지 않는다.
