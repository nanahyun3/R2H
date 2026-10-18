# ruff: noqa: E501
"""11번 노트북 생성기 (11-lock-1) — 대표 6종 ETF 개별 급변 구간: 구간·스케일·지속 → 바텀업 → 누적수익률 → SVR–GARCH CUSUM.

--write 로만 쓴다. 모든 코드 줄에 한국어 주석 (빠지면 멈춤). 해석 수치는 마지막 CLAIMS 셀이 결과표와 대조한다.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "11_대표6종ETF_개별급변구간_바텀업_누적수익률_CUSUM.ipynb"
HANGUL = re.compile(r"[가-힣]")
CLOSERS = {")", "]", "}", "),", "],", "},", ")]", "})"}


def md(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    """주석이 빠진 코드 줄이 있으면 멈춘다 (t18·t19 생성기와 같은 검사)."""
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


def fig(call: str, name_expr: str) -> nbformat.NotebookNode:
    return code(f"""
_cap = {call}  # 결과로 그림을 다시 그리고 캡션 수치를 받는다
CAP[{name_expr}] = _cap  # 캡션 수치 보관
display(Image(data=preview(FIGDIR / ({name_expr} + ".png"))))  # 저장된 PNG(320dpi)의 축소 미리보기
""")


SETUP = r"""
# 새 커널 첫 셀: BLAS 스레드를 NumPy 로드 전에 1로 고정해 결과를 결정적으로 만든다.
import os  # 환경변수 설정
import sys  # 인터프리터·모듈 경로 확인
from pathlib import Path  # 저장소 상대 경로

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # 네 BLAS 계열 변수
    os.environ[key] = "1"  # 다중 스레드 합산 순서에 따른 비트 차이를 막는다
assert "numpy" not in sys.modules, "새 커널에서 첫 셀부터 실행해야 합니다"  # 숨은 커널 상태 금지
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t20_etf_shock_bottomup_v1.json").is_file())  # 저장소 루트 탐색
sys.path.insert(0, str(ROOT / "src"))  # 이 작업트리의 r2h 패키지를 우선 사용

import csv  # 보호 파일 SHA 목록
import hashlib  # 파일 지문
import importlib.metadata as metadata  # 설치 패키지 버전 조회
import json  # 설정·캡션
import platform  # Python 버전

import matplotlib  # 그림 백엔드
matplotlib.use("Agg")  # 화면 없이 파일로 저장
import numpy as np  # 수치 배열
import pandas as pd  # 결과표
from IPython.display import Image, display  # 표·그림 출력
import matplotlib.pyplot as plt  # 그림 기본 설정
from matplotlib import font_manager  # 한글 글꼴 등록

FONT_FILE = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")  # 한글 도판용 나눔고딕
assert FONT_FILE.is_file(), "한글 도판 렌더링을 위한 나눔고딕 파일이 없습니다"  # 글꼴 없으면 중단
font_manager.fontManager.addfont(str(FONT_FILE))  # matplotlib 글꼴 목록에 등록
plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT_FILE)).get_name()  # 한글 글꼴 사용
plt.rcParams["axes.unicode_minus"] = False  # 음수 기호 깨짐 방지

# 09·10 과 같은 고정 환경이어야 한다.
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2"}  # 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": metadata.version("scipy"), "matplotlib": metadata.version("matplotlib")}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패로 처리
assert ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
pd.set_option("display.width", 220)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화
pd.set_option("display.max_colwidth", 120)  # 긴 문자열 표시

from r2h.etf_shock import pipeline as P  # 11번 계산
from r2h.etf_shock.figures import Figures11  # 11번 그림

assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
BASE = ROOT / "research/etf_shock_bottomup_11"  # 11번 산출물 폴더
RES = BASE / "results"  # 결과표
FIGDIR = BASE / "figures"  # 그림 (PNG 320dpi + SVG)


def preview(path, width=1100):  # 노트북 용량을 줄이는 축소 미리보기 (원본은 figures/)
    from io import BytesIO  # 메모리 버퍼
    from PIL import Image as PILImage  # 이미지 축소
    im = PILImage.open(path)  # 320dpi 원본
    im.thumbnail((width, width * 3))  # 가로 1100px 이하로 축소
    buf = BytesIO()  # 출력 버퍼
    im.save(buf, format="PNG", optimize=True)  # PNG 로 다시 저장
    return buf.getvalue()  # 바이트 반환


def sha(p):  # 파일 SHA256
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()  # 바이트 단위 지문


# 11번 계약·설정 동결 지문.
for line in (BASE / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():  # 동결 기록
    digest, name = line.split(maxsplit=1)  # 해시·경로
    assert sha(ROOT / name) == digest, f"동결 파일 변경: {name}"  # 변경되면 중단
# 이전 연구 보호 파일(W3 목록) 과 09·10·W3 결과 폴더의 시작 지문.
PROTECTED = list(csv.DictReader(open(ROOT / "research/joint_cusum_w3/W3_PROTECTED_SHA256.csv", encoding="utf-8")))  # W3 보호 목록
assert not [r["path"] for r in PROTECTED if sha(ROOT / r["path"]) != r["sha256"]], "보호 파일 변경"  # 기존 연구는 읽기만
WATCH = [ROOT / "research/peer_relative_shock_w4/results", ROOT / "research/common_volatility_candidates_10/results", ROOT / "research/joint_cusum_w3/results/08"]  # 09·10·W3 결과 폴더
BEFORE = {str(p.relative_to(ROOT)): sha(p) for d in WATCH for p in sorted(d.glob("*")) if p.is_file()}  # 시작 지문
print("작업트리:", ROOT, "| 보호 파일", len(PROTECTED), "개 불변 | 감시 파일", len(BEFORE), "개")  # 검증 요약
print("실행 환경:", ACTUAL_ENV)  # 환경 기록
"""

RUN = r"""
# 09 ETF 상태 읽기 → σ·경계 재계산 검증 → W3 CUSUM 재실행(72/72 대조) → 구간·바텀업·누적수익률·CUSUM 요약.
R = P.run(ROOT)  # 결과는 research/etf_shock_bottomup_11/results/ (가격 역산 가능한 일별 표는 저장하지 않음)
CFG, D, IV, CU = R["cfg"], R["daily"], R["intervals"], R["cusum"]  # 설정·일별·구간·CUSUM
FG = Figures11(R, ROOT)  # 그림 생성기
CAP = {}  # 그림 캡션 수치
NAMES = FG.names  # 종목명
print("ETF:", CFG["tickers"], "| 구간 총", len(IV), "개 | CUSUM 대조", R["cusum_info"]["n_checked"], "셀 일치")  # 실행 요약
"""

ETF_INTRO = {
    "069500": r"""
**왜 이 ETF 인가.** KODEX 200 은 KOSPI200 을 1배로 따르는 국내 주식시장의 기준 ETF 다. 08(W3)의 바텀업에서도 S1 의 기준(anchor)이었다.
- 09·10 에서는 KOSPI200 4종을 한 그룹으로 묶고 Core Pair(069500·102110) 둘 다 A 일 때만 그룹 A 로 봤다. 여기서는 **069500 단독**이다.
""",
    "229200": r"""
**왜 이 ETF 인가 (코스닥 확장).** KODEX 코스닥150 은 같은 국내 주식이지만 성장·중소형 비중이 크다. W3 의 S1 은 069500 과 229200 의 쌍이었다. 국내 주식 안에서 급변이 같이 오는지, 코스닥만 따로 오는지를 본다.
""",
    "148070": r"""
**왜 이 ETF 인가 (국채 확장).** KIWOOM 국고채10년은 장기 금리 위험이다. W3 의 S2 에서 처음 들어온 비주식 자산이다. 주식 급변과 금리 급변이 같은 날 오는지 본다.
""",
    "153130": r"""
**왜 이 ETF 인가 (단기채 확장).** KODEX 단기채권은 듀레이션이 매우 짧다. σ 가 연 0.2–0.6% 수준이라 **절대 수준은 아주 작다**. 급변(A)은 자기 과거 분위로 정의하므로 이런 자산도 급변 구간을 가질 수 있다. W3 의 S3 이다.
""",
    "133690": r"""
**왜 이 ETF 인가 (미국 나스닥 확장).** TIGER 미국나스닥100 은 환노출 미국 기술주다. W3 의 S4 다. 국내 급변이 해외발인지 보는 비교축이다.
""",
    "261220": r"""
**왜 이 ETF 인가 (원유 확장).** KODEX WTI원유선물(H)은 원자재 위험이다. W3 의 S5 다. 원유 고유의 급변과 다자산 동시 급변을 가른다.
""",
}

ETF_INTERP = {
    "069500": r"""
**해석 — KOSPI200 (069500).**

*① 급변 구간 (전체 연도).*
- q20 기준으로 2020 파일럿 4구간, 주분석 2021–2025 **7구간 95일**, 2026 2구간이 나왔다.
- q60 은 주분석에서 2구간이다. 2024-08-05~11-05 (60일), 그리고 2025-11-18 에 시작해 데이터 끝(2026-10-02)까지 이어지는 214일 구간이다.

*② 스케일·지속.*
- 주분석에서 가장 큰 구간은 **2024-08-05~09-02 (20일)** 이다. 최대 σ20 은 43.4% 로, 그날 경계의 1.83배이고 과거 중앙 σ 의 2.7배다.
- 가장 긴 구간은 **2025-11-04~12-18 (33일)** 이다.
- 2021-01-29 (1일), 2024-10-07~08 (2일), 2025-10-27~30 (4일) 은 최대 σ 가 경계의 1.01–1.08배다. 경계를 겨우 넘은 짧은 구간이다.

*③ 바텀업 — 왜 잡혔나.*
- **2024-08**: 하루(2024-08-05, −9.63%)가 최대 σ 일 창 분산의 **63%** 를 만든 단일 충격형이다. 구간은 그날이 20일 창에서 빠지는 날(09-03)에 정확히 끝났다(창 이탈 종료). 따라서 20일이라는 지속기간은 시장이 20일간 흔들렸다는 뜻이 아니다. **충격 하루가 창에 머문 기간**이다.
- **2025-04**: 2025-04-07 −5.87% (32%) 와 04-10 +5.98% (40%) 의 급락·급반등 두 날이 만들었다.
- **2025-11~12**: 최대 기여일 몫이 17% 인 누적형이다. −4% 안팎의 날이 여러 번 이어졌다.
- 같은 날 A 인 노출 그룹 수(10번 N_A)는 2024-08 에 최대 10, 2025-04 에 12 로 시장 공통 급변이었다 (C1 포함 20일·17일). 2025-11~12 는 최대 4 로 **국내 주식 고유**의 급변이다 (C1 0일).

*④ 누적수익률.*
- 2024-08 구간: 첫날 −9.2% 낙폭 뒤 회복해 구간 수익률 −1.0%. 구간 전 20일 −7.5%, 후 20일 −3.8%.
- 2025-04 구간: +3.7%. 구간 후 20일 +12.9% 로 반등이 이어졌다.
- 2025-11~12 구간: 직전 20일 +25.8% 의 급등 뒤에 왔다. 구간 수익률 −5.2%, 최대 낙폭 −9.5% 다. **급락 국면만이 아니라 급등 뒤의 흔들림도 급변으로 잡힌다.**

*⑤ SVR–GARCH CUSUM.*
- 2021–2025 동안 069500 은 12개 셀(3정책 × 4창) **어디에서도 경보가 0일**이다.
- 가장 가까이 간 것은 2024-08 구간의 정책 A·w=60 으로, T/crit 0.95 였다.
- 급변일의 T/crit 중앙값(A·w20 0.46)은 나머지 날(0.45)과 거의 같다. 관측 변동성이 급등해도 SVR 예측분산으로 나눈 잔차에서는 그 상승이 흡수된다. W3 의 결론과 같은 방향이다.

*2026 (주분석 제외).* 2026-02-02~09-16 의 153일 구간이 있다 (최대 σ20 119%). 2026-07-31 의 +21.65% 는 102110 +22.06%, 레버리지 122630 +38.4%, 인버스 114800 −25.0% 와 같은 날 함께 나타나 원자료가 서로 일관된다. CUSUM 은 2026 을 계산하지 않았다.
""",
    "229200": r"""
**해석 — 코스닥150 (229200).**
- 주분석 q20 **13구간 121일**. 069500 보다 구간이 많고 짧다. 2022 년에만 8구간(02~03월 4개, 06~07월, 10월 3개)이다.
- 가장 큰 구간은 **2023-10-31~12-01 (24일)** 이다. 최대 σ 65.8% 로 경계의 1.73배다. 하루(2023-11-06, +13.66%)가 창 분산의 57% 를 만들었고, 그날이 창에서 빠지며 끝났다. 같은 날 069500 도 +4.57% 로 급변이 시작됐다.
- 2024-08-05~09-02 (20일) 은 069500 과 날짜가 같다. 2024-08-05 −11.15% (54%) 의 단일 충격이고, 역시 창 이탈로 끝났다.
- 2022 년 구간들은 모두 누적형(최대 기여 16–28%)이다. 한 번의 사건보다 하락장 속 큰 날들이 이어진 결과다.
- **확장 관점**: 229200 의 급변일 121일 중 069500 과 같은 날은 47일이다. 13구간 중 9구간은 069500 의 급변일과 하루도 겹치지 않는다 (코스닥 단독 급변).
- CUSUM: 경보 0. 구간 최대 T/crit 은 2023-08 구간의 0.85 다.
""",
    "148070": r"""
**해석 — 국고채10년 (148070).**
- 주분석 q20 **19구간 261일**. 6종 중 주식이 아닌 자산에서 급변일이 가장 많다. 2022 년에 몰려 있다.
- 가장 긴 구간은 **2022-03-22~07-12 (78일)** 이다. 가장 큰 구간은 **2022-09-22~11-22 (42일, 최대 σ 14.7%, 경계의 1.72배)** 이다. 둘 다 누적형(최대 기여 21%)이다. 금리 급등기에 ±1–2% 의 날이 길게 이어진 결과다.
- **확장 관점**: 148070 의 급변일은 069500 과 **하루도 겹치지 않는다 (0일)**. 앞 단계(069500·229200) 중 하나와 겹친 날은 35일이고, 19구간 중 13구간은 단독이다. 국채 급변은 주식 급변과 다른 시기에 온다.
- 2023-03-10~04-06 (20일) 구간의 CUSUM T/crit 0.94 가 이 ETF 의 최대다. 경보는 없다.
""",
    "153130": r"""
**해석 — 단기채권 (153130).**
- 주분석 q20 **21구간 269일**. σ 는 연 0.17–2.5% 다. **절대 변동성은 아주 작지만 자기 과거 분위로는 급변**이다.
- 가장 긴 구간은 2022-04-13~07-13 (63일)이고, 2022-08-26~11-03 (46일, 경계의 2.70배)이 이어진다. 2022 금리 국면이다.
- **주의**: 2024-01-30~02-29 구간은 최대 σ 2.49% 로 경계의 **7.97배**다. 이 값은 2024-01-31 의 +0.50% 하루(50%)가 만들었다. 이날은 T18(09) 에서 **원자료 이상치 후보(153130 2024-01-30·31)** 로 기록했다. 실제 급변으로 해석하지 않는다.
- **확장 관점**: 069500 과 같은 날은 1일뿐이다. 앞 단계와 겹친 날은 179일이고 대부분 148070(국채)과 겹친다. 21구간 중 6구간만 단독이다.
- CUSUM: W3 경보 32일(정책 A·base, w=120)은 **모두 급변일이 아닌 날**에 있다.
""",
    "133690": r"""
**해석 — 미국 나스닥100 (133690).**
- 주분석 q20 **6구간 80일**. 2022 년 4구간과 2024-08, 2025-04 다.
- 2025-04-07~05-12 (23일) 이 가장 크다. 최대 σ 65.7% 로 경계의 2.16배이고, 2025-04-10 +10.08% 의 날이 창 분산의 33% 를 만들었다.
- 2024-08-05~09-02 (20일) 은 069500·229200 과 날짜가 같다. 단일 충격(08-05 −6.74%)의 창 이탈 종료다.
- **확장 관점**: 6구간 모두 앞 단계 ETF 의 급변일과 겹친다 (단독 0). 069500 과 같은 날은 42일이다. 2024-08·2025-04 는 국내 급변과 해외 급변이 같은 날 일어난 다자산 사건이다.
- CUSUM: W3 경보 4일(정책 B·w20 3일, base·w20 1일)은 모두 급변일이 아닌 날이다.
""",
    "261220": r"""
**해석 — WTI원유 (261220).**
- 주분석 q20 **3구간 59일**. q60 주분석 구간은 없다.
- 2022-03-07~04-06 (22일) 은 최대 σ 99.8%, 구간 최대 낙폭 −21.3% 의 누적형이다.
- 2025-06-24~07-21 (20일) 은 하루(06-24, −14.47%)가 65% 를 만든 단일 충격이고, 창 이탈로 끝났다. 같은 날 A 그룹 수는 최대 2 로 **원유 고유 급변**이다.
- 2025-04-10~05-07 (17일) 은 다자산 급변(N_A 12)에 원유가 함께한 경우다.
- CUSUM: W3 경보 9일(정책 A·w60 4일, w120 5일)은 모두 급변일이 아닌 날이다.
""",
}


def etf_section(k: int, t: str) -> list[nbformat.NotebookNode]:
    sec = 2 + k
    cells = [
        md(f"## {sec}. {t} — 선정 · 급변 구간 · 스케일·지속 · 바텀업 · 누적수익률 · CUSUM"),
        md(f"### {sec}.1 ETF 선정\n" + ETF_INTRO[t]),
        md(f"### {sec}.2 급변 구간 — 전체 연도 (2019–2026)"),
        code(f"""
# {t} 의 q20·q60 급변 구간 전부 (전체 달력에서 한 번에 추출, 기간 지위는 시작일 기준 태그).
X = IV[IV["ticker"] == "{t}"]  # 이 ETF 의 구간
display(X[["interval_id", "q", "period", "start", "end", "duration", "primary_days", "right_censored_data_end", "peak_date", "peak_sigma", "peak_U", "peak_over_boundary", "peak_over_past_median"]].round(3))  # 구간·스케일 표
display(R["summary"][R["summary"]["ticker"] == "{t}"])  # 기간 지위별 요약
"""),
        fig(f'FG.e1_timeline("{t}", "{k}")', f'"E1_{k}_{t}_timeline"'),
        md(f"### {sec}.3 스케일·지속"),
        fig(f'FG.e2_scale("{t}", "{k}")', f'"E2_{k}_{t}_scale"'),
        md(f"### {sec}.4 바텀업 — 왜 잡혔나 (주분석 q20 구간)"),
        code(f"""
# 최대 σ 일의 q 일 창에서 각 날의 분산 기여 (r−r̄)²/Σ, 진입일 수익률, 창 이탈 종료, 시장 공통성(10번 N_A·C1).
XP = X[(X["q"] == 20) & (X["period"] == "PRIMARY")]  # 주분석 q20 구간
display(XP[["interval_id", "start", "end", "duration", "shock_type", "top1_date", "top1_r", "top1_share", "top3", "window_exit_end", "entry_r", "entry_sigma_jump", "other_q_overlap_days", "max_N_A_q20", "C1_days"]].round(3))  # 바텀업 표
"""),
        code(f"""
# 확대 대상: 주분석 q20 구간 중 지속 상위 3개 (동률은 시작일 순, 결과를 보고 바꾸지 않는 표시 규칙).
ZOOM = FG.zoom_targets("{t}")  # 구간 ID 목록
print("확대 대상:", ZOOM)  # 대상 출력
for _iv in ZOOM:  # 구간마다
    CAP[f"E3_{k}_{{_iv}}"] = FG.e3_bottomup("{t}", _iv, "{k}")  # 바텀업 4층 확대 그림
    display(Image(data=preview(FIGDIR / f"E3_{k}_{{_iv}}.png")))  # 미리보기
"""),
        md(f"### {sec}.5 누적수익률"),
        code(f"""
# 구간 수익률·최대 낙폭은 구간 시작 전날 종가 기준, 앞뒤 20거래일 수익률 (%).
display(XP[["interval_id", "start", "end", "ret_pre20_pct", "ret_interval_pct", "max_drawdown_pct", "ret_post20_pct"]].round(2))  # 누적수익률 표
"""),
        md(f"### {sec}.6 SVR–GARCH CUSUM"),
        code(f"""
# 구간별 12셀(3정책 × 4창) 최대 T/crit 와 경보 셀-일 수, 2021–2025 급변일 vs 나머지 날 분포.
RC = [c for c in X.columns if c.startswith("maxR_")]  # 셀별 최대 비율 열
display(XP[["interval_id", "start", "end", "cusum_coverage_A20", "cusum_maxR_any", "cusum_alarm_days_any"] + RC].round(2))  # 구간별 CUSUM
IO = R["inside_outside"]  # 안팎 분포
display(IO[IO["ticker"] == "{t}"].pivot_table(index=["policy", "w"], columns="side", values=["median_R", "max_R", "alarm_days"]).round(3))  # 셀별 안팎
"""),
    ]
    if k > 1:
        cells += [
            md(f"### {sec}.7 확장 — 앞 단계 ETF 와의 겹침"),
            code(f"""
# 단계별 급변일 겹침 (주분석 q20): 069500 과 같은 날, 앞 단계 ETF 중 하나와 같은 날, 앞 단계와 겹치지 않는 단독 구간 수.
display(R["stage"][R["stage"]["order"] <= {k}])  # 지금까지의 확장 단계
"""),
        ]
    cells.append(md(ETF_INTERP[t]))
    return cells


def book() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 11 · 대표 6종 ETF 개별 급변 구간 — 바텀업 해부 · 누적수익률 · SVR–GARCH CUSUM

**「KOSPI200 에서 코스닥·국채·단기채·나스닥·원유로 확장하며, 각 ETF 가 자기 과거 대비 고변동성(급변)이었던 구간이 언제·얼마나 크게·얼마나 오래 나타났고, 왜 잡혔으며, 그때 가격과 SVR–GARCH 잔차 CUSUM 은 어땠는가」**

- 연구 ID `t20_etf_shock_bottomup_11`, 프로토콜 `11-lock-1`, 기준 커밋 `20f19fb` (10번 최종), 브랜치 `research/11_etf_shock_bottomup`.
- 계약 `research/etf_shock_bottomup_11/ANALYSIS_CONTRACT.md` (`b7c3197`) — 구간 계산 전에 커밋했다.
- **기술·탐색 연구**다. 검정, 예측성능, 최적 정의를 다루지 않는다. 09 판정·10 후보·W3 결론은 바꾸지 않는다.
"""),
        md("## 0. 실행 환경·동결 지문"),
        code(SETUP),
        md("## 0.1 전체 계산 실행"),
        code(RUN),
        md(r"""
## 1. 이 노트북이 보는 것 — 10번 C1 과의 차이

**10번 C1** 은 **시장 전체**의 정의다.
- 20개 ETF 를 17개 노출 그룹으로 묶고, 같은 날 A(자기 과거 대비 20일 변동성 상위 10%)인 그룹이 9개 이상인 날을 후보로 본다.
- 2021–2025 에서는 2022-10-11~12, 2024-08-05~09-02, 2025-04-10~05-07 의 세 구간이다.

**이 노트북**은 **ETF 하나하나**의 정의다. 각 ETF 의 A 가 1 인 연속 거래일을 그 ETF 의 급변 구간으로 본다. 그리고 그 위에 다섯 층을 쌓는다.

| 층 | 내용 |
|---|---|
| ① 구간 | 전체 연도(2019–2026)에서 잡힌 구간, 기간 지위 (2019 정의 불가 · 2020 파일럿 · 2021–2025 주분석 · 2026 부분) |
| ② 스케일·지속 | 최대 σ(%), 그날 급변 경계 σ 대비 배율, 과거 중앙 σ 대비 배율, 거래일 수 |
| ③ 바텀업 | 최대 σ 일의 20일 창에서 각 날의 분산 기여 → 단일 충격형/누적형, 창 이탈 종료, 시장 공통성(10번 N_A·C1) |
| ④ 누적수익률 | 2019-01-02 기준 누적, 구간 수익률·최대 낙폭(시작 전날 기준), 앞뒤 20일 |
| ⑤ CUSUM | W3 의 SVR–GARCH 잔차 CUSUM T 를 W3 임계값으로 나눈 T/crit (1 이상이면 경보) |

순서는 08(W3)의 확장 순서다: 069500 (S1 기준) → 229200 (코스닥) → 148070 (국채10년) → 153130 (단기채) → 133690 (나스닥) → 261220 (원유).
"""),
        md(r"""
## 2. 정의와 계산 검증

- **수익률·변동성**: `r = 100·log(C_t/C_{t−1})`, `σ(q) = √252 · std(r_{t−q+1..t}, ddof=1)` (연환산 %). 09 의 σ 를 다시 계산해 일치를 확인했다.
- **급변(A)**: σ(q) 의 엄밀 과거 확장형 mid-rank 분위 ≥ 0.90 (기준 252개 이상). 2019 는 기준이 모자라 정의할 수 없다.
- **급변 경계 σ**: 같은 규칙에서 역산한 값이다. 과거 n 개 중 ⌈0.9n⌉ 번째 작은 σ 이며, **A=1 ⟺ σ > 경계** 가 동점 없는 전 일자에서 성립한다 (assert).
- **분산 기여**: `(r_i − r̄)² / Σ(r_j − r̄)²`. 합이 1 이고, 이 합으로 σ 를 정확히 다시 만든다 (assert).
- **단일 충격형**: 최대 기여일 몫 ≥ 30%. **창 이탈 종료**: 구간 다음 날이 최대 기여일 + 20거래일, 즉 그 날이 창에서 빠진 날이다.
- **CUSUM**: W3 의 `run_pipeline` (연간 SVR 적합 → 정책 A·B·base 표준화 잔차 → 그해 안 이동창 CUSUM) 을 그대로 다시 실행했다. W3 요약표와 72개 셀 모두 일치한다. 임계값은 W3 `crit_w3` 그대로다. **2021–2025 만** 있다. 매년 1월 첫 w−1 일은 공백이다.
"""),
        code(r"""
# 검증 결과: CUSUM 72셀 대조, W3 임계값 표, 그리고 2021–2025 에서 W3 경보일이 급변일과 겹치는지.
print("CUSUM W3 대조 셀:", R["cusum_info"]["n_checked"])  # 72
display(pd.read_csv(RES / "cusum_crit_w3.csv", dtype={"ticker": str}).pivot_table(index="ticker", columns=["policy", "w"], values="crit_w3").round(3))  # 임계값
IOA = R["inside_outside"]  # 안팎 분포
print("급변일(A20)의 경보 셀-일:", int(IOA[IOA.side == "A20 날"].alarm_days.sum()), "| 나머지 날의 경보 셀-일:", int(IOA[IOA.side == "비 A20 날"].alarm_days.sum()))  # 핵심 대비
"""),
    ]
    for k, t in enumerate(["069500", "229200", "148070", "153130", "133690", "261220"], start=1):
        cells += etf_section(k, t)
    cells += [
        md("## 9. 6종 종합 — 확장 지도"),
        fig("FG.x1_stack()", '"X1_six_etf_stack"'),
        fig("FG.x2_participation()", '"X2_kospi200_participation"'),
        code(r"""
# 확장 단계 표 (주분석 q20) 와 KOSPI200 구간별 참여 일수.
display(R["stage"])  # 단계별 겹침
display(R["k200_participation"])  # 069500 구간 × 다른 5종
"""),
        fig("FG.x3_cusum_io()", '"X3_cusum_inside_outside"'),
        fig("FG.x4_all()", '"X4_all_intervals"'),
        md(r"""
**해석 (X1–X4).**
- **확장 지도**: 국내 주식(069500·229200)의 급변은 2023-11, 2024-08, 2025-04 에 함께 온다. 국채·단기채(148070·153130)의 급변은 2022 금리 국면에 길게 몰려 있고 국내 주식과 거의 겹치지 않는다 (069500 과 같은 날: 148070 0일, 153130 1일).
- 나스닥(133690)의 6구간은 모두 앞 단계 ETF 와 겹친다. 원유(261220)는 2025-06 의 고유 급변 하나를 더한다.
- **KOSPI200 구간의 성격 (X2)**: 2024-08 은 코스닥·나스닥이 20일 모두 함께했다. 2025-04 는 나스닥 22일, 원유 17일, 코스닥 14일이 함께한 다자산 급변이다. 2023-11 은 코스닥만, 2025-10~12 는 069500 단독이다.
- **지속기간의 기계적 성분 (X4)**: 주분석 q20 구간 69개 중 25개가 단일 충격형이다. 24개는 최대 기여일이 창에서 빠지는 날 끝났다. 20거래일 근처에 몰린 지속기간은 상당 부분 **창 길이의 흔적**이다.
- **CUSUM (X3)**: 6종 × 12셀 어디에서도 **급변일에 경보가 0일**이다. W3 의 경보(153130 32일·261220 9일·133690 4일)는 모두 급변이 아닌 날에 있다. 정책 A 의 급변일 T/crit 중앙값도 나머지 날과 비슷한 범위다 (4개 창 × 6종: 0.37–0.59 대 0.29–0.57). 관측 변동성의 급등과 SVR 표준화 잔차의 분산 변화는 다른 시점에 나타난다.
"""),
        md(r"""
## 10. 결론 · 한계 · 다음 단계

**결론**
1. ETF 단위 급변 구간은 자산마다 시기가 다르다. 국내 주식은 2023-11·2024-08·2025-04(·2025-11 국내 고유), 국채·단기채는 2022 금리 국면, 원유는 2022-03·2025-06 이다.
2. 시장 공통 급변(10번 C1)은 이 개별 구간들이 같은 날 겹친 부분이다. 2024-08 과 2025-04 가 대표적이다.
3. 많은 구간이 큰 하루의 충격이 20일 창에 머무른 기간이다. 지속기간을 해석할 때 이 기계적 성분을 먼저 빼야 한다.
4. SVR–GARCH CUSUM 은 급변일에 경보를 내지 않았다. CUSUM 은 관측 변동성 급변의 대리 지표가 아니다. 두 신호는 서로 다른 층으로 다뤄야 한다 (CNN 입력이라면 별개 채널).

**한계**
- 기술·탐색 분석이다. 계약 직전에 구간 개수를 훑어보았다.
- CUSUM 은 2021–2025 만 있다. 2026 의 큰 구간(069500 153일 등)에는 CUSUM 층이 없다.
- 153130 의 2024-01-30~02-29 구간은 원자료 이상치 후보가 만든 것이다.
- 확대 그림은 지속 상위 3개 구간만이다. 나머지 구간은 표로 본다.

**다음 단계 후보**: 같은 다섯 층을 나머지 14종으로 확장 · 창 이탈 종료를 분리한 '사건 기준 지속기간' 정의 · CUSUM 을 표준화 전 분산 기준으로 다시 정의할지(W3 후속) 결정.
"""),
        md("## 11. CLAIMS 및 재현성 검증"),
        code(r"""
# 해석 문단의 숫자를 결과 파일에서 다시 읽어 대조한다 (불일치면 실패).
def row(i):  # 구간 ID 로 한 행
    return IV[IV["interval_id"] == i].iloc[0]  # 구간 행


def prim(t, q=20):  # 주분석 구간
    return IV[(IV["ticker"] == t) & (IV["q"] == q) & (IV["period"] == "PRIMARY")]  # 필터


ST = R["stage"].set_index("ticker")  # 확장 단계 표
K2 = R["k200_participation"].assign(start=lambda z: z["start"].astype(str)).set_index("start")  # KOSPI200 참여
IOA = R["inside_outside"]  # 안팎 분포
CLAIMS = [  # (주장, 관측, 기대)
    ("CUSUM W3 대조 셀", R["cusum_info"]["n_checked"], 72),  # W3 대조 72/72
    ("069500 q20 기간별 구간 수", tuple(int((IV[(IV.ticker == "069500") & (IV.q == 20)].period == p).sum()) for p in ("PILOT", "PRIMARY", "PARTIAL_NON_BLIND")), (4, 7, 2)),  # 본문 ①
    ("069500 q20 주분석 일수", int(prim("069500").duration.sum()), 95),  # 본문 ①
    ("069500 q60 주분석 구간", tuple(f"{a}~{b}" for a, b in zip(prim("069500", 60).start, prim("069500", 60).end)), ("2024-08-05~2024-11-05", "2025-11-18~2026-10-02")),  # 본문 ①
    ("2024-08 구간", (str(row("069500_q20_007").start), str(row("069500_q20_007").end), int(row("069500_q20_007").duration)), ("2024-08-05", "2024-09-02", 20)),  # 본문 ②
    ("2024-08 σ·배율", (round(float(row("069500_q20_007").peak_sigma), 1), round(float(row("069500_q20_007").peak_over_boundary), 2), round(float(row("069500_q20_007").peak_over_past_median), 1)), (43.4, 1.83, 2.7)),  # 본문 ②
    ("2024-08 최대 기여", (str(row("069500_q20_007").top1_date), round(float(row("069500_q20_007").top1_r), 2), round(float(row("069500_q20_007").top1_share), 2), bool(row("069500_q20_007").window_exit_end)), ("2024-08-05", -9.63, 0.63, True)),  # 본문 ③
    ("069500 최장 주분석 구간", (str(row("069500_q20_011").start), str(row("069500_q20_011").end), int(row("069500_q20_011").duration), int(prim("069500").duration.max())), ("2025-11-04", "2025-12-18", 33, 33)),  # 본문 ②
    ("경계 겨우 넘은 3구간 배율", tuple(round(float(row(i).peak_over_boundary), 2) for i in ("069500_q20_005", "069500_q20_008", "069500_q20_010")), (1.02, 1.01, 1.08)),  # 본문 ②
    ("2025-04 두 날", row("069500_q20_009").top3.split("; ")[:2], ["2025-04-10 +5.98% (40%)", "2025-04-07 -5.87% (32%)"]),  # 본문 ③
    ("2025-11 누적형 최대 기여", (row("069500_q20_011").shock_type, round(float(row("069500_q20_011").top1_share), 2)), ("누적형", 0.17)),  # 본문 ③
    ("069500 N_A·C1", tuple(int(row(i).max_N_A_q20) for i in ("069500_q20_007", "069500_q20_009", "069500_q20_011")) + tuple(int(row(i).C1_days) for i in ("069500_q20_007", "069500_q20_009", "069500_q20_011")), (10, 12, 4, 20, 17, 0)),  # 본문 ③
    ("2024-08 누적수익률", tuple(round(float(row("069500_q20_007")[c]), 1) for c in ("max_drawdown_pct", "ret_interval_pct", "ret_pre20_pct", "ret_post20_pct")), (-9.2, -1.0, -7.5, -3.8)),  # 본문 ④
    ("2025-04 누적수익률", (round(float(row("069500_q20_009").ret_interval_pct), 1), round(float(row("069500_q20_009").ret_post20_pct), 1)), (3.7, 12.9)),  # 본문 ④
    ("2025-11 누적수익률", tuple(round(float(row("069500_q20_011")[c]), 1) for c in ("ret_pre20_pct", "ret_interval_pct", "max_drawdown_pct")), (25.8, -5.2, -9.5)),  # 본문 ④
    ("069500 경보 전체", int(IOA[IOA.ticker == "069500"].alarm_days.sum()), 0),  # 본문 ⑤
    ("2024-08 최대 T/crit", (round(float(row("069500_q20_007").cusum_maxR_any), 2), round(float(row("069500_q20_007").maxR_A_60), 2)), (0.95, 0.95)),  # 본문 ⑤
    ("069500 A·w20 중앙 안팎", tuple(round(float(IOA[(IOA.ticker == "069500") & (IOA.policy == "A") & (IOA.w == 20) & (IOA.side == s)].median_R.iloc[0]), 2) for s in ("A20 날", "비 A20 날")), (0.46, 0.45)),  # 본문 ⑤
    ("2026 구간", (str(row("069500_q20_013").start), str(row("069500_q20_013").end), int(row("069500_q20_013").duration), round(float(row("069500_q20_013").peak_sigma))), ("2026-02-02", "2026-09-16", 153, 119)),  # 2026 부분 연도
    ("2026-07-31 4종", tuple(round(float(v), 2) for v in (100 * np.log(pd.read_csv(ROOT / CFG["inputs"]["closes"], index_col=0).loc[["2026-07-30", "2026-07-31"], ["069500", "102110", "122630", "114800"]]).diff().iloc[1])), (21.65, 22.06, 38.36, -24.99)),  # 원자료 일관성
    ("229200 구간·일수", (len(prim("229200")), int(prim("229200").duration.sum()), int((pd.to_datetime(prim("229200").start).dt.year == 2022).sum())), (13, 121, 8)),  # 코스닥 해석 대조
    ("229200 2023-11", (int(row("229200_q20_013").duration), round(float(row("229200_q20_013").peak_sigma), 1), round(float(row("229200_q20_013").peak_over_boundary), 2), round(float(row("229200_q20_013").top1_r), 2), round(float(row("229200_q20_013").top1_share), 2), bool(row("229200_q20_013").window_exit_end)), (24, 65.8, 1.73, 13.66, 0.57, True)),  # 코스닥 해석 대조
    ("229200 2024-08", (round(float(row("229200_q20_014").top1_r), 2), round(float(row("229200_q20_014").top1_share), 2), bool(row("229200_q20_014").window_exit_end)), (-11.15, 0.54, True)),  # 코스닥 해석 대조
    ("229200 겹침", (int(ST.loc["229200", "days_with_069500"]), int(ST.loc["229200", "intervals_alone_vs_prev"])), (47, 9)),  # 확장
    ("229200 최대 T/crit", round(float(prim("229200").cusum_maxR_any.max()), 2), 0.85),  # 코스닥 해석 대조
    ("229200 2022 최대 기여 범위·유형", (round(float(prim("229200")[pd.to_datetime(prim("229200").start).dt.year == 2022].top1_share.min()), 2), round(float(prim("229200")[pd.to_datetime(prim("229200").start).dt.year == 2022].top1_share.max()), 2), set(prim("229200")[pd.to_datetime(prim("229200").start).dt.year == 2022].shock_type)), (0.16, 0.28, {"누적형"})),  # 코스닥 해석 대조
    ("148070 구간·일수", (len(prim("148070")), int(prim("148070").duration.sum())), (19, 261)),  # 국채 해석 대조
    ("148070 최장·최대", (int(row("148070_q20_009").duration), int(row("148070_q20_013").duration), round(float(row("148070_q20_013").peak_sigma), 1), round(float(row("148070_q20_013").peak_over_boundary), 2), round(float(row("148070_q20_009").top1_share), 2), round(float(row("148070_q20_013").top1_share), 2)), (78, 42, 14.7, 1.72, 0.21, 0.21)),  # 국채 해석 대조
    ("148070 겹침", (int(ST.loc["148070", "days_with_069500"]), int(ST.loc["148070", "days_with_any_prev"]), int(ST.loc["148070", "intervals_alone_vs_prev"])), (0, 35, 13)),  # 확장
    ("148070 최대 T/crit", (round(float(prim("148070").cusum_maxR_any.max()), 2), round(float(row("148070_q20_020").cusum_maxR_any), 2)), (0.94, 0.94)),  # 국채 해석 대조
    ("153130 구간·일수", (len(prim("153130")), int(prim("153130").duration.sum())), (21, 269)),  # 단기채 해석 대조
    ("153130 2024-01", (round(float(row("153130_q20_025").peak_sigma), 2), round(float(row("153130_q20_025").peak_over_boundary), 2), str(row("153130_q20_025").top1_date), round(float(row("153130_q20_025").top1_r), 2), round(float(row("153130_q20_025").top1_share), 2)), (2.49, 7.97, "2024-01-31", 0.5, 0.5)),  # 이상치 후보
    ("153130 2022 두 구간", (int(row("153130_q20_011").duration), int(row("153130_q20_014").duration), round(float(row("153130_q20_014").peak_over_boundary), 2)), (63, 46, 2.7)),  # 단기채 해석 대조
    ("153130 겹침", (int(ST.loc["153130", "days_with_069500"]), int(ST.loc["153130", "days_with_any_prev"]), int(ST.loc["153130", "intervals_alone_vs_prev"])), (1, 179, 6)),  # 확장
    ("133690 구간·일수", (len(prim("133690")), int(prim("133690").duration.sum())), (6, 80)),  # 나스닥 해석 대조
    ("133690 2025-04", (int(row("133690_q20_008").duration), round(float(row("133690_q20_008").peak_sigma), 1), round(float(row("133690_q20_008").peak_over_boundary), 2), round(float(row("133690_q20_008").top1_r), 2), round(float(row("133690_q20_008").top1_share), 2)), (23, 65.7, 2.16, 10.08, 0.33)),  # 나스닥 해석 대조
    ("133690 겹침", (int(ST.loc["133690", "intervals_alone_vs_prev"]), int(ST.loc["133690", "days_with_069500"])), (0, 42)),  # 확장
    ("261220 구간·일수·q60", (len(prim("261220")), int(prim("261220").duration.sum()), len(prim("261220", 60))), (3, 59, 0)),  # 원유 해석 대조
    ("261220 2022-03", (round(float(row("261220_q20_002").peak_sigma), 1), round(float(row("261220_q20_002").max_drawdown_pct), 1), row("261220_q20_002").shock_type), (99.8, -21.3, "누적형")),  # 원유 해석 대조
    ("261220 2025-06", (round(float(row("261220_q20_004").top1_r), 2), round(float(row("261220_q20_004").top1_share), 2), bool(row("261220_q20_004").window_exit_end), int(row("261220_q20_004").max_N_A_q20)), (-14.47, 0.65, True, 2)),  # 원유 해석 대조
    ("급변일 경보 (6종 12셀)", int(IOA[IOA.side == "A20 날"].alarm_days.sum()), 0),  # 핵심
    ("비급변일 경보 ETF별", tuple(int(IOA[(IOA.ticker == t) & (IOA.side == "비 A20 날")].alarm_days.sum()) for t in ("153130", "261220", "133690")), (32, 9, 4)),  # W3 경보
    ("주분석 q20 구간·단일·창이탈", (len(IV[(IV.q == 20) & (IV.period == "PRIMARY")]), int((IV[(IV.q == 20) & (IV.period == "PRIMARY")].shock_type == "단일 충격형").sum()), int(IV[(IV.q == 20) & (IV.period == "PRIMARY")].window_exit_end.sum())), (69, 25, 24)),  # 그림 X4 해석
    ("KOSPI200 구간 참여 2024-08·2025-04", (int(K2.loc["2024-08-05", "229200"]), int(K2.loc["2024-08-05", "133690"]), int(K2.loc["2025-04-07", "133690"]), int(K2.loc["2025-04-07", "261220"]), int(K2.loc["2025-04-07", "229200"])), (20, 20, 22, 17, 14)),  # 그림 X2 해석
    ("2023-11·2025-11 참여", (int(K2.loc["2023-11-06", "229200"]), int(K2.loc["2023-11-06"][["148070", "153130", "133690", "261220"]].sum()), int(K2.loc["2025-11-04"][["229200", "148070", "153130", "133690", "261220"]].sum())), (13, 0, 0)),  # 그림 X2 해석
    ("A20 날 중앙 T/crit 범위 (A 정책)", (round(float(IOA[(IOA.policy == "A") & (IOA.side == "A20 날")].median_R.min()), 2), round(float(IOA[(IOA.policy == "A") & (IOA.side == "A20 날")].median_R.max()), 2)), (0.37, 0.59)),  # 그림 X3 해석
    ("비 A20 날 중앙 T/crit 범위 (A 정책)", (round(float(IOA[(IOA.policy == "A") & (IOA.side == "비 A20 날")].median_R.min()), 2), round(float(IOA[(IOA.policy == "A") & (IOA.side == "비 A20 날")].median_R.max()), 2)), (0.29, 0.57)),  # 그림 X3 해석
]  # 끝
bad = {k: (o, x) for k, o, x in CLAIMS if o != x}  # 불일치 주장
print(f"CLAIMS {len(CLAIMS) - len(bad)}/{len(CLAIMS)} 일치")  # 결과
assert not bad, bad  # 불일치가 있으면 해석 문단을 고쳐야 한다
"""),
        code(r"""
# 09·10·W3 결과 폴더가 실행 전후로 바이트 동일한지 확인하고, 캡션 수치를 저장한다.
AFTER = {str(p.relative_to(ROOT)): sha(p) for d in WATCH for p in sorted(d.glob("*")) if p.is_file()}  # 종료 지문
assert AFTER == BEFORE, "09·10·W3 산출물이 바뀌었습니다"  # 변경 금지
(RES / "figure_captions.json").write_text(json.dumps(CAP, ensure_ascii=False, indent=1, default=str, sort_keys=True) + "\n", encoding="utf-8")  # 캡션 저장
print("09·10·W3 산출물 불변 ·", len(P.results_digest(ROOT)), "개 결과 CSV ·", len(list(FIGDIR.glob("*.png"))), "PNG ·", len(list(FIGDIR.glob("*.svg"))), "SVG")  # 산출물 수
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"display_name": "Python 3 (R2H .venv)", "language": "python", "name": "python3"}
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
