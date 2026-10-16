# ruff: noqa: E501
"""W2 (W2-lock-1) 05·06·07 연구보고서 노트북 생성기.

실행 출력이 있는 노트북을 무심코 지우지 않도록 --write 명시 실행만 허용한다.
생성 후 ``scripts/run_t14_notebooks.py`` 로 05→06→07 을 새 커널에서 순차 실행한다.
코드 셀의 모든 코드 줄에는 한국어 주석을 손으로 단다 (빠지면 생성 단계에서 멈춘다).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NBDIR = ROOT / "notebooks"
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
        # 노트북 규칙 테스트와 같은 판정: 따옴표로 시작하는 줄은 줄끝 주석을 인정하지 않는다.
        trailing = "#" in s and not s.startswith(("'", '"')) and HANGUL.search(s.split("#", 1)[1])
        if not (prev_comment or trailing or s in CLOSERS):
            raise ValueError(f"한국어 주석 없는 코드 줄: {line!r}")
        prev_comment = False
    return nbformat.v4.new_code_cell(text)


SETUP = r"""
# 새 커널 첫 셀: BLAS 스레드를 NumPy 로드 전에 1로 고정해 결과를 결정적으로 만든다.
import os  # 환경변수 설정
import sys  # 인터프리터·모듈 경로 확인
from pathlib import Path  # 저장소 상대 경로

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # 네 BLAS 계열 변수
    os.environ[key] = "1"  # 다중 스레드 합산 순서에 따른 비트 차이를 막는다
assert "numpy" not in sys.modules, "새 커널에서 첫 셀부터 실행해야 합니다"  # 숨은 커널 상태 금지
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t14_multihorizon_w2_v1.json").is_file())  # 저장소 루트 탐색
sys.path.insert(0, str(ROOT / "src"))  # 이 작업트리의 r2h 패키지를 우선 사용

import csv  # 보호 파일 SHA 목록
import importlib.metadata as metadata  # 설치 패키지 버전 조회
import json  # 설정·인계 파일
import platform  # Python 버전

import matplotlib.pyplot as plt  # 그림 기본 설정
import numpy as np  # 수치 배열
import pandas as pd  # 결과표
from IPython.display import Image, display  # 표·그림 출력
from matplotlib import font_manager  # 한글 글꼴 등록

# T12·W1 재현 환경과 같은 버전이어야 한다 (user-site 의 다른 numpy/pandas 를 잡으면 여기서 멈춘다).
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2"}  # W2 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": metadata.version("scipy"), "matplotlib": metadata.version("matplotlib")}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패로 처리
assert "site-packages" in np.__file__ and ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
FONT_FILE = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")  # 한글 도판용 나눔고딕
assert FONT_FILE.is_file(), "한글 도판 렌더링을 위한 나눔고딕 파일이 없습니다"  # 글꼴 없으면 중단
font_manager.fontManager.addfont(str(FONT_FILE))  # matplotlib 글꼴 목록에 등록
plt.rcParams["font.family"] = [font_manager.FontProperties(fname=str(FONT_FILE)).get_name(), "DejaVu Sans"]  # 한글 우선·기호 대체
plt.rcParams["axes.unicode_minus"] = False  # 음수 기호 깨짐 방지
pd.set_option("display.width", 200)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화

from r2h.multihorizon.core import load_cfg, sha256  # W2 동결 설정·해시
from r2h.window_study.empirical import verify_frozen  # T12 동결 입력 검증 (W1 함수 재사용)
from r2h.window_study.simulation import load_cfg as load_w1_cfg  # W1 동결 설정

CFG = load_cfg(ROOT)  # W2 동결 설정 configs/t14_multihorizon_w2_v1.json
CFG_W1 = load_w1_cfg(ROOT)  # W1 동결 설정 configs/t13_window_study_v1.json (읽기만)
SOURCE = Path(os.environ.get("T12_FROZEN_ROOT", ROOT.parents[1] / "1016/R2H_T12_Final")).resolve()  # T12 종결 작업트리 (명시 경로)
assert SOURCE.name == "R2H_T12_Final" and SOURCE.is_dir(), SOURCE  # 새 위치의 형제 기본값이 아닌 실제 경로
assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
FROZEN = verify_frozen(ROOT, SOURCE, CFG_W1)  # 00·01·02 노트북·원자료 22개·run manifest·일별 cache 20종 대조
# 계약·설정 동결 SHA 와 W1 보호 파일 153개를 대조한다.
FREEZE = [line.split(maxsplit=1) for line in (ROOT / "research/multihorizon_w2/CONTRACT_FREEZE_SHA256.txt").read_text().splitlines()[:3]]  # 동결 기록
for digest, name in FREEZE:  # 설정·계약·보호목록
    assert sha256(ROOT / name) == digest, f"동결 파일 변경: {name}"  # 결과를 본 뒤 규칙 변경 금지
PROTECTED = list(csv.DictReader(open(ROOT / "research/multihorizon_w2/W1_PROTECTED_SHA256.csv", encoding="utf-8")))  # 7205e91 시점 해시
CHANGED = [r["path"] for r in PROTECTED if sha256(ROOT / r["path"]) != r["sha256_at_7205e91"]]  # 바뀐 W1 파일
assert not CHANGED, f"W1 보호 파일 변경: {CHANGED}"  # W1 결과·노트북·계약은 읽기만
BASE = ROOT / "research/multihorizon_w2"  # W2 산출물 폴더
FIG = BASE / "figures"  # 그림 폴더
FIG.mkdir(parents=True, exist_ok=True)  # 없으면 만든다
print("작업트리:", ROOT)  # 실행 위치 기록
print("동결 T12:", FROZEN)  # 입력 검증 결과
print("W2 프로토콜:", CFG["protocol_version"], "| 설정 SHA256:", FREEZE[0][0][:16], "| 계약 SHA256:", FREEZE[1][0][:16])  # 동결 지문
print("W1 보호 파일", len(PROTECTED), "개 불변 · 실행 환경:", ACTUAL_ENV)  # 보호·환경 기록
"""


def book05() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 05 · 개별 ETF 다중 기간 변동성 국면 연구

**연구 질문.** ETF 한 종목 안에서, 여러 시간 규모(3·7·14·20·30·60·120 거래일)로 잰 변동성이 **과거보다 얼마나 높거나 낮은가**, 그리고 **직전 같은 길이 구간보다 얼마나 커지거나 줄었는가**? 그런 상태가 여러 기간에서 동시에 나타나는 날짜 구간은 어디인가? 그 구간에서 기존 SVR–GARCH–CUSUM(W1) 통계량은 어떻게 움직였는가?

**W1 과 무엇이 다른가.**

| | W1 (03·04) | W2 (이 노트북) |
|---|---|---|
| 대상 | CUSUM 검정창 w 선정 | 변동성 **상태**의 다중 기간 기술 |
| 핵심 양 | 표준화 잔차 e 의 창 내 CUSUM 통계량 T_w | 수익률 제곱의 평균 V⁽q⁾, 직전 대비 로그비 D⁽q⁾, 과거 분위 U |
| 기준 | 합성 귀무로 보정한 연간 임계값 | ETF 자기 과거의 경험분포 (탐색적) |
| 결론 형태 | 적격 창 0/4 (최적창 없음) | 구간·순위의 기술. 유의성 주장 없음 |

W1 의 비적격 판정은 바꾸지 않는다. CUSUM 은 여기서 **탐색적 보조 신호**이며 정답 라벨이 아니다.

**용어.**
- 실현분산 대용치 V⁽q⁾: 최근 q 거래일 일별 로그수익률 제곱의 평균이다. 고빈도 자료로 만든 엄밀한 실현분산이 아니다.
- 실현 변동성 RV⁽q⁾ = √V⁽q⁾ 이고, 단위는 하루당 % 다.
- 로그분산비 D⁽q⁾ = log(V_t⁽q⁾ / V_{t−q}⁽q⁾) 다. 직전 같은 길이 구간과의 비교다.
- mid-rank 분위 U: 평가일 **이전** 값들 가운데 현재값의 위치(0–1)이며, 동점은 반으로 센다.

**입력.**
- W1 종결 커밋 `7205e91` 을 쓴다.
- 원자료 20종은 FinanceDataReader 종가이며, 기간은 2019-01-02~2026-10-02 다.
- T12 일별 잔차 cache 는 `b_nb_20261016T181251` 이다.
- 사전 계약 `research/multihorizon_w2/W2_연구계약.md` (W2-lock-1) 과 설정 `configs/t14_multihorizon_w2_v1.json` 을 쓴다.
- 계약과 설정은 신호·구간을 계산하기 **전에** 커밋했다 (`1fbdb1d`).

**연도.**
- 2019 는 기준분포 축적용이다.
- 2020 은 파일럿이다.
- **2021–2025 가 주 해석 연도다.**
- 2026 은 10/2 까지의 부분·비블라인드 구간이다.

**실행.** `python scripts/t14_build_notebooks.py --write` 다음에 `python scripts/run_t14_notebooks.py` 를 실행한다 (R2H `.venv`, 약 1분). 인터넷 접속은 하지 않는다.
"""),
        md(
            "## 0. 실행 환경·동결 입력 검증\n\n아래 셀은 버전 고정, 한글 글꼴, T12 동결 입력, W2 계약 SHA, W1 보호 파일 153개 불변을 확인한다. 하나라도 어긋나면 멈춘다."
        ),
        code(SETUP),
        md(r"""
## 1. 자료 출처·해시·수익률 단위

**왜 필요한가.** 분산·예측분산·CUSUM 을 한 표에서 비교하려면 세 값의 수익률 단위와 날짜가 같아야 한다. T12 는 % 단위 로그수익률을 썼다.

**산식.** $r_{i,t} = 100\cdot\log(P_{i,t}/P_{i,t-1})$ [%]. 이에 따라 분산 V 와 T12 의 `vhat` 은 %² 단위다.

**검사 항목.**
- 원자료 SHA256 이 T11 공식 종목표와 같은지
- cache 의 `r` 과 원자료로 계산한 r 의 최대 절대차
- `e = r/√vhat` 재현 오차. 비양수 `vhat` 은 제외하고 개수를 따로 센다
"""),
        code(r"""
# 05 엔진: 일별 특징 → 신호 → 에피소드 → 공통 구간 → 순위, CUSUM 일별 재계산과 W1 대조까지 한 번에 만든다.
from r2h.multihorizon.stage05 import run_stage05  # 05 단계 계산 (src/r2h/multihorizon/stage05.py)

S05 = run_stage05(ROOT, SOURCE, ROOT, CFG, CFG_W1)  # 원자료 SHA 대조 포함, 결과 CSV 를 research/multihorizon_w2/results/05 에 쓴다
UNI = S05["universe"]  # 종목표 (이름·유형·노출 그룹)
display(UNI[["ticker", "name", "category", "exposure_group"]])  # 20종 ETF 와 사전 고정 노출 그룹
UNITS = S05["units"]  # 단위 검사표
display(UNITS)  # 종목별 단위 검사
assert UNITS.max_abs_diff_r.max() < 1e-8  # cache r 과 원자료 % 로그수익률이 같은 단위 (직렬화 반올림 이내)
assert UNITS.max_abs_e_minus_r_over_sqrt_vhat.max() < 1e-8  # e = r/√vhat (vhat>0) 재현
print("cache r 대 원자료 r 최대 절대차:", f"{UNITS.max_abs_diff_r.max():.2e}", "% | e 재현 최대 오차:", f"{UNITS.max_abs_e_minus_r_over_sqrt_vhat.max():.2e}")  # 요약
print("정책 A 비양수 vhat (Z 점수 계산 제외 대상):", int(UNITS.n_vhat_nonpositive_A.sum()), "일")  # 비양수 예측분산 개수
"""),
        md(r"""
**해석.** cache 의 `r` 은 원자료로 계산한 % 로그수익률과 직렬화 반올림(10자리) 범위에서 같다. 따라서 V(%²)와 `vhat`(%²)은 같은 단위로 비교할 수 있다.

정책 A 의 `vhat` 가운데 9일은 0 이하다. T12 는 RAW 예측을 허용했다. 이 9일은 07 의 예측분산 정규화에서 제외하고 개수를 공개한다.
"""),
        md(r"""
## 2. 관찰기간 h, 분산기간 q, CUSUM 창 w — 세 길이는 다른 것이다

| 기호 | 뜻 | 값 | 쓰이는 곳 |
|---|---|---|---|
| **q** | 실현분산을 평균하는 기간 | 1·3·7·14·20·30·60·120 | V⁽q⁾, D⁽q⁾, U |
| **h** | 가격 누적수익률 관찰기간 | 1·3·7·14·20·30·60·120 | 07 의 C⁽h⁾, R_{t→t+h} |
| **w** | 기존 CUSUM 검정창 | 20·30·60·120 | T_w (W1 그대로) |

- 주 비교에서는 h=q 로 짝짓는다. 다만 코드와 표에서는 다른 열로 둔다.
- q=1 은 '하루 수익률 제곱' 이다. 변동성 국면이 아니라 **단일 일간 충격**으로만 표시한다 (결정 1).
- 1·3·7·14일 기간에는 CUSUM 을 적용하지 않는다 (마스터 지시서 §3.1).
- 주 중첩 분석은 q∈{3,7,14,20,30,60,120} 의 7개 기간이다. 최대 동시 반응 수는 7 이다.
- 7개 기간은 같은 수익률을 공유한다. 예를 들어 q=120 창은 q=3 창을 포함한다. 그래서 "5개 기간이 반응" 은 독립 증거 5개가 아니다.
"""),
        md(r"""
## 3. 실현분산과 변동성 수준

$$V_{i,t}^{(q)}=\frac{1}{q}\sum_{s=t-q+1}^{t} r_{i,s}^{2}\ [\%^2],\qquad RV_{i,t}^{(q)}=\sqrt{V_{i,t}^{(q)}}\ [\%/\text{일}]$$

평균을 빼지 않는다. 일별 평균수익률은 일별 변동에 비해 매우 작기 때문에, 짧은 창에서 표본평균을 빼면 오히려 잡음이 커진다. 아래 셀은 KODEX 200 의 한 날짜에서 원자료로 직접 계산한 값과 엔진 값을 맞춰 본다.
"""),
        code(r"""
# 계산 예시: 069500, 2024-08-05 (전 세계 주가 급락일) 의 q=3·20 실현분산을 원자료에서 손으로 계산해 엔진 값과 비교한다.
P = S05["prices"]["069500"].set_index("Date").Close  # 069500 종가 (원)
R = 100 * np.log(P / P.shift(1))  # % 로그수익률
DAY = pd.Timestamp("2024-08-05")  # 예시 날짜
pos = R.index.get_loc(DAY)  # 거래일 위치
FEAT = S05["features"]  # 20종 × 날짜 × q 일별 특징 (Git 제외 파일과 동일)
for q in (3, 20):  # 두 기간
    by_hand = float((R.iloc[pos - q + 1 : pos + 1] ** 2).mean())  # q 일 수익률 제곱 평균
    eng = FEAT[(FEAT.ticker == "069500") & (FEAT.q == q) & (FEAT.date == DAY)].iloc[0]  # 엔진 행
    print(f"q={q:>3}: 직접 V={by_hand:.4f} %² · 엔진 V={eng.V:.4f} %² · RV={eng.RV:.3f} %/일 · 직전 V={eng.V - eng.dV:.4f} · D={eng.D:.3f} · U_V={eng.U_V:.3f} (기준 {int(eng.n_ref_V)}개)")  # 값 비교
    assert abs(by_hand - eng.V) < 1e-9  # 엔진 = 정의
print("당일 수익률:", round(float(R.iloc[pos]), 3), "%")  # 충격 크기
"""),
        md(r"""
## 4. 직전 동일 길이 대비 로그분산비

$$D_{i,t}^{(q)}=\log\frac{V_{i,t}^{(q)}}{V_{i,t-q}^{(q)}},\quad q\ge 3$$

- D>0 이면 최근 q 일 분산이 바로 앞 q 일보다 크고, D<0 이면 작다. D=log 2≈0.69 는 분산이 2배가 됐다는 뜻이다.
- q=120 비교에는 240 거래일이 필요하다. 그래서 전년도 자료를 잇는다 (§3.3 신규 경계 규칙, W1 의 PURE 와 별개).
- 분자나 분모가 0 이면 epsilon 을 더하지 않고 `NaN` 으로 둔다. 사유는 분자 0 / 분모 0 / 둘 다 0 으로 따로 기록한다 (결정 1).
- 원 분산과 절대차 dV 는 보존한다.
"""),
        md(r"""
## 5. Mid-rank 확장형 과거 분위

$$U(x_t)=\frac{\#\{X<x_t\}+0.5\,\#\{X=x_t\}}{n},\qquad X=\{x_s:\ s<t,\ x_s\ \text{유효}\},\ n\ge 252$$

**규칙.**
- 기준집합에는 평가일보다 엄밀히 앞선 날짜만 들어간다. 현재값은 다음 날부터 기준에 들어간다.
- V 와 D 는 각자의 분포를 쓴다.
- 유효 비교값이 252 개 미만이면 `NOT_ESTIMABLE` 이다.
- 이웃 날짜의 V⁽q⁾ 는 q−1 일을 공유한다. 그래서 252 개는 252 개 독립 관측이 아니다.
- 분위는 '과거 이 ETF 기준에서 얼마나 드문가' 를 보이는 **탐색적 척도**다. 귀무분포 아래의 p값이 아니다.

**동점 예시.** 기준이 {0, 0, 1} 이고 현재값이 0 이면, U=(0+0.5·2)/3=0.333 이다. '≤' 로 세면 0.667, '<' 로 세면 0 이다. mid-rank 는 그 중간이다.
"""),
        code(r"""
# 시점 누수 검사: 미래 값을 극단적으로 바꿔도 과거 날짜의 분위가 그대로인지 실제 069500 q=20 계열로 확인한다.
from r2h.multihorizon.core import midrank_past  # 분위 함수

v20 = FEAT[(FEAT.ticker == "069500") & (FEAT.q == 20)].sort_values("date").V.to_numpy()  # 실제 V⁽20⁾ 계열
u0, n0, _ = midrank_past(v20, CFG["min_reference_obs"])  # 원 분위
v_mut = v20.copy()  # 복사본
v_mut[1200:] = 1e9  # 1,200번째 거래일 이후를 극단값으로 오염
u1, _, _ = midrank_past(v_mut, CFG["min_reference_obs"])  # 오염 후 분위
assert np.array_equal(u0[:1200], u1[:1200], equal_nan=True)  # 과거 분위 불변 = 미래 정보 미사용
assert np.allclose(u0, FEAT[(FEAT.ticker == "069500") & (FEAT.q == 20)].sort_values("date").U_V.to_numpy(), equal_nan=True)  # 엔진 값과 동일
print("누수 검사 통과: 1,200일 이후 값을 바꿔도 앞선 1,200일의 분위는 비트 단위로 같다. 최초 분위일 기준 수 =", int(n0[np.flatnonzero(np.isfinite(u0))[0]]))  # 결과
"""),
        md(r"""
## 6. 영분산과 초기 관측 부족 처리

**왜 필요한가.**
- 가격이 하루 동안 변하지 않으면 r=0 이다. 단기채권(153130)처럼 변동이 작은 ETF 에서 자주 일어난다.
- q 가 짧으면 V=0 이 되고, 로그비의 분자나 분모가 0 이 된다.
- 이런 날을 0 이나 임의의 작은 수로 채우면 '극단적 확대·축소' 신호가 인위적으로 생긴다.

아래 표는 종목·기간별 결측 사유와 비율이다. 동점이 많은 ETF 의 동점 비율도 함께 싣는다.
"""),
        code(r"""
# 결측·적격성 표: 영분산 결측 사유, 최초 분위 계산일, 2021–2025 동점 비율.
ELIG = S05["eligibility"]  # 종목 × q 표
zero = ELIG[ELIG.zero_missing_total > 0][["ticker", "q", "n_V_zero", "NUMERATOR_ZERO", "DENOMINATOR_ZERO", "BOTH_ZERO", "OK", "zero_missing_rate_of_computable", "tie_share_V", "tie_share_D"]]  # 영분산 결측이 있는 행만
display(zero.sort_values("zero_missing_rate_of_computable", ascending=False).reset_index(drop=True))  # q≥3 영분산 결측 (q=1 은 D 미산출이라 0)
q1 = ELIG[ELIG.q == 1][["ticker", "n_V_zero", "tie_share_V"]].sort_values("n_V_zero", ascending=False)  # q=1 영수익률 일수
display(q1.head(6))  # 일간 충격 채널의 영(0) 수익률·동점 비율 상위
first = ELIG.groupby("q")[["first_U_V_date", "first_U_D_date"]].max()  # 20종 중 가장 늦은 최초 분위일
display(first)  # 기간별 최초 분위 계산일 (20종 최댓값)
chk = ELIG[(ELIG.ticker == "069500") & (ELIG.q == 120)].iloc[0]  # Phase 0 검증 근거
assert str(chk.first_U_D_date)[:10] == "2020-12-29"  # Phase 0 의 120일 로그분산비 최초 분위일과 일치 (계약 §2.3 표의 '분위 최초 계산일' 은 U_D 기준)
assert (first.loc[first.index >= 3, "first_U_D_date"].astype(str).str[:10] < "2021-01-01").all() and (first.first_U_V_date.astype(str).str[:10] < "2021-01-01").all()  # 2021–2025 는 모든 q 에서 계산 가능 (q=1 은 D 미산출)
assert int(ELIG[ELIG.q >= 7].zero_missing_total.sum()) == 0  # q≥7 영분산 결측 0 (Phase 0 와 동일)
print("q=3 영분산 결측:", ELIG[(ELIG.q == 3) & (ELIG.zero_missing_total > 0)].set_index("ticker").zero_missing_total.to_dict())  # 종목별 건수
"""),
        md(r"""
**해석.**
- 영분산 결측은 q=3 의 두 종목(153130·132030)에만 있다. q≥7 에서는 없다.
- q=1 의 영(0) 수익률은 20종 모두에 있다. 이 때문에 q=1 의 분위는 0 근처 동점이 많다. 결정 1 대로 q=1 은 '일간 충격' 보조 채널로만 쓴다.
- 069500 의 120일 로그분산비 분위는 2020-12-29 부터 계산된다. Phase 0 사전 점검과 같다.
- 따라서 2020 의 긴 q 신호는 일부 기간에만 있고, 그 해는 파일럿으로만 읽는다.
"""),
        md(r"""
## 7. 8개 기간 신호

| 채널 | 조건 | 의미 |
|---|---|---|
| 고변동성 수준 `HIGH_LEVEL` | U_V ≥ 0.90 | 과거 이 ETF 기준 상위 10% 분산 |
| 저변동성 수준 `LOW_LEVEL` | U_V ≤ 0.10 | 하위 10% |
| 변동성 확대 `EXPANSION` | U_D ≥ 0.90 | 직전 대비 분산 증가가 과거 상위 10% |
| 변동성 축소 `CONTRACTION` | U_D ≤ 0.10 | 하위 10% |
| 일간 충격 `DAILY_SHOCK` (보조) | q=1 의 U_V ≥ 0.90 | 하루 수익률 제곱이 과거 상위 10% |

- 10% 는 후보를 만들기 위한 분위 기준이다. p=0.10 검정이 아니다.
- 확장형 분위라면 신호 비율이 대략 0.10 근처일 것으로 기대한다. 그러나 시기별 변동성이 다르면 크게 달라질 수 있다.
- 5%·20% 기준과 고정 504일 기준분포는 같은 데이터에 병렬로 적용한 민감도다. 주 결과는 바꾸지 않는다.
"""),
        code(r"""
# 2021–2025 신호 비율 (20종 평균) — 주 기준 10% · 확장형 기준분포.
RATES = S05["rates"]  # 기준·채널·종목·q 별 신호 비율
main_rates = RATES[(RATES.threshold_set == "main_10pct") & (RATES.reference == "expanding")]  # 주 결과
display(main_rates.pivot_table(index="channel", columns="q", values="signal_rate_core", aggfunc="mean").round(3))  # 채널 × q 평균 비율
spread = main_rates[main_rates.channel == "HIGH_LEVEL"].pivot_table(index="ticker", columns="q", values="signal_rate_core").round(2)  # 종목별 고변동성 비율
display(spread)  # 종목마다 신호 비율이 얼마나 다른가
print("고변동성 수준 q=120 신호 비율 범위:", spread[120].min(), "~", spread[120].max())  # 장기 범위
"""),
        md(r"""
**해석.**
- 짧은 q(3–30)의 평균 신호 비율은 0.07–0.10 이다. 0.10 근처지만 체계적으로 조금 낮다.
- 긴 q(60·120)의 확대·고변동성 비율은 0.04–0.09 로 더 낮다.
  - 가능한 설명은 기준분포다. 2020 년 급락기의 긴 창 분산이 확장형 기준분포의 상단을 차지하고 있으면, 이후 평가일의 값이 '상위 10%' 에 들기 어렵다.
  - 이번 계약은 이 설명을 따로 검정하지 않는다. 고정 504일 기준 민감도(§14)에서 간접적으로만 드러난다.
- 종목별 차이가 크다 (위 표).
  - 채권형 148070·153130 은 고변동성 비율이 0.15–0.38 로 높다. 이들의 2019–2020 기준기간이 2022 이후보다 조용했기 때문이다.
  - 반대로 헬스케어 143860, 원유 261220 같은 종목은 긴 q 비율이 0 이다.
  - 이것은 '2021–2025 가 그 ETF 자신의 과거 대비 조용했는가 거칠었는가' 를 반영한다. 신호 기준의 오류가 아니다.
"""),
        md(r"""
## 8. 상태별 개별 기간 에피소드

같은 ETF·q·채널에서 **연속된 신호 거래일**을 하나의 에피소드로 묶는다.
- 비신호일은 건너뛰어 병합하지 않는다. 이 점에서 W1 CUSUM 의 '5일 이내 병합' 과 다르다.
- `episode_confirmed_at` 은 마지막 신호일 다음 거래일이다. 그날 종가 후에야 에피소드가 끝났음을 안다.
- `estimated_change_at` 은 `NOT_ESTIMATED` 다. 별도 변화점 추정기를 쓰지 않았으므로, 에피소드 시작일을 구조변화의 참시점으로 적지 않는다.
"""),
        code(r"""
# 에피소드 요약 (2021–2025 시작): 채널 × q 의 에피소드 수와 지속일 중앙값·최댓값.
EP = S05["episodes"]  # 기간별 에피소드
core_ep = EP[EP.year_status == "PRIMARY"]  # 주 해석 연도
summ = core_ep.groupby(["channel", "q"]).duration_trading_days.agg(["size", "median", "max"]).unstack("q")  # 수·중앙·최대
display(summ)  # 짧은 q 는 잦고 짧은 에피소드, 긴 q 는 드물고 긴 에피소드
print("전체 에피소드:", len(EP), "| 2021–2025 시작:", len(core_ep))  # 규모
"""),
        md(r"""
## 9. 기간 간 중첩 구간 — 공통 구간

**규칙 (사용자 §6.4, 계약 §4.4).**
1. 같은 ETF·채널에서 날짜 t 에 신호가 켜진 주 q 의 수를 센다 (`overlap_count`, 0–7).
2. 그 수가 3 이상인 날이 `OVERLAP_CANDIDATE_DAY` 다.
3. 연속된 후보일의 최대 묶음을 **공통 구간**으로 정한다. 시작과 끝은 실제로 3개 이상이 동시에 반응한 날이다.
4. 서로 다른 기간의 에피소드가 이어진다는 이유로 중간의 비중첩일을 붙이지 않는다.

**순위.** (1) 구간 안 최대 동시 반응 수, (2) 지속 거래일 수의 사전식 내림차순이다. 동점은 공동 순위(min)다. 순위 범위는 ETF × 채널이다. 연도는 표시만 하고 순위 키에 넣지 않는다.

단기(3·7·14)·중기(20·30)·장기(60·120) 참여, 최대 분위, 일간 충격, CUSUM 겹침은 **설명 변수**로만 둔다. 가중합 점수로 만들지 않는다.
"""),
        code(r"""
# 공통 구간 개수: 채널 × 연도 지위, 그리고 2021–2025 의 최대 동시 반응 수 분포.
IV = S05["intervals"]  # 20종 공통 구간 (순위 포함)
display(IV.groupby(["channel", "year_status"]).size().unstack(fill_value=0))  # 연도 지위별 구간 수
P_IV = IV[IV.year_status == "PRIMARY"]  # 2021–2025 시작 구간
display(P_IV.groupby("channel").max_overlap_count.value_counts().unstack(fill_value=0))  # 최대 동시 반응 수 3–7 분포
display(P_IV.groupby(["channel", "start_year"]).size().unstack(fill_value=0))  # 연도별 구간 수
display(P_IV.groupby("channel")[["short", "mid", "long"]].mean().round(3))  # 단·중·장기 참여 비율
"""),
        md(r"""
**해석 (2021–2025).**
- 공통 구간은 네 채널 모두에서 20종 전부에 있다. 구간 수는 고변동성 290, 확대 253, 저변동성 363, 축소 262 다.
- 7개 기간이 **모두** 동시에 반응한 구간은 고변동성 23, 저변동성 9, 확대 2, 축소 0 이다.
- 같은 7개 기간이라도, 수준 채널은 오래 지속되는 상태라 긴 q 까지 동시에 켜지기 쉽다.
- 변화 채널(D)은 q 마다 비교 시점이 다르다. 그래서 7개가 같은 날 함께 켜지는 일이 드물다. 이것은 정의의 차이이지 '확대 국면이 드물다' 는 뜻이 아니다.
"""),
        md(r"""
## 10. ETF 별 탐색적 순위

각 ETF·채널의 1위 공통 구간이다. 아래 첫 표는 연도 지위와 무관한 전체 순위다 (계약 [A-5]). 두 번째 표는 같은 순위에서 2021–2025 시작 구간만 **표시**한 것이다. 순위를 다시 매기지 않는다.
"""),
        code(r"""
# ETF × 채널의 1위 구간 (동점이면 이른 것) — 전체 순위와 2021–2025 표시.
cols = ["ticker", "name", "channel", "interval_start", "interval_end", "duration_trading_days", "max_overlap_count", "active_q_ever", "year_status", "cusum_alarm_w", "cusum_coverage"]  # 표 열
TOP = IV[IV.rank_in_etf_channel == 1].sort_values("interval_start").groupby(["ticker", "channel"]).head(1)  # 1위 (공동 1위 중 가장 이른 구간)
display(TOP[TOP.channel.isin(["HIGH_LEVEL", "EXPANSION"])][cols].sort_values(["channel", "max_overlap_count", "duration_trading_days"], ascending=[True, False, False]).reset_index(drop=True))  # 고변동성·확대 1위
print("1위 구간이 2026(부분·비블라인드)에 시작하는 ETF×채널 수:", int((TOP.year_status == "PARTIAL_NON_BLIND").sum()), "/", len(TOP))  # 2026 편중
best_core = P_IV.sort_values(["max_overlap_count", "duration_trading_days"], ascending=False).groupby("channel").head(5)  # 2021–25 상위 표시
display(best_core[[*cols, "rank_in_etf_channel"]].sort_values(["channel", "max_overlap_count", "duration_trading_days"], ascending=[True, False, False]).reset_index(drop=True))  # 채널별 상위 5
"""),
        md(r"""
**해석.**
- **2026 편중.** ETF×채널 1위 구간 80개 가운데 28개가 2026 년에 시작한다. 고변동성 수준은 20개 중 14개, 확대는 20개 중 10개다.
  - KOSPI200 동일 노출 4종: 2026-02-02 ~ 10-01, 162거래일 · 7/7
  - 반도체 2026-01-27 ~ 09-28 등
  - 2026 년 국내 주식형 ETF 의 실현 변동성이 2019 년 이후 그 ETF 의 과거 분포에서 최상단에 오래 머물렀다는 뜻이다.
  - 2026 은 부분·비블라인드 자료이므로, 이 사실을 '2026 국면이 가장 중요하다' 는 결론으로 일반화하지 않는다.
- **2021–2025 안에서 가장 길게 7/7 이 유지된 고변동성 구간은 채권형이다.**
  - 단기채권 153130: 2022-08-24 ~ 2023-02-27 (127일), 2022-04-14 ~ 08-22 (89일)
  - 국고채10년 148070: 2022-03-28 ~ 08-02 (89일), 2022-08-16 ~ 12-06 (77일)
  - 2022 년 금리 급등기와 겹친다. 다만 이것은 날짜 일치일 뿐, 원인 추정이 아니다.
- **확대 채널 상위는 짧고 날카로운 사건이다.**
  - 차이나CSI300 192090: 2024-09-27 ~ 11-14, 7/7
  - 2024-08 초 국내 주식형 다수 (069500·102110·229200·반도체·철강·레버리지): 6/7
  - 2025-04 미국 주식 2종 (133690·219480): 6/7
  - 2026-02 ~ 04 에도 KOSPI200 동일 노출 3종(069500·102110·122630)의 확대 7/7 구간이 있다. 이것이 이 세 종목의 확대 채널 전체 1위다.
  - 이 사건들은 06 에서 노출 군집 단위로 다시 본다.
"""),
        md(r"""
## 11. 대표 ETF 4종의 실제 구간

대표 4종은 W1 과 같다. 069500 KODEX 200, 229200 KODEX 코스닥150, 148070 KIWOOM 국고채10년, 102110 TIGER 200 이다. 102110 은 069500 과 같은 KOSPI200 노출이다. 그래서 4종을 독립된 4개 노출로 세지 않는다.

그림은 순서대로 (1) 가격·일간 충격·기간별 RV 3단 패널, (2) U_V 히트맵, (3) U_D 히트맵, (4) 에피소드·공통 구간·CUSUM 시간축, (5) 상위 구간 사례다.
"""),
        code(r"""
# 그림 05-1: 대표 4종의 가격·일간 충격·기간별 실현 변동성 3단 패널.
from r2h.multihorizon import figures as F  # W2 그림 함수

REP = CFG["representative_tickers"]  # 대표 4종
NAMES = UNI.set_index("ticker").name.to_dict()  # 코드 → 이름
CUS = S05["cusum"]  # 일별 CUSUM 재계산 (정책·창·임계값·표본별 상태)
MAIN_C = CUS[CUS.policy == "A"].set_index(["ticker", "date"])  # 주 CUSUM: 정책 A
FIG_FILES = []  # 그림 파일 목록
for k, t in enumerate(REP):  # 대표 4종 반복
    close = S05["prices"][t].set_index("Date").Close  # 종가
    ft = FEAT[FEAT.ticker == t]  # 해당 ETF 특징
    alarm_any = MAIN_C.loc[t][[f"pipe_common_w{w}" for w in CFG["cusum_windows"]]].eq("ALARM").any(axis=1)  # 네 창 중 하나라도 경보
    FIG_FILES += F.three_panel(t, NAMES[t], close, ft, IV[IV.ticker == t], alarm_any, FIG, f"05-1{'abcd'[k]}")  # 그림 저장
    display(Image(filename=str(FIG_FILES[-2]), width=900))  # PNG 표시
"""),
        md(r"""
**그림 05-1 해석.**
- 069500·102110 두 KOSPI200 상품의 음영(고변동성 공통 구간)이 거의 같다. 같은 노출이기 때문이다.
- 국고채10년 148070 은 2022 년 전체가 고변동성 수준이다. 주식형 ETF 는 2022 가 아니라 2024-08 과 2025 말–2026 에 고변동성 구간이 몰린다.
- 보라색 CUSUM 경보는 RV 가 높은 구간과 자주 엇갈린다.
  - 예: 069500 의 2026 고변동성 구간에는 경보가 없다. 다만 그 구간의 앞부분(연초 119 거래일)은 CUSUM 을 계산할 수 없다.
  - CUSUM 은 SVR–GARCH 예측분산으로 나눈 잔차의 창 내 변화를 본다. 그래서 '변동성이 높다' 는 사실 자체에는 반응하지 않는다 (§13).
"""),
        code(r"""
# 그림 05-2·05-3: 대표 4종 × 8개 q 의 과거 분위 히트맵 (수준 U_V, 변화 U_D).
items = [(t, NAMES[t], FEAT[FEAT.ticker == t]) for t in REP]  # 대표 4종 입력
FIG_FILES += F.quantile_heatmaps(items, "U_V", FIG, "05-2", "대표 4종 — 기간별 실현분산 수준의 과거 분위 U_V (q × 거래일)")  # 수준 히트맵
display(Image(filename=str(FIG_FILES[-2]), width=900))  # 표시
FIG_FILES += F.quantile_heatmaps(items, "U_D", FIG, "05-3", "대표 4종 — 직전 동일 길이 대비 로그분산비의 과거 분위 U_D (q × 거래일)")  # 변화 히트맵
display(Image(filename=str(FIG_FILES[-2]), width=900))  # 표시
"""),
        md(r"""
**그림 05-2·05-3 해석.**
- 수준 히트맵(05-2)은 긴 q 에서 넓은 짙은 띠를 보인다. 상태가 오래 지속되기 때문이다.
- 변화 히트맵(05-3)은 짧은 q 에서 빨강·파랑이 빠르게 번갈아 나타난다. 긴 q 에서는 확대 뒤 축소가 반 박자 늦게 이어진다.
- 두 히트맵의 짙은 영역은 겹치는 날도 있지만 대부분 어긋난다. 수준이 높은 상태는 오래 지속되고, 확대(빨강)는 그 상태로 들어가는 짧은 시기에 몰린다.
- 이것이 '수준과 변화는 다른 구간을 강조한다' 는 관찰의 그림 근거다. 수치는 §14 의 Jaccard 와 겹침 비율로 확인한다.
"""),
        code(r"""
# 그림 05-4: 069500 과 148070 의 기간별 에피소드·공통 구간·CUSUM 창별 경보 시간축.
for t, k in (("069500", "a"), ("148070", "b")):  # 주식형·채권형 대비
    cw = {w: MAIN_C.loc[t][f"pipe_common_w{w}"].eq("ALARM") for w in CFG["cusum_windows"]}  # 창별 경보일
    FIG_FILES += F.episode_timeline(t, NAMES[t], EP[EP.ticker == t], IV[IV.ticker == t], cw, FIG, f"05-4{k}")  # 시간축 저장
    display(Image(filename=str(FIG_FILES[-2]), width=900))  # 표시
"""),
        md(r"""
**그림 05-4 해석.**
- 짧은 q(3·7)의 에피소드는 잘게 끊긴다. 긴 q(60·120)는 몇 달짜리 막대 하나다.
- 공통 구간(진한 막대)은 그 둘이 실제로 겹친 날만 남긴다. 그래서 긴 q 막대보다 훨씬 짧다.
- CUSUM 경보(맨 위 네 줄)는 각 연도 앞쪽 약 119 거래일 동안 표시가 없다. 공통일 규칙 때문에 계산할 수 없는 기간이다 (`NOT_AVAILABLE`, 무경보 아님).
"""),
        code(r"""
# 그림 05-5: 대표 4종 각각의 고변동성·확대 채널 1위 공통 구간 (구간 ±60 거래일).
for ch, k in (("HIGH_LEVEL", "a"), ("EXPANSION", "b")):  # 두 채널
    cases = []  # 사례 입력
    for t in REP:  # 대표 4종
        row = TOP[(TOP.ticker == t) & (TOP.channel == ch)].iloc[0]  # 1위 구간
        close = S05["prices"][t].set_index("Date").Close  # 종가
        alarm_any = MAIN_C.loc[t][[f"pipe_common_w{w}" for w in CFG["cusum_windows"]]].eq("ALARM").any(axis=1)  # 경보일
        cases.append(F.build_case(row, close, FEAT[FEAT.ticker == t], alarm_any))  # 사례 데이터
    FIG_FILES += F.case_zoom(cases, FIG, f"05-5{k}")  # 저장
    display(Image(filename=str(FIG_FILES[-2]), width=900))  # 표시
"""),
        md(r"""
**그림 05-5 해석.**
- 고변동성 1위 구간 (05-5a): 주식형 3종(069500·229200·102110)은 2026 구간이다. 국고채10년은 2022-03-28 ~ 08-02 구간이다.
- 확대 1위 구간 (05-5b)은 수준 1위 구간보다 훨씬 짧다.
  - 069500·102110: 2026-02-23 ~ 04-13 (35일)
  - 229200: 2024-08 초 (21일)
  - 148070: 9일, 5/7
- 가격 방향이 섞여 있다. 같은 '변동성 확대' 안에 하락 급변과 상승 급변이 모두 있다.
- 가격 방향은 이 연구의 신호 정의에 들어가지 않는다 (D1). 방향별 반응은 07 에서 분리한다.
"""),
        md(r"""
## 12. 기존 CUSUM 일별 경보의 재계산과 W1 대조

W1 은 일별 경보를 저장하지 않았다. 그래서 T12 잔차 `e` 와 W1 동결 임계값으로 다시 만든다. 재계산한 값은 W1 의 `04_real/alarm_metrics.csv` 와 행 단위로 일치해야 한다. 대조 항목은 다음과 같다.
- 종목·연도·정책·창
- 임계값 2종 × 표본 2종 = 6,720 행
- 유효일, 경보일, 에피소드 수, 첫 경보일

일치하지 않으면 이 노트북은 멈춘다.
"""),
        code(r"""
# W1 대조: 재계산한 일별 경보로 W1 집계를 행 단위로 재현한다.
VER = S05["verify"]  # 대조표
assert VER._merge.eq("both").all() and VER.match.all(), VER[~VER.match].head()  # 6,720 행 전부 일치해야 한다
print("W1 alarm_metrics 재현:", int(VER.match.sum()), "/", len(VER), "행 일치 (유효일·경보일·에피소드·첫 경보일)")  # 결과
# 연도 경계 검사: 매년 첫 날 공통일 표본은 계산 불가여야 하고, 연도를 넘는 창은 없다.
first_days = CUS.sort_values("date").groupby(["ticker", "year", "policy"]).head(CFG_W1["common_start_zero_based"])  # 각 연도 처음 119 거래일
assert first_days[[f"pipe_common_w{w}" for w in CFG["cusum_windows"]]].eq("NOT_AVAILABLE").all().all()  # 공통일 시작 전은 NOT_AVAILABLE
w120_first = CUS.sort_values("date").groupby(["ticker", "year", "policy"]).head(119)  # w=120 창이 차기 전 119일
assert w120_first["pipe_own_w120"].eq("NOT_AVAILABLE").all() and w120_first["T_w120"].isna().all()  # own 표본도 연도 경계를 넘지 않는다
print("연도 경계 검사 통과: 연초 119 거래일은 공통일 표본에서 모두 NOT_AVAILABLE, w=120 own 표본도 창이 차기 전 계산 없음")  # 결과
"""),
        md(r"""
## 13. 기존 CUSUM 과의 관계 (H3)

**질문.** 실현분산의 높은 수준(U_V), 직전 대비 변화(D), W1 CUSUM 통계량 T_w 는 서로 어떻게 관련되는가?

**미리 밝혀 둘 구조.** `rolling_cusum` 코드(T12·W1 원본)를 보면 세 가지가 확인된다.
1. 입력은 SVR–GARCH 예측분산으로 나눈 표준화 잔차 $e_t=r_t/\sqrt{\hat v_t}$ 다.
2. 통계량은 창 안의 제곱 누적합 경로의 최대 절대 편차다. 즉 양측이다.
3. 그 편차를 **창 자신의** 4차 적률 기반 $\hat\tau$ 로 나눈다.

그래서 T_w 는 창 전체의 변동성 수준에 대해 척도 불변이다. 측정하는 것은 '예측분산 대비 잔차 분산이 창 **안에서** 바뀌었는가' 이고, 상승과 하락 모두에 반응한다.

따라서 RV 수준과 T 의 상관이 약하더라도, 그것은 곧바로 CUSUM 이 틀렸다는 증거가 아니다. 두 양은 측정 대상이 다르다. 반대로 상관이 강하더라도, 같은 수익률에서 나온 값이므로 독립 검증이 아니다.

**표본.** 2021–2025, 정책 A, W1 연간 임계값, 공통일이다. 정책 B·base, own_pure 표본, T12 점별 임계값은 병렬 민감도로 둔다.
"""),
        code(r"""
# H3 표: (1) Spearman ρ 의 ETF 중앙값 (q=w 대각), (2) 경보일 대 비경보일 U_V 분위, (3) 구간–CUSUM 커버리지.
SP = S05["spearman"]  # ETF × q × w × 변수 × 정책
diag = SP[(SP.q == SP.w)].groupby(["policy", "variable", "w"]).spearman.median().unstack("w").round(3)  # q=w 대각의 ETF 중앙값
display(diag)  # 수준·변화와 T 의 순위상관
CT = S05["contrast"]  # 경보/비경보 분포
ct = CT[CT.q == CT.w].pivot_table(index=["variant", "w"], columns="state", values=["median_U_V", "share_U_V_ge_090", "n_days", "n_etf"]).round(3)  # q=w 비교
display(ct)  # 경보일 수가 작은 칸(w=20)은 해석하지 않는다
cov = {v: (P_IV[f"cusum_{p}alarm_w"].value_counts().reindex(["NONE", "NOT_AVAILABLE"]).fillna(0).astype(int).to_dict() | {"ALARM_겹침": int((~P_IV[f"cusum_{p}alarm_w"].isin(["NONE", "NOT_AVAILABLE"])).sum()), "평균_커버리지": round(float(P_IV[f"cusum_{p}coverage"].mean()), 3)}) for v, p in (("주(A·연간·공통일)", ""), ("A·own_pure", "A_own_"), ("A·T12 점별", "A_point_"), ("B", "B_"), ("base", "base_"))}  # 변형별 구간 겹침
display(pd.DataFrame(cov).T)  # 2021–2025 공통 구간 1,168개 중 CUSUM 경보가 겹친 구간 수와 계산 가능 비율
"""),
        code(r"""
# 그림 05-6: ρ 행렬 · 경보/비경보 분위 · 경보 전후 사건 궤적.
FIG_FILES += F.rv_cusum_relation(SP[SP.policy == "A"], CT[CT.variant == "main"], S05["event_traj"], FIG, "05-6", tuple(CFG["core_years"]))  # 저장 (사건 궤적도 2021–2025)
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
EVN = S05["events"]  # CUSUM 에피소드 첫 경보 사건
print("사건 수 (2021–2025, 정책 A·연간 임계값·공통일):", EVN[EVN.year.isin(CFG["core_years"])].groupby("w").size().to_dict(), "| 2020–2026 전체:", EVN.groupby("w").size().to_dict())  # 창별 사건 수
"""),
        md(r"""
**H3 해석 — 지지하는 관찰과 지지하지 않는 관찰을 나란히.**

| | 관찰 (2021–2025, 정책 A) |
|---|---|
| 관계 있음 쪽 | w=120 경보일의 U_V⁽¹²⁰⁾ 중앙값은 0.84 로 비경보일 0.50 보다 높다 (경보일 149일·7종). w=30 은 0.62 대 0.55 (28일·6종) |
| 관계 없음·반대 쪽 | ρ(U_V⁽q=w⁾, T_w) 의 ETF 중앙값은 −0.11 ~ −0.01 이다. w=60 경보일의 U_V⁽⁶⁰⁾ 중앙값은 0.26 으로 비경보일 0.52 보다 **낮다** (103일·11종) |
| 해석 불가 | w=20 경보일은 2일·사건 2건뿐이라 분포를 해석하지 않는다 |
| 비교 가능 범위 | 2021–2025 공통 구간 1,168개 가운데 주 CUSUM 이 하루도 계산되지 않은 구간이 496개다. 평균 계산 가능 비율은 0.56 이다. own_pure 표본에서는 그런 구간이 73개, 비율은 0.93 이다 |

**대안 설명.** w=60 경보가 낮은 RV 수준과 함께 나오는 것은 위의 구조로 설명될 수 있다. CUSUM 은 양측이고 척도 불변이다. 그래서 고변동성이 **가라앉는** 창이나, 낮은 변동성 안의 상대적 변화에도 반응한다. 이번 계약은 경보의 방향(상승/하락)을 나누지 않았으므로, 이 설명을 검증하지 않았다.

**결론의 범위.**
- 'RV 수준이 높은 날에 CUSUM 이 더 자주 경보한다' 는 w=120 에서만 기술적으로 관찰된다. 창마다 방향이 일관되지 않다.
- 세 값이 같은 수익률에서 나왔으므로, 어느 쪽도 CUSUM 의 정확도 검증이 아니다.
- W1 의 검정창 비적격(0/4) 판정은 그대로다.
"""),
        md(r"""
## 14. 통계적 해석·대안 설명·제약

### 가설별 판정 (계약 [A-13]: 지지 / 비지지 를 같은 형식으로)
"""),
        code(r"""
# 주장–근거 대조: 본문에 적은 수치를 실제 결과에서 다시 계산해 일치를 확인한다 (불일치면 멈춘다).
JAC = S05["jaccard"]  # ETF 별 고변동성 후보일 대 확대 후보일 Jaccard
SENS = S05["sensitivity"]  # 임계값·기준분포 민감도
CLAIMS = {  # 본문 수치
    # 본문 주장 (계산값, 본문값)
    "W1 대조 일치 행": (int(VER.match.sum()), 6720),
    # 본문 주장 (계산값, 본문값)
    "2021–25 공통 구간 HIGH/EXP/LOW/CON": (tuple(P_IV.channel.value_counts().reindex(["HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"]).astype(int)), (290, 253, 363, 262)),
    # 본문 주장 (계산값, 본문값)
    "2021–25 7/7 구간 HIGH/EXP/LOW/CON": (tuple(P_IV[P_IV.max_overlap_count == 7].channel.value_counts().reindex(["HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"]).fillna(0).astype(int)), (23, 2, 9, 0)),
    # 본문 주장 (계산값, 본문값)
    "주 CUSUM 미계산 구간 / 전체": ((int((P_IV.cusum_alarm_w == "NOT_AVAILABLE").sum()), len(P_IV)), (496, 1168)),
    # 본문 주장 (계산값, 본문값)
    "주 CUSUM 경보 겹침 구간": (int((~P_IV.cusum_alarm_w.isin(["NONE", "NOT_AVAILABLE"])).sum()), 33),
    # 본문 주장 (계산값, 본문값)
    "own_pure 미계산 구간": (int((P_IV.cusum_A_own_alarm_w == "NOT_AVAILABLE").sum()), 73),
    # 본문 주장 (계산값, 본문값)
    "ρ 중앙값 A q=w (20,30,60,120)": (tuple(diag.loc[("A", "U_V")].round(2)), (-0.01, -0.09, -0.11, -0.06)),
    # 본문 주장 (계산값, 본문값)
    "w120 경보/비경보 U_V 중앙값": (tuple(CT[(CT.variant == "main") & (CT.w == 120) & (CT.q == 120)].set_index("state").median_U_V.reindex(["ALARM", "NO_ALARM"]).round(2)), (0.84, 0.5)),
    # 본문 주장 (계산값, 본문값)
    "w60 경보/비경보 U_V 중앙값": (tuple(CT[(CT.variant == "main") & (CT.w == 60) & (CT.q == 60)].set_index("state").median_U_V.reindex(["ALARM", "NO_ALARM"]).round(2)), (0.26, 0.52)),
    # 본문 주장 (계산값, 본문값)
    "고변동성·확대 후보일 Jaccard 중앙값 (최소, 최대)": ((round(float(JAC.jaccard.median()), 2), round(float(JAC.jaccard.min()), 2), round(float(JAC.jaccard.max()), 2)), (0.27, 0.07, 0.59)),
    # 본문 주장 (계산값, 본문값)
    "고변동성 후보일 중 확대 후보일과 겹친 비율 (20종 합산)": (round(JAC.n_both.sum() / JAC.n_high_days.sum(), 2), 0.29),
    # 본문 주장 (계산값, 본문값)
    "ETF×채널 1위 2026 시작 (전체, 고변동성, 확대)": ((int((TOP.year_status == "PARTIAL_NON_BLIND").sum()), int(((TOP.year_status == "PARTIAL_NON_BLIND") & (TOP.channel == "HIGH_LEVEL")).sum()), int(((TOP.year_status == "PARTIAL_NON_BLIND") & (TOP.channel == "EXPANSION")).sum())), (28, 14, 10)),
    # 본문 주장 (계산값, 본문값)
    "민감도 1위 구간 유지 (5% 축소)": (int(SENS[(SENS.variant == "sens_5pct") & (SENS.channel == "CONTRACTION")].top1_overlap_retained.iloc[0]), 10),
    # 본문 주장 (계산값, 본문값)
    "민감도 1위 구간 유지 (그 외 15칸 모두 20/20)": (bool(SENS[~((SENS.variant == "sens_5pct") & (SENS.channel == "CONTRACTION"))].top1_overlap_retained.eq(20).all()), True),
}  # 끝
for k, (got, want) in CLAIMS.items():  # 하나씩
    assert got == want, f"{k}: 계산 {got} ≠ 본문 {want}"  # 본문 수치 불일치면 중단
    print(f"✓ {k}: {got}")  # 확인
display(JAC.sort_values("jaccard").reset_index(drop=True))  # ETF 별 Jaccard
display(SENS.pivot_table(index="channel", columns="variant", values=["n_intervals_core", "n_max7_core", "top1_overlap_retained"]))  # 민감도 표
"""),
        md(r"""
| 가설 | 지지하는 관찰 | 지지하지 않는·제한하는 관찰 |
|---|---|---|
| **H1** 개별 ETF 상태 변화 | 20종 모두 과거 분위 상·하위 10% 상태가 반복된다. 수준과 변화는 다른 날을 가리킨다 (고변동성·확대 후보일 Jaccard 중앙값 0.27, 범위 0.07–0.59. 고변동성 후보일 중 확대 후보일이기도 한 날은 0.29) | 분위는 자기 과거 기준의 탐색 척도다. 2020 급락이 기준분포 상단을 차지해 긴 q 신호 비율이 0.04–0.09 로 낮다. 확증적 기각이 아니다 |
| **H2** 다중 기간 공통성 | 2021–2025 공통 구간 1,168개. 7/7 동시 구간이 고변동성 23·저변동성 9·확대 2 | 7개 기간은 같은 수익률을 공유한다. 중첩 귀무분포를 보정하지 않았으므로 '유의한 공통 구간' 이 아니다. 확대·축소 7/7 은 드물다 (2·0) |
| **H3** RV–CUSUM | w=120 경보일 U_V 중앙값 0.84 > 비경보일 0.50 | ρ 중앙값 −0.11~−0.01. w=60 은 반대 방향(0.26 < 0.52). 공통 구간의 42%(496/1,168)는 CUSUM 계산 불가 |

**민감도.**
- 5%·20% 기준과 고정 504일 기준분포에서 구간 **수**는 크게 바뀐다. 예: 20% 기준 축소 구간 1,173개.
- 그러나 각 ETF·채널의 1위 구간 날짜는 16칸 가운데 15칸에서 20/20 이 유지된다. 예외는 5% 기준 축소 채널(10/20)이다.
- 주 결과는 10%·확장형 그대로다.

**대안 설명과 제약.**
1. **기준분포 효과.** 2019–2020 의 몇 달이 분위의 상단을 정한다. 같은 RV 라도 언제 평가하느냐에 따라 분위가 달라진다. 이 효과는 고정 504일 민감도에서 일부 드러난다 (고변동성 2021–25 구간 290 → 344).
2. **중첩 창 의존.** 날짜·q·ETF 사이의 강한 의존 때문에 구간 수를 독립 시행으로 세지 않는다.
3. **2026 편중.** 전체 순위 1위의 상당수가 부분·비블라인드 연도다.
4. **원자료 정의.** FDR 종가는 분배 소급조정 추정치다. O/H/L 일관성은 보장되지 않는다 (C-0012 DEC-3).
5. **사후 구간.** 시작일은 사후에 정한 구간 시작이다. 실시간 조기경보 시점이 아니다. 확인일은 `episode_confirmed_at` 이다.
"""),
        md(r"""
## 15. 재현성 및 결과 검증 — 06 으로의 인계
"""),
        code(r"""
# 그림 색인·결과 해시를 기록하고 05→06 인계 파일을 쓴다.
fig_index = pd.DataFrame({"file": [str(p.relative_to(BASE)) for p in FIG_FILES], "sha256": [sha256(p) for p in FIG_FILES]})  # 그림 해시
fig_index.to_csv(BASE / "results/05/figure_index_05.csv", index=False)  # 그림 색인 저장
MAN = S05["manifest"]  # 05 결과 해시
handoff = {"from": "05", "to": "06", "protocol_version": CFG["protocol_version"], "config_sha256": FREEZE[0][0], "contract_sha256": FREEZE[1][0], "t12_run_id": CFG["t12_run_id"], "environment": ACTUAL_ENV, "results": MAN["files_sha256"], "work_files": MAN["work_sha256"], "figure_index_sha256": sha256(BASE / "results/05/figure_index_05.csv")}  # 인계 내용
(BASE / "results/05_to_06.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 인계 파일 저장
display(pd.Series(MAN["files_sha256"]).rename("sha256").to_frame())  # 결과 CSV 해시
print("그림", len(FIG_FILES) // 2, "개 (PNG 320dpi + SVG) · 인계 파일:", BASE / "results/05_to_06.json")  # 요약
"""),
        md(r"""
**산출물 (Git 포함).** `research/multihorizon_w2/results/05/` 아래:
- `eligibility_missingness.csv`, `signal_rates.csv`, `period_episodes.csv`, `overlap_intervals.csv`
- `cusum_w1_reconciliation.csv`, `unit_checks.csv`, `sensitivity_intervals.csv`
- `h1_level_vs_change_jaccard.csv`, `h3_*.csv`
- `05_manifest.json`, `figure_index_05.csv`
- 인계 파일 `05_to_06.json`

**Git 제외.** 가격을 역산할 수 있는 일별 표는 `outputs/t14/05/` 에 둔다: `daily_features.csv.gz`, `daily_overlap.csv.gz`, `daily_cusum.csv.gz`. 해시만 인계 파일에 남긴다.

**다음 단계.** 06 은 이 인계 파일의 해시를 대조한 뒤, 같은 공통 구간을 노출 군집과 20종 전체로 확장한다.
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3 (R2H .venv)",
        "language": "python",
    }
    return nb


def book06() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 06 · 노출 군집과 20종 전체의 공통 변동성 구간 연구

**연구 질문 (H4).** 05 에서 ETF 하나씩 찾은 다중 기간 변동성 국면이 다른 ETF 에서도 같은 시기에 나타나는가? 그 반복은 같은 지수를 추종하는 상품끼리의 '복제' 인가, 서로 다른 자산군에 걸친 '공통 충격' 인가?

**왜 필요한가.** 20종 가운데 4종(KODEX 200·TIGER 200·KODEX 레버리지·KODEX 인버스)은 같은 KOSPI200 지수에 노출돼 있다. 종목 수로만 세면 KOSPI200 사건 하나가 4건으로 보인다. 그래서 다음 두 기준을 함께 제시한다.
- **ETF 등가중**: 20종을 각각 1개로 센다.
- **노출 그룹 등가중**: 17개 그룹으로 센다. KOSPI200 4종은 1개 그룹이다.

**입력.**
- 05 의 인계 파일 `results/05_to_06.json` 을 쓴다. 결과 CSV 17개와 Git 제외 일별 파일 3개의 SHA256 을 대조한다.
- W1 의 사전 고정 노출 그룹(`category_exposure`)과 T11 공식 종목표의 자산유형(category)을 쓴다.
- 새로 상관계수 군집을 만들지 않는다. 전체 기간의 상관으로 묶으면 '과거 당시 이미 알았던 분류' 처럼 보이게 되기 때문이다.

**규칙 (계약 §4.7 [A-7]–[A-9]).**
- **교차 공통일**: 같은 날·같은 채널에서 05 의 후보일(≥3개 q 동시)을 가진 노출 그룹이 3개 이상인 날. 연속된 교차 공통일이 교차 공통 구간이다.
- **순위**: (최대 그룹 수, 지속일) 사전식이다. 종목 기준 비교에서는 (최대 ETF 수, 지속일)을 쓴다.
- **그룹 내부 공통일**: 같은 그룹의 2종 이상이 같은 날 후보인 날 (KOSPI200 만 해당).
- **민감도**: 미국 주식 2종(S&P500 선물·나스닥100)을 한 그룹으로 묶은 16개 그룹.

**해석 수준.** 자산 간 의존을 보존한 귀무보정을 하지 않았다. 따라서 모든 공통성은 **탐색적 기술**이다. 여러 그룹이 동시에 반응했다는 사실을 '유의한 시장 공통 국면' 으로 쓰지 않는다.
"""),
        md("## 0. 실행 환경·동결 입력 검증"),
        code(SETUP),
        md(r"""
## 1. 05 결과의 해시·설정 검증

05 가 남긴 결과 CSV·일별 파일·그림 색인의 SHA256 을 다시 계산해 인계 파일과 맞춘다. 설정·계약 SHA 도 05 와 같아야 한다.
"""),
        code(r"""
# 05→06 인계 검증과 06 계산 (노출 군집·교차 공통 구간·그룹 내부·연도 요약·20종 전체 순위).
from r2h.multihorizon.stage06 import run_stage06  # 06 단계 계산 (src/r2h/multihorizon/stage06.py)

S06 = run_stage06(ROOT, CFG)  # 인계 해시 불일치면 여기서 멈춘다
H05 = S06["handoff05"]  # 05 인계 내용
assert H05["config_sha256"] == FREEZE[0][0] and H05["contract_sha256"] == FREEZE[1][0]  # 05 와 같은 동결 설정·계약
assert H05["environment"] == ACTUAL_ENV  # 05 와 같은 실행 환경
assert sha256(BASE / "results/05/figure_index_05.csv") == H05["figure_index_sha256"]  # 05 그림 색인 불변
print("05 인계 검증 통과: 결과", len(H05["results"]), "개 · 일별 파일", len(H05["work_files"]), "개 SHA256 일치")  # 결과
"""),
        md(r"""
## 2. ETF 유니버스와 유형, 기존 연구의 경제적 노출 그룹
"""),
        code(r"""
# 노출 그룹 정의표: 주 17개 그룹, 미국 주식 묶음 민감도 16개 그룹, 명목 배수 (07 에서 사용).
EXPO = S06["exposure_groups"]  # 노출 그룹 표
display(EXPO)  # 20종 정의
print("주 노출 그룹 수:", EXPO.exposure_group.nunique(), "| 민감도 그룹 수:", EXPO.exposure_group_us.nunique(), "| 자산유형 수:", EXPO.category.nunique())  # 그룹 수
assert EXPO.exposure_group.nunique() == 17 and EXPO.exposure_group_us.nunique() == 16  # 계약 [A-7]
display(EXPO.groupby("category").ticker.apply(list).to_frame("ETF"))  # 자산유형별 구성
"""),
        md(r"""
**표 해석.**
- 노출 그룹(17개)과 자산유형(9개)은 다른 축이다.
  - 자산유형 `broad_market` 에는 KOSPI200·코스닥150·미국 S&P500·나스닥100·중국 CSI300 이 함께 있다. 이들은 서로 다른 시장이다.
  - 노출 그룹은 **같은 지수를 추종하는 상품끼리만** 묶는다.
- 레버리지(2배)와 인버스(−1배)도 KOSPI200 그룹에 넣는다.
  - 분산 채널(V, D)은 수익률의 부호와 무관하다.
  - 배수가 m 이면 분산은 m² 배이지만, 그 ETF 자기 과거 분위 U 는 배수에 거의 영향을 받지 않는다.
"""),
        md(r"""
## 3. 군집 중복 집계 검사

KOSPI200 4종이 같은 날 모두 후보이면 ETF 수는 4 만큼 늘고, 노출 그룹 수는 1 만 늘어야 한다. 실제 일별 표에서 확인한다.
"""),
        code(r"""
# 중복 집계 검사: (n_etf − n_group) 은 그날 후보인 KOSPI200 종목 수 − 1 (최소 0) 과 같아야 한다.
DAILY = S06["cross_daily_counts"]  # 날짜 × 채널 집계
OV = S06["overlap"]  # 05 일별 중첩 표
k = OV[OV.ticker.isin(CFG["exposure_kospi200"]) & OV.overlap_candidate_day].groupby(["channel", "date"]).ticker.nunique()  # 날짜별 KOSPI200 후보 수
chk = DAILY.set_index(["channel", "date"]).join(k.rename("k200"), how="left").fillna({"k200": 0})  # 결합
assert ((chk.n_etf - chk.n_group) == (chk.k200 - 1).clip(lower=0)).all()  # 그룹 수는 KOSPI200 을 한 번만 센다
print("중복 집계 검사 통과:", len(chk), "개 날짜×채널. KOSPI200 4종 동시 후보일 수 =", int((chk.k200 == 4).sum()))  # 결과
"""),
        md(r"""
## 4. KOSPI200 동일 노출 ETF 4종 비교 — 군집 내부 구간 중첩
"""),
        code(r"""
# 그룹 내부: 2021–2025 후보일 Jaccard (쌍별) 와 ≥2종 동시 후보 구간.
WJ = S06["within_group_pair_jaccard"]  # KOSPI200 쌍 Jaccard
display(WJ.pivot_table(index=["ticker_a", "ticker_b"], columns="channel", values="jaccard").round(3))  # 쌍 × 채널
WI = S06["within_group_intervals"]  # 그룹 내부 구간
display(WI[WI.year_status == "PRIMARY"].groupby("channel").agg(구간=("duration_trading_days", "size"), 네종목_동시=("max_members", lambda s: int((s == 4).sum())), 지속일_중앙=("duration_trading_days", "median")))  # 2021–25 요약
display(WI[(WI.channel == "EXPANSION") & (WI.year_status == "PRIMARY")].reset_index(drop=True))  # 확대 채널 내부 구간 전체
from r2h.multihorizon import figures as F  # W2 그림 함수

NAMES = EXPO.set_index("ticker").name.to_dict()  # 코드 → 이름
FIG_FILES = []  # 그림 파일 목록
FIG_FILES += F.kospi200_case(OV, WJ, NAMES, CFG["exposure_kospi200"], [("2024-07-15", "2024-09-30"), ("2026-01-15", "2026-04-30")], FIG, "06-3")  # 그림 06-3
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 06-3).**
- 2021–2025 후보일 Jaccard 는 고변동성 수준에서 0.93–0.99, 확대에서 0.75–0.93 이다. 같은 지수를 추종하는 네 상품은 사실상 같은 신호를 낸다.
- 인버스 114800 이 들어간 쌍의 일치도가 가장 낮다 (확대 0.75–0.82). 원인으로는 상품 구조(−1배 일별 재조정, 영(0) 수익률 90일로 많음)를 생각할 수 있다. 이번에 검증하지는 않았다.
- 2024-08 확대 구간은 네 종목 모두 2024-08-02 에 시작한다. 끝나는 날은 08-23(인버스) ~ 09-02 로 조금 다르다.
- 2026-02 ~ 04 구간은 레버리지 122630 이 02-19 로 가장 먼저 시작한다. 069500·102110 의 02-23 보다 2거래일 빠르다.
- **결론의 범위:** 이 4종의 동시 반응은 독립된 4번의 관측이 아니라 **한 노출의 반복 측정**이다. 아래 모든 교차 집계는 이 4종을 한 그룹으로 센다.
"""),
        md(r"""
## 5. 군집 간 공통성 — 노출이 다른 ETF 쌍의 일치도
"""),
        code(r"""
# 모든 ETF 쌍 (190쌍) 의 2021–2025 후보일 Jaccard: 같은 노출 그룹 / 같은 자산유형 / 둘 다 다름.
PJ = S06["all_pair_jaccard"]  # 쌍 × 채널
tab = PJ.assign(관계=np.where(PJ.same_group, "같은 노출 그룹", np.where(PJ.same_category, "다른 노출·같은 자산유형", "다른 자산유형"))).groupby(["channel", "관계"]).jaccard.agg(["size", "median", "max"]).round(3)  # 관계별 요약
display(tab)  # 같은 노출 ≫ 같은 유형 > 다른 유형
for ch in ("HIGH_LEVEL", "EXPANSION"):  # 두 주 채널
    top = PJ[(PJ.channel == ch) & ~PJ.same_group].sort_values("jaccard", ascending=False).head(6).copy()  # 다른 노출 쌍 상위
    top["a"], top["b"] = top.ticker_a.map(NAMES), top.ticker_b.map(NAMES)  # 이름
    print(ch, "— 노출이 다른 쌍 중 일치도 상위")  # 제목
    display(top[["ticker_a", "a", "ticker_b", "b", "same_category", "n_both", "jaccard"]].round(3).reset_index(drop=True))  # 표
"""),
        md(r"""
**해석.**
- 노출이 다른 ETF 쌍의 후보일 일치도 중앙값은 낮다. 고변동성 0.09–0.11, 확대 0.11–0.18 이다. 같은 노출 그룹(0.96·0.84)과는 차이가 크다.
- 그럼에도 노출이 다른 쌍 중 일치도가 높은 조합이 있다.
  - 고변동성: 국고채10년–단기채권 0.51 (금리), 미국 S&P500–나스닥100 0.45
  - 확대: 은행–고배당 0.58, 미국 2종 0.57
  - 미국 2종을 한 그룹으로 묶는 민감도는 이 관찰 때문에 사전에 넣어 두었다 (§8).
- 일치도가 높다고 같은 원인이라는 뜻은 아니다. 두 계열은 같은 날짜 축을 공유하고 지속성이 강해, 우연히 겹치는 날도 많다.
"""),
        md(r"""
## 6. 전체 ETF 공통 구간 — 노출 그룹 기준 교차 공통 구간
"""),
        code(r"""
# 그룹 기준 교차 공통 구간 (≥3 노출 그룹 동시 후보) 과 종목 기준 (≥3 ETF) 의 개수·상위 구간.
CG = S06["cross_intervals_group"]  # 그룹 기준
CE = S06["cross_intervals_etf"]  # 종목 기준
cnt = pd.concat({"그룹 기준(≥3/17)": CG.groupby(["channel", "year_status"]).size(), "종목 기준(≥3/20)": CE.groupby(["channel", "year_status"]).size()}, axis=1).fillna(0).astype(int)  # 개수 비교
display(cnt)  # 연도 지위별 개수
cols = ["channel", "interval_start", "interval_end", "duration_trading_days", "max_count", "max_n_etf", "max_n_category", "year_status", "rank_in_channel", "groups_ever"]  # 표 열
for ch in ("HIGH_LEVEL", "EXPANSION"):  # 두 주 채널
    display(CG[CG.channel == ch].head(8)[cols].reset_index(drop=True))  # 채널 전체 순위 상위 8
FIG_FILES += F.group_count_timeline(DAILY, CG, FIG, "06-2", 17)  # 그림 06-2
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 06-2).**

1. **시장 공통 확대 사건 (2021–2025).** 노출 그룹 다수가 같은 날 변동성 확대 후보가 된 구간은 두 개가 두드러진다.
   - 2024-08-02 ~ 09-02 (21일): 최대 11/17 그룹, 14개 ETF
   - 2025-04-07 ~ 05-07 (20일): 최대 10/17 그룹, 13개 ETF
   - 이 밖에는 6개 그룹 이하다.
2. **그룹 기준 전체 1위는 2026 구간이다.**
   - 확대: 2026-01-26 ~ 04-13, 52일, 14 그룹
   - 고변동성: 2020 파일럿(2020-02-24 ~ 05-08, 17/17 그룹 전부), 그다음 2026-01-21 ~ 09-15 (160일, 13 그룹)
   - 두 해 모두 주 해석 연도 밖이다.
3. **채권·통화가 주도한 2022 고변동성 공통 구간.**
   - 2022-09-07 ~ 12-07 (62일, 7개 그룹)과 2022-05-30 ~ 07-19 (35일, 6개 그룹)에는 KOSPI200 그룹이 **없다**.
   - 대신 국고채10년·단기채권·달러선물·미국 주식·반도체·2차전지 등이 함께 반응했다.
   - 주식형이 주도한 2024-08·2025-04 와는 구성이 다른 공통 국면이다.
4. **개별 사건과의 대비.** 05 의 확대 7/7 구간인 차이나CSI300(2024-09-27 ~ 11-14)은, 같은 기간 후보 그룹이 최대 3개에 그친다. 다중 기간으로는 가장 강한 확대 가운데 하나지만, 시장 공통 사건은 아니다.
"""),
        md(r"""
## 7. ETF × 거래일 히트맵과 연도별 분포
"""),
        code(r"""
# 그림 06-1 (ETF × 거래일) 과 06-4 (연도별 후보일 비율, ETF 등가중 대 그룹 등가중).
FIG_FILES += F.etf_day_heatmap(OV, EXPO, FIG, "06-1")  # 그림 06-1
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
YS = S06["yearly_summary"]  # 연도 요약
display(YS[YS.channel.isin(["HIGH_LEVEL", "EXPANSION"])][["year", "year_status", "channel", "etf_equal_share", "group_equal_share"]].round(3).reset_index(drop=True))  # 등가중 비교
cat_cols = [c for c in YS.columns if c.startswith("cat_")]  # 자산유형 열
display(YS[(YS.channel == "HIGH_LEVEL") & YS.year.between(2020, 2026)].set_index("year")[cat_cols].round(2))  # 자산유형별 고변동성 후보일 비율
FIG_FILES += F.yearly_bars(YS, FIG, "06-4")  # 그림 06-4
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 06-1·06-4).**
- **고변동성 수준.** 2021–2025 에서 후보일 비율(노출 그룹 등가중)이 가장 높은 해는 2022(0.168)다.
  - 2022 의 높은 비율은 채권·통화 유형이 끌어올렸다 (위 자산유형 표).
  - 2026 부분 연도는 0.529 로 2021–2025 의 어느 해보다 3배 이상 높다.
- **확대.** 2021–2025 중에는 2024 가 가장 높다 (그룹 등가중 0.092). 2024-08 사건의 영향이다.
- **두 가중 방식의 차이는 작다.**
  - 대부분 연도에서 0.01 안쪽이다.
  - 예외는 고변동성 2022(ETF 0.142 대 그룹 0.168)와 2025(0.150 대 0.126)다.
  - 2022 는 KOSPI200 4종의 고변동성 후보일 비율이 0 이었던 해다. 그래서 4종을 1개로 줄이면 '후보 아님' 의 무게가 줄어 비율이 오른다.
  - 2025 는 반대로 4종이 함께 후보였던 날이 많아(0.288), 1개로 줄이면 비율이 내려간다.
"""),
        md(r"""
## 8. 종목 기준과 노출 그룹 기준 순위 비교, 미국 주식 묶음 민감도
"""),
        code(r"""
# 그림 06-5: 종목 기준 상위 교차 구간에서 최대 ETF 수와 최대 그룹 수의 차이. 미국 2종 묶음 민감도 개수.
FIG_FILES += F.rank_basis_compare(CE, FIG, "06-5")  # 그림 06-5
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
CU = S06["cross_intervals_group_us_sensitivity"]  # 미국 묶음 16개 그룹 기준
sens = pd.concat({"주(17그룹)": CG[CG.year_status == "PRIMARY"].groupby("channel").size(), "미국 2종 묶음(16그룹)": CU[CU.year_status == "PRIMARY"].groupby("channel").size(), "종목 기준(20)": CE[CE.year_status == "PRIMARY"].groupby("channel").size()}, axis=1)  # 2021–25 개수
display(sens)  # 기준별 교차 공통 구간 수
"""),
        md(r"""
**해석 (그림 06-5).**
- 종목 기준 상위 12개 구간의 대부분(고변동성 10/12, 확대 10/12)은 최대 ETF 수가 최대 그룹 수보다 3 크다. KOSPI200 4종이 함께 후보여서 1개로 줄어든 차이다.
- 차이가 0 인 구간은 KOSPI200 이 빠진 공통 국면이다. 2022 채권·통화 구간이 그 예다.
- 2021–2025 교차 공통 구간 수는 기준에 따라 조금 달라진다.
  - 고변동성: 46(주) / 48(미국 묶음) / 47(종목 기준)
  - 확대: 23 / 24 / 25
  - 노출을 어떻게 묶느냐가 '몇 개의 공통 구간' 이라는 숫자를 바꾼다. 그러나 상위 사건의 정체(2024-08·2025-04·2022 채권 국면)는 바꾸지 않는다.
"""),
        md(r"""
## 9. 20종 전체 중첩 순위 — ETF 공통 구간을 한 표로

05 의 ETF 별 공통 구간을 채널별로 합쳐 같은 키로 다시 순위를 매긴다. 각 구간에는 같은 기간 최대 후보 그룹 수와, 그룹 기준 교차 공통 구간과의 겹침 여부를 붙인다.
"""),
        code(r"""
# 20종 전체 순위표와 '개별 사건 대 공통 사건' 구분.
GL = S06["global_interval_rank"]  # 전 ETF 공통 구간 + 전체 순위 + 교차 주석
show = ["ticker", "name", "channel", "interval_start", "interval_end", "duration_trading_days", "max_overlap_count", "rank_global_channel", "rank_in_etf_channel", "year_status", "max_n_group_during", "overlaps_cross_group_interval"]  # 표 열
for ch in ("HIGH_LEVEL", "EXPANSION"):  # 두 주 채널
    display(GL[(GL.channel == ch) & (GL.year_status == "PRIMARY")].head(10)[show].reset_index(drop=True))  # 2021–25 시작 상위 10 (전체 순위 유지)
share = GL[GL.year_status == "PRIMARY"].groupby("channel").overlaps_cross_group_interval.mean().round(3)  # 교차 공통과 겹친 비율
display(share.to_frame("그룹 기준 교차 공통 구간과 겹친 ETF 구간 비율 (2021–25)"))  # 표
"""),
        md(r"""
**해석.**
- 2021–2025 의 ETF 별 고변동성 공통 구간 가운데 77.6% 는 그룹 기준 교차 공통 구간과 날짜가 겹친다. 확대는 51.8%, 저변동성 68.6%, 축소 22.9% 다.
- 고변동성 상태는 여러 시장이 함께 겪는 경우가 많다. 반면 변동성 **축소**는 종목마다 따로 일어나는 경우가 대부분이다.
- 이 비율은 '공통 충격의 비중' 추정치가 아니다. 지속성이 긴 채널일수록 우연히 겹칠 기회가 많기 때문이다.
"""),
        md(r"""
## 10. 공통 구간 순위·해석·한계 — 가설 H4 판정
"""),
        code(r"""
# 주장–근거 대조: 본문 수치를 결과에서 다시 계산해 확인한다.
PRI = lambda d: d[d.year_status == "PRIMARY"]  # 2021–25 필터
exp_top = PRI(CG[CG.channel == "EXPANSION"]).head(2)  # 2021–25 확대 상위 2
CLAIMS = {  # 본문 수치
    # 본문 주장 (계산값, 본문값)
    "2021–25 그룹 기준 교차 구간 HIGH/EXP/LOW/CON": (tuple(PRI(CG).groupby("channel").size().reindex(["HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"])), (46, 23, 43, 17)),
    # 본문 주장 (계산값, 본문값)
    "확대 상위 2 (시작, 그룹 수)": (tuple(zip(exp_top.interval_start, exp_top.max_count, strict=True)), (("2024-08-02", 11), ("2025-04-07", 10))),
    # 본문 주장 (계산값, 본문값)
    "KOSPI200 쌍 Jaccard 범위 HIGH": ((round(WJ[WJ.channel == "HIGH_LEVEL"].jaccard.min(), 2), round(WJ[WJ.channel == "HIGH_LEVEL"].jaccard.max(), 2)), (0.93, 0.99)),
    # 본문 주장 (계산값, 본문값)
    "KOSPI200 쌍 Jaccard 범위 EXP": ((round(WJ[WJ.channel == "EXPANSION"].jaccard.min(), 2), round(WJ[WJ.channel == "EXPANSION"].jaccard.max(), 2)), (0.75, 0.93)),
    # 본문 주장 (계산값, 본문값)
    "차이나 2024-09 확대 구간의 최대 그룹 수": (int(GL[(GL.ticker == "192090") & (GL.channel == "EXPANSION") & (GL.interval_start == "2024-09-27")].max_n_group_during.iloc[0]), 3),
    # 본문 주장 (계산값, 본문값)
    "2022 고변동성 그룹 등가중 비율": (round(float(YS[(YS.year == 2022) & (YS.channel == "HIGH_LEVEL")].group_equal_share.iloc[0]), 3), 0.168),
    # 본문 주장 (계산값, 본문값)
    "2026 고변동성 그룹 등가중 비율": (round(float(YS[(YS.year == 2026) & (YS.channel == "HIGH_LEVEL")].group_equal_share.iloc[0]), 3), 0.529),
    # 본문 주장 (계산값, 본문값)
    "교차 겹침 비율 HIGH/EXP/LOW/CON": (tuple(share.reindex(["HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"])), (0.776, 0.518, 0.686, 0.229)),
    # 본문 주장 (계산값, 본문값)
    "민감도 개수 HIGH (주, 미국묶음, 종목)": (tuple(sens.loc["HIGH_LEVEL"].astype(int)), (46, 48, 47)),
    # 본문 주장 (계산값, 본문값)
    "KOSPI200 4종 2022 고변동성 후보일 비율": (round(float(OV[OV.ticker.isin(CFG["exposure_kospi200"]) & (OV.channel == "HIGH_LEVEL") & (OV.date.dt.year == 2022)].overlap_candidate_day.mean()), 3), 0.0),
    # 본문 주장 (계산값, 본문값)
    "종목 기준 상위 12 중 ETF−그룹 = 3 인 구간 수 (HIGH, EXP)": (tuple(int((d.max_n_etf - d.max_n_group).eq(3).sum()) for d in (CE[CE.channel == c].sort_values(["rank_in_channel", "interval_start"]).head(12) for c in ("HIGH_LEVEL", "EXPANSION"))), (10, 10)),
    # 본문 주장 (계산값, 본문값)
    "2022-09 고변동성 교차 구간에 KOSPI200 없음": ("KOSPI200_동일노출" not in CG[(CG.channel == "HIGH_LEVEL") & (CG.interval_start == "2022-09-07")].groups_ever.iloc[0], True),
}  # 끝
for k, (got, want) in CLAIMS.items():  # 하나씩
    assert got == want, f"{k}: 계산 {got} ≠ 본문 {want}"  # 불일치면 중단
    print(f"✓ {k}: {got}")  # 확인
"""),
        md(r"""
| | 지지하는 관찰 | 지지하지 않는·제한하는 관찰 |
|---|---|---|
| **H4** 노출 군집 공통 변화 | 같은 노출(KOSPI200 4종)은 후보일 Jaccard 0.75–0.99 로 거의 같은 구간을 가진다. 노출이 다른 ETF 사이에도 2024-08 (11/17 그룹)·2025-04 (10/17) 확대, 2022 채권·통화 주도 고변동성(6–7 그룹) 같은 공통 구간이 있다 | 노출이 다른 쌍의 일치도 중앙값은 0.09–0.18 로 낮다. 다중 기간으로 가장 강한 확대 중 하나(차이나 2024-09)는 개별 사건이다. 축소 구간은 77% 가 교차 공통과 겹치지 않는다. 의존을 보존한 귀무보정이 없으므로 '유의한 공통성' 이 아니다 |

**대안 설명.**
1. **같은 달력 효과.** 모든 ETF 는 같은 거래일과 같은 기준분포 시작일(2019-01)을 공유한다. 기준분포에 들어간 시기가 같으므로 분위가 같은 방향으로 움직일 수 있다. 예: 2019–2020 이 조용했던 자산은 2022 에 일제히 '높음' 으로 보인다.
2. **지속성.** 고변동성 상태는 수개월 지속된다. 그래서 독립인 두 계열도 우연히 겹치는 날이 많다. 확대보다 고변동성의 교차 겹침 비율이 높은 것(77.6% 대 51.8%)은 이 효과와 구별되지 않는다.
3. **노출 정의.** 미국 주식 2종을 묶으면 개수가 바뀐다. 상관 기반 군집을 쓰면 더 바뀔 수 있다. 이번에는 전체 기간 상관으로 사후 군집을 만들지 않았다.

**반증 가능성.** 각 ETF 의 후보일 열을 연도 안에서 원형 이동해 자기 지속성은 보존하고 동시성만 해체하면, 교차 공통 구간 수의 귀무분포를 만들 수 있다. 관측 수가 그 분포 안에 있다면 '공통성' 은 지속성으로 설명된다. 이 검정은 W2-lock-1 범위 밖이다. 후속 연구에서 사전 등록 후 수행한다.
"""),
        md(r"""
## 11. 07 로 전달할 구간 계약
"""),
        code(r"""
# 06→07 인계: 05·06 결과 해시, 07 이 쓸 구간 표(전체 순위·교차 주석 포함)와 노출 정의.
fig_index = pd.DataFrame({"file": [str(p.relative_to(BASE)) for p in FIG_FILES], "sha256": [sha256(p) for p in FIG_FILES]})  # 그림 해시
fig_index.to_csv(BASE / "results/06/figure_index_06.csv", index=False)  # 그림 색인
MAN6 = S06["manifest"]  # 06 결과 해시
handoff = {"from": "06", "to": "07", "protocol_version": CFG["protocol_version"], "config_sha256": FREEZE[0][0], "contract_sha256": FREEZE[1][0], "environment": ACTUAL_ENV, "results": {**H05["results"], **MAN6["files_sha256"]}, "work_files": H05["work_files"], "figure_index_sha256": sha256(BASE / "results/06/figure_index_06.csv"), "interval_table_for_07": "results/06/global_interval_rank.csv", "exposure_table_for_07": "results/06/exposure_groups.csv"}  # 인계 내용
(BASE / "results/06_to_07.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 저장
display(pd.Series(MAN6["files_sha256"]).rename("sha256").to_frame())  # 06 결과 해시
print("그림", len(FIG_FILES) // 2, "개 · 인계 파일:", BASE / "results/06_to_07.json")  # 요약
"""),
        md(r"""
**07 에 넘기는 것.**
- `global_interval_rank.csv`: 05 의 ETF 별 공통 구간 전부. ETF 범위·전체 순위, 같은 기간 최대 그룹 수, 교차 공통 겹침 여부가 붙어 있다.
- `exposure_groups.csv`: 노출 그룹과 명목 배수.
- 07 은 이 구간들의 **가격 반응**과 **같은 날짜 다른 ETF 대비 상대 움직임**을 본다.

**넘기지 않는 것.** 구간을 '급등' 이나 '구조변화' 의 정답으로 쓰는 해석이다. 구간은 분산 분위 규칙으로 만든 탐색 후보다.
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3 (R2H .venv)",
        "language": "python",
    }
    return nb


def book07() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 07 · 가격 반응·ETF 상대 움직임·CNN 후보 인계

**연구 질문 (H5).**
- 05·06 에서 찾은 변동성 국면 구간에서 가격은 어떤 방향과 크기로 움직였는가?
- 같은 날짜의 다른 ETF 와 비교하면 어떤 상대적 특성이 있었는가?
- 기존 CUSUM 경보와 가격 움직임은 시간적으로 어떤 관계였는가?
- 이 구간들을 CNN 특징학습 후보로 넘길 때 무엇을 넘기고 무엇을 넘기지 말아야 하는가?

**왜 필요한가.** 이 연구의 주 대상은 방향과 무관한 변동성 국면이다 (D1). 그러나 팀의 상위 주제는 'ETF 급등 국면 탐지' 다. 그래서 변동성 국면이 가격 상승·하락과 어떻게 함께 나타나는지를 **신호와 분리된 결과**로 기술해 둬야 한다. 그래야 다음 연구가 변동성 후보를 급등 정답으로 오인하지 않는다.

**시점 규칙 (결정 4, 계약 §3-4).**

| 열 | 정의 | 언제 알 수 있나 |
|---|---|---|
| `C` (h) | $\sum_{s=t-h+1}^{t} r_s$ 과거 h 일 누적 로그수익률 [%] | t 종가 |
| `Z_A` (h) | $C/\sqrt{\sum_{s=t-h+1}^{t}\hat v_s}$ — 당시 1-step 예측분산의 사후 합으로 나눈 설명 점수 | t 종가 (다기간 사전 예측 아님) |
| `U_C` (h) | C 의 확장형 mid-rank 과거 분위 | t 종가 |
| `fwd_R` (h) | $\sum_{s=t+1}^{t+h} r_s$ 미래 h 일 | **t+h 종가 이후 (사후)** |
| `fwd_Zfix_A` | $R/\sqrt{h\,\hat v_t}$ — t 시점 분산 수준을 고정한 대용치 | t+h 이후 |
| `fwd_Zpost_A` | $R/\sqrt{\sum_{s=t+1}^{t+h}\hat v_s}$ — 미래 1-step 예측의 사후 합 | t+h 이후 |

- Z 점수는 h-step 조건부분산 예측이 아니다. 보정된 Z-검정의 p값으로 쓰지 않는다.
- 주 정책은 A 이고, B·base 는 민감도다. 비양수 `vhat` 이 들어간 창은 계산하지 않는다 (05 §1: 정책 A 9일).

**상대수익률 4종 (계약 [A-11]·[A-12]).**
1. **단순 차이**: $C_i-\text{median}_{j\neq i}C_j$
2. **표준화 차이**: $Z_{A,i}-\text{median}_{j\neq i}Z_{A,j}$
3. **동일 노출 상대**: KOSPI200 그룹 안에서 $C_i-m_i\,C_{069500}$ ($m$ = 명목 배수 +1·+2·−1)
4. **노출 조정**: $C_i/m_i$ 를 다른 ETF 의 같은 값 중앙값과 비교. 다른 자산유형 중앙값 대비 차이도 함께 제시한다.

경제적 노출이 다른 ETF 사이의 단순 상승률 차이는 우열이나 위험조정 성과가 아니다.
"""),
        md("## 0. 실행 환경·동결 입력 검증"),
        code(SETUP),
        md(r"""
## 1. 05·06 결과 및 후보 구간 해시 검증
"""),
        code(r"""
# 06→07 인계 검증 (05·06 결과 CSV 와 05 일별 파일 해시) 후 07 계산.
# 07 단계 계산 함수 (src/r2h/multihorizon/stage07.py)
from r2h.multihorizon.stage07 import regime_relative_table, run_stage07, same_exposure_tracking

SOURCE_COMMITS = "base=7205e91348c38584ecca74ea64e4bbc426730e86;contract=1fbdb1d;w2_release=see research/multihorizon_w2/W2_RELEASE_MANIFEST.json"  # 출처 커밋 (릴리스 커밋은 매니페스트에 기록)
S07 = run_stage07(ROOT, SOURCE, CFG, SOURCE_COMMITS)  # 인계 해시 불일치면 여기서 멈춘다
H06 = S07["handoff06"]  # 06 인계 내용
assert H06["config_sha256"] == FREEZE[0][0] and H06["contract_sha256"] == FREEZE[1][0] and H06["environment"] == ACTUAL_ENV  # 같은 계약·환경
assert sha256(BASE / "results/06/figure_index_06.csv") == H06["figure_index_sha256"]  # 06 그림 색인 불변
print("06 인계 검증 통과: 05·06 결과", len(H06["results"]), "개 · 05 일별 파일", len(H06["work_files"]), "개 SHA256 일치")  # 결과
"""),
        md(r"""
## 2. 과거·미래 가격 반응의 구분 검사

과거 h 일 값이 t 이후 수익률을 쓰지 않는지, 미래 h 일 값이 t 이전 수익률을 쓰지 않는지를 실제 자료로 확인한다.
"""),
        code(r"""
# 시점 검사: 원자료에서 직접 계산한 과거·미래 합과 엔진 값을 비교하고, 미래값을 오염시켜 과거 열이 그대로인지 본다.
from r2h.multihorizon.stage07 import forward_sum, trailing_sum  # 합 함수

PF = S07["price"]  # 20종 × 날짜 × h 가격 특징 (Git 제외 파일과 동일)
RW = S07["r_wide"]  # 날짜 × 20종 % 로그수익률
r0 = RW["069500"].to_numpy()  # 069500 수익률
t = RW.index.get_loc(pd.Timestamp("2024-08-05"))  # 예시 날짜 위치
row = PF[(PF.ticker == "069500") & (PF.h == 20) & (PF.date == pd.Timestamp("2024-08-05"))].iloc[0]  # 엔진 행
assert abs(row.C - r0[t - 19 : t + 1].sum()) < 1e-9 and abs(row.fwd_R - r0[t + 1 : t + 21].sum()) < 1e-9  # 정의대로
r_mut = r0.copy()  # 복사본
r_mut[t + 1 :] = 999.0  # t 이후를 오염
assert np.array_equal(trailing_sum(r_mut, 20)[: t + 1], trailing_sum(r0, 20)[: t + 1], equal_nan=True)  # 과거 합은 미래를 쓰지 않는다
r_mut2 = r0.copy()  # 복사본
r_mut2[: t + 1] = -999.0  # t 까지를 오염
assert np.isclose(forward_sum(r_mut2, 20)[t], forward_sum(r0, 20)[t])  # 미래 합은 t 까지를 쓰지 않는다
print(f"2024-08-05 069500: 과거 20일 C={row.C:.2f}% (t 종가에 앎) · 미래 20일 R={row.fwd_R:.2f}% (가용일 {row.fwd_available_at}) · Z_A={row.Z_A:.2f} · fwd_Zfix_A={row.fwd_Zfix_A:.2f}")  # 예시
"""),
        md(r"""
## 3. 기간별 누적수익률과 예측분산 대비 점수 — 전체 분포
"""),
        code(r"""
# 2021–2025 전 ETF·전 거래일의 h 별 C·Z_A·fwd_R 분포 (비교 기준선).
CORE = PF[PF.date.dt.year.isin(CFG["core_years"])]  # 주 해석 연도
base_tab = CORE.groupby("h").agg(C_중앙=("C", "median"), C_양수비율=("C", lambda s: float((s > 0).mean())), Z_A_중앙절대=("Z_A", lambda s: float(s.abs().median())), Z_B_중앙절대=("Z_B", lambda s: float(s.abs().median())), Z_base_중앙절대=("Z_base", lambda s: float(s.abs().median())), fwd_R_중앙=("fwd_R", "median"), n=("C", "size")).round(3)  # h 별 요약
display(base_tab)  # 기준선
UNCOND = CORE.groupby("h").fwd_R.median().to_dict()  # 무조건부 미래 h 일 중앙값
print("Z_A 계산 불가 (비양수·결측 vhat 포함 창) 비율, h=20:", round(float(CORE[CORE.h == 20].Z_A.isna().mean()), 4))  # 결측 비율
"""),
        md(r"""
**해석.**
- 2021–2025 의 20일 누적 로그수익률은 ETF·날짜를 합쳐 보면 중앙값이 약 +0.38% 다.
- |Z_A| 중앙값이 h 와 함께 크게 변하지 않는다. 1-step 예측분산의 합이 h 일 수익률 변동을 대체로 같은 척도로 정규화한다는 뜻이다.
- 표준정규라면 |Z| 중앙값은 0.67 이다. 관측값 0.65–0.82 는 그 근처다 (h=120 에서 가장 크다).
- 이 표는 아래 국면별 반응의 비교 기준이다. 국면별 값은 이 기준과 함께 읽는다.
"""),
        md(r"""
## 4. 변동성 확대·축소·고·저 국면별 가격 방향과 분포
"""),
        code(r"""
# 2021–2025 시작 공통 구간의 사전·구간 중·사후 반응 요약과 그림 07-1.
from r2h.multihorizon import figures as F  # W2 그림 함수

RE = S07["reaction"]  # 구간별 가격 반응
P_RE = RE[RE.year_status == "PRIMARY"]  # 주 해석 구간
cols = ["pre_C_h20", "during_C", "post_R_h20", "post_Zfix_A_h20", "post_Zpost_A_h20", "during_rel_simple", "post_rel_h20"]  # 열
summ = P_RE.groupby("channel")[cols].median().round(3)  # 중앙값
summ["during_양수비율"] = P_RE.groupby("channel").during_C.apply(lambda s: float((s > 0).mean())).round(3)  # 구간 중 상승 비율
summ["post20_양수비율"] = P_RE.groupby("channel").post_R_h20.apply(lambda s: float((s > 0).mean())).round(3)  # 사후 상승 비율
summ["n"] = P_RE.groupby("channel").size()  # 구간 수
display(summ)  # 채널별 반응
NA_END = RE.groupby(["year_status", "channel"]).post_available_at_h20.apply(lambda s: int((s == "NOT_AVAILABLE_DATA_END").sum())).unstack(fill_value=0)  # 자료 끝 결측
display(NA_END)  # 사후 20일을 계산할 수 없는 구간 수 (2026 에 집중)
FIG_FILES = []  # 그림 목록
FIG_FILES += F.reaction_boxes(RE, UNCOND, FIG, "07-1")  # 그림 07-1
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 07-1, 2021–2025 시작 구간).**
- **방향은 섞여 있다.** 구간 중 상승 비율은 고변동성 60.3%, 확대 56.5%, 저변동성 51.2%, 축소 53.1% 다. 변동성 확대·고변동성은 하락만이 아니라 상승 급변도 포함한다.
- **구간 중 수익률 중앙값은 고변동성 +0.51% 로 가장 크고, 나머지는 0 근처다.** 고변동성 구간은 길어서(중앙값 3일, 최대 127일) 상승 추세가 겹쳐 든다.
- **사전 20일:** 저변동성(+1.11%)과 축소(+1.40%)는 조용한 상승 뒤에 나타난다. 확대(+0.11%)와 고변동성(+0.16%)은 기준선(+0.38%)보다 약한 가격 뒤에 나타난다.
- **사후 20일 (사후 결과):** 고변동성 +0.69%, 축소 +0.57%, 확대 +0.25%, 저변동성 −0.19% 다. 기준선 +0.38% 와의 차이는 날짜·ETF 가 겹친 구간들의 기술 통계다. 예측력 주장이 아니다.
- **자료 끝 결측.** 2026 구간은 사후 20일을 계산할 수 없는 경우가 많다 (축소 30/73, 고변동성 14/59). 결측을 버리지 않고 `NOT_AVAILABLE_DATA_END` 로 센다. 2021–2025 구간은 모두 계산 가능하다.
"""),
        md(r"""
## 5. ETF 별 과거 기준 대비 가격 반응과 전후 궤적
"""),
        code(r"""
# 구간 시작 ±60 거래일 평균 경로 (절대·상대) 와, 후보일의 과거 20일 수익률 과거 분위 U_C.
PM = pd.read_csv(BASE / "results/07/interval_path_mean.csv", header=[0, 1], index_col=[0, 1])  # 저장된 평균 경로 (2021–25)
FIG_FILES += F.path_figure(PM, FIG, "07-2")  # 그림 07-2
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
OV = pd.read_csv(ROOT / "outputs/t14/05/daily_overlap.csv.gz", dtype={"ticker": str}, parse_dates=["date"])  # 05 일별 중첩
REL = S07["relative"]  # 일별 상대 움직임
RT = regime_relative_table(OV, REL, PF, CFG)  # 채널 × 후보일 여부 요약 (h=20)
display(RT.round(3))  # 후보일 대 비후보일
"""),
        md(r"""
**해석 (그림 07-2).** 경로는 시작 전날 종가를 0 으로 둔 누적 로그수익률이다. 그래서 −60 일의 값은 '시작 전 60일 수익률 × (−1)' 이다.
- **평균 기준.** 네 채널 모두 시작 전 60일 동안 올랐다. 확대 +3.28%, 저변동성 +2.14%, 축소 +2.07%, 고변동성 +1.87% 다.
  - 확대 구간 ETF 는 같은 기간 나머지 19종 중앙값보다 평균 2.23%p 더 올랐다.
  - 시작 뒤 60일 평균은 고변동성 +3.84%, 확대 +3.24%, 축소 +2.65%, 저변동성 +0.56% 다.
- **중앙값 기준 (결과표).** 크기가 훨씬 작다. 예를 들어 확대 구간의 시작 전 60일 상승은 +0.45%, 시작 뒤 60일은 +1.54% 다. 평균 경로는 2025 말–2026 국내 주식형처럼 큰 상승 구간 몇 개가 끌어올린 것이다.
- 따라서 '확대 직전에 가격이 올랐다' 를 일반 경향으로 읽지 않는다. 중앙값은 §4 의 사전 20일 표(+0.11%)와 같은 방향의 작은 값이다.
- ETF 자기 과거 기준(U_C)으로 보면 확대 후보일의 과거 20일 수익률 분위 중앙값은 0.42 로, 비후보일 0.50 보다 낮다. 확대는 그 ETF 기준으로 상대적으로 약한 가격 뒤에 나타나는 경향이 있다.
- 저변동성·축소 후보일은 과거 20일 상승 비율이 65% 로, 비후보일 57–58% 보다 높다.
"""),
        md(r"""
## 6. 같은 날짜 다른 ETF 대비 상대수익률 · 서로 다른 자산군과의 상대 움직임
"""),
        code(r"""
# 그림 07-4: 채널별 후보일 대 비후보일의 상대 움직임 4종.
FIG_FILES += F.regime_relative_figure(RT, FIG, "07-4")  # 그림 07-4
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
cat_rel = REL[(REL.h == 20) & REL.date.dt.year.isin(CFG["core_years"])].merge(OV[OV.channel == "EXPANSION"][["ticker", "date", "overlap_candidate_day"]], on=["ticker", "date"]).merge(S07["expo"][["ticker", "category"]], on="ticker")  # 확대 채널 × 자산유형
display(cat_rel.groupby(["category", "overlap_candidate_day"]).rel_cross_asset.median().unstack().round(3))  # 자산유형별 다른 유형 대비 (확대 후보일 여부)
"""),
        md(r"""
**해석 (그림 07-4).**
- 확대 후보일의 과거 20일 단순 상대수익률 중앙값은 +0.28%p 다. 비후보일은 −0.01 이다.
  - 그 ETF 의 절대 수익률은 약했다 (C 중앙값 0.06%).
  - 그러나 같은 날 나머지 19종의 중앙값은 더 약했다.
  - 확대 후보일은 시장 전체가 흔들린 날에 몰려 있다 (06 의 2024-08·2025-04). 그래서 '그날 다른 ETF 보다 덜 빠졌다' 는 상대 효과가 함께 잡힌다.
- 고변동성 후보일의 노출 조정 상대값은 +0.21%p 다. 레버리지·인버스를 명목 배수로 나눈 뒤 비교한 값이다.
- 축소 후보일은 반대로 단순 상대 −0.17%p, 노출 조정 −0.26%p 다. 축소는 그 ETF 가 다른 ETF 보다 덜 오른 조용한 시기에 나타난다.
- 저변동성 후보일의 '다른 자산유형 대비' 값은 +0.23%p 다. 조용한 상승 국면에 있는 주식형이 채권·통화 대비 앞서는 구성이다.
- 모든 값은 ETF·날짜를 합친 중앙값이다. 경제적 노출이 다른 상품 사이의 성과 우열로 읽지 않는다.
"""),
        md(r"""
## 7. 동일 지수 ETF 의 추적 차이 — 레버리지·인버스 구조
"""),
        code(r"""
# KOSPI200 그룹: 명목 배수 조정 후 069500 대비 20일 차이 (C_i − m_i·C_069500), 069500 고변동성 후보일 여부로 나눔.
TR = same_exposure_tracking(REL, OV, CFG)  # 추적 차이 요약 (2021–2025)
display(TR.round(3))  # 069500 행은 102110 − 069500 (같은 값이 두 행에 나온다)
IV = S07["intervals"]  # 05·06 구간표
FIG_FILES += F.tracking_figure(REL, IV[(IV.ticker == "069500") & (IV.channel == "HIGH_LEVEL")], S07["expo"].set_index("ticker").name.to_dict(), FIG, "07-3")  # 그림 07-3
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 07-3).**
- **같은 배수 상품 (TIGER 200 대 KODEX 200).** 20일 차이 중앙값은 +0.01%p, 10–90% 범위는 ±0.1%p 안쪽이다. 고변동성 여부와 거의 무관하다.
- **레버리지 122630.** '2×KODEX 200' 대비 20일 차이 중앙값이 평소 −0.54%p 다. KODEX 200 고변동성 후보일에는 **−1.21%p** 로 두 배 넘게 벌어진다.
- **인버스 114800.** 같은 비교에서 +0.03 → **−0.53%p** 다.
- 일일 재조정 상품은 기초지수 분산이 클수록 h 일 로그수익률이 m×기초보다 작아진다 (변동성 손실, 대략 $-\tfrac{m(m-1)}{2}\sigma^2 h$). 관찰된 방향과 크기 순서(레버리지 > 인버스 > 1배)는 이 설명과 맞는다. 다만 보수·괴리·배당 차이를 분리해 검정하지는 않았다.
- **시사점.** 변동성 국면에서는 '같은 노출' 상품끼리도 가격 반응이 체계적으로 달라진다. 레버리지·인버스의 가격 급등·급락을 기초지수 급등·급락과 같은 사건으로 라벨링하면 오차가 생긴다.
"""),
        md(r"""
## 8. CUSUM 경보와 가격 움직임의 시간적 관계
"""),
        code(r"""
# CUSUM 첫 경보일 대 비경보 공통일의 과거 20일 수익률, 그리고 공통 구간 시작 → 구간 안 첫 경보 시차.
CPS = pd.read_csv(BASE / "results/07/cusum_alarm_price_summary.csv")  # 요약 (2021–2025)
display(CPS.round(3))  # w × 그룹
IDX = RW.index  # 거래일 축
q = IV[(IV.year_status == "PRIMARY") & IV.cusum_first_alarm_in_interval.notna()]  # 경보가 겹친 2021–25 구간
LAGS = pd.Series([IDX.get_loc(pd.Timestamp(a)) - IDX.get_loc(pd.Timestamp(s)) for s, a in zip(q.interval_start, q.cusum_first_alarm_in_interval, strict=True)])  # 시차 (거래일)
print("경보가 겹친 2021–25 구간:", len(LAGS), "개 · 시차 중앙값", LAGS.median(), "일 · 같은 날", int((LAGS == 0).sum()), "개 · 최대", LAGS.max(), "일")  # 요약
FIG_FILES += F.cusum_price_figure(CPS, LAGS, FIG, "07-5")  # 그림 07-5
display(Image(filename=str(FIG_FILES[-2]), width=950))  # 표시
"""),
        md(r"""
**해석 (그림 07-5).**
- **경보 직전 가격.** CUSUM 첫 경보일의 과거 20일 수익률 중앙값은 비경보 공통일(+0.32%)보다 대체로 높다. w=30 은 +1.15%, w=120 은 +0.49% 다. w=60 은 +0.35% 로 비슷하다.
  - 첫 경보는 11–18건뿐이다. 그래서 방향을 일반화하지 않는다.
  - 특히 w=20 (2건)은 해석하지 않는다.
- **시차.** 2021–2025 공통 구간 가운데 CUSUM 경보가 겹친 33개 구간에서, 첫 경보는 구간 시작과 같은 날이 16개다. 중앙값은 1거래일 뒤이고, 최대 25일이다.
  - 같은 날 일어난 경우가 많은 것은 두 신호가 같은 큰 수익률 하나에 함께 반응하기 때문으로 보인다. 독립적인 '조기 경보' 가 아니다.
  - 연초 119 거래일은 CUSUM 을 계산할 수 없어, 그 시기의 구간은 비교에서 빠진다 (05 §13: 496/1,168 구간).
"""),
        md(r"""
## 9. CNN 특징학습 후보 구간 계약
"""),
        code(r"""
# CNN 후보 표: 사용자 §10 필수 22개 정보가 모두 복원되는지, 정답 라벨 열이 없는지 확인한다.
CNN = S07["cnn"]  # 후보 구간 표
REQUIRED = {"candidate_id": "candidate_id", "ticker": "ticker", "exposure_group": "exposure_group", "episode_state": "episode_state", "episode_start": "episode_start", "episode_end": "episode_end", "available_at": "available_at", "episode_confirmed_at": "episode_confirmed_at", "estimated_change_at": "estimated_change_at", "active_q": "active_q", "max_overlap_count": "max_overlap_count", "duration_trading_days": "duration_trading_days", "realized_variance_features": "rv_*", "relative_variance_features": "rel_*", "price_response_features": "px_*", "cusum_w": "cusum_w", "cusum_statistic": "cusum_statistic", "cusum_alarm_at": "cusum_alarm_at", "cusum_threshold_type": "cusum_threshold_type", "is_exploratory_candidate": "is_exploratory_candidate", "source_commit": "source_commit", "protocol_version": "protocol_version"}  # 필수 필드 → 실제 열
for need, col in REQUIRED.items():  # 22개 확인
    ok = any(c.startswith(col[:-1]) for c in CNN.columns) if col.endswith("*") else col in CNN.columns  # 접두사 또는 정확한 열
    assert ok, f"CNN 필수 필드 누락: {need}"  # 누락이면 중단
assert len(REQUIRED) == 22 and not any("label" in c.lower() for c in CNN.columns)  # 22개 · 라벨 열 없음
assert CNN.is_exploratory_candidate.all() and (CNN.estimated_change_at == "NOT_ESTIMATED").all()  # 탐색 후보 · 변화점 미추정
assert CNN.candidate_id.is_unique  # 후보 ID 유일
print("CNN 후보:", len(CNN), "행 ·", CNN.shape[1], "열 · 2021–25", int((CNN.year_status == "PRIMARY").sum()), "행 · 사후 20일 자료 끝 결측", int((CNN.px_post_available_at_h20 == "NOT_AVAILABLE_DATA_END").sum()), "행")  # 요약
display(CNN.groupby(["episode_state", "year_status"]).size().unstack(fill_value=0))  # 채널 × 연도 지위
display(CNN.head(3).T)  # 열 예시
"""),
        md(r"""
**CNN 인계 계약 (요약).** 전체 필드 사전은 `research/multihorizon_w2/CNN_후보구간_인계계약_W2.md` 에 있다.

- **후보는 정답이 아니다.**
  - `cnn_candidate_intervals_w2.csv` 는 분산 분위 규칙으로 만든 **탐색 후보**다. 행은 ETF·채널별 공통 구간 1,711개다.
  - '가격 급등' 이나 '구조변화' 의 정답 라벨로 쓰지 않는다. 표에 라벨 열을 만들지 않았다.
- **시점.**
  - `available_at` 은 구간 첫날 종가 이후다. 3개 이상 q 가 동시에 켜진 것을 그날 종가 후 안다.
  - `episode_confirmed_at` 은 구간이 끝났음을 아는 날이다.
  - `px_post_*` 열은 구간 종료 뒤 h 일의 **사후 결과**다. 입력 특징으로 쓰면 미래 정보 누수다.
- **중복.**
  - KOSPI200 4종의 구간은 거의 같은 날짜다 (06: Jaccard 0.75–0.99).
  - 학습·평가를 분할할 때는 `exposure_group` 단위로 묶어야 같은 사건이 두 쪽에 들어가지 않는다.
- **W1 후보와의 관계.** W1 의 `cnn_candidate_intervals.csv` (CUSUM 첫 경보, 142행)와는 다른 규칙이다. 두 표를 합쳐 중복 학습하지 않는다.
- **CNN 을 급등 탐지기로 평가하려면 먼저 필요한 것들** (W1 인계 계약과 같음):
  1. 독립 가격 급등 라벨과 허용 시차
  2. 음성 사례 정의
  3. 온라인 정보 차단
  4. 자산·기간 블라인드 분리
  5. 사전 비용 지표
"""),
        md(r"""
## 10. 전체 W2 연구의 통합 해석
"""),
        code(r"""
# 주장–근거 대조: 07 본문 수치를 결과에서 다시 계산해 확인한다.
CLAIMS = {  # 본문 수치
    # 본문 주장 (계산값, 본문값)
    "기준선 20일 fwd_R 중앙값": (round(UNCOND[20], 2), 0.38),
    # 본문 주장 (계산값, 본문값)
    "구간 중 상승 비율 HIGH/EXP/LOW/CON": (tuple(summ.during_양수비율.reindex(["HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION"]).round(3)), (0.603, 0.565, 0.512, 0.531)),
    # 본문 주장 (계산값, 본문값)
    "구간 중 중앙값 HIGH": (round(float(summ.loc["HIGH_LEVEL", "during_C"]), 2), 0.51),
    # 본문 주장 (계산값, 본문값)
    "사후 20일 중앙값 HIGH/CON/EXP/LOW": (tuple(summ.post_R_h20.reindex(["HIGH_LEVEL", "CONTRACTION", "EXPANSION", "LOW_LEVEL"]).round(2)), (0.69, 0.57, 0.25, -0.19)),
    # 본문 주장 (계산값, 본문값)
    "사전 20일 중앙값 LOW/CON/EXP/HIGH": (tuple(summ.pre_C_h20.reindex(["LOW_LEVEL", "CONTRACTION", "EXPANSION", "HIGH_LEVEL"]).round(2)), (1.11, 1.4, 0.11, 0.16)),
    # 본문 주장 (계산값, 본문값)
    "2026 사후 20일 자료 끝 결측 CON/HIGH": ((int(NA_END.loc["PARTIAL_NON_BLIND", "CONTRACTION"]), int(NA_END.loc["PARTIAL_NON_BLIND", "HIGH_LEVEL"])), (30, 14)),
    # 본문 주장 (계산값, 본문값)
    "2021–25 자료 끝 결측": (int(NA_END.loc["PRIMARY"].sum()), 0),
    # 본문 주장 (계산값, 본문값)
    "확대 후보일 U_C 중앙값 (후보, 비후보)": (tuple(RT[RT.channel == "EXPANSION"].set_index("overlap_candidate_day").median_U_C.reindex([True, False]).round(2)), (0.42, 0.5)),
    # 본문 주장 (계산값, 본문값)
    "확대 후보일 단순 상대 중앙값": (round(float(RT[(RT.channel == "EXPANSION") & RT.overlap_candidate_day].median_rel_simple.iloc[0]), 2), 0.28),
    # 본문 주장 (계산값, 본문값)
    "고변동성 후보일 노출 조정 상대": (round(float(RT[(RT.channel == "HIGH_LEVEL") & RT.overlap_candidate_day].median_rel_exposure_adj.iloc[0]), 2), 0.21),
    # 본문 주장 (계산값, 본문값)
    "축소 후보일 단순·노출조정 상대": (tuple(RT[(RT.channel == "CONTRACTION") & RT.overlap_candidate_day][["median_rel_simple", "median_rel_exposure_adj"]].iloc[0].round(2)), (-0.17, -0.26)),
    # 본문 주장 (계산값, 본문값)
    "저변동성 후보일 다른 자산유형 대비": (round(float(RT[(RT.channel == "LOW_LEVEL") & RT.overlap_candidate_day].median_rel_cross_asset.iloc[0]), 2), 0.23),
    # 본문 주장 (계산값, 본문값)
    "레버리지 추적 차이 (비후보, 후보)": (tuple(TR[TR.ticker == "122630"].set_index("overlap_candidate_day")["median"].reindex([False, True]).round(2)), (-0.54, -1.21)),
    # 본문 주장 (계산값, 본문값)
    "인버스 추적 차이 (비후보, 후보)": (tuple(TR[TR.ticker == "114800"].set_index("overlap_candidate_day")["median"].reindex([False, True]).round(2)), (0.03, -0.53)),
    # 본문 주장 (계산값, 본문값)
    "CUSUM 겹침 구간 시차 (n, 같은 날, 중앙값, 최대)": ((len(LAGS), int((LAGS == 0).sum()), float(LAGS.median()), int(LAGS.max())), (33, 16, 1.0, 25)),
    # 본문 주장 (계산값, 본문값)
    "CUSUM 첫 경보 과거 20일 중앙값 w30/w60/w120": (tuple(CPS[CPS.group == "first_alarm"].set_index("w").median_C20.reindex([30, 60, 120]).round(2)), (1.15, 0.35, 0.49)),
    # 본문 주장 (계산값, 본문값)
    "평균 경로 −60일 (HIGH, EXP, LOW, CON)": (tuple(round(float(PM.loc[c][("path", "mean")].loc[-60]), 2) for c in ("HIGH_LEVEL", "EXPANSION", "LOW_LEVEL", "CONTRACTION")), (-1.87, -3.28, -2.14, -2.07)),
    # 본문 주장 (계산값, 본문값)
    "평균 경로 +60일 (HIGH, EXP, CON, LOW)": (tuple(round(float(PM.loc[c][("path", "mean")].loc[60]), 2) for c in ("HIGH_LEVEL", "EXPANSION", "CONTRACTION", "LOW_LEVEL")), (3.84, 3.24, 2.65, 0.56)),
    # 본문 주장 (계산값, 본문값)
    "확대 상대 경로 −60일 평균, 중앙 경로 −60·+60": ((round(float(PM.loc["EXPANSION"][("path_rel", "mean")].loc[-60]), 2), round(float(PM.loc["EXPANSION"][("path", "median")].loc[-60]), 2), round(float(PM.loc["EXPANSION"][("path", "median")].loc[60]), 2)), (-2.23, -0.45, 1.54)),
    # 본문 주장 (계산값, 본문값)
    "CNN 후보 행 수": (len(CNN), 1711),
    # 본문 주장 (계산값, 본문값)
    "사후 20일 상대 (4채널 모두 음수)": (bool((summ.post_rel_h20 < 0).all()), True),
}  # 끝
for k, (got, want) in CLAIMS.items():  # 하나씩
    assert got == want, f"{k}: 계산 {got} ≠ 본문 {want}"  # 불일치면 중단
    print(f"✓ {k}: {got}")  # 확인
"""),
        md(r"""
### H5 판정

| 지지하는 관찰 | 지지하지 않는·제한하는 관찰 |
|---|---|
| 국면별 사전 가격이 다르다: 저변동성·축소는 조용한 상승(+1.1–1.4%) 뒤, 확대는 약한 가격(+0.11%, U_C 0.42) 뒤에 나타난다. 확대 후보일은 같은 날 다른 ETF 보다 덜 빠졌다 (+0.28%p). 레버리지·인버스의 추적 차이는 고변동성일에 두 배 이상 벌어진다 | 구간 중 상승 비율이 51–60% 로, 변동성 국면이 가격 방향을 정하지 않는다. 사후 20일 '나머지 19종 대비' 값은 네 채널 **모두** 음수다 (−0.18~−0.67%p). 채널과 무관한 공통 편향이므로 국면 효과가 아니라 구성 효과(구간이 많은 채권·단기채권 등 저수익 종목)일 가능성이 크다. 겹친 구간들이라 독립 표본이 아니다 |

### 통합 해석 — W2 전체 (05·06·07)

1. **수준과 변화는 다른 것을 본다 (H1).**
   - 고변동성 수준은 길게 지속되고, 확대는 그 상태로 들어가는 짧은 시기에 몰린다.
   - 두 후보일의 Jaccard 중앙값은 0.27 이다.
2. **여러 시간 규모의 동시 반응은 흔하지만 '유의함' 은 아니다 (H2).**
   - 2021–2025 공통 구간은 1,168개이고, 그 가운데 7/7 은 고변동성 23 · 확대 2 다.
   - 보정된 귀무분포가 없다.
3. **W1 CUSUM 은 RV 수준과 거의 무관하다 (H3).**
   - ρ 중앙값은 −0.11~−0.01 이다.
   - 공통 구간의 42% 는 연초 미계산 기간이라 CUSUM 과 비교할 수 없다.
   - W1 비적격 판정은 유지한다.
4. **공통성은 노출 구조로 상당 부분 설명된다 (H4).**
   - 같은 지수 4종은 사실상 한 신호다.
   - 서로 다른 노출이 함께 반응한 2021–2025 사건은 2024-08 · 2025-04 (확대, 10–11/17 그룹)와 2022 채권·통화 주도 고변동성이다.
5. **변동성 국면은 가격 방향 라벨이 아니다 (H5).**
   - 상승과 하락이 섞여 있다.
   - 같은 노출 상품끼리도 레버리지 구조에 따라 반응이 체계적으로 다르다.

**이 연구가 주장하지 않는 것.**
- CUSUM 이 참 구조변화 시점을 찾았다.
- 여러 기간이 겹쳤으므로 유의하다.
- q=1 은 안정적 레짐이다.
- 구간 시작일이 실시간 경보 시점이다.
- CNN 후보가 급등 정답이다.
- 이번 분석이 독립 외부 검증이다.
"""),
        md(r"""
## 11. 재현성 — 결과 해시와 릴리스 인계
"""),
        code(r"""
# 07 그림 색인과 05·06·07 전체 결과 해시를 묶은 인계 파일.
fig_index = pd.DataFrame({"file": [str(p.relative_to(BASE)) for p in FIG_FILES], "sha256": [sha256(p) for p in FIG_FILES]})  # 그림 해시
fig_index.to_csv(BASE / "results/07/figure_index_07.csv", index=False)  # 그림 색인
MAN7 = S07["manifest"]  # 07 결과 해시
final = {"from": "07", "protocol_version": CFG["protocol_version"], "config_sha256": FREEZE[0][0], "contract_sha256": FREEZE[1][0], "environment": ACTUAL_ENV, "results": {**H06["results"], **MAN7["files_sha256"]}, "work_files": {**H06["work_files"], **MAN7["work_sha256"]}, "figure_indexes": {k: sha256(BASE / f"results/{k}/figure_index_{k}.csv") for k in ("05", "06", "07")}}  # 최종 인계
(BASE / "results/07_final.json").write_text(json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")  # 저장
print("결과 파일", len(final["results"]), "개 · Git 제외 작업 파일", len(final["work_files"]), "개 · 그림", len(FIG_FILES) // 2, "개")  # 요약
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3 (R2H .venv)",
        "language": "python",
    }
    return nb


BOOKS = {
    "05": ("05_개별ETF_다중기간_변동성국면연구.ipynb", book05),
    "06": ("06_노출군집_공통변동성구간_연구.ipynb", book06),
    "07": ("07_가격반응_ETF상대움직임_CNN인계.ipynb", book07),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="노트북 파일을 실제로 덮어쓴다 (실행 출력 삭제)")
    parser.add_argument("--only", choices=tuple(BOOKS), help="해당 노트북만 생성")
    args = parser.parse_args()
    for key, (name, fn) in BOOKS.items():
        if args.only and key != args.only:
            continue
        nb = fn()
        if args.write:
            nbformat.write(nb, NBDIR / name)
            print("작성:", NBDIR / name)
        else:
            print("검사 통과 (쓰지 않음):", name, len(nb.cells), "셀")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
