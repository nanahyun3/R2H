# ruff: noqa: E501
"""W3 (W3-lock-2) 노트북 08 연구보고서 생성기.

실행 출력이 있는 노트북을 무심코 지우지 않도록 --write 명시 실행만 허용한다.
생성 후 ``scripts/run_t15_notebook.py`` 로 새 커널에서 실행한다. 모든 코드 줄에는 한국어 주석을 손으로 단다
(빠지면 생성 단계에서 멈춘다). 해석 문단의 수치는 ``INTERP`` 에 적고, 같은 수치를 CLAIMS 셀이 결과와 대조한다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "08_대표6종ETF_공동CUSUM_바텀업통계식별.ipynb"
INTERP_FILE = ROOT / "research/joint_cusum_w3/notebook_interpretation.json"
HANGUL = re.compile(r"[가-힣]")
CLOSERS = {")", "]", "}", "),", "],", "},", ")]", "})"}


def md(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    """주석이 빠진 코드 줄이 있으면 멈춘다 (기계적 자동 주석은 넣지 않는다)."""
    text = source.strip()
    prev_comment = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            prev_comment = False
            continue
        if s.startswith("#"):
            prev_comment = bool(HANGUL.search(s))
            continue
        trailing = "#" in s and not s.startswith(("'", '"')) and HANGUL.search(s.split("#", 1)[1])
        if not (prev_comment or trailing or s in CLOSERS):
            raise ValueError(f"한국어 주석 없는 코드 줄: {line!r}")
        prev_comment = False
    return nbformat.v4.new_code_cell(text)


def interp(key: str) -> nbformat.NotebookNode:
    """결과 해석 문단 (MC 완료 후 작성한 JSON). 없으면 생성을 멈춘다 — 빈 해석으로 배포하지 않는다."""
    data = json.loads(INTERP_FILE.read_text(encoding="utf-8"))
    if key not in data:
        raise KeyError(f"해석 문단 없음: {key}")
    return md(data[key])


SETUP = r"""
# 새 커널 첫 셀: BLAS 스레드를 NumPy 로드 전에 1로 고정해 결과를 결정적으로 만든다.
import os  # 환경변수 설정
import sys  # 인터프리터·모듈 경로 확인
from pathlib import Path  # 저장소 상대 경로

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # 네 BLAS 계열 변수
    os.environ[key] = "1"  # 다중 스레드 합산 순서에 따른 비트 차이를 막는다
assert "numpy" not in sys.modules, "새 커널에서 첫 셀부터 실행해야 합니다"  # 숨은 커널 상태 금지
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t15_joint_cusum_w3_v2.json").is_file())  # 저장소 루트 탐색
sys.path.insert(0, str(ROOT / "src"))  # 이 작업트리의 r2h 패키지를 우선 사용

import csv  # 보호 파일 SHA 목록
import gzip  # Git 제외 일별 표 압축
import hashlib  # 결과 해시
import importlib.metadata as metadata  # 설치 패키지 버전 조회
import json  # 설정·메타
import platform  # Python 버전

import matplotlib.pyplot as plt  # 그림 기본 설정
import numpy as np  # 수치 배열
import pandas as pd  # 결과표
from IPython.display import Image, display  # 표·그림 출력
from matplotlib import font_manager  # 한글 글꼴 등록

# T12·W1·W2 재현 환경과 같은 버전이어야 한다 (user-site 의 다른 numpy/pandas 를 잡으면 여기서 멈춘다).
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2"}  # 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": metadata.version("scipy"), "matplotlib": metadata.version("matplotlib")}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패로 처리
assert "site-packages" in np.__file__ and ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
FONT_FILE = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")  # 한글 도판용 나눔고딕
assert FONT_FILE.is_file(), "한글 도판 렌더링을 위한 나눔고딕 파일이 없습니다"  # 글꼴 없으면 중단
font_manager.fontManager.addfont(str(FONT_FILE))  # matplotlib 글꼴 목록에 등록
plt.rcParams["font.family"] = [font_manager.FontProperties(fname=str(FONT_FILE)).get_name(), "DejaVu Sans"]  # 한글 우선·기호 대체
plt.rcParams["axes.unicode_minus"] = False  # 음수 기호 깨짐 방지
pd.set_option("display.width", 220)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화

from r2h.joint_cusum import analysis as A  # W3 관측 분석 (MC 와 같은 함수 경로)
from r2h.joint_cusum import figures as F  # W3 그림
from r2h.joint_cusum.pipeline import load_cfg  # W3 동결 설정 (lock-2)

assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
CFG = load_cfg()  # configs/t15_joint_cusum_w3_v2.json
BASE = ROOT / "research/joint_cusum_w3"  # W3 산출물 폴더
RES = BASE / "results/08"  # 집계 결과 (Git 포함)
FIG = BASE / "figures"  # 그림 (PNG 320dpi + SVG)
WORK = ROOT / "outputs/t15/08"  # 일별 표 (Git 제외 — 가격 역산 가능)
for d in (RES, FIG, WORK):  # 폴더 준비
    d.mkdir(parents=True, exist_ok=True)  # 없으면 만든다


def sha(p):  # 파일 SHA256
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()  # 바이트 단위 지문


# 계약·설정 동결 지문 (lock-1 기록 + lock-2 개정) 과 보호 파일 252개를 대조한다.
for line in (BASE / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():  # 동결 기록 4줄
    digest, name = line.split(maxsplit=1)  # 해시·경로
    assert sha(ROOT / name) == digest, f"동결 파일 변경: {name}"  # 결과를 본 뒤 규칙 변경 금지
PROTECTED = list(csv.DictReader(open(BASE / "W3_PROTECTED_SHA256.csv", encoding="utf-8")))  # W1·W2·T12·노트북 00–07
CHANGED = [r["path"] for r in PROTECTED if sha(ROOT / r["path"]) != r["sha256"]]  # 바뀐 보호 파일
assert not CHANGED, f"보호 파일 변경: {CHANGED}"  # 기존 연구는 읽기만
META = json.loads((ROOT / "outputs/t15/mc/inference_meta.json").read_text())  # MC 완료 시점·산출 해시
BAD_MC = [n for n, h in META["files"].items() if sha(ROOT / "outputs/t15/mc" / n) != h]  # MC 산출물 변조 검사
assert not BAD_MC, f"MC 산출물이 기록과 다름: {BAD_MC}"  # 기록된 MC 결과만 쓴다


def save_csv(df, name):  # 결과표 저장 (결정적 형식)
    df.to_csv(RES / name, index=False, float_format="%.10g")  # 반올림 형식 고정
    return RES / name  # 경로 반환


print("작업트리:", ROOT)  # 실행 위치
print("프로토콜:", CFG["protocol_version"], "| 보호 파일", len(PROTECTED), "개 불변 | MC 완료:", META["completed_at"])  # 동결 지문
print("실행 환경:", ACTUAL_ENV)  # 환경 기록
"""


def book() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 08 · 대표 6종 ETF 공동 SVR–GARCH–CUSUM 바텀업 통계 식별

**「여섯 ETF의 공동 SVR–GARCH–CUSUM 불안정성에 대한 단계적 통계적 식별: 기존 동적 시장 동조구조 대비 추가 공동 반응의 검정」**

- 연구 ID `R2H_W3_JOINT_CUSUM_08`, 프로토콜 `W3-lock-2`.
- 계약: `research/joint_cusum_w3/W3_연구계약.md` (lock-1 `9cdeccb`) 와 `W3_계약개정_lock2.md` (`955d126`).
- 설정: `configs/t15_joint_cusum_w3_v2.json`.
- 반복 수 동결 기록: `MC_REPS_FREEZE.md`.
- 모든 규칙은 실제 ETF 의 공동 통계량을 계산하기 **전에** 커밋했다.

이 노트북이 최대화하는 것은 유의한 구간의 **개수가 아니다**. 통계적 식별의 신뢰성, 검출력 평가의 정확성, 정보 가용성 준수, 재현성이다. 검정이 부정적이거나, 귀무모형이 부적합하거나, 계산이 부족하면 그것도 결과로 보고한다.
"""),
        md("## 0. 실행 환경·동결 지문"),
        code(SETUP),
        # ── 01 ──
        md(r"""
## 01. W1/W2 연구 승계와 W3 문제 정의

**무엇을 승계하는가.**

| 단계 | 결론 | W3 에서의 쓰임 |
|---|---|---|
| T12 | 연간 expanding SVR–GARCH 잔차, 정책 A·B·base | 같은 함수로 관측·모의 잔차를 만든다 (`fit_annual`·`forecast_year`) |
| W1 (03·04) | 이동 CUSUM 적격 창 **0/4** (최적창 없음) | 판정을 바꾸지 않는다. CUSUM 통계량 T_w 는 공동 검정의 재료로만 쓴다 |
| W2 (05–07) | 다중 기간 변동성 상태, 공통 구간 (탐색적, 귀무 보정 없음) | 구조변화 정답이 아니다. q 특징 규칙만 승계해 순차 탐지에 쓴다 |

**W3 의 문제.** W2 의 공통성은 "같은 날 여러 ETF 가 반응했다" 는 **관찰**이었다. W3 는 두 가지를 묻는다.
1. 그 공동 반응이 **기존 시장 동조성**으로 설명되는가? 이를 위해 동조성을 보존한 귀무모형(H0-B: DCC-t)을 모든 반복에서 연간 SVR 재적합까지 포함해 모의한다.
2. 바텀업으로 자산을 하나씩 더할 때 새 자산이 **추가 정보**를 주는가?

**한계.**
- 2021–2025 는 이미 W1·W2 에서 본 자료다. 이 노트북의 결과는 독립 외부 검증이 아니다.
- 모든 p 값은 지정한 귀무모형에 조건부다.
"""),
        # ── 02 ──
        md(r"""
## 02. 여섯 ETF·세 정책·바텀업 가설

| 코드 | 종목 | 단계 |
|---|---|---|
| 069500 | KODEX 200 | S1 (기준 ETF) |
| 229200 | KODEX 코스닥150 | S1 |
| 148070 | KIWOOM 국고채10년 | S2 신규 |
| 153130 | KODEX 단기채권 | S3 신규 |
| 133690 | TIGER 미국나스닥100 | S4 신규 |
| 261220 | KODEX WTI원유선물(H) | S5 신규 |

- S1 ⊂ S2 ⊂ … ⊂ S5 의 순서는 결과와 무관하게 고정했다.
- 부분 분석은 크기 2 이상 **57개 부분집합 전부**다 (15·20·15·6·1).

| 가설 | 검정 | α |
|---|---|---|
| H1 개별 잔차 분산 불안정성 | 기술 (W1 0/4 유지) | — |
| H2 (H0-A) 시간 정렬 이상의 공동 반응 | 보조. 원형 이동·블록 재표집 | 보조 |
| **H3 (H0-B) 동적 시장 동조 이상의 공동 불안정성** | **주 검정** (DCC-t, 전체 재적합 MC) | 주 경로 0.02 · 부분집합 0.02 |
| H4 신규 ETF 조건부 참여 | S2–S5 고정 순서 | 각 0.02 (사슬) |
| H5 의존구조 자체의 변화 | 보조 진단 (V6 합성 + 구간 전후 상관) | — |
| H6 사후 가격 반응 | `EXPLORATORY_REUSED_DATA` | 0.01 예약 (미사용) |

**정책.** A 는 관측 proxy, B 는 재귀 예측, base 는 직전 60일 표본분산이다. 세 정책을 동등하게 다룬다. 결과를 본 뒤 주 정책을 고르지 않는다.
"""),
        # ── 03 ──
        md(r"""
## 03. 원자료·모형·워크포워드 시간 계약

**두 시간 기준.**
- **A. 워크포워드 관측.**
  - 연간 SVR 은 그해 이전 자료로 적합하고 파라미터를 고정한다. 예측분산과 잔차는 날마다 순차로 계산한다.
  - 날짜 t 의 신호는 t 종가 뒤에 확정된다.
  - 시차 탐색이 미래 날짜의 신호를 썼다면, 그 공동 신호는 가장 늦은 참여 신호의 날에야 알 수 있다 (`joint_confirmed_at`).
- **B. 사후 통계 식별.** 2021–2025 전체의 최대통계량 p 값과 구간 순위는 당시 쓸 수 있던 정보가 아니다 (`retrospective_p_value`, `inference_completed_at`).

**첫 검증.**
- 이 노트북은 관측 6종을 MC 반복과 **같은 함수**(`run_pipeline`) 로 처리한다.
- 그 결과는 T12 cache 의 e·vhat 과 같아야 한다. 같아야 관측 통계량과 귀무 통계량이 같은 구성이 된다.
"""),
        code(r"""
# 관측 6종: 원자료 → 연간 SVR 재적합 → 정책별 잔차 → 연도 안 이동창 CUSUM → 위치 구간별 꼬리점수 Q
OBS = A.load_obs(CFG, ROOT)  # MC 반복과 같은 run_pipeline·q_score
print("평가일:", OBS.dates[0].date(), "~", OBS.dates[-1].date(), len(OBS.dates), "일 | 배열 T:", OBS.out.T.shape, "| Q:", OBS.Q.shape)  # 범위 확인
# T12 cache 의 e·vhat 과 대조 (CSV 반올림 이내여야 같은 함수 경로)
T12 = ROOT.parents[1] / "1016/R2H_T12_Final/outputs/t12/work/b_nb_20261016T181251"  # T12 동결 cache
rec = []  # ETF·정책별 최대 차
for i, tk in enumerate(OBS.tickers):  # 6종
    d = pd.read_csv(T12 / tk / "daily.csv.gz", dtype={"ticker": str, "policy": str}, parse_dates=["date"])  # cache 일별
    for p_i, p in enumerate(("A", "B", "base")):  # 세 정책
        b = d[(d.window == 0) & (d.policy == p)].set_index("date").reindex(OBS.dates)  # 같은 날짜로 정렬
        rec.append({"ticker": tk, "policy": p, "max_abs_de": float(np.nanmax(np.abs(b.e.to_numpy() - OBS.out.e[i, p_i]))), "max_abs_dvhat": float(np.nanmax(np.abs(b.vhat.to_numpy() - OBS.out.vhat[i, p_i]))), "nan_mismatch": int((np.isnan(b.e.to_numpy()) != np.isnan(OBS.out.e[i, p_i])).sum())})  # 차이
REPRO = pd.DataFrame(rec)  # 재현 대조표
save_csv(REPRO, "t12_reproduction_check.csv")  # 근거 저장
assert REPRO.max_abs_de.max() < 1e-8 and REPRO.nan_mismatch.sum() == 0, REPRO  # 같은 함수 경로 확인
display(REPRO.describe().loc[["max"]])  # 최대 차만 표시
"""),
        code(r"""
# W1 common 표본 무결성 대조: W1 동결 임계값으로 6종 일별 경보를 다시 세어 W1 집계와 맞춘다 (lock-2 §6)
from r2h.multihorizon.cusum import critical_tables, daily_cusum, load_daily_cache, verify_against_w1  # W2 가 쓴 대조 함수
from r2h.window_study.simulation import load_cfg as load_w1_cfg  # W1 동결 설정

W1CFG = load_w1_cfg(ROOT)  # configs/t13_window_study_v1.json
SRC = ROOT.parents[1] / "1016/R2H_T12_Final"  # T12 종결 작업트리
pipe_c, point_c = critical_tables(SRC, W1CFG["base_t12_run_id"], ROOT)  # W1·T12 임계값
cus = pd.concat([daily_cusum(t, load_daily_cache(SRC, W1CFG["base_t12_run_id"], t), W1CFG, pipe_c, point_c, [20, 30, 60, 120]) for t in OBS.tickers])  # 6종 일별 경보
w1m = pd.read_csv(ROOT / "research/window_study_w1/results/04_real/alarm_metrics.csv", dtype={"ticker": str})  # W1 집계
w1m = w1m[w1m.ticker.str.zfill(6).isin(OBS.tickers)]  # 6종만
W1CHK = verify_against_w1(cus, w1m, [20, 30, 60, 120], W1CFG["episode_gap_non_alarm_days"])  # 행 단위 대조
save_csv(W1CHK[["ticker", "year", "policy", "w", "threshold_type", "sample_type", "match"]], "w1_common_integrity_check.csv")  # 근거
print("W1 집계 대조:", int(W1CHK.match.sum()), "/", len(W1CHK), "행 일치")  # 결과
assert W1CHK.match.all(), W1CHK[~W1CHK.match].head()  # 전부 일치해야 한다
"""),
        # ── 04 ──
        md(r"""
## 04. ETF별 개별 CUSUM 경로 및 적격성

**문제.** 여섯 ETF 의 개별 CUSUM 은 언제, 얼마나 크게 반응했는가?

**산식.**
- T_{i,p,w,t} 는 W1 원 함수 `rolling_cusum` 으로 계산한다. 그해 잔차 안에서만 계산하며, 첫 유효 위치는 w−1 이다.
- 그 이전 날짜는 `NOT_AVAILABLE` 이고, 무경보로 바꾸지 않는다.
- 개별 경보 기준은 **W3 own-valid 보정 임계값**이다 (lock-2 §6). H0_CALIBRATION 반복에서 그해 own-valid 일의 최대 T 를 모으고, 그 95% 분위를 ETF·정책·창마다 따로 쓴다.
- W1 동결 임계값은 무결성 대조용으로만 쓴다.
"""),
        code(r"""
# ETF·정책·창별 개별 CUSUM 요약: 유효일·W3 경보일·W1 기준 경보일(참고)·최대 T
FLAGS3 = A.cusum_alarm_flags(OBS, "w3")  # 주: W3 own-valid 보정 임계값
FLAGS1 = A.cusum_alarm_flags(OBS, "w1")  # 참고: W1 동결 임계값
CRIT3 = json.loads((ROOT / "outputs/t15/mc/w3_individual_criticals.json").read_text())  # W3 임계값
rows = []  # 요약 행
for i, tk in enumerate(OBS.tickers):  # 6종
    for p_i, p in enumerate(("A", "B", "base")):  # 세 정책
        for w_i, w in enumerate((20, 30, 60, 120)):  # 네 창
            T = OBS.out.T[i, p_i, w_i]  # 일별 통계량
            rows.append({"ticker": tk, "policy": p, "w": w, "valid_days": int(np.isfinite(T).sum()), "not_available_days": int((~np.isfinite(T)).sum()), "crit_w3": CRIT3[f"w3:{tk}:{p}:{w}"], "alarm_days_w3": int(FLAGS3[tk, p, w].sum()), "alarm_days_w1_ref": int(FLAGS1[tk, p, w].sum()), "max_T": float(np.nanmax(T)), "max_Q": float(np.nanmax(OBS.Q[i, p_i, w_i]))})  # 한 칸
INDIV = pd.DataFrame(rows)  # 개별 CUSUM 요약
save_csv(INDIV, "individual_cusum_summary.csv")  # 근거 저장
display(INDIV.pivot_table(index="ticker", columns=["policy"], values="alarm_days_w3", aggfunc="sum"))  # ETF×정책 경보일 합
display(INDIV.groupby("w")[["valid_days", "not_available_days"]].first())  # 창별 계산 가능일 (연초 불능)
"""),
        code(r"""
# 그림 08-1 (가·나): 공통 날짜축의 가격·|r|·정책 A CUSUM (패널별 척도)
NAMES = CFG["universe"]["names"]  # 종목명
PIPE = {(p, w): pipe_c[p, w] for p in ("A", "B", "base") for w in (20, 30, 60, 120)}  # W1 임계값 (점선 참고)
P1a = F.fig_individual(OBS, NAMES, PIPE, ["069500", "229200", "148070"], FIG, "08-1(가)")  # 국내 주식·국채
P1b = F.fig_individual(OBS, NAMES, PIPE, ["153130", "133690", "261220"], FIG, "08-1(나)")  # 단기채·나스닥·원유
display(Image(filename=str(P1a[0]), width=900))  # 렌더 확인
display(Image(filename=str(P1b[0]), width=900))  # 렌더 확인
"""),
        interp("ch04"),
        # ── 05 ──
        md(r"""
## 05. 1·3·7·14일 단기 변동성 순차 탐지

**문제.** 어떤 ETF 가 3일 신호에 먼저 반응하고, 어떤 ETF 가 20·60·120일 CUSUM 에서 늦게 반응하는가? 실제 일별 정보만 써서 답한다.

**산식.**
- **W2 q 특징.**
  - V⁽q⁾ = mean r² 이고, D⁽q⁾ = log(V_t/V_{t−q}) (q≥3) 다.
  - U 는 엄밀한 과거 확장형 mid-rank 분위이고, 최소 252개 값이 필요하다.
  - 확대 후보는 U_D ≥ 0.90, 고변동성 후보는 U_V ≥ 0.90 이다.
  - q=1 은 일간 충격이다.
- **잔차 에너지 (승인서 §5.3).**
  - E⁽ʰ⁾_t = log(mean e²[t−h+1..t] / mean e²[t−h−59..t−h]) 이고, h ∈ {1,3,7,14} 다.
  - 그해 잔차 안에서만 계산하고, 분모가 0이면 NaN 이다.
  - H0_CALIBRATION 꼬리 1% 를 탐색 후보로 쓴다.
- **지위.** 이 단기 신호들은 **분위 기반 탐색 후보**이며 가족 보정 경보가 아니다. 귀무에서의 후보일 비율은 holdout 반복으로 따로 보인다.
"""),
        code(r"""
# ETF 별 일별 q 신호 · E(h) 후보 · CUSUM 경보 에피소드별 '단기 후보 → 경보' 지연
QS = A.q_signals(OBS)  # W2 규칙 (q=1·3·7·14·20·30·60·120)
ECAND = A.energy_candidates(OBS)  # E(h) 보정 꼬리 1% 후보
SEQ = A.sequential_alarm_episodes(OBS, QS, FLAGS3, ECAND)  # W3 경보 에피소드별 지연
save_csv(SEQ, "sequential_alarm_episodes.csv")  # 근거
LAGSUM = SEQ.groupby(["ticker", "w"]).agg(alarm_episodes=("alarm_days", "size"), share_preceded_q3=("lag_from_q3_EXP", lambda s: float(s.notna().mean())), median_lag_q3=("lag_from_q3_EXP", "median"), median_lag_q7=("lag_from_q7_EXP", "median"), median_lag_E3=("lag_from_E3", "median")).reset_index()  # ETF×창 요약
save_csv(LAGSUM, "sequential_lag_summary.csv")  # 근거
display(LAGSUM)  # 표
HOLD_Q = np.load(ROOT / "outputs/t15/mc/null_eval_holdout.npz")["q_signal_rate"].mean(axis=0)  # 귀무 후보일 비율 (ETF, q, 채널)
QNULL = pd.DataFrame([{"ticker": tk, "q": q, "null_EXP_rate": HOLD_Q[i, k, 0], "null_HIGH_rate": HOLD_Q[i, k, 1]} for i, tk in enumerate(OBS.tickers) for k, q in enumerate((3, 7, 14))])  # 표
save_csv(QNULL, "q_candidate_rate_under_null.csv")  # 근거
display(QNULL.pivot(index="ticker", columns="q", values="null_EXP_rate").round(3))  # 귀무에서도 약 10% 가 후보
"""),
        code(r"""
# 사례 창 순차 반응표 (2024-08 · 2025-04) 와 그림 08-2
CASES = {"2024-08 (2024-07-25~09-30)": ("2024-07-25", "2024-09-30"), "2025-04 (2025-03-25~05-30)": ("2025-03-25", "2025-05-30")}  # 승인서 §18 G6 사례
CASE_T = {k: A.case_sequence(OBS, QS, FLAGS3, a, b) for k, (a, b) in CASES.items()}  # ETF 별 첫 신호 날짜
for k, df in CASE_T.items():  # 두 사례
    save_csv(df, f"case_sequence_{k[:7]}.csv")  # 근거
    display(df[["ticker", "first_daily_shock_q1", "first_EXP_q3", "first_EXP_q7", "first_EXP_q14", "first_CUSUM_w20", "first_CUSUM_w60", "first_CUSUM_w120", "last_CUSUM_w60"]])  # 표
P2 = F.fig_sequence(CASE_T, SEQ, NAMES, FIG, "08-2")  # 순차 탐지 그림
display(Image(filename=str(P2[0]), width=950))  # 렌더 확인
"""),
        code(r"""
# 단기 창 w=3·7·14 CUSUM 적격성 (W1 규칙을 W3 own-valid 표본에 적용) — 주 검정 가족에는 넣지 않는다
POWER = A.power_tables(OBS)  # 합성 검정력 (13장에서 자세히)
ELIG = A.short_window_eligibility(OBS, POWER["delays"])  # 크기·검출·지연·퇴화
save_csv(ELIG, "short_window_eligibility.csv")  # 근거
display(ELIG.groupby(["w", "role"]).agg(size_ok=("size_ok", "mean"), power_ok=("power_ok", "mean"), eligible=("verdict", lambda s: int((s == "ELIGIBLE").sum())), cells=("verdict", "size"), nan_share=("nan_share_own_valid", "max"), distinct_min=("distinct_values_200reps", "min")))  # 창별 요약
"""),
        interp("ch05"),
        # ── 06 ──
        md(r"""
## 06. 귀무 꼬리위치 및 공동 통계량

**산식 (lock-2 §7.1).**
- 개별 꼬리위치는 u = (1 + #{T* ≥ T}) / (N+1), Q = −log u 다.
  - T* 는 H0_CALIBRATION 2,000 반복의 같은 (ETF, 정책, 창, **연중 위치 구간**) 값이다.
  - 위치 구간은 [0,60)·[60,110)·[110,160)·[160,210)·[210,끝) 이다.
  - 풀 최대값을 넘으면 1/(N+1) 로 두고, 외삽하지 않는다.
- 공동 점수:
  - J_all(S) = min_{i∈S} Q̃_i, J_2(S) = 두 번째로 큰 Q̃_i 다.
  - Q̃ 는 기준 ETF 에서는 Q, 나머지에서는 max_{l∈{−2..2}} Q(t+l) 다.
- 비기준 ETF 의 반응 하나는 시차를 통해 최대 5개 기준일에 대응할 수 있다. 귀무 반복도 같은 규칙으로 계산하므로 보정된다.
- 133690 의 KRX 날짜 시차는 미국 기초시장 반영일 차이일 수 있다. 경제적 선후관계로 읽지 않는다.
- Q 는 개별 이례성 점수이며, 공동성의 보정 p 값이 아니다.
"""),
        code(r"""
# 꼬리표 풀 크기와 관측 Q 분포, 57개 부분집합의 일별 공동 점수 (Git 제외 저장)
TT = OBS.tt  # 위치 구간별 꼬리표
POOL = pd.DataFrame([{"ticker": tk, "policy": p, "w": w, "bin": k, "n_pool": int(TT.n_pool[i, p_i, w_i, k])} for i, tk in enumerate(OBS.tickers) for p_i, p in enumerate(("A", "B", "base")) for w_i, w in enumerate((20, 30, 60, 120)) for k in range(len(TT.edges))])  # 칸별 풀 크기
save_csv(POOL, "tail_table_pool_sizes.csv")  # 근거
display(POOL.pivot_table(index="w", columns="bin", values="n_pool", aggfunc="min"))  # 창×위치 구간 최소 풀 (0 = 계산 불능 위치)
DAILY = pd.concat([A.joint_daily(OBS, s) for s in OBS.subsets], ignore_index=True)  # 집합×일 공동 점수
with gzip.GzipFile(WORK / "joint_daily.csv.gz", "wb", mtime=0) as fh:  # 결정적 gzip (Git 제외)
    fh.write(DAILY.to_csv(index=False, float_format="%.10g").encode())  # 일별 표
print("일별 공동 점수:", DAILY.shape, "| SHA256", sha(WORK / "joint_daily.csv.gz")[:16])  # 지문만 기록
"""),
        # ── 07–09 ──
        md(r"""
## 07–09. S1 → S5 바텀업: 국내 주식 공동성과 신규 ETF 조건부 참여

**검정 통계량.**
- S1: M_S1 = max_{p,w,t} J_all(S1) 이다.
- S2–S5: C_Sk = max_{(p,w): |E|≥5} mean_{t∈E} Q̃_new 이고, E_{k−1} = {t : J_2(S_{k−1}) ≥ −log 0.01} 이다.
- **모든 귀무 반복에서 E 를 다시 만든다.** 무조건부 파이프라인 검정이며, 조건부 귀무와 섞지 않는다.

**판정.**
- 고정 순서 S1→S5, 각 단계 α=0.02 로 판정한다.
- 기각되지 않았거나 판정이 불가능한 단계에서 확증 사슬이 멈춘다. 멈춤은 후속 단계에 공동성이 없다는 뜻이 아니다.
- 다음 경우 그 단계는 `NULL_MODEL_INVALID` 다.
  - H0-B 유효성(N1·N3·N4) 이 실패한 경우
  - 조건부 귀무 유효성 검사(13장, V1·V2) 가 실패한 경우
- 단계별 J_all·J_2 는 α 밖의 기술 통계로 함께 낸다.
"""),
        code(r"""
# 귀무 적합도 (N1·N3·N4·LB) → 통계량별 H0-B 유효성, 조건부 귀무 유효성 (V1·V2), 단계 판정
VAL = A.null_validity(OBS)  # 연도 모형별 envelope · 2/5 규칙
COND, COND_OK = A.conditional_null_check(OBS)  # 앞 단계만 변할 때 신규 ETF 검정의 기각률
TESTS = A.test_tables(OBS, VAL, COND_OK)  # 주 경로·부분집합 판정
STAGE = TESTS["stage"]  # S1–S5 표
save_csv(STAGE, "stage_tests.csv")  # 근거
save_csv(COND, "conditional_null_validity.csv")  # 근거
display(STAGE[["stage", "members", "obs", "p_dcc_label", "p_dcc_ci99_low", "p_dcc_ci99_high", "h0b_valid", "conditional_null_valid", "p_ccc", "p_h0a_circular_shift_within_year", "p_h0a_circular_block_bootstrap_within_year", "status", "confirmatory_status"]])  # 판정표
display(STAGE[["stage", "jall_obs", "jall_p_dcc_descriptive", "j2_obs", "j2_p_dcc_descriptive"]])  # 기술 통계 (α 밖)
display(COND)  # 조건부 귀무 유효성
"""),
        code(r"""
# 그림 08-3: 단계 통계량 vs DCC 귀무 분포 · ETF×단계 조건부 참여 강도
NULL_DCC = np.load(ROOT / "outputs/t15/mc/null_eval_dcc.npz")  # H0_EVALUATION (DCC) 50,000
NC = {"S1": NULL_DCC["M_subset"][:, 0], **{f"S{k + 2}": NULL_DCC["C_stage"][:, k] for k in range(4)}}  # 단계별 귀무
PART = A.participation_table(OBS)  # 기술 통계
save_csv(PART, "stage_participation.csv")  # 근거
P3 = F.fig_bottom_up(STAGE, NC, PART, FIG, "08-3")  # 바텀업 그림
display(Image(filename=str(P3[0]), width=950))  # 렌더 확인
"""),
        interp("ch07_09"),
        # ── 10 ──
        md(r"""
## 10. 전체 57개 부분집합

**검정 통계량.**
- M_S = max_{p,w,t} J_all(S) 다. 정책·창·날짜·시차 탐색은 귀무 반복에서 똑같이 수행한다.
- J_2(S) 는 기술용이다. 상위 집합의 J_2 는 가장 강한 쌍이 정하기 때문이다.

**다중검정.**
- 57개에 Holm α=0.02 를 적용하고, 민감도로 Westfall–Young minP 를 본다.
- 가족 해상도 규칙: B × 0.02/57 ≥ 10. DCC 50,000 이면 17.5 다.
- 153130 이나 148070 이 들어간 부분집합은 귀무 적합도에 따라 확증에서 빠질 수 있다.
- 같은 사건이 주 경로와 부분집합에 다시 나타나도 독립 증거가 아니다.
"""),
        code(r"""
# 57개 부분집합 판정표와 그림 08-4 (원시 점수와 판정을 다른 패널에)
SUB = TESTS["subset"]  # 57행
save_csv(SUB, "subset57_tests.csv")  # 근거
save_csv(TESTS["family_resolution_ok"], "family_resolution.csv")  # 가족 해상도
assert len(SUB) == 57 and SUB.subset.is_unique  # 누락·중복 없음
display(TESTS["family_resolution_ok"])  # B×기준
display(SUB.status.value_counts().rename("부분집합 수"))  # 상태 분포
display(SUB.sort_values("p_dcc").head(12)[["subset", "M_obs", "p_dcc_label", "p_dcc_ci99_low", "p_dcc_ci99_high", "h0b_valid", "holm_status", "status", "p_minp_adjusted", "p_ccc", "p_h0a_circular_shift_within_year"]])  # p 하위 12
P4 = F.fig_subsets(SUB, FIG, "08-4")  # 57개 그림
display(Image(filename=str(P4[0]), width=950))  # 렌더 확인
"""),
        interp("ch10"),
        # ── 11–12 ──
        md(r"""
## 11–12. H0-A 시간 정렬 귀무 · H0-B DCC-t / CCC-t 귀무

**H0-A (보조).**
- ETF·연도마다 변환 하나를 뽑는다. 원형 이동과 블록 20의 원형 블록 재표집, 두 방법이다.
- 그 변환을 그 ETF-연도의 세 정책·네 창 유효 구간에 똑같이 적용한다. `NOT_AVAILABLE` 구간은 그대로 둔다.
- 두 방법을 합산하지 않는다. **두 방법이 모두 기각할 때만** H0-A 기각으로 본다 (보수적 규칙, H0-A 계산 전에 고정).
- H0-A 는 상대적 시간 정렬의 이례성을 본다. 공통 시장 요인을 보존하지 않는다.

**H0-B (주).**
- 평가연도 y 마다 **y 이전 수익률로만** GARCH(1,1)-t 주변 + DCC(1,1)-t 결합을 적합한다.
- 반복마다 model_y 로 2019..y 경로를 실제 날짜 위에 모의하고, 연간 SVR 재적합부터 공동 통계량까지 전 과정을 반복한다.
- CCC-t 는 같은 시드(공통 난수)로 돌린 민감도다. DCC 가 부적합해도 CCC 로 대체하지 않는다.

**적합도 게이트.**
- N1 수치: 어느 해든 실패하면 해당 ETF 또는 전체가 무효다.
- N3 ETF 별: 첨도·r² 자기상관·분산·정확 0 비율·LB(z, z²).
- N4 쌍별: 상관·하위 5% 동시 초과·60일 상관 sd.
- N3·N4 는 연도 모형마다 관측(자료 < y) 을 모의 envelope 0.5–99.5% 와 비교하고, 5개 연도 중 2개 이상 벗어나면 탈락이다.
- N5 (주변 CUSUM 본체) 는 진단만 한다.
"""),
        code(r"""
# 귀무 적합도 표 (N1 연도별 실패 · N3 · N4 · LB) 와 그림 08-9
N1 = VAL["n1"]  # 연도·모형·항목별
save_csv(N1, "null_validity_N1.csv")  # 근거
save_csv(VAL["n3"], "null_validity_N3.csv")  # 근거
save_csv(VAL["n4"], "null_validity_N4.csv")  # 근거
save_csv(VAL["lb"], "null_validity_ljungbox.csv")  # 근거
display(N1[~N1.ok])  # 실패 항목만
display(VAL["n3"][["ticker", "N1_margin_ok_all_years", "kurt_years_outside", "acf_r2_years_outside", "var_years_outside", "zero_share_years_outside", "lb10_z_p_years_below_0.01", "lb10_z2_p_years_below_0.01", "N3_pass"]])  # ETF 별
display(VAL["n4"][["pair", "corr_years_outside", "coexceed_years_outside", "rollcorr_sd_years_outside", "N4_fail_count", "N4_pass"]])  # 쌍별
print("H0-B 유효 단계:", [k for k, v in VAL["valid_stage"].items() if v], "| 유효 부분집합:", sum(VAL["valid_subset"].values()), "/ 57")  # 요약
N5 = A.n5_marginal(OBS)  # 주변 CUSUM 본체 진단
save_csv(N5, "null_diagnostic_N5_marginal_cusum.csv")  # 근거
display(N5.groupby("ticker")[["median_inside", "iqr_inside"]].mean())  # 칸 비율
P9 = F.fig_validity(VAL["n3"].rename(columns=lambda c: c.replace("_last", "")), VAL["n4"], FIG, "08-9")  # 적합도 그림 (마지막 연도 모형 기준 표시)
display(Image(filename=str(P9[0]), width=950))  # 렌더 확인
"""),
        code(r"""
# H0-A 진단 · 초기조건 민감도 · 귀무 분포 비교 그림 08-5
H0AD = A.h0a_diagnostics(OBS)  # 접합부·허용 이동·중복
save_csv(H0AD, "h0a_diagnostics.csv")  # 근거
display(H0AD)  # 표
ROB = A.robustness_compare(OBS)  # burn-in 500 vs 2000
save_csv(ROB, "robustness_burnin.csv")  # 근거
display(ROB.pivot_table(index="statistic", columns="quantile", values=["burn500", "burn2000"]).round(3))  # 분위 비교
NULL_CCC = np.load(ROOT / "outputs/t15/mc/null_eval_ccc.npz")  # CCC 5,000 (같은 시드)
H0A = {m: np.load(ROOT / f"outputs/t15/mc/h0a_{m}.npz") for m in CFG["null_models"]["H0A"]["methods"]}  # H0-A 두 방법
st_obs = STAGE.set_index("stage").obs  # 관측 단계 통계량
NULLS = {}  # 통계량별 귀무 묶음
for name, key, k in (("S1: M_S1", "M_subset", 0), ("S2: C_S2", "C_stage", 0), ("S4: C_S4", "C_stage", 2)):  # 대표 세 통계량
    NULLS[name] = {"H0-A 원형 이동": H0A["circular_shift_within_year"][key][:, k], "H0-A 블록": H0A["circular_block_bootstrap_within_year"][key][:, k], "H0-B DCC-t (주)": NULL_DCC[key][:, k], "H0-B CCC-t (민감도)": NULL_CCC[key][:, k]}  # 네 분포
P5 = F.fig_nulls({"S1: M_S1": st_obs["S1"], "S2: C_S2": st_obs["S2"], "S4: C_S4": st_obs["S4"]}, NULLS, FIG, "08-5")  # 비교 그림
display(Image(filename=str(P5[0]), width=950))  # 렌더 확인
"""),
        interp("ch11_12"),
        # ── 13 ──
        md(r"""
## 13. 합성 검정력·오경보

**설계.**
- 모든 반복에서 연간 SVR 재적합을 포함한다.
- 변화 연도는 균등하게 뽑고, 연중 위치는 130–170, 지속은 연말까지다. 분산 배율은 ×2 / ×0.5 다.

| 시나리오 | 내용 | 목표 |
|---|---|---|
| V1 | 069500·229200 동시 ×2 | S1 |
| V2 | V1 + 148070 ×2 | S1·S2 |
| V3_d1·d3·d5 | V1 + 148070 이 1·3·5일 늦게 ×2 | S2 (J_all) |
| V4 | 148070·133690 만 ×2 | 부분집합 |
| V5 | S1 ×2, 148070 ×0.5 | S1·S2 |
| V6 | 분산 불변, 상관만 max(Q̄, 0.7) | S1·S5 |
| V7 | 정상 공통 충격 −6σ 하루 (모수 불변) | **음성 대조** |

**조건부 귀무 유효성.**
- V1 은 앞 단계(S1)만 실제로 변하고 S2–S5 의 신규 ETF 는 변하지 않는 상황이다. 이때 C_Sk 의 기각률이 α=0.02 를 넘지 않아야 한다.
- V2 에서는 S3–S5 를 같은 방식으로 본다.

**검출률.** 분모는 **전체 반복**이다. 검출된 반복만 따로 세지 않는다.

**크기.**
- holdout 귀무 1,000 반복을 관측처럼 판정해 실제 크기를 잰다.
- 단기 q 후보·E(h)·개별 CUSUM 의 첫 반응 지연도 같은 반복에서 잰다.
"""),
        code(r"""
# 실제 크기 (holdout) · 경로 수준 판정 · 유의일 검출률 · 지연 · 그림 08-6
SIZE = A.size_check(OBS)  # holdout 1,000 → 실제 크기
save_csv(SIZE, "size_check_holdout.csv")  # 근거
display(SIZE)  # 크기
for k in ("path", "detection", "delays", "criticals"):  # 네 표
    save_csv(POWER[k], f"power_{k}.csv")  # 근거
display(POWER["path"].round(3))  # 시나리오별 경로 수준 기각률·참여
display(POWER["detection"][["scenario", "family", "R", "detected_60", "detected_60_wilson_low", "detected_60_wilson_high", "detected_within_5", "detected_within_20", "median_delay_detected", "false_sig_before_tau", "ep_start_err_median", "ep_end_err_median"]].round(3))  # 검출
P6 = F.fig_power(POWER["detection"], POWER["delays"], FIG, "08-6")  # 검정력 그림
display(Image(filename=str(P6[0]), width=950))  # 렌더 확인
"""),
        interp("ch13"),
        # ── 14 ──
        md(r"""
## 14. 계층적 다중검정

**오류 예산.**
- 전체 α = 0.05 = 주 경로 0.020 + 부분집합 0.020 + 가격 예약 0.010 (사용하지 않음).

**고정 순서 절차의 오류 통제 전제.**
- 단계 k 의 검정은 단계 1..k−1 이 모두 기각됐을 때만 확증 지위를 갖는다. 각 단계 검정이 그 단계의 귀무에서 크기 ≤ α 이면 가족 FWER ≤ α 다.
- 각 단계 검정은 전체 무변화 DCC 귀무에서 크기를 맞췄다 (holdout 으로 확인).
- 그러나 "앞 단계가 실제로 변한" 부분 귀무에서는 크기가 보장되지 않는다. 그래서 13장의 조건부 귀무 유효성 검사로 따로 확인했다. 실패한 단계는 확증에서 뺀다.

**MC 정밀도.**
- 모든 p 에 Clopper–Pearson 99% 구간을 붙인다. 구간이 기준을 포함하면 `INSUFFICIENT_MONTE_CARLO` 다.
- 사전에 정한 연장 규칙(+25,000 회 1회, 24시간 예산 이내) 을 적용했는지 함께 기록한다.
"""),
        code(r"""
# 다중검정 요약: 주 경로 사슬 · 부분집합 Holm · minP 민감도 · CCC 민감도 · 연장 규칙 적용 여부
MT = pd.DataFrame([{"family": "주 경로 S1–S5 (고정 순서 α=0.02)", "hypotheses": 5, "significant_h0b": int((STAGE.confirmatory_status == "SIGNIFICANT_H0B").sum()), "chain_stop_stage": next((s for s, c in zip(STAGE.stage, STAGE.confirmatory_status) if c != "SIGNIFICANT_H0B"), "없음"), "insufficient_mc": int((STAGE.status == "INSUFFICIENT_MONTE_CARLO").sum())}, {"family": "부분집합 57 (Holm α=0.02)", "hypotheses": 57, "significant_h0b": int((SUB.status == "SIGNIFICANT_H0B").sum()), "chain_stop_stage": "—", "insufficient_mc": int((SUB.status == "INSUFFICIENT_MONTE_CARLO").sum())}])  # 가족 요약
EXT = json.loads((ROOT / "research/joint_cusum_w3/MC_EXTENSION_DECISION.json").read_text())  # 연장 규칙 판정 기록
MT["extension_rule"] = EXT["decision"]  # 적용 여부
save_csv(MT, "multiple_testing_summary.csv")  # 근거
display(MT)  # 표
display(SUB[SUB.p_minp_adjusted.notna()].sort_values("p_minp_adjusted").head(8)[["subset", "p_dcc", "p_minp_adjusted", "holm_status"]])  # minP 민감도
"""),
        # ── 15 ──
        md(r"""
## 15. 공동 반응 구간 추출

**두 대상을 구분한다.**
- **공동 반응 날짜**: J_max(S,t) = max_{p,w} J_all 이 유의일 기준 이상인 날이다. S1 은 귀무 M_S1 의 98% 분위, 부분집합은 1−0.02/57 분위를 쓴다.
- **공동 반응 구간**: J_max ≥ c0 = −log 0.01 인 연속일이다. 비반응일은 건너뛰지 않는다.
  - 구간 수준 귀무 통계량은 누적 초과량 Σ(J_max − c0) 의 반복별 최대값이다.
  - 구간 경계와 지속의 유의성은 S1 에서만, 그리고 그 p ≤ 0.02 이고 S1 유의일 검정이 기각됐을 때만 주장한다.
  - 유의일이 하나 있다고 해서 구간 전체 경계가 유의한 것은 아니다.

**시점 필드.** `episode_start_at` · `episode_end_at` · `joint_anchor_at` (최대 점수일) · `joint_confirmed_at` (시차를 반영한 첫 이용 가능일) · `episode_confirmed_at` (끝 다음 거래일) · `retrospective_p_value` · `inference_completed_at`.
"""),
        code(r"""
# 57개 집합의 탐색 구간 · 유의일 수 · 구간 수준 p · 판정 · 방향 (16장)
EP = A.direction(OBS, A.episodes(OBS, TESTS, VAL))  # 구간 + 방향
save_csv(EP, "joint_episodes.csv")  # 근거 (날짜·점수만, 가격 없음)
display(EP.groupby("size").agg(episodes=("subset", "size"), with_sig_days=("n_days_ge_day_critical", lambda s: int((s > 0).sum()))))  # 크기별
display(EP.day_level_status.value_counts().rename("구간 수 (유의일 판정)"))  # 상태
TOP = EP.sort_values("cumulative_excess", ascending=False).head(15)  # 누적 초과 상위
display(TOP[["subset", "episode_start_at", "episode_end_at", "joint_confirmed_at", "n_days", "max_J", "cumulative_excess", "n_days_ge_day_critical", "p_label", "day_level_status", "episode_level_status", "direction"]])  # 상위 구간
"""),
        code(r"""
# 그림 08-7: 상위 공동 구간과 두 사례 창 확대 (유의일 음영은 그 집합이 유의일 기준을 넘은 날)
dates = OBS.dates  # 평가일
def sig_flag(subset):  # 집합의 유의일 플래그
    dj = DAILY[DAILY.subset == subset].set_index("date").reindex(dates)  # 일별 점수
    crit = EP[EP.subset == subset].day_critical.iloc[0] if (EP.subset == subset).any() else np.inf  # 유의일 기준
    return (dj.J_all_max >= crit).to_numpy()  # 플래그
top1 = TOP.iloc[0]  # 누적 초과 1위 구간
WIN = [(f"누적 초과 1위: {top1.subset} ({top1.episode_start_at}~{top1.episode_end_at}, {top1.direction})", str(pd.Timestamp(top1.episode_start_at) - pd.Timedelta(days=40))[:10], str(pd.Timestamp(top1.episode_end_at) + pd.Timedelta(days=40))[:10]), ("2024-08 사례 (S1 기준 음영)", "2024-07-10", "2024-10-15"), ("2025-04 사례 (S1 기준 음영)", "2025-03-10", "2025-06-15")]  # 세 창
SIGD = {WIN[0][0]: sig_flag(top1.subset), WIN[1][0]: sig_flag("069500+229200"), WIN[2][0]: sig_flag("069500+229200")}  # 음영
P7 = F.fig_episode_zoom(OBS, WIN, SIGD, NAMES, FIG, "08-7")  # 확대 그림
display(Image(filename=str(P7[0]), width=950))  # 렌더 확인
"""),
        interp("ch15"),
        # ── 16 ──
        md(r"""
## 16. 공통 구간의 확대·축소 방향

- CUSUM-of-squares 는 방향을 주지 않는다. 그래서 구간 e² 평균을 직전 60 평가일 e² 평균으로 나눈 비율로 방향을 판정한다 (최대 점수 정책).
  - ≥ 1.25 는 확대, ≤ 0.8 은 축소다.
  - 구성원 판정이 모두 같으면 공동 확대·공동 축소, 섞이면 혼합, 아니면 판정 불가다.
- 전후 구간을 CUSUM 극대점 기준으로 고르므로 사후 선택 편향이 있다. **방향에는 유의성을 주장하지 않는다.**
- H5 보조 진단으로 구간 전후 60일 수익률 상관 변화를 기술한다 (보정 없음).
"""),
        code(r"""
# 방향 분포 (크기·유의 판정별) 와 H5 상관 변화 기술
display(pd.crosstab(EP["size"], EP.direction))  # 크기별 방향
display(pd.crosstab(EP.day_level_status, EP.direction))  # 판정별 방향
CORR = A.pair_correlation_shift(OBS, EP)  # 구간 전후 상관
save_csv(CORR, "h5_pair_correlation_shift.csv")  # 근거
display(CORR.groupby("pair").delta.describe()[["count", "mean", "50%"]].round(3))  # 쌍별 요약
"""),
        interp("ch16"),
        # ── 17 ──
        md(r"""
## 17. 5·10·20일 가격 반응 (탐색, `EXPLORATORY_REUSED_DATA`)

- **기준일**: 공동 신호 이용 가능일(`joint_confirmed_at`) 종가의 다음 날부터 잰다. 기준 ETF 날짜를 매매 가능 시점으로 소급하지 않는다.
- **비교**: 단독 반응, 2종 이상 공동 반응, H0-B 유의 구간, 대조일.
  - 대조일은 같은 ETF·연도에서 그날의 사전 U_V(q=20) 십분위가 같고 ±20일 안에 후보가 없는 날이다. 매칭 변수는 그날까지의 정보만 쓴다.
- **결과 변수**: 누적 로그수익률, 나머지 5종 평균 대비 상대값, 경로 최대 상승·하락, 반전 비율.
- **추론**: 20일 날짜 블록 bootstrap 으로 한다. 겹친 사후 구간이 있으므로 iid t 검정은 쓰지 않는다.
- 2021–2025 는 이미 탐색한 자료다. 확증 검정은 미래 독립 자료에서 α=0.01 로 한다 (미사용). W2 의 −0.84%p 를 검증된 가설로 쓰지 않는다.
"""),
        code(r"""
# 가격 반응 요약 · 미래 확증 검정의 필요 표본 · 그림 08-8
PRICE = A.price_response(OBS, EP, QS, seed=int(CFG["seed"]))  # 탐색 분석
save_csv(PRICE["summary"], "price_response_summary.csv")  # 요약만 Git (일별 수익률 미포함)
with gzip.GzipFile(WORK / "price_events.csv.gz", "wb", mtime=0) as fh:  # 사건별 수익률은 Git 제외
    fh.write(PRICE["events"].to_csv(index=False, float_format="%.10g").encode())  # 저장
display(PRICE["summary"][["group", "h", "n_events", "n_date_blocks", "median_ret", "ci95_low", "ci95_high", "median_rel_vs_other5", "share_up", "reversal_share", "label"]].round(3))  # 요약
REQ = A.confirmatory_power_requirement(PRICE["summary"], PRICE["events"])  # 미래 확증 설계
save_csv(REQ, "price_future_confirmatory_requirement.csv")  # 근거
display(REQ.round(3))  # 표
P8 = F.fig_price(PRICE["summary"], FIG, "08-8")  # 가격 그림
display(Image(filename=str(P8[0]), width=950))  # 렌더 확인
"""),
        interp("ch17"),
        # ── 18 ──
        md(r"""
## 18. 2024년 8월·2025년 4월 사례

통계 설계와 임계값을 모두 확정한 **뒤에** 해석한다. 사례 창은 승인서 §18 G6 이 지정했다. 사례 날짜를 실시간 조기 탐지에 성공한 날로 읽지 않는다.
"""),
        code(r"""
# 두 사례 창과 겹치는 공동 구간 (모든 집합) — 날짜·참여·판정·방향
for name, (a, b) in CASES.items():  # 두 사례
    m = (pd.to_datetime(EP.episode_end_at) >= pd.Timestamp(a)) & (pd.to_datetime(EP.episode_start_at) <= pd.Timestamp(b))  # 창과 겹침
    sub = EP[m].sort_values("cumulative_excess", ascending=False)  # 겹치는 구간
    save_csv(sub, f"case_episodes_{name[:7]}.csv")  # 근거
    print(name, "| 겹치는 공동 구간", len(sub), "개 | 유의일 판정 분포", sub.day_level_status.value_counts().to_dict())  # 요약
    display(sub.head(10)[["subset", "episode_start_at", "episode_end_at", "joint_confirmed_at", "max_J", "cumulative_excess", "day_level_status", "direction"]])  # 상위
"""),
        interp("ch18"),
        # ── 19 ──
        md("## 19. 결과·비지지 가설·연구 한계"),
        interp("ch19"),
        # ── 20 ──
        md(r"""
## 20. 재현성 및 최종 감사

- 본문 수치는 아래 CLAIMS 가 이 실행의 결과와 대조한다.
- 결과 파일과 그림의 SHA256 은 `figure_index_08.csv` 와 `results_index_08.csv` 에 기록한다.
- MC 산출물은 첫 셀에서 `inference_meta.json` 의 해시와 대조했다.
"""),
        code(r"""
# 본문 수치 대조 (CLAIMS) — 해석 문단에 적은 값과 이번 실행 결과가 같아야 한다
CLAIMS = json.loads((ROOT / "research/joint_cusum_w3/notebook_claims.json").read_text(encoding="utf-8"))  # 해석 문단의 수치 목록
ENV = {"STAGE": STAGE, "SUB": SUB, "SIZE": SIZE, "POWER": POWER, "EP": EP, "VAL": VAL, "COND": COND, "ELIG": ELIG, "PRICE": PRICE, "LAGSUM": LAGSUM, "INDIV": INDIV, "CASE_T": CASE_T, "W1CHK": W1CHK, "np": np, "pd": pd}  # 평가 이름공간
bad = []  # 불일치 목록
for c in CLAIMS:  # 하나씩
    got = eval(c["expr"], {}, ENV)  # 결과에서 계산 (식은 저장소에 커밋된 JSON)
    if (isinstance(c["want"], float) and not np.isclose(float(got), c["want"], atol=c.get("atol", 0))) or (not isinstance(c["want"], float) and got != c["want"]):  # 비교
        bad.append((c["id"], got, c["want"]))  # 불일치 기록
print("CLAIMS", len(CLAIMS), "개 중 불일치", len(bad))  # 요약
assert not bad, bad  # 하나라도 다르면 중단
"""),
        code(r"""
# 결과·그림 색인과 해시 (결정적 형식) — 감사 근거
fig_idx = pd.DataFrame([{"file": p.name, "sha256": sha(p)} for p in sorted(FIG.glob("fig08_*"))])  # 그림 색인
res_idx = pd.DataFrame([{"file": p.name, "sha256": sha(p)} for p in sorted(RES.glob("*.csv")) if p.name not in ("figure_index_08.csv", "results_index_08.csv")])  # 결과 색인
fig_idx.to_csv(RES / "figure_index_08.csv", index=False)  # 저장
res_idx.to_csv(RES / "results_index_08.csv", index=False)  # 저장
print("그림", len(fig_idx), "개 · 결과표", len(res_idx), "개 · 일별 Git 제외 파일:", sorted(p.name for p in WORK.iterdir()))  # 요약
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3 (R2H .venv)",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python"}
    return nb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="노트북 파일을 실제로 쓴다 (출력 비움)")
    a = ap.parse_args()
    nb = book()
    if a.write:
        nbformat.write(nb, NB)
        print("작성:", NB)
    else:
        print("검사만 (셀", len(nb.cells), "개). --write 로 쓴다")


if __name__ == "__main__":
    main()
