# ruff: noqa: E501
"""10번 노트북 생성기 (10-lock-1) — ETF 20종 공통 고변동성 급변 후보 구간 비교.

실행 출력이 있는 노트북을 무심코 지우지 않도록 --write 명시 실행만 허용한다.
생성 후 ``scripts/run_t19_notebook.py`` 로 새 커널에서 실행한다. 모든 코드 줄에는 한국어 주석을 단다
(빠지면 생성 단계에서 멈춘다). 해석 문단의 수치는 마지막 CLAIMS 셀이 결과표와 다시 대조한다.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "10_ETF20종_공통고변동성_급변후보구간비교.ipynb"
HANGUL = re.compile(r"[가-힣]")
CLOSERS = {")", "]", "}", "),", "],", "},", ")]", "})"}


def md(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    """주석이 빠진 코드 줄이 있으면 멈춘다 (t18 생성기와 같은 검사)."""
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


def fig(method: str, name: str, *args: str) -> nbformat.NotebookNode:
    arg = ", ".join(args)
    return code(f"""
CAP["{name}"] = FG.{method}({arg})  # 결과로 그림을 다시 그리고 캡션 수치를 받는다
display(Image(data=preview(FIGDIR / "{name}.png")))  # 저장된 PNG(320dpi)의 축소 미리보기
print(json.dumps(CAP["{name}"], ensure_ascii=False, default=str)[:700])  # 그림 캡션의 실제 수치
""")


def table(expr: str, note: str) -> nbformat.NotebookNode:
    return code(f"""
display({expr})  # {note}
""")


SETUP = r"""
# 새 커널 첫 셀: BLAS 스레드를 NumPy 로드 전에 1로 고정해 결과를 결정적으로 만든다.
import os  # 환경변수 설정
import sys  # 인터프리터·모듈 경로 확인
from pathlib import Path  # 저장소 상대 경로

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # 네 BLAS 계열 변수
    os.environ[key] = "1"  # 다중 스레드 합산 순서에 따른 비트 차이를 막는다
assert "numpy" not in sys.modules, "새 커널에서 첫 셀부터 실행해야 합니다"  # 숨은 커널 상태 금지
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t19_common_vol_candidates_v1.json").is_file())  # 저장소 루트 탐색
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

# 09(W4) 와 같은 고정 환경이어야 한다 (user-site 의 다른 numpy/pandas 를 잡으면 여기서 멈춘다).
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2"}  # 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": metadata.version("scipy"), "matplotlib": metadata.version("matplotlib")}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패로 처리
assert ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
pd.set_option("display.width", 220)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화
pd.set_option("display.max_colwidth", 140)  # 그룹 명단이 잘리지 않게

from r2h.common_vol import pipeline as P  # 10번 계산 (09 파이프라인은 호출하지 않는다)
from r2h.common_vol.figures import Figures10  # 10번 그림

assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
BASE = ROOT / "research/common_volatility_candidates_10"  # 10번 산출물 폴더
RES = BASE / "results"  # 결과표
FIGDIR = BASE / "figures"  # 그림 (PNG 320dpi + SVG)
W4 = ROOT / "research/peer_relative_shock_w4"  # 09 산출물 (읽기만)


def preview(path, width=1600):  # 노트북 용량을 줄이는 축소 미리보기 (원본은 figures/)
    from io import BytesIO  # 메모리 버퍼
    from PIL import Image as PILImage  # 이미지 축소
    im = PILImage.open(path)  # 320dpi 원본
    im.thumbnail((width, width * 3))  # 가로 1600px 이하로 축소
    buf = BytesIO()  # 출력 버퍼
    im.save(buf, format="PNG", optimize=True)  # PNG 로 다시 저장
    return buf.getvalue()  # 바이트 반환


def sha(p):  # 파일 SHA256
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()  # 바이트 단위 지문


# 10번 계약·설정 동결 지문 (결과를 보고 규칙을 바꾸지 않았음을 확인).
for line in (BASE / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():  # 동결 기록 2줄
    digest, name = line.split(maxsplit=1)  # 해시·경로
    assert sha(ROOT / name) == digest, f"동결 파일 변경: {name}"  # 변경되면 중단
# 이전 연구(노트북 00–08, W1–W3, T12) 보호 파일 불변 확인.
PROTECTED = list(csv.DictReader(open(ROOT / "research/joint_cusum_w3/W3_PROTECTED_SHA256.csv", encoding="utf-8")))  # W3 가 남긴 보호 목록
CHANGED = [r["path"] for r in PROTECTED if sha(ROOT / r["path"]) != r["sha256"]]  # 바뀐 보호 파일
assert not CHANGED, f"보호 파일 변경: {CHANGED}"  # 기존 연구는 읽기만
# 09 노트북과 W4 results 지문을 작업 시작 시점에 기록해 두고 마지막 셀에서 다시 대조한다.
W4_BEFORE = {p.name: sha(p) for p in sorted((W4 / "results").glob("*"))} | {"09_notebook": sha(ROOT / "notebooks/09_ETF20종_Peer상대변동성_급변구간정의.ipynb")}  # 시작 지문
print("작업트리:", ROOT)  # 실행 위치
print("보호 파일", len(PROTECTED), "개 불변 · W4 results", len(W4_BEFORE) - 1, "개 지문 기록")  # 검증 요약
print("실행 환경:", ACTUAL_ENV)  # 환경 기록
"""

RUN = r"""
# 09 산출물 승계 게이트 → 12개 규칙 일별 판정 → 구간 → 비교·사례. 결과는 research/common_volatility_candidates_10/results/.
R = P.run(ROOT)  # 09 의 그룹 A 상태만 읽는다 (W4 results/figures 는 쓰지 않는다)
CFG, VER = R["cfg"], R["verify"]  # 설정과 승계 검증 결과
FG = Figures10(R, ROOT)  # 그림 생성기 (같은 결과 객체)
CAP = {}  # 그림별 캡션 수치
D, IV, SM = R["daily"], R["intervals"], R["summary"]  # 일별 표·구간표·후보 요약
PRI = D[D["period"] == "PRIMARY"]  # 주분석 2021–2025
IVP = IV[IV["period"] == "PRIMARY"]  # 주분석 구간
SMI = SM.set_index("rule")  # 규칙 ID 로 조회
print("프로토콜:", CFG["protocol_version"], "| 설계 지위:", CFG["design_status"])  # 실행 정보
print("주분석 거래일:", len(PRI), "| 규칙", len(R["rules"]), "개 | 주분석 구간 총", len(IVP), "개")  # 핵심 규모
"""


def book() -> nbformat.NotebookNode:
    cells = [
        md(r"""
# 10 · ETF 20종 공통 고변동성 기반 급변 후보 구간 추출·비교·선정

**「17개 경제적 노출 그룹이 같은 날 동시에 자기 과거 대비 고변동성(A)을 보이는 정도로 정의한 급변 후보 구간 — 20·60거래일 × 최소 동시 참여 그룹 수 k 의 비교」**

- 연구 ID `t19_common_volatility_candidates_10`, 프로토콜 `10-lock-1`, 기준 커밋 `172cbb3` (W4 최종), 브랜치 `research/10_common_volatility_candidate_intervals`.
- 계약 `research/common_volatility_candidates_10/CANDIDATE_RESEARCH_CONTRACT.md` — 후보 구간을 계산하기 전에 커밋했다 (`1ab42bd`, 개정 1 `3b183f8`).
- **설계 지위: 사후 탐색 연구.** 09번(W4) 결과를 본 뒤 설계했다. 특히 C3(k=12)·C4(k=6)의 임계값은 09번의 관측 최대 참여값과 같다.
- 이 노트북의 산출물은 **정의별 실제 후보 구간 목록과 비교평가표**다. 통계적 구조변화의 입증, CNN 예측성능 검증, 최적 정의의 선언이 아니다.
- 09번 판정 `VALID_ZERO_INTERVALS` (17/17 ∧ A ∧ B) 는 그대로 유지한다.
"""),
        md("## 0. 실행 환경·동결 지문"),
        code(SETUP),
        md("## 0.1 전체 계산 실행"),
        code(RUN),
        # ── 1 ──
        md(r"""
## 1. 연구 목적 — 왜 W4 의 17/17 A∩B 에서 구간이 0개였는가

09번(W4)은 급변 구간을 다음과 같이 정의했다.

- A: 각 ETF 의 20·60거래일 연환산 σ 가 자기 과거 확장형 분위 0.90 이상.
- B: 각 ETF 의 σ 가 Peer 대비 평소 비율에서 위·아래 5% 꼬리로 벗어남.
- 17개 노출 그룹 **모두**가 같은 날 A 와 B 를 함께 만족.

결과는 주분석 1,225일 중 0일, 구간 0개였다 (`VALID_ZERO_INTERVALS`). 이것은 계산 실패가 아니라 정의가 만든 정직한 결과다.

원인은 09번 §12 에서 분해했다.

- A 와 B 는 서로 다른 현상이다. A 는 "모두가 함께 흔들리는가", B 는 "평소 짝과 다르게 흔들리는가" 를 잰다.
- 시장 전체가 흔들리는 날에는 Peer 도 같이 흔들리므로 B 가 오히려 잘 켜지지 않는다. 2020-03 처럼 A 가 17/17 인 날에도 B 는 3–6/17 이었다.
- 주분석에서 A 만 보아도 동시 참여는 최대 12/17 (q20) · 6/17 (q60) 이다. 17/17 은 A 만으로도 닿지 않는다.

따라서 "급변 구간이 없다" 는 결론과 "정의가 너무 엄격하다" 는 문제는 분리해서 다뤄야 한다. 10번은 후자를 다룬다.
"""),
        # ── 2 ──
        md(r"""
## 2. 이번 연구 질문 — 시장 공통 고변동성의 정의 후보

10번은 **A 를 후보 구간의 주 기준**으로 쓴다. B 와 A∩B 는 후보 구간을 사후에 설명하는 데만 쓰고, 진입 조건에 넣지 않는다.

| 상태 | 묻는 것 | 10번에서의 역할 |
|---|---|---|
| A | 여러 자산이 각각 자기 과거보다 높은 변동성을 보이는가 | 후보 구간의 진입·종료 기준 |
| B | 각 ETF 가 Peer 와의 평소 변동성 관계에서 이탈했는가 | 사후 특성 기술 |
| AB | 높은 변동성과 상대 괴리가 동시에 나타났는가 | 사후 특성 기술 |

답할 질문은 네 가지다.

1. 자기 과거 대비 고변동성인 날이 여러 노출 그룹에서 실제로 얼마나 겹치는가?
2. q = 20·60 과 k = 9·10·12·6 등을 적용하면 어떤 날짜와 구간이 나오는가?
3. 규칙마다 구간 수, 지속기간, 참여 그룹, 사건, 시간적 일관성이 어떻게 다른가?
4. 최종 정의를 고르려면 어떤 장단점과 한계를 따져야 하는가?
"""),
        # ── 3 ──
        md(r"""
## 3. 09번 결과·동결 계약 검증 (승계 게이트)

09번 파이프라인은 다시 실행하지 않는다 (W4 results 와 figures 를 다시 쓰기 때문이다). 대신 09번이 남긴 그룹별 일별 상태 `group_daily_states.csv` 를 읽고, 다음을 먼저 확인했다.

1. W4 `RELEASE_MANIFEST.json` 의 09 노트북·파일 지문 전부. 예외는 1건이다. `evidence/reproducibility_report.md` 는 매니페스트 작성 뒤 W4 최종 커밋 `172cbb3` 이 한 줄(검증 파일 수 89→91)만 고쳤다. 이 사실은 계약 개정 1 로 적었고, 이 파일만 새 지문으로 대조한다.
2. 그룹 상태에서 다시 센 날짜·q 별 `N_A`, `n_eval_A` 가 `global_daily_counts.csv` 와 전 행 일치.
3. 기간별 최대 A·17/17 일수·NA 일수가 `global_by_period.csv` 와 일치.
4. W4 구간표 0행, 판정 `VALID_ZERO_INTERVALS`.
"""),
        code(r"""
# 승계 게이트 결과: 기간 지위별로 다시 센 값과 09 기록을 나란히 보인다.
print("매니페스트 파일", VER["n_manifest_files"], "개 · 대조 행", VER["rows_checked"], "· W4 판정", VER["w4_verdict"], "· W4 구간", VER["w4_intervals"])  # 요약
print("매니페스트 이후 정정 파일:", list(VER["post_manifest_edits"]))  # 예외 1건
display(VER["period_check"])  # 기간별 재계산 vs 09 기록
"""),
        md(r"""
**해석.**
- 주분석 2021–2025 는 q20·q60 모두 1,225일이고 NA 가 0일이다. 17개 그룹이 매일 평가 가능하므로 분모 17 을 그대로 쓴다.
- 09번 사실이 재현됐다: 주분석 최대 A 는 q20 12, q60 6 이다. 2020 파일럿 q20 의 17/17 은 16일이다.
- 2020 파일럿은 기준 이력이 쌓이기 전이라 q20 26일, q60 66일이 NA 다. 이 날들은 0 이 아니라 관측 불능으로 처리한다.
"""),
        # ── 4 ──
        md(r"""
## 4. 17개 경제적 노출 그룹과 A 상태

- 집계 단위는 ETF 20종이 아니라 **노출 그룹 17개**다. KOSPI200 동일노출 4종(069500·102110·122630·114800)은 한 그룹이고, 나머지 16종은 각자 한 그룹이다.
- KOSPI200 그룹의 A 는 09번 규칙 그대로 Core Pair(069500·102110) 둘 다 A 일 때만 1 이다.
- A 는 과거 **분위**(0–1) 기준이다. 연환산 σ 의 절대 수준(%)이 아니다. 같은 A 라도 단기채권 153130 의 σ 는 0.x%, 레버리지·주식 ETF 는 수십 %다.
"""),
        code(r"""
# 노출 그룹 17개와 구성 ETF (W2 exposure_groups.csv 원본).
EG = R["states"]["eg"]  # 20종 표
display(EG.groupby("exposure_group", sort=False).agg(구성=("ticker", ", ".join), 이름=("name", " / ".join), 범주=("category", "first")))  # 그룹별 구성
assert EG["exposure_group"].nunique() == 17 and len(EG) == 20  # 17 그룹·20 ETF
"""),
        fig("g01_state_maps", "G01_group_A_state_maps"),
        md(r"""
**해석 (G01).**
- 주분석에서 같은 날 A 인 그룹 수 N_A 는 대부분 0–3 이다. 중앙값은 q20·q60 모두 1, 평균은 q20 1.75, q60 1.46 이다.
- q20 에서 N_A 가 9 이상으로 솟는 곳은 세 군데뿐이다: 2022-10, 2024-08, 2025-04.
- 2022 에는 채권(148070·153130)과 달러(261240)가 긴 띠를 만든다. 주식 그룹이 같이 켜지는 날은 짧다.
- q60 은 같은 사건을 늦고 길게 본다. 최대 6 은 2022-11 과 2024-10~11 에만 나온다.
"""),
        # ── 5 ──
        md("## 5. 20일·60일 공통 고변동성 참여도"),
        code(r"""
# 주분석 N_A 분포: k 이상인 날 수 (q20·q60). 같은 날 동시 참여 기준이다.
dist = pd.DataFrame({f"q{q}": [int((PRI[f"n_A_q{q}"] >= k).sum()) for k in range(0, 18)] for q in (20, 60)}, index=pd.Index(range(0, 18), name="k"))  # 생존표
display(dist.T)  # k 별 일수
"""),
        fig("g03_k_curve", "G03_k_survival_curves"),
        md(r"""
**해석 (G03).**
- q20 에서 N_A ≥ k 인 날은 k=7·8·9 에서 46·41·39일로 거의 평평하다. k=10 에서 28일, k=11 에서 11일로 급히 줄고, 13 이상은 0일이다.
- 따라서 k=9 는 평탄한 구간의 끝에 있다. k 를 7–9 사이에서 바꾸면 후보일이 크게 바뀌지 않는다. 반면 k=10 이상에서는 한 단계마다 결과가 크게 바뀐다.
- q60 은 k=6 에서 14일, k=7 이상에서 0일이다. q60 의 C4(k=6) 는 관측 최대값 바로 위의 칼날 위에 있다.
- 오른쪽 그림처럼 구간 수는 k 에 대해 단조가 아니다. q20 은 k=9 에서 3개, k=10 에서 5개다. 긴 구간이 하루 미충족 때문에 쪼개지기 때문이다.
"""),
        # ── 6 ──
        md(r"""
## 6. C1–C4 후보 규칙과 계산 정의

`N_A(t,q) = Σ_g 1[A(g,t,q)=1]`, 후보 `C(k,q,t) = 1[N_A ≥ k]`. 17개 그룹 중 하나라도 NA 이면 그날은 NA 다.

| 후보 | q | k | 이름 | 목적 |
|---|---|---|---|---|
| C1 | 20 | 9 | 과반 공통 고변동성 | 노출 그룹의 과반이 같은 날 고변동성 |
| C2 | 20 | 10 | 강한 공통 고변동성 | C1 보다 강한 공통성 |
| C3 | 20 | 12 | 광범위한 극단적 고변동성 | 관측 최대 수준 (= 09 q20 최대) |
| C4 | 60 | 6 | 중기 고변동성 | 지속적 중기 국면 (= 09 q60 최대) |

- 통제 비교: k = 9·10·12 를 q60 에도, k = 6 을 q20 에도 적용한다. k = 17 은 W4 연결 참고, k = 3 은 W2 "3그룹 이상" 개념의 참고다.
- **C4 의 6/17 은 C1 의 9/17 보다 완화된 기준이다.** C1 과 C4 의 차이를 q 효과만으로 읽지 않는다.
- q=20 은 20거래일이다 (21일이 아니다). 변동성 측정기간 q 와 W1·W3 의 CUSUM 검정창 w 는 다른 개념이다.
"""),
        table('R["rules"]', "격자 12개 규칙과 역할"),
        # ── 7 ──
        md("## 7. 일별 후보 상태 생성"),
        fig("g04_rule_ribbons", "G04_rule_ribbons"),
        code(r"""
# 무결성: 같은 q 에서 날짜 집합 포함관계 (k 가 크면 부분집합), 구간 날짜 = 후보일, 중복 포함 없음은 pipeline.check_intervals 가 assert 했다.
for q in (20, 60):  # 두 기간
    ks = CFG["k_grid"]  # 격자 k 3·6·9·10·12·17
    for k1, k2 in zip(ks[:-1], ks[1:]):  # 인접 k 쌍
        assert not ((D[f"q{q}_k{k2}"] == 1) & (D[f"q{q}_k{k1}"] != 1)).any()  # 엄격 ⊆ 완화
print("포함관계 OK: C3 ⊆ C2 ⊆ C1 (q20), q60 도 k 단조")  # 확인
display(R["integrity"][R["integrity"]["period"] == "PRIMARY"])  # 규칙별 후보일·구간 수·NA (주분석)
"""),
        md(r"""
**해석 (G04).**
- 같은 q 안에서 위(완화)에서 아래(엄격)로 갈수록 파란 날이 줄어들고, 아래 줄의 파란 날은 항상 위 줄에도 있다 (assert 통과).
- q60 은 k ≥ 9 에서 한 번도 켜지지 않는다. 관측 최대가 6 이기 때문이다. 0 도 유효한 결과이며 임계값을 바꾸지 않았다.
"""),
        # ── 8 ──
        md(r"""
## 8. 실제 급변 후보 구간 전수 추출

규칙: 첫 1 이 시작일, 0 이 나오면 직전 1 에서 종료, 하루짜리 보존, 갭 병합 없음, NA 는 끊는 경계. 기간 첫날·마지막 날이 1 이면 옆 기간의 상태로 좌우 검열을 적는다.
"""),
        code(r"""
# C1–C4 주분석 구간 전수. '동시 최대'(max_n_A) 와 '한 번이라도'(n_groups_ever) 를 따로 적는다.
COLS = ["interval_id", "candidate", "start", "end", "duration_trading_days", "max_n_A", "max_n_A_first_date", "n_days_at_max", "mean_n_A", "median_n_A", "start_n_A", "end_n_A", "n_groups_always", "n_groups_ever", "n_groups_never", "max_n_B", "max_n_AB", "evaluable_share", "left_censored", "right_censored", "exit_reason"]  # 표시 열
MAIN_IV = IVP[IVP["candidate"].isin(["C1", "C2", "C3", "C4"])]  # 주 후보 구간
display(MAIN_IV[COLS].round(2))  # 구간 표
"""),
        code(r"""
# 구간별 참여 그룹 명단: 최대 첫날 · 매일 · 전혀 참여 안 함 (그룹 ID 는 ETF 코드, KOSPI200 은 묶음 그룹).
display(MAIN_IV[["interval_id", "groups_at_max_first_day", "groups_always", "groups_never"]])  # 명단 표
"""),
        fig("g05_gantt", "G05_candidate_gantt"),
        fig("g02_count_with_intervals", "G02_count_and_candidate_intervals"),
        md(r"""
**해석 (G05·G02).** 주분석 2021–2025 에서 실제로 나온 구간은 다음과 같다.

| 후보 | 구간 | 거래일 | 동시 최대 N_A |
|---|---|---|---|
| C1 (q20 k9) | 2022-10-11~10-12 | 2 | 9 |
| | 2024-08-05~09-02 | 20 | 10 |
| | 2025-04-10~05-07 | 17 | 12 |
| C2 (q20 k10) | 2024-08-07 | 1 | 10 |
| | 2024-08-12~08-26 | 10 | 10 |
| | 2024-08-28~08-30 | 3 | 10 |
| | 2025-04-10~04-28 | 13 | 12 |
| | 2025-05-07 | 1 | 10 |
| C3 (q20 k12) | 2025-04-11~04-23 | 9 | 12 |
| C4 (q60 k6) | 2022-11-21~11-22 | 2 | 6 |
| | 2022-11-24~11-29 | 4 | 6 |
| | 2024-10-24~11-04 | 8 | 6 |

- 주 후보 구간은 모두 12개이고, 좌우 검열된 구간은 없다. 모든 구간은 다음 날 조건 미충족(0)으로 끝났다.
- 모든 주 후보 구간에서 ever 참여 그룹 수가 동시 최대 N_A 와 같다. 구간 중 참여한 그룹이 최대일에 모두 함께 A 였다는 뜻이다. 그래도 이 값은 데이터가 정한 결과일 뿐이다. 표현은 항상 '동시 최대' 기준으로 한다.
- C4 의 2022-11 은 11-23 하루가 5/17 로 내려가 두 구간으로 나뉜다. 갭 병합을 하지 않는 주 정의 그대로다.
"""),
        # ── 9 ──
        md("## 9. 후보 정의별 구간 수·지속일·범위 비교"),
        code(r"""
# 12개 규칙 전수 비교표 (주분석). 0개 규칙은 gap = k − 관측 최대 를 함께 적는다.
SHOW = ["rule", "label", "q", "k", "n_intervals", "candidate_days", "candidate_share", "n_one_day", "duration_mean", "duration_median", "duration_max", "observed_max_n_A", "gap_k_minus_max", "mean_n_A_on_candidate_days", "mean_stability_jaccard", "mean_core_share", "top5_longest"]  # 표시 열
display(SM[SHOW].round(3))  # 전수 비교표
"""),
        fig("g06_effects", "G06_k_and_q_effects"),
        fig("g13_simul_vs_ever", "G13_simultaneous_vs_ever"),
        md(r"""
**해석 (G06·G13).**
- **C1**: 3구간, 39일 (주분석의 3.2%). 1일 구간 0개, 지속 중앙값 17일. 인접일 참여 집합 Jaccard 평균 0.98 로 구성이 안정적이다.
- **C2**: 5구간, 28일 (2.3%). 1일 구간이 2개다. 2024-08 의 C1 구간 하나가 C2 에서 세 조각이 된다.
- **C3**: 1구간, 9일 (0.7%). 2025-04 하나만 남는다.
- **C4**: 3구간, 14일 (1.1%). 지속 중앙값 4일, 최장 8일로 C1 보다 짧다.
- 0개 규칙: q20 k17 (gap 5), q60 k9·k10·k12·k17 (gap 3·4·6·11). 이 기준들은 2021–2025 에 관측된 공통성 수준을 넘는다.
- G13 에서 세 막대(매일·동시 최대·ever)가 겹치는 정도가 '같은 날 동시 급변' 의 순도다. C3·C4 는 세 값이 모두 같다. C1 의 2025-04 구간은 매일 참여 8, 동시 최대 12 로 차이가 가장 크다.
"""),
        # ── 10 ──
        md("## 10. 임계값 k 의 효과 (q 고정)"),
        fig("g08_split", "G08_split_and_vanish"),
        code(r"""
# k 를 한 단계 올릴 때 완화 규칙의 각 구간이 소멸·유지·분할되는지 (q20, k 6→9→10→12→17).
KID = R["split_kids"]  # 완화 구간별 자식 수
display(KID[(KID["q"] == 20) & (KID["k_loose"] >= 6)][["k_loose", "k_strict", "loose_id", "start", "end", "loose_days", "n_children", "strict_days_kept", "relation"]])  # 분할 표
display(R["jaccard"].pivot(index="rule_a", columns="rule_b", values="jaccard").loc[["q20_k6", "q20_k9", "q20_k10", "q20_k12"], ["q20_k6", "q20_k9", "q20_k10", "q20_k12"]].round(3))  # q20 날짜 Jaccard
"""),
        md(r"""
**해석 (G08).**
- k=6 (진단) → C1: 9개 구간 중 6개가 사라진다. 2022-03-17, 2022-06-27~28, 06-30, 07-06~08, 10-31, 2023-10-31~11-01 의 1–3일 구간들이다. 2022-10, 2024-08, 2025-04 셋만 남는다.
- C1 → C2: 2022-10-11~12 (N_A 9) 가 사라진다. 2024-08 (20일)은 3개로, 2025-04 (17일)는 2개로 **분할**된다. 날짜는 39 → 28일로 줄지만 구간은 3 → 5개로 늘어난다.
  - 2024-08 이 나뉘는 날은 08-05·06·08·09·27, 09-02 이다. 이날들의 N_A 는 9 다.
  - 2025-04 가 나뉘는 날은 04-29·30, 05-02 이다. 역시 N_A 9 다.
- C2 → C3: 2024-08 이 통째로 사라진다 (그 사건의 최대는 10). 2025-04-11~23 만 남는다.
- 날짜 Jaccard: C1–C2 0.72, C1–C3 0.23. 같은 q 안에서는 포함관계라 Jaccard = |엄격|/|완화| 이다.
- 결론: k 는 '어떤 사건이 남는가' 와 '사건이 몇 조각으로 보이는가' 를 함께 바꾼다. k=10 은 N_A 가 9–10 을 오가는 사건(2024-08)을 조각낸다.
"""),
        # ── 11 ──
        md("## 11. 기간 q 의 효과 (k 고정)"),
        table('R["horizon"]', "k 별 q20 vs q60 날짜 겹침·Jaccard·겹치는 구간 쌍"),
        fig("g07_jaccard", "G07_rule_jaccard"),
        md(r"""
**해석 (G07, 기간 통제).**
- 같은 k=6 에서 q20 은 65일, q60 은 14일이다. **겹치는 날은 0일**이다 (Jaccard 0). 20일 창이 공통 고변동성을 보일 때 60일 창은 아직 오르는 중이고, 60일 창이 최대일 때 20일 창은 이미 내려온 뒤다.
- k=3 에서도 Jaccard 는 0.17 이다. q20 구간 30개 중 q60 구간과 한 번이라도 겹치는 것은 15개다.
- k = 9·10·12 에서 q60 은 0일이다. 따라서 "C1 은 q20, C4 는 q60" 의 차이에는 k 의 차이(9 vs 6)와 q 의 차이가 섞여 있다. 같은 k=9 로 비교하면 q60 은 아무 구간도 만들지 않는다.
- 해석: q20 은 **충격 시점의 동시 고변동성**을, q60 은 **충격 뒤 남은 고변동성의 누적**을 본다. 둘은 같은 현상의 다른 단면이며 한쪽이 다른 쪽을 대신하지 않는다.
"""),
        # ── 12 ──
        md(r"""
## 12. 2022년 사례 심층 분석 (E1 — 채권 중심 고변동성)

사례 창 2022-01-03~12-29 (09 와 같은 창). 비교 기준: W2 HIGH_LEVEL 2022-09-07~12-07, 09 q20 A 최대 9/17 (2022-10-11).
"""),
        fig("g_event", "G09_event_E1_2022_bond", '"E1_2022_bond"', '"09"'),
        code(r"""
# E1 창 안의 규칙별 결과와 C1 후보일의 일별 상태.
EVT = R["events"]  # 사례 × 규칙
display(EVT[(EVT["event"] == "E1_2022_bond") & EVT["rule"].isin(["q20_k3", "q20_k6", "q20_k9", "q20_k10", "q20_k12", "q60_k3", "q60_k6"])][["rule", "candidate", "candidate_days", "candidate_days_in_w2_ref", "w2_ref_days", "n_intervals", "intervals", "window_max_n_A", "window_max_first_date"]])  # 규칙별
display(R["event_days"][R["event_days"]["event"] == "E1_2022_bond"])  # C1 후보일
"""),
        md(r"""
**해석 (E1).**
- **C1 에서 실제 연속 구간**: 2022-10-11~10-12, 단 2거래일 (N_A 9). 참여 그룹은 코스닥150·반도체·2차전지·철강·미국 S&P500·국고채10년·단기채권·금·달러다. 주식·채권·원자재·통화가 함께 켜진 날이다.
- **C2 에서 사라지는 날짜**: 이 2일이 전부 사라진다. 2022년의 최대가 9 이므로 C2·C3 는 2022년에 0일이다.
- **q60 에서는 다르게 남는다**: C4 는 2022-11-21~22, 11-24~29 (6일, N_A 6)를 잡는다. q20 정점보다 약 6주 늦다. 구성은 코스닥150·반도체·미국 S&P500·국고채10년·단기채권·달러다. 11-23 하루가 5/17 이라 두 구간으로 나뉜다.
- W2 참고 구간(62거래일) 중 C1 은 2일, C4 는 6일만 포함한다. 2022년의 고변동성은 **오래 지속됐지만 동시 참여 폭은 좁았다**. 채권·달러가 긴 띠를 만드는 동안 주식 그룹은 짧게 들어왔다 나갔다.
- 해석: 2022는 '과반 동시' 기준으로는 거의 보이지 않는다. '중기 누적' 기준(C4)이나 완화 기준(k=6, 23일)으로 보인다. 어떤 정의를 고르느냐에 따라 2022년을 급변기로 볼지가 갈린다.
"""),
        # ── 13 ──
        md(r"""
## 13. 2024년 8월 사례 심층 분석 (E2 — 다자산 변동성 확대)

사례 창 2024-07-01~09-30. 비교 기준: W2 EXPANSION 2024-08-02~09-02.
"""),
        fig("g_event", "G10_event_E2_2024_08", '"E2_2024_08"', '"10"'),
        code(r"""
# E2 창 안의 규칙별 결과와 C1 후보일별 N_A·C2 포함 여부 (분할 원인 확인).
display(EVT[(EVT["event"] == "E2_2024_08") & EVT["rule"].isin(["q20_k6", "q20_k9", "q20_k10", "q20_k12", "q60_k3", "q60_k6"])][["rule", "candidate", "candidate_days", "n_intervals", "intervals", "window_max_n_A", "window_max_first_date"]])  # 규칙별
display(R["event_days"][R["event_days"]["event"] == "E2_2024_08"])  # C1 후보일
"""),
        md(r"""
**해석 (E2).**
- **C1**: 2024-08-05~09-02, 20거래일 연속. 동시 최대 10 (첫 도달 08-07). k=6 과 k=9 의 구간이 똑같다. 08-05 에 N_A 가 1 에서 9 로 한꺼번에 뛰었다는 뜻이다.
- **참여 구성**: KOSPI200·코스닥150·반도체·은행·자동차·2차전지·헬스케어·철강·고배당·미국 나스닥100 의 10개 그룹. 국고채·단기채·금·원유·달러·중국·미국 S&P500선물은 한 번도 참여하지 않았다. **국내 주식 중심의 동시 급변**이다.
- **C2**: N_A 가 9 와 10 을 오가며 3조각(1·10·3일)이 된다. 같은 사건이 C2 로는 세 개의 사건처럼 보인다.
- **C3**: 0일 (사건 최대 10 < 12).
- **q60**: 창 안 최대 4/17 (09-25). C4 는 이 사건 안에서 0일이다. 대신 2024-10-24~11-04 에 C4 구간(8일)이 나온다. 구성은 KOSPI200·코스닥150·반도체·은행·철강·중국 CSI300 이다. 8월 충격 뒤 남은 국내 주식 고변동성과 중국 변동성의 누적으로 읽힌다.
- 외부 맥락(이 데이터로 원인을 검증하지 않음): 2024-08-05 전후 글로벌 주식 급락·엔 캐리 청산 시기와 겹친다.
"""),
        # ── 14 ──
        md(r"""
## 14. 2025년 4월 사례 심층 분석 (E3 — 다자산 변동성 확대)

사례 창 2025-03-17~06-13. 비교 기준: W2 HIGH_LEVEL 2025-04-07~05-26.
"""),
        fig("g_event", "G11_event_E3_2025_04", '"E3_2025_04"', '"11"'),
        code(r"""
# E3 창 안의 규칙별 결과와 C1 후보일별 상태.
display(EVT[(EVT["event"] == "E3_2025_04") & EVT["rule"].isin(["q20_k6", "q20_k9", "q20_k10", "q20_k12", "q60_k3", "q60_k6"])][["rule", "candidate", "candidate_days", "n_intervals", "intervals", "window_max_n_A", "window_max_first_date"]])  # 규칙별
display(R["event_days"][R["event_days"]["event"] == "E3_2025_04"])  # C1 후보일
"""),
        md(r"""
**해석 (E3).**
- **C1**: 2025-04-10~05-07, 17거래일. 동시 최대 12 (04-11~04-23 의 9일 내내).
- **C3**: 2025-04-11~04-23 (9일). 2021–2025 에서 C3 가 남는 유일한 사건이다.
- **참여 구성 (최대일 12개)**: KOSPI200·코스닥150·반도체·2차전지·헬스케어·철강·미국 S&P500·미국 나스닥100·중국 CSI300·금·원유·달러. 은행·자동차·고배당·국고채10년·단기채권은 참여하지 않았다. 2024-08 과 달리 **해외 주식·원자재·통화까지 퍼진 다자산 급변**이다.
- **C2**: 04-10~04-28 (13일) 과 05-07 (1일) 로 나뉜다. 04-29·30, 05-02 에 N_A 가 9 로 내려갔기 때문이다.
- **q60**: 창 안 최대 4/17. C4 는 0일이다. 60일 창에서는 이 충격이 6개 그룹의 동시 고변동성까지 쌓이지 않았다.
- 외부 맥락(검증하지 않음): 2025-04 초 미국 관세 발표 이후의 글로벌 변동성 확대 시기와 겹친다.
"""),
        # ── 15 ──
        md("## 15. 후보 구간 내부 참여 그룹 분석"),
        fig("g12_participation", "G12_group_participation"),
        code(r"""
# 주 후보별 그룹 참여 비율 표 (후보일 중 A 인 비율 vs 주분석 전체 A 비율).
PT = R["participation"]  # 참여 표
display(PT.pivot(index="label", columns="candidate", values="share_on_candidate_days").reindex([R["states"]["label"][g] for g in R["states"]["groups"]]).round(2))  # 그룹 × 후보
"""),
        md(r"""
**해석 (G12).**
- C1 후보일 39일 동안 반도체(091230)·2차전지(305540)는 100%, KOSPI200·나스닥100 은 95%, 코스닥150 은 92% 참여했다. **C1 의 공통성은 주식 그룹이 이끈다**.
- 국고채10년·단기채권은 C1 후보일의 5% (2022-10 의 2일)에만 참여한다. 채권 고변동성은 C1 정의에서 거의 드러나지 않는다.
- C4 는 구성이 다르다. 2022-11 (채권·달러·미국 주식) 과 2024-10~11 (국내 주식·중국) 두 묶음이 번갈아 나온다.
- 함의: 17개 그룹 중 **주식 계열이 12개**(국내 9 · 해외 3)이고, 채권 2 · 원자재 2 · 통화 1 의 **비주식은 5개**뿐이다 (W2 `exposure_groups.csv` 범주 기준). 주식 충격만으로도 과반(9/17) 기준을 넘을 수 있다. 반대로 비주식 5개가 모두 켜져도 k=9 에 닿지 않는다. '17개 중 k 개' 기준은 주식 충격에 유리하며, 이것은 정의의 한계로 남는다.
"""),
        # ── 16 ──
        md("## 16. B 및 AB 를 이용한 보조 해석"),
        fig("g14_b_ab", "G14_B_AB_inside_outside"),
        table('R["b_ab"].round(3)', "후보일 vs 비후보일의 N_B·N_AB"),
        md(r"""
**해석 (G14).**
- C1 후보일의 평균 N_B 는 2.18, 비후보일은 1.65 다. Peer 상대 괴리는 후보일에 조금 늘 뿐이다.
- C3 후보일(2025-04)의 평균 N_B 는 1.00 으로 비후보일(1.67)보다 **낮다**. 가장 넓은 공통 고변동성 때 Peer 도 함께 흔들려 상대 괴리가 줄어든다. 09번에서 본 A–B 의 엇갈림과 같은 방향이다.
- N_AB 가 후보일에 높은 것(C1 1.56 vs 0.16)은 A 가 AB 의 필요조건이기 때문에 생기는 부분적인 기계적 효과다. 독립적인 근거로 쓰지 않는다.
- 결론: B 를 진입 조건에 넣으면 공통 고변동성 구간이 오히려 사라진다. 10번에서 B 를 보조 설명으로만 쓰는 이유다.
"""),
        # ── 17 ──
        md("## 17. 2020 파일럿과 2026 별도 탐색 (주분석 아님)"),
        fig("g16_pilot_2026", "G16_pilot2020_and_2026"),
        code(r"""
# 2020 파일럿과 2026 부분 연도의 규칙별 요약 (주분석과 섞지 않는다).
COLS2 = ["rule", "label", "n_intervals", "candidate_days", "duration_max", "observed_max_n_A", "first_start", "last_end", "censored_intervals", "evaluable_days", "days_in_period"]  # 표시 열
display(R["summary_pilot"][COLS2])  # 2020 파일럿
display(R["summary_2026"][COLS2])  # 2026 부분 연도 (10-02 까지)
display(IV[(IV["period"] != "PRIMARY") & IV["candidate"].isin(["C1", "C2", "C3", "C4"])][["interval_id", "start", "end", "duration_trading_days", "max_n_A", "entry_after", "left_censored", "right_censored"]])  # 파일럿·2026 주 후보 구간
"""),
        md(r"""
**해석 (G16).**
- **2020 파일럿**: q20 은 2020-03-16~04-06 에 17/17 이 16일이다 (09 재현). C1 은 2020-02-28~04-23 의 39일 구간을 포함해 40일이다. q60 구간은 모두 2020-04-07 에 시작한다. 그 직전은 기준 이력 부족으로 NA 이므로 진입 직전 상태는 'AFTER_NA' 다. 실제 시작은 더 이를 수 있다.
- **2026 (부분 연도, 2026-10-02 까지)**: C1 110일, C4 155일 (2026-01-29~09-16 한 구간). 주분석 5년 전체보다 많다. 2026 이 확장형 기준 대비 이례적인 고변동성 해였다는 뜻이다. 다만 비맹검 부분 연도라 정의를 고르는 근거로 쓰지 않는다.
- 두 기간 모두 **후보 정의의 성능 검증 근거가 아니다**. 2020 의 17/17 이 있었다고 해서 k=17 이 좋은 정의라는 뜻도 아니다.
"""),
        # ── 18 ──
        md("## 18. 기존 W2·W3 와의 정의 차이"),
        table('R["w2w3"]', "주 후보 구간과 W2 교차 그룹 구간·W3 공동 에피소드의 겹침 (비교만)"),
        md(r"""
**해석.**

| 항목 | W2 (06) | W3 (08) | 10번 후보 |
|---|---|---|---|
| 변동성 | `mean(r²)` (평균 0, ddof 0), q 3–120 | SVR–GARCH 잔차 CUSUM, 검정창 w | 표본표준편차 연환산 σ, q 20·60 |
| 고변동 판정 | 과거 분위 (HIGH_LEVEL·EXPANSION 채널) | 공동 CUSUM 통계량 | 과거 분위 0.90 (09 의 A) |
| KOSPI200 | 구성원 하나라도 (OR) | 대표 6종(069500·229200·148070·153130·261220·133690) 중 069500 하나 | Core Pair 둘 다 (AND) |
| 공통성 | 여러 q 중 3개 이상 겹친 ETF 의 그룹 수 | 공동 통계 유의성 | 같은 날 A 그룹 수 ≥ k |
| 결론 지위 | 탐색적 | `LOW_POWER_INCONCLUSIVE` + `NULL_MODEL_INVALID` (유의 공동 구간 0) | 사후 탐색 후보 |

- C1 의 세 구간은 모두 W2 HIGH_LEVEL·EXPANSION 구간과 겹친다. 다만 경계는 다르다. 예를 들어 2025-04 의 W2 HIGH_LEVEL 은 04-07~05-26 (13그룹), C1 은 04-10~05-07 이다. W2 경계를 복사하지 않았으므로 다른 것이 정상이다.
- W3 공동 에피소드와 겹치는 주 후보 구간은 2025-04 의 C1·C2·C3 뿐이다 (W3 는 귀무모형 부적합으로 탐색적이다). 10번은 W3 의 검출력 문제를 해결하지 않는다. 10번은 검정이 아니라 상태 정의다.
"""),
        # ── 19 ──
        md("## 19. 후보 간 비교평가 및 의사결정표"),
        fig("g15_yearly", "G15_yearly_candidate_days"),
        code(r"""
# 의사결정표: 수치는 결과표에서, 성격·한계는 위 장들의 해석을 요약한다.
DEC = pd.DataFrame([  # 후보별 비교
    {"후보": c, "q": CFG["main_candidates"][c]["q"], "k": CFG["main_candidates"][c]["k"], "구간 수": int(SMI.loc[r, "n_intervals"]), "후보일": int(SMI.loc[r, "candidate_days"]), "1일 구간": int(SMI.loc[r, "n_one_day"]), "최장": int(SMI.loc[r, "duration_max"]), "관측 최대 대비 k": f"{CFG['main_candidates'][c]['k']}/{int(SMI.loc[r, 'observed_max_n_A'])}"}  # 수치 열
    for c, r in (("C1", "q20_k9"), ("C2", "q20_k10"), ("C3", "q20_k12"), ("C4", "q60_k6"))  # 네 후보
]).set_index("후보")  # 표 정리
DEC["대표 사건"] = ["2022-10(2일)·2024-08(20일)·2025-04(17일)", "2024-08(3조각)·2025-04(2조각)", "2025-04(9일)만", "2022-11(2조각)·2024-10~11(8일)"]  # 위 §8–§14 결과
DEC["강조하는 시장 상태"] = ["충격 시점의 과반 동시 고변동성", "C1 중 더 넓은 동시성 (조각남)", "관측 최대 수준의 극단 동시성", "충격 뒤 누적된 중기 고변동성"]  # 성격
DEC["주요 한계"] = ["2022 채권 국면은 2일만 · 주식 그룹 비중에 민감", "N_A 9↔10 진동으로 사건 분할 · 2022 소멸", "k=관측 최대 (사후 선택) · 사건 1개", "k=관측 최대 (칼날) · q20 사건과 날짜 0일 겹침"]  # 한계
display(DEC)  # 의사결정표
"""),
        md(r"""
**해석 — 무엇을 근거로 고를 것인가.**

1. **사건 포착 범위**: 세 사례(2022·2024-08·2025-04)를 모두 잡는 후보는 C1 하나다. C2 는 2022 를 잃고, C3 는 2025-04 만 남긴다. C4 는 2022 와 2024 를 늦게 잡고 2025-04 는 놓친다.
2. **경계 안정성**: k 를 한 단계 바꿨을 때 결과가 얼마나 흔들리는가. q20 의 후보일은 k=7–9 에서 46·41·39 로 평탄하다. k=10 이상에서는 급변한다. C1 은 평탄 구간의 끝, C2·C3 는 급변 구간, C4 는 관측 최대 바로 위의 칼날이다.
3. **사건 단위의 일관성**: C1 은 사건 하나를 구간 하나로 본다 (1일 구간 0개). C2 는 같은 사건을 여러 구간으로 나눈다 (1일 구간 2개). CNN 학습 표본을 구간 단위로 자를 계획이라면 이 차이가 표본 수를 바꾼다.
4. **사후 선택의 정도**: C3·C4 의 k 는 09번의 관측 최대와 같다. 정의상 '최대 도달일' 과 같아지므로 독립적인 정의라기보다 관측의 재표현이다.
5. **기간 q 의 의미**: q20 과 q60 은 같은 날짜를 거의 공유하지 않는다 (k=6 에서 0일). 어느 하나를 고르는 문제가 아니라 '충격 시점' 과 '충격 후 누적' 중 무엇을 라벨로 삼을지의 문제다.
"""),
        # ── 20 ──
        md(r"""
## 20. 발표용 최종 요약 (교수·연구팀 브리핑)

### ① 문제 정의
기존 정의(17개 노출 그룹 모두 A∩B, 20∨60일)에서는 2021–2025 주분석 1,225일 동안 유효한 급변 구간이 **0개**였다 (`VALID_ZERO_INTERVALS`, 판정 유지).

### ② 원인
A(자기 과거 대비 고변동성)는 시장 공통 현상이고, B(Peer 대비 상대 괴리)는 개별 ETF 의 이탈이다. 시장 전체가 흔들리면 Peer 도 함께 흔들려 B 가 줄어든다. 그래서 두 상태가 17개 그룹에서 동시에 나타나지 않는다. A 만 보아도 동시 참여는 최대 12/17 (q20) · 6/17 (q60) 이다.

### ③ 연구 전환
시장 공통 고변동성 A 하나에 집중했다. "같은 날 A 인 그룹이 k 개 이상" 인 날을 후보로 두고, q ∈ {20, 60} × k ∈ {3, 6, 9, 10, 12, 17} 격자를 비교했다. B·AB 는 사후 설명으로만 썼다. **09번 결과를 본 뒤 설계한 사후 탐색**이다.

### ④ 정의별 실제 결과 (2021–2025)
| 후보 | 규칙 | 구간 | 후보일 | 실제 구간 |
|---|---|---|---|---|
| C1 | q20, ≥9/17 | 3 | 39 | 2022-10-11~12 · 2024-08-05~09-02 · 2025-04-10~05-07 |
| C2 | q20, ≥10/17 | 5 | 28 | 2024-08 3조각 · 2025-04-10~04-28 · 2025-05-07 |
| C3 | q20, ≥12/17 | 1 | 9 | 2025-04-11~04-23 |
| C4 | q60, ≥6/17 | 3 | 14 | 2022-11-21~22 · 2022-11-24~29 · 2024-10-24~11-04 |

### ⑤ 비교평가
- C1 은 **충격 시점의 과반 동시 고변동성**을 잡는다. 세 사례를 모두 포함하고 사건당 구간 하나로 나온다.
- C2 는 더 넓은 동시성을 요구한다. 2022 를 잃고 2024-08 을 세 조각으로 나눈다.
- C3 는 2025-04 다자산 급변 하나만 남기는 **극단 표지**다.
- C4 는 **충격 뒤 누적된 중기 고변동성**이다. q20 후보와 날짜가 겹치지 않는다.

### ⑥ 최종 의사결정 (승인 전 — 제안만)
- **제안 A (주 후보)**: C1 (q20, k=9). 비용: 2022 채권 국면이 2일로 축소된다. 주식 그룹 구성에 민감하다.
- **제안 B (보완층)**: C4 (q60, k=6) 를 별도 '중기 고변동성' 라벨로 병기한다. 비용: k 가 관측 최대라 칼날 위에 있고, 사후 선택 성격이 가장 강하다.
- **제안 C (극단 표지)**: C3 를 C1 내부의 '극단' 하위 표지로 쓴다. 비용: 사건 1개라 학습 표본으로는 부족하다.
- 어느 쪽이든 최종 정의는 **새 계약(lock)** 으로 고정한다. 그 뒤 2026 이후의 맹검 자료와 미래 수익률 꼬리 같은 독립 정답으로 평가해야 한다. 갭 병합(하루 미충족 연결) 여부도 그 계약에서 정한다.

### 한 문장 요약
> 2021–2025 에서 17개 노출 그룹의 공통 고변동성은 20일 기준 과반(≥9/17)으로는 2022-10·2024-08·2025-04 의 세 구간(39일)으로, 극단(≥12/17)으로는 2025-04 한 구간(9일)으로, 60일 기준(≥6/17)으로는 충격 뒤 2022-11·2024-10~11 의 누적 구간(14일)으로 나타나며, 17/17 동시 급변은 A 만으로도 관측되지 않았다.

### PPT 구성 초안 (6장)
1. **문제** — 17/17 A∩B = 0 구간. 원인은 A·B 의 엇갈림 (09 F27 · 10 G14).
2. **전환** — A 하나, 같은 날 참여 그룹 수 N_A. 17 그룹 상태 지도 (G01).
3. **k 와 q 의 효과** — 생존곡선·분할 (G03 · G08). k=7–9 평탄, 10 이상 급변. q20·q60 겹침 0.
4. **실제 구간** — C1–C4 간트와 표 (G05 · ④ 표).
5. **사례 3개** — 2022 채권 (G09) · 2024-08 국내 주식 (G10) · 2025-04 다자산 (G11).
6. **의사결정** — 제안 A·B·C 와 비용, 다음 단계: 새 lock, 2026 맹검, 독립 정답 (§19 표).
"""),
        # ── 21 ──
        md(r"""
## 21. 한계·검증·후속 연구 조건

**한계**
- 사후 탐색: 격자는 09번 결과를 본 뒤 정했다. C3·C4 의 k 는 관측 최대와 같다.
- 그룹 구성 편향: 17개 중 주식 계열이 다수다. '17개 중 k 개' 기준은 주식 충격에 유리하다. 그룹 가중이나 자산군별 쿼터는 이번 범위가 아니다.
- A 의 기준은 확장형 과거 분위다. 2026 처럼 이례적인 해 뒤에는 기준이 높아져 같은 σ 라도 A 가 덜 켜진다.
- 갭 병합을 하지 않는다. 하루 미충족으로 사건이 쪼개진다 (C2 2024-08 3조각, C4 2022-11 2조각).
- 외부 사건 이름은 맥락일 뿐이다. 이 데이터로 원인을 검증하지 않았다.
- 원문 지시서가 일부(PART VI 중간~PART XII 검증 1–9) 잘려 있었다. E2·E3 는 목차와 09 사건 창으로 재구성했다.

**검증 (이 노트북 또는 pytest `tests/unit/test_common_vol_10.py` 에서 assert)**
- 09 승계: 매니페스트 지문(예외 1건 명시), N_A·n_eval 전 행, 기간별 최대·17/17·NA.
- 같은 q 의 날짜 포함관계, 같은 날짜의 구간 중복 없음, 후보일 수 = 구간 지속일 합, 구간 최대 = 일별 원자료, 참여 그룹 명단 길이 = 집계 수 (ever + 없음 = 17) — `pipeline.check_intervals`.
- NA ≠ 0 (합성 테스트), 기간 분리(2020·2021–2025·2026), 연도 경계 연속 (합성 테스트 + 실제 2024-12→2025-01 구간), 주분석 끝 구간의 우측 검열 = 2026-01-02 상태 (pytest).
- C3·C4 날짜 집합 = 09 `max_participation_days` 의 최대 도달일 (교차 앵커).
- W4 17/17 AB 0개 유지, 09 노트북·W4 results 지문 작업 전후 동일.

**후속 연구 조건**
1. 교수·연구팀이 C1/C4/C3 조합 중 하나를 고르면 새 계약(lock)으로 고정한다 (갭 병합·그룹 가중 포함).
2. 평가는 라벨과 독립된 정답(예: 미래 수익률 꼬리)으로 사전 등록한다.
3. 2026 이후 맹검 자료로 확인한다.
"""),
        # ── 22 ──
        md("## 22. CLAIMS 및 재현성 검증"),
        code(r"""
# 해석 문단의 숫자를 결과 파일에서 다시 읽어 대조한다 (불일치면 실패).
def iv_str(c):  # 후보의 주분석 구간 문자열
    x = IVP[IVP["candidate"] == c]  # 해당 후보
    return "; ".join(f"{a}~{b}" for a, b in zip(x["start"], x["end"]))  # 시작~끝 목록


GBP = pd.read_csv(W4 / "results/global_by_period.csv")  # 09 기간별 요약
EVD = R["event_days"]  # 사례별 C1 후보일
PTc = R["participation"].set_index(["candidate", "group"])  # 참여 비율
BAB = R["b_ab"].set_index(["candidate", "side"])  # B·AB 안팎
HZ = R["horizon"].set_index("k")  # q 비교
JC = R["jaccard"].set_index(["rule_a", "rule_b"])  # 날짜 Jaccard
EV = R["events"].set_index(["event", "rule"])  # 사례 × 규칙
CLAIMS = [  # (주장, 관측, 기대)
    ("주분석 거래일", len(PRI), 1225),  # 주분석 2021–2025
    ("주분석 q20 NA", int((PRI["n_eval_A_q20"] < 17).sum()), 0),  # 전부 평가 가능
    ("q20 최대 N_A", int(PRI["n_A_q20"].max()), int(GBP[(GBP.period == "PRIMARY") & (GBP.q == 20)].max_n_A.iloc[0])),  # 09 와 같음
    ("q60 최대 N_A", int(PRI["n_A_q60"].max()), int(GBP[(GBP.period == "PRIMARY") & (GBP.q == 60)].max_n_A.iloc[0])),  # 09 와 같음
    ("q20 최대 N_A 값", int(PRI["n_A_q20"].max()), 12),  # 본문 12
    ("q60 최대 N_A 값", int(PRI["n_A_q60"].max()), 6),  # 본문 6
    ("파일럿 q20 17/17 일수 = 09", int(R["summary_pilot"].set_index("rule").loc["q20_k17", "candidate_days"]), int(GBP[(GBP.period == "PILOT") & (GBP.q == 20)].days17_A.iloc[0])),  # 09 재현
    ("파일럿 q20 17/17 값", int(R["summary_pilot"].set_index("rule").loc["q20_k17", "candidate_days"]), 16),  # 본문 16일
    ("파일럿 q60 04-07 진입 직전", set(IV[(IV.period == "PILOT") & (IV.q == 60) & (IV.start.astype(str) == "2020-04-07")]["entry_after"]), {"AFTER_NA"}),  # NA 직후 진입
    ("파일럿 q60 시작일", set(IV[(IV.period == "PILOT") & (IV.q == 60)].groupby("rule")["start"].min().astype(str)), {"2020-04-07"}),  # 모두 04-07
    ("2024-08-02·05 N_A", (int(D.loc[D["date"] == "2024-08-02", "n_A_q20"].iloc[0]), int(D.loc[D["date"] == "2024-08-05", "n_A_q20"].iloc[0])), (1, 9)),  # 1 → 9 도약
    ("q20 평균 N_A", round(float(PRI["n_A_q20"].mean()), 2), 1.75),  # 그림 G01 해석
    ("q60 평균 N_A", round(float(PRI["n_A_q60"].mean()), 2), 1.46),  # 그림 G01 해석
    ("k=7·8·9 일수", tuple(int((PRI["n_A_q20"] >= k).sum()) for k in (7, 8, 9)), (46, 41, 39)),  # 평탄
    ("k=10·11 일수", tuple(int((PRI["n_A_q20"] >= k).sum()) for k in (10, 11)), (28, 11)),  # 급감
    ("C1 구간", iv_str("C1"), "2022-10-11~2022-10-12; 2024-08-05~2024-09-02; 2025-04-10~2025-05-07"),  # §8 표
    ("C2 구간", iv_str("C2"), "2024-08-07~2024-08-07; 2024-08-12~2024-08-26; 2024-08-28~2024-08-30; 2025-04-10~2025-04-28; 2025-05-07~2025-05-07"),  # §8 표
    ("C3 구간", iv_str("C3"), "2025-04-11~2025-04-23"),  # §8 표
    ("C4 구간", iv_str("C4"), "2022-11-21~2022-11-22; 2022-11-24~2022-11-29; 2024-10-24~2024-11-04"),  # §8 표
    ("후보일 C1–C4", tuple(int(SMI.loc[r, "candidate_days"]) for r in ("q20_k9", "q20_k10", "q20_k12", "q60_k6")), (39, 28, 9, 14)),  # 본문 §9 대조
    ("구간 수 C1–C4", tuple(int(SMI.loc[r, "n_intervals"]) for r in ("q20_k9", "q20_k10", "q20_k12", "q60_k6")), (3, 5, 1, 3)),  # 본문 §9 대조
    ("1일 구간 C1·C2", (int(SMI.loc["q20_k9", "n_one_day"]), int(SMI.loc["q20_k10", "n_one_day"])), (0, 2)),  # 본문 §9 대조
    ("C1 지속 중앙값", float(SMI.loc["q20_k9", "duration_median"]), 17.0),  # 본문 §9 대조
    ("C4 지속 중앙·최장", (float(SMI.loc["q60_k6", "duration_median"]), int(SMI.loc["q60_k6", "duration_max"])), (4.0, 8)),  # 본문 §9 대조
    ("C1 안정성 Jaccard", round(float(SMI.loc["q20_k9", "mean_stability_jaccard"]), 2), 0.98),  # 본문 §9 대조
    ("후보 비율 C1·C2·C3·C4 %", tuple(round(100 * float(SMI.loc[r, "candidate_share"]), 1) for r in ("q20_k9", "q20_k10", "q20_k12", "q60_k6")), (3.2, 2.3, 0.7, 1.1)),  # 본문 §9 대조
    ("0개 규칙 gap", tuple(int(SMI.loc[r, "gap_k_minus_max"]) for r in ("q20_k17", "q60_k9", "q60_k10", "q60_k12", "q60_k17")), (5, 3, 4, 6, 11)),  # 본문 §9 대조
    ("주 후보 구간 수", len(MAIN_IV), 12),  # 본문 §8 대조
    ("주 후보 검열 구간", int(((MAIN_IV["left_censored"] != False) | (MAIN_IV["right_censored"] != False)).sum()), 0),  # 검열 없음  # noqa: E712
    ("주 후보 종료 사유", set(MAIN_IV["exit_reason"]), {"CONDITION_EXITED"}),  # 모두 0 으로 종료
    ("ever = 동시 최대", bool((MAIN_IV["n_groups_ever"] == MAIN_IV["max_n_A"]).all()), True),  # 본문 §8 대조
    ("C1 2025-04 매일·최대", tuple(MAIN_IV[(MAIN_IV.candidate == "C1") & (MAIN_IV.start.astype(str) == "2025-04-10")][["n_groups_always", "max_n_A"]].iloc[0]), (8, 12)),  # 본문 §9 대조
    ("C4 2022-11-23 N_A", int(D.loc[D["date"] == "2022-11-23", "n_A_q60"].iloc[0]), 5),  # 분할 원인
    ("k6→C1 소멸 구간", int(((KID.q == 20) & (KID.k_loose == 6) & (KID.relation == "소멸")).sum()), 6),  # 본문 §10 대조
    ("C1→C2 분할", tuple(KID[(KID.q == 20) & (KID.k_loose == 9)]["n_children"]), (0, 3, 2)),  # 본문 §10 대조
    ("C1–C2·C1–C3 Jaccard", (round(float(JC.loc[("q20_k9", "q20_k10"), "jaccard"]), 2), round(float(JC.loc[("q20_k9", "q20_k12"), "jaccard"]), 2)), (0.72, 0.23)),  # 본문 §10 대조
    ("2024-08 N_A 9 인 C1 날", tuple(str(x) for x in EVD[(EVD.event == "E2_2024_08") & ~EVD.in_C2].date), ("2024-08-05", "2024-08-06", "2024-08-08", "2024-08-09", "2024-08-27", "2024-09-02")),  # 본문 §10 대조
    ("2025-04 C2 제외 날", tuple(str(x) for x in EVD[(EVD.event == "E3_2025_04") & ~EVD.in_C2].date), ("2025-04-29", "2025-04-30", "2025-05-02")),  # 본문 §10 대조
    ("k=6 q 겹침", (int(HZ.loc[6, "q20_days"]), int(HZ.loc[6, "q60_days"]), int(HZ.loc[6, "both_days"])), (65, 14, 0)),  # 본문 §11 대조
    ("k=3 q Jaccard·접촉", (round(float(HZ.loc[3, "jaccard"]), 2), int(HZ.loc[3, "q20_intervals_touching_q60"]), int(HZ.loc[3, "q20_intervals"])), (0.17, 15, 30)),  # 본문 §11 대조
    ("E1 C1·C4 일수", (int(EV.loc[("E1_2022_bond", "q20_k9"), "candidate_days"]), int(EV.loc[("E1_2022_bond", "q60_k6"), "candidate_days"])), (2, 6)),  # 본문 §12 대조
    ("E1 W2 참고 일수·k6", (int(EV.loc[("E1_2022_bond", "q20_k9"), "w2_ref_days"]), int(EV.loc[("E1_2022_bond", "q20_k6"), "candidate_days"])), (62, 23)),  # 본문 §12 대조
    ("E2 q20 최대·날짜", (int(EV.loc[("E2_2024_08", "q20_k9"), "window_max_n_A"]), EV.loc[("E2_2024_08", "q20_k9"), "window_max_first_date"]), (10, "2024-08-07")),  # 본문 §13 대조
    ("E2 q60 최대·날짜", (int(EV.loc[("E2_2024_08", "q60_k6"), "window_max_n_A"]), EV.loc[("E2_2024_08", "q60_k6"), "window_max_first_date"]), (4, "2024-09-25")),  # 본문 §13 대조
    ("E2 k6 = C1", EV.loc[("E2_2024_08", "q20_k6"), "intervals"] == EV.loc[("E2_2024_08", "q20_k9"), "intervals"], True),  # 본문 §13 대조
    ("E3 q60 최대", int(EV.loc[("E3_2025_04", "q60_k6"), "window_max_n_A"]), 4),  # 본문 §14 대조
    ("C1 참여 반도체·2차전지·KOSPI200·나스닥·코스닥", tuple(round(float(PTc.loc[("C1", g), "share_on_candidate_days"]), 2) for g in ("091230", "305540", "KOSPI200_동일노출", "133690", "229200")), (1.0, 1.0, 0.95, 0.95, 0.92)),  # 본문 §15 대조
    ("C1 참여 채권", (round(float(PTc.loc[("C1", "148070"), "share_on_candidate_days"]), 2), round(float(PTc.loc[("C1", "153130"), "share_on_candidate_days"]), 2)), (0.05, 0.05)),  # 본문 §15 대조
    ("C1 N_B 안팎", (round(float(BAB.loc[("C1", "후보일"), "mean_n_B"]), 2), round(float(BAB.loc[("C1", "비후보일"), "mean_n_B"]), 2)), (2.18, 1.65)),  # 본문 §16 대조
    ("C3 N_B 안팎", (round(float(BAB.loc[("C3", "후보일"), "mean_n_B"]), 2), round(float(BAB.loc[("C3", "비후보일"), "mean_n_B"]), 2)), (1.0, 1.67)),  # 본문 §16 대조
    ("C1 N_AB 안팎", (round(float(BAB.loc[("C1", "후보일"), "mean_n_AB"]), 2), round(float(BAB.loc[("C1", "비후보일"), "mean_n_AB"]), 2)), (1.56, 0.16)),  # 본문 §16 대조
    ("2020 C1 일수", int(R["summary_pilot"].set_index("rule").loc["q20_k9", "candidate_days"]), 40),  # 본문 §17 대조
    ("2026 C1·C4 일수", tuple(int(R["summary_2026"].set_index("rule").loc[r, "candidate_days"]) for r in ("q20_k9", "q60_k6")), (110, 155)),  # 본문 §17 대조
    ("W3 겹침 후보 구간", tuple(R["w2w3"][R["w2w3"]["w3_joint_episode_overlap_n"] > 0]["interval_id"]), ("q20_k9_PRI_003", "q20_k10_PRI_004", "q20_k12_PRI_001")),  # 본문 §18 대조
    ("C1 구간 W2 겹침", bool((R["w2w3"][R["w2w3"].candidate == "C1"]["w2_overlap_n"] > 0).all()), True),  # 본문 §18 대조
    ("W4 판정 유지", VER["w4_verdict"], "VALID_ZERO_INTERVALS"),  # 09 판정
    ("그룹 범주: 주식·비주식", (int(EG.drop_duplicates("exposure_group")["category"].isin(["broad_market", "sector", "theme", "strategy", "leveraged_inverse"]).sum()), int(EG.drop_duplicates("exposure_group")["category"].isin(["rates", "money_market", "commodity", "currency"]).sum())), (12, 5)),  # 본문 §15 대조
    ("2026 주 후보 검열 구간", int(((IV.period == "PARTIAL_NON_BLIND") & IV.candidate.isin(["C1", "C2", "C3", "C4"]) & ((IV.left_censored != False) | (IV.right_censored != False))).sum()), 0),  # 그림 G16 각주 대조  # noqa: E712
]  # 끝
bad = {k: (o, x) for k, o, x in CLAIMS if o != x}  # 불일치 주장
print(f"CLAIMS {len(CLAIMS) - len(bad)}/{len(CLAIMS)} 일치")  # 결과
assert not bad, bad  # 불일치가 있으면 해석 문단을 고쳐야 한다
"""),
        code(r"""
# 09 노트북과 W4 results 가 이 노트북 실행 전후로 바이트 동일한지 확인한다 (원본 보호).
W4_AFTER = {p.name: sha(p) for p in sorted((W4 / "results").glob("*"))} | {"09_notebook": sha(ROOT / "notebooks/09_ETF20종_Peer상대변동성_급변구간정의.ipynb")}  # 종료 지문
assert W4_AFTER == W4_BEFORE, "09 산출물이 바뀌었습니다"  # 변경 금지
DIG = P.results_digest(ROOT)  # 10번 결과 파일 SHA256
(BASE / "results/figure_captions.json").write_text(json.dumps(CAP, ensure_ascii=False, indent=1, default=str, sort_keys=True) + "\n", encoding="utf-8")  # 캡션 수치 저장
print("09·W4 산출물 불변 ·", len(DIG), "개 결과 CSV ·", len(list(FIGDIR.glob("*.png"))), "PNG ·", len(list(FIGDIR.glob("*.svg"))), "SVG")  # 산출물 수
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
