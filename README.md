# R2H
주가 급등 국면 포착 에이전트 (2026.9~2027.6, 홍익대학교 졸업 프로젝트)

## 1012 기준선 — 무엇이 들어 있고, 무엇이 없는가

이 브랜치는 2조·4조가 함께 쓸 **최소 공통 스캐폴드**다. 연구 결론이나 탐지 성능을 담은 저장소가 아니다.

| 영역 | 상태 | 위치 |
|---|---|---|
| 입력 관측 계약 (OHLCV long table 검증, as-of 절단, 데이터 버전 해시) | 제안 v0.1 · 테스트 | `src/r2h/data/` |
| 과거 정보만 쓰는 feature (로그수익률·변동성·이동평균·거래량비·r/σ·rolling 상관·부호 국면) | 이식 + 원본과 parity 확인 | `src/r2h/features/` |
| 탐지 출력 계약 + 인터페이스 (`online` / `posthoc` 구분) | 제안 v0.1 · 테스트 | `src/r2h/detection/schema.py`, `base.py` |
| 참조 탐지기 `VolScaledThreshold`, `PageCUSUM` | **REFERENCE — 합성 데이터에서만 검증, 실제 ETF 성능 없음** | `src/r2h/detection/baselines.py` |
| 사후 CUSUM-of-squares 검정 (Lee·Kim·Lee 2020 §3) | 원본 모듈 바이트 동일 이식 · **원문 수치 미재현 (METHOD_FIDELITY_UNRESOLVED)** | `src/r2h/detection/paper2020_cusum.py`, `posthoc.py` |
| 사건 정답 계약 · 경보↔사건 매칭 · 지표 · 시간 분할 · 귀무검정 | 제안 v0.1 · 테스트 | `src/r2h/evaluation/` |
| 백테스트 | **SCHEMA_ONLY** (체결 시점 규칙·비용 함수만, 성과 수치 없음) | `src/r2h/backtest/` |
| 연구 근거 요약 (ETF EDA · Track A · Track B) | 재현 감사 결과 포함 | `research/` |

**없는 것**: 원시 시세 데이터 (재배포 권리 미확인 — 해시만 기록), 승인된 Ground Truth, 실제 ETF 탐지율·오탐·지연·수익률 수치,
SVR–GARCH 적합 코드 (SA_ETF 쪽에 있음), 온라인 CUSUM 최종본(W04).
계약 v0.1 은 2조·4조·교수 승인 전의 **제안**이다 → `docs/architecture/CONTRACT_v0.1.md`, 열린 결정 → `docs/decisions/OPEN_DECISIONS.md`.

## Quickstart

요구: Python ≥ 3.11 (CI·검증은 3.12), [uv](https://docs.astral.sh/uv/) 권장.

```bash
git clone https://github.com/nanahyun3/R2H.git && cd R2H
git checkout 1012
uv sync --extra dev                       # uv.lock 기준으로 .venv 생성
uv run pytest                             # unit · integration · property · leakage
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python examples/synthetic_demo.py --out outputs/synthetic_demo.json
```

uv 없이: `python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest` (버전은 lock 이 아니라 `pyproject.toml` 범위로 풀린다).

`examples/synthetic_demo.py` 는 **합성 데이터**(주입한 상승 drift 를 정답으로 둠)에서 두 참조 탐지기를 돌려 사건 수준 지표를 출력한다.
같은 config 로 두 번 실행하면 출력 JSON 이 같아야 한다 (테스트로 확인). 이 수치는 실제 ETF 성능이 아니다.

## 사용 예

아래 블록은 테스트(`tests/integration/test_readme_example.py`)가 그대로 실행한다. 실제 데이터에서는 `returns` 를 일간 로그수익률
(`r2h.features.log_returns`), `truth` 를 승인된 정답 표로 바꾼다.

```python
from r2h.detection import VolScaledThreshold
from r2h.evaluation import MatchConfig, event_metrics, match_alarms
from r2h.synthetic import InjectedSurge, ground_truth_from_injections, surge_series

surges = [InjectedSurge(start=300, length=10, drift=0.012)]
returns, calendar = surge_series(1000, surges, seed=1)  # 합성 일간 로그수익률 (실제 시세 아님)
truth = ground_truth_from_injections(calendar, surges, ticker="SYN")

signals = VolScaledThreshold(window=60, k=3.0).run(returns, ticker="SYN", data_version="synthetic")
alarms, events = match_alarms(signals, truth, calendar, MatchConfig(max_delay=5, cooldown=5, direction=1))
print(event_metrics(alarms, events, ticker_years=len(calendar) / 252))
```

새 탐지기(CUSUM 최종본·BOCPD 등)는 `r2h.detection.Detector` 프로토콜(`method_id`·`model_version`·`mode`·`params()`·`run()`)을 따르고
`build_signal_frame` 으로 출력하면 매칭·지표를 그대로 쓸 수 있다.

## 규칙

- 온라인 신호는 `available_until <= signal_at` (검증 함수가 강제). 사후 검정은 `mode="posthoc"` 이며 온라인 평가에 넣을 수 없다.
- 정답 라벨은 탐지기와 독립된 정의로 만든다. 미래 구간을 본 라벨은 평가에만 쓴다.
- 임계값·하이퍼파라미터는 개발 구간에서만 고른다. 2026 은 기존 EDA 가 이미 본 데이터라 blind holdout 이 아니다.
- 원시 시세·API 키·개인정보·저작권 PDF 는 커밋하지 않는다 (`.gitignore`).

## 출처

코드 출처와 원본 sha256: `docs/provenance/PROVENANCE.md` · 원본 대비 수치 parity: `docs/provenance/PARITY.md` ·
연구 재현 상태: `research/REPRODUCTION_STATUS.md` · 인계·일정: `docs/handoff/HANDOFF_1012.md`.
