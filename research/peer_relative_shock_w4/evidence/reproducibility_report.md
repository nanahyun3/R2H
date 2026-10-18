# W4 재현성 보고

실행 환경: R2H .venv (Python 3.12.3 · numpy 2.5.4 · pandas 3.0.6 · scipy 1.18.1 · matplotlib 3.11.2), 스레드 1, PYTHONNOUSERSITE=1.

| 비교 | 대상 | 결과 |
|---|---|---|
| 경로 A: 노트북 09 새 커널 실행 (`scripts/run_t18_notebook.py`) vs 경로 B: `scripts/run_t18_pipeline.py` | `results/` + `figures/` (PNG·SVG) 89개 | 바이트 동일 |
| 같은 두 경로 | `outputs/t18/` 비공개 일별 표 10개 (gzip mtime 0) | 바이트 동일 |
| 노트북 재실행 (경로 A 2회차) vs 경로 B | `results/` + `figures/` | 바이트 동일 |

- 그림 결정성: SVG 해시 salt 를 고정하고(`t18_peer_shock_w4`), PNG·SVG 메타데이터의 날짜·생성기 필드를 비운다.
- 캡션 JSON 은 키를 정렬해 쓴다. 정렬 전에는 두 경로의 그림 호출 순서가 달라 이 파일 하나만 키 순서가 달랐다.
- 결과 지문: `evidence/results_digest.json` (results/ 아래 파일별 SHA256).
- 원자료 지문: `evidence/source_hashes.json` (평가 20 + Peer 51, MANIFEST 와 일치).
