# ruff: noqa: E501
"""12B 노트북 생성기 (12B-lock-1) — KODEX 200 CUSUM × 시장변수·연환산변동성 정렬 비교.

--write 로만 쓴다. 모든 코드 줄에 한국어 주석 (빠지면 멈춤, 12번 생성기와 같은 검사).
해석 문단의 숫자는 ``notebook_claims.json`` 의 (주장, 결과파일, 식, 기대값) 으로 마지막 셀이 다시 계산해 대조한다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "12B_KODEX200_CUSUM_시장변수_연환산변동성_정렬비교.ipynb"
BASE = ROOT / "research/k200_cusum_overlay_12b"
HANGUL = re.compile(r"[가-힣]")
CLOSERS = {")", "]", "}", "),", "],", "},", ")]", "})"}


def md(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    """주석이 빠진 코드 줄이 있으면 멈춘다."""
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


def fig(name: str) -> nbformat.NotebookNode:
    return code(f"""
display(Image(data=preview(FIGDIR / "{name}.png")))  # 저장된 PNG(320dpi)의 축소 미리보기
print(json.dumps(CAP.get("{name}", {{}}), ensure_ascii=False, default=str)[:700])  # 캡션 수치 (결과 파일에서 계산)
""")


def table(expr: str, note: str) -> nbformat.NotebookNode:
    return code(f"""
# {note}
display({expr})  # 표 출력
""")


SETUP = r"""
# 새 커널 첫 셀: BLAS 스레드를 NumPy 로드 전에 1로 고정해 결과를 결정적으로 만든다.
import os  # 환경변수 설정
import sys  # 인터프리터·모듈 경로 확인
from pathlib import Path  # 저장소 상대 경로

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):  # 네 BLAS 계열 변수
    os.environ[key] = "1"  # 다중 스레드 합산 순서에 따른 비트 차이를 막는다
assert "numpy" not in sys.modules, "새 커널에서 첫 셀부터 실행해야 합니다"  # 숨은 커널 상태 금지
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t22_k200_overlay_v1.json").is_file())  # 저장소 루트 탐색
sys.path.insert(0, str(ROOT / "src"))  # 이 작업트리의 r2h 패키지를 우선 사용

import contextlib  # 단계 출력 가두기
import hashlib  # 파일 지문
import importlib.metadata as metadata  # 설치 패키지 버전 조회
import importlib.util  # 단계 스크립트 불러오기
import io  # 출력 버퍼
import json  # 설정·캡션
import platform  # Python 버전
import time  # 단계 소요 시간

import matplotlib  # 그림 백엔드
matplotlib.use("Agg")  # 화면 없이 파일로 저장
import numpy as np  # 수치 배열
import pandas as pd  # 결과표
from IPython.display import Image, Markdown, display  # 표·그림·문단 출력
import matplotlib.pyplot as plt  # 그림 기본 설정
from matplotlib import font_manager  # 한글 글꼴 등록

FONT_FILE = Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf")  # 한글 도판용 나눔고딕
assert FONT_FILE.is_file(), "한글 도판 렌더링을 위한 나눔고딕 파일이 없습니다"  # 글꼴 없으면 중단
font_manager.fontManager.addfont(str(FONT_FILE))  # matplotlib 글꼴 목록에 등록
plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(FONT_FILE)).get_name()  # 한글 글꼴 사용
plt.rcParams["axes.unicode_minus"] = False  # 음수 기호 깨짐 방지

# 12번과 같은 고정 환경 (user-site 차단 포함).
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2", "scikit-learn": "1.9.1"}  # 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), **{k: metadata.version(k) for k in ("numpy", "pandas", "scipy", "matplotlib", "scikit-learn")}}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패
assert ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
pd.set_option("display.width", 220)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화
pd.set_option("display.max_rows", 60)  # 행 생략 완화

from r2h.k200_overlay import figures as G  # 12B 그림 (대표 쌍·라벨)

assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
BASE = ROOT / "research/k200_cusum_overlay_12b"  # 12B 산출물 폴더
RES = BASE / "results"  # 결과표
FIGDIR = BASE / "figures"  # 그림 (PNG 320dpi + SVG)
OUT = ROOT / "outputs/t22"  # 일별 장형 Parquet (Git 제외)


def sha(p):  # 파일 SHA256
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()  # 바이트 단위 지문


def preview(path, width=1100):  # 노트북 용량을 줄이는 축소 미리보기 (원본은 figures/)
    from PIL import Image as PILImage  # 이미지 축소
    im = PILImage.open(path)  # 320dpi 원본
    im.thumbnail((width, width * 3))  # 가로 1100px 이하로 축소
    buf = io.BytesIO()  # 출력 버퍼
    im.save(buf, format="PNG", optimize=True)  # PNG 로 다시 저장
    return buf.getvalue()  # 바이트 반환


# 계약 동결 지문: 국면·이벤트 정의는 계산 전에 커밋한 그대로여야 한다.
FREEZE = dict(reversed(line.split(maxsplit=1)) for line in (BASE / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines())  # 경로 → 해시
assert all(sha(ROOT / p) == h for p, h in FREEZE.items()), "12B-lock-1 계약 파일 변경"  # 동결본과 같아야 한다
# 12번 기준 커밋 c8998a6 의 추적 파일 915개 지문 — 실행 전후 모두 같아야 한다 (G0).
PROT = [line.split(maxsplit=1) for line in (BASE / "evidence/PROTECTED_12_SHA256.txt").read_text().splitlines()]  # (해시, 경로)
bad = [p for h, p in PROT if sha(ROOT / p) != h]  # 바뀐 보호 파일
assert not bad, f"보호 파일 변경: {bad[:5]}"  # 12번 산출물은 읽기만
INPUTS = [line.split(maxsplit=1) for line in (BASE / "evidence/INPUT_SHA256.txt").read_text().splitlines()]  # 동결 입력 (Feature Store·귀무표·원자료)
bad_in = [p for h, p in INPUTS if sha(ROOT / p) != h]  # 바뀐 입력
assert not bad_in, f"동결 입력 변경: {bad_in}"  # 12번 Feature Store 를 그대로 써야 한다
print("작업트리:", ROOT, "| 12번 보호", len(PROT), "개 · 입력", len(INPUTS), "개 불변 | 환경", ACTUAL_ENV)  # 검증 요약
"""

RUN = r"""
# 12B 계산 전부를 이 커널에서 다시 실행한다: 정렬 → 국면 → X1 → OFAT·합의 → 국면 반응 → 증분 정보 → 압축 → 그림.
# SVR 재학습·Monte Carlo 는 없다 (X1w 용 fit 0 표본내 잔차 1회 재계산만, model_hash 대조).
STAGES = ["run_t22_align", "run_t22_regimes", "run_t22_x1", "run_t22_compare", "run_t22_response", "run_t22_features", "t22_compress", "run_t22_figures"]  # 단계 순서
LOG = {}  # 단계별 소요·출력 끝부분
for name in STAGES:  # 단계마다
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")  # 스크립트 모듈 명세
    mod = importlib.util.module_from_spec(spec)  # 모듈 객체
    spec.loader.exec_module(mod)  # 불러오기 (main 은 아직 실행 안 함)
    buf, t0 = io.StringIO(), time.monotonic()  # 출력 버퍼·시작 시각
    with contextlib.redirect_stdout(buf):  # 긴 표 출력은 버퍼로
        rc = mod.main()  # 단계 실행
    assert rc == 0, f"{name} 실패: {buf.getvalue()[-2000:]}"  # 0 이 아니면 게이트 실패
    LOG[name] = (round(time.monotonic() - t0, 1), buf.getvalue().strip().splitlines()[-1][:160])  # 소요 초·마지막 줄
display(pd.DataFrame(LOG, index=["초", "마지막 출력"]).T)  # 단계 요약
CAP = json.loads((RES / "figure_captions.json").read_text(encoding="utf-8"))  # 그림 캡션 수치
T = {p.name: pd.read_csv(p) for p in sorted(RES.glob("*.csv*"))}  # 결과표 전부
print("결과표", len(T), "개 · 그림", len(CAP), "개")  # 산출물 수
"""

EXPLORER = r"""
# 탐색 인터페이스 (ipywidgets 가 R2H .venv 에 없어 함수 호출형, D-01). 같은 함수를 인자만 바꿔 다시 부르면 된다.
AL = pd.read_parquet(OUT / "policy_market_aligned.parquet")  # 681,999행 정렬 원장
MA = pd.read_parquet(OUT / "market_daily_master.parquet")  # 시장 마스터 1,473일
REG = pd.read_csv(ROOT / "research/k200_cusum_controlled_12/EXPERIMENT_REGISTRY.csv", keep_default_na=False, dtype=str)  # 등록부 464
META = AL.groupby("experiment_id")[["family", "detector_type", "window_w", "policy_id", "reset_rule", "parent_experiment_id"]].first()  # 실험 메타


def find(text="", detector=None, svr=None, rule=None, family=None):  # 실험 ID 검색·필터 (부분 문자열, 탐지기, SVR 정책, 변화점 규칙, 계열)
    m = META[META.index.str.contains(text, regex=False)]  # ID 부분 일치
    for col, val in (("detector_type", detector), ("policy_id", svr), ("family", family)):  # 정확 일치 필터
        if val is not None:  # 지정된 것만
            m = m[m[col] == val]  # 거르기
    if rule is not None:  # 변화점 규칙 (예: 'V20_two')
        m = m[m["reset_rule"].str.contains(rule, regex=False)]  # 초기화 규칙 부분 일치
    return m  # 메타 표


def show(ids, year=None, scale="T_past_pct", anchor=20, width=13):  # 여러 정책을 시장 위에 중첩 (scale: cusum_raw_T · T_past_pct · T_posthoc_pct · T_over_h)
    ids = [ids] if isinstance(ids, str) else list(ids)  # 단일 ID 허용
    assert len(ids) <= 8, "한 화면에 8개까지 (명세 §7)"  # 과밀 방지
    d = MA["date"]  # 날짜축
    sel = (d.dt.year == year) if year else np.ones(len(d), bool)  # 연도 뷰
    fig, ax = plt.subplots(3, 1, figsize=(width, 7.5), sharex=True, gridspec_kw={"height_ratios": [0.8, 0.8, 1.6]})  # 가격·변동성·CUSUM
    ax[0].plot(d[sel], MA["indexed_close"][sel], color="k", lw=1)  # 가격지수
    ax[0].set_ylabel("가격지수")  # 축 이름
    ax[1].plot(d[sel], MA[f"annualized_vol_{anchor}"][sel], color="#eb6834", lw=1)  # 선택한 연환산 앵커
    ax[1].set_ylabel(f"연환산 {anchor}일")  # 축 이름
    for k, eid in enumerate(ids):  # 정책마다
        s = AL[AL["experiment_id"] == eid].set_index("date").reindex(d)[scale].to_numpy(float)  # 원장 값 그대로
        ax[2].plot(d[sel], s[sel], lw=1, label=f"{eid} (NA {int(np.isnan(s[sel]).sum())}일)")  # 결측은 선이 끊긴다
    ax[2].set_ylabel(scale)  # 척도 이름
    ax[2].legend(fontsize=8, frameon=False)  # 범례
    buf = io.BytesIO()  # 그림 버퍼
    fig.savefig(buf, format="png", dpi=90, bbox_inches="tight")  # 작은 해상도로
    plt.close(fig)  # 메모리 해제
    display(Image(data=buf.getvalue()))  # 표시


def show_pair(child, parent=None, year=None, anchor=20):  # 부모–자식 자동 선택 중첩 (부모 생략 시 등록부 부모)
    parent = parent or META.loc[child, "parent_experiment_id"]  # 등록부 부모
    same = META.loc[child, "detector_type"] == META.loc[parent, "detector_type"]  # 같은 공식인지
    scale = "cusum_raw_T" if same else "T_past_pct"  # 공식이 다르면 원시 비교 금지
    print(f"부모 {parent} → 자식 {child} · 척도 {scale} · 바뀐 것 {REG.set_index('experiment_id').loc[child, 'changed_variable']}")  # 쌍 요약
    show([parent, child], year=year, scale=scale, anchor=anchor)  # 같은 함수로 그림


find(rule="V20_two").head(8)  # 예: 주 변화점 규칙을 쓰는 실험
"""


def claims() -> list[dict]:
    """해석 문단의 수치 (결과 파일 · 질의식 · 기대값)."""
    C = []

    def add(claim, file, expr, expected, rnd=3):
        C.append({"claim": claim, "file": file, "expr": expr, "expected": expected, "round": rnd})

    a = "policy_market_alignment_audit.csv"
    add("정렬 행 수", a, "int(df.loc[df.check=='aligned_rows','value'].iloc[0])", 681999, 0)
    add("일별 실험 수", a, "int(df.loc[df.check=='daily_experiments','value'].iloc[0])", 463, 0)
    add("정렬 감사 전부 통과", a, "int(df['pass'].astype(str).eq('True').all())", 1, 0)
    add("rv252 결측 일수", a, "int(float(df.loc[df.check=='rv252_na_days','value'].iloc[0]))", 6, 0)
    m = "market_daily_summary.csv"
    add("2020 연환산 20일 최대", m, "df.loc[df.calendar_year==2020,'ann_vol20_max'].iloc[0]", 72.68, 2)
    add("2020 실현 연변동성", m, "df.loc[df.calendar_year==2020,'realized_ann_vol_year'].iloc[0]", 29.4, 1)
    add("2020 SVR 예측 연환산 평균", m, "df.loc[df.calendar_year==2020,'pred_ann_vol_B1_mean'].iloc[0]", 16.05, 2)
    x = "x1_alarm_days.csv"
    add("X1 상방 경보일", x, "int((df.series=='X1_up_alarm_a05').sum())", 0, 0)
    add("X1 하방 경보일", x, "int((df.series=='X1_down_alarm_a05').sum())", 4, 0)
    add("X1 양방향 경보일", x, "int((df.series=='X1_two_alarm_a05').sum())", 3, 0)
    add("원래 Page 상방 경보일", x, "int((df.series=='E3_up_alarm_a05').sum())", 2, 0)
    add("X1w 상방 첫 경보", x, "str(df.loc[df.series=='X1w_up_alarm_a05_REFERENCE','date'].min())", "2020-03-18", 0)
    add("Page 상방 첫 경보", x, "str(df.loc[df.series=='E3_up_alarm_a05','date'].min())", "2020-03-23", 0)
    add("X1 하방 마지막 경보", x, "str(df.loc[df.series=='X1_down_alarm_a05','date'].max())", "2021-07-01", 0)
    e = "x1_event_table.csv"
    add("2021–2025 사건 X1 상방 최대 비율", e, "df[(df.event_set=='A_t20')&(df.period=='PRIMARY')]['X1_up_path_max_over_h'].max()", 0.46, 2)
    add("2025-11 사건 Page 상방 자유상태 비율", e, "df.loc[df.interval_id=='069500_q20_011','E3_up_free_max_over_h'].iloc[0]", 1.56, 2)
    add("2025-11 사건 Page 상방 경보경로 비율", e, "df.loc[df.interval_id=='069500_q20_011','E3_up_path_max_over_h'].iloc[0]", 0.39, 2)
    xd = "x1_real_daily.csv"
    add("X1 첫 유효일", xd, "str(df.loc[df.m_hat_X1.notna(),'date'].min())[:10]", "2020-09-21", 0)
    add("2024-08-05 v̂", xd, "df.loc[df.date.astype(str).str.startswith('2024-08-05'),'predicted_variance_B1'].iloc[0]", 5.01, 2)
    add("2024-08-05 e", xd, "df.loc[df.date.astype(str).str.startswith('2024-08-05'),'e_B1'].iloc[0]", -4.3, 2)
    add("2020 평균 m̂ X1w", xd, "df.loc[df.date.astype(str).str.startswith('2020'),'m_hat_X1w'].mean()", 2.59, 2)
    s = "svr_forecast_ceiling_summary.csv"
    add("B1 예측 상한 값", s, "df.loc[(df.policy_id=='B1')&(df.model_fit_id==0),'ceiling_value'].iloc[0]", 1.127, 3)
    add("B1 예측 상한 일수", s, "int(df.loc[(df.policy_id=='B1'),'days'].sum())", 32, 0)
    add("B1 예측 상한 마지막 날", s, "str(df.loc[(df.policy_id=='B1'),'last'].max())", "2020-08-21", 0)
    add("2024-08 상한 정책 수", s, "int(df[df['first'].astype(str).str.startswith('2024-08')].policy_id.nunique())", 4, 0)
    v = "annualized_volatility_response.csv"
    add("원수익률 CoS 확대−안정", v, "df.set_index('experiment_id').loc['E3_raw_rolling_cos','contrast_EXPANDING_minus_STABLE']", 0.27, 2)
    add("B1 확대−안정", v, "df.set_index('experiment_id').loc['B1','contrast_EXPANDING_minus_STABLE']", 0.194, 3)
    add("B1 감소−안정", v, "df.set_index('experiment_id').loc['B1','contrast_CONTRACTING_minus_STABLE']", 0.13, 2)
    add("Page 상방 높은 수준 유지 대비", v, "df.set_index('experiment_id').loc['E3_page_up','contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE']", 0.254, 3)
    add("B1 높은 수준 유지 대비", v, "df.set_index('experiment_id').loc['B1','contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE']", 0.001, 3)
    add("Page 상방 ρ(수준)", v, "df.set_index('experiment_id').loc['E3_page_up','rho_vol20']", 0.578, 3)
    add("X1 상방 ρ(수준)", v, "df.set_index('experiment_id').loc['X1_page_up_sn','rho_vol20']", 0.262, 3)
    add("X1 하방 ρ(수준)", v, "df.set_index('experiment_id').loc['X1_page_down_sn','rho_vol20']", -0.376, 3)
    add("Page 하방 ρ(d5)", v, "df.set_index('experiment_id').loc['E3_page_down','rho_d5']", -0.259, 3)
    add("2020 제외 시 수준 ρ 부호 변경 수", v, "int((np.sign(df.rho_vol20)*np.sign(df.rho_vol20_ex2020)<0).sum())", 0, 0)
    ll = "lead_lag_peak.csv"
    add("Page 상방 ρ0", ll, "df.set_index('experiment_id').loc['E3_page_up','rho_lag0']", 0.444, 3)
    add("Page 하방 ρ0", ll, "df.set_index('experiment_id').loc['E3_page_down','rho_lag0']", -0.455, 3)
    add("X1 하방 ρ0", ll, "df.set_index('experiment_id').loc['X1_page_down_sn','rho_lag0']", -0.453, 3)
    add("B1 최대 시차", ll, "df.set_index('experiment_id').loc['B1','peak_lag']", -19.0, 0)
    o = "ofat_pair_comparison.csv"
    add("OFAT 비교 쌍", o, "len(df)", 462, 0)
    add("G4 엄격 불일치", o, "int((~df.ofat_consistent.astype(bool)).sum())", 5, 0)
    add("G4 구조 판정 불일치", o, "int((~df.ofat_consistent_structural.astype(bool)).sum())", 0, 0)
    add("w20 vs w60 ρ", o, "df.set_index('child').loc['E2_w20','raw_spearman']", 0.072, 3)
    add("w252 vs w60 ρ", o, "df.set_index('child').loc['E2_w252','raw_spearman']", 0.351, 3)
    add("w252 경보일", o, "df.set_index('child').loc['E2_w252','alarm_days_child']", 159, 0)
    add("w252 추가 NA", o, "df.set_index('child').loc['E2_w252','added_na_days']", 192, 0)
    add("변화점 초기화 ρ (B1)", o, "df.set_index('child').loc['E8_reset_only','raw_spearman']", 1.0, 3)
    add("변화점 초기화 추가 NA (B1)", o, "df.set_index('child').loc['E8_reset_only','added_na_days']", 204, 0)
    add("X1 상방 vs Page 상방 ρ", o, "df.set_index('child').loc['X1_page_up_sn','raw_spearman']", -0.247, 3)
    add("CoS 초기화 쌍 추가 NA 중앙값", o, "df[(df.changed_variable=='reset')&df.child.str.contains('rolling|^B0|E1_(?:half|two|three|every|annual)|E8_reset_only',regex=True)&~df.child.str.contains('page')].added_na_days.median()", 242.0, 0)
    c = "agreement_clusters.csv"
    add("값 군집 수", c, "int(df.value_cluster.nunique())", 73, 0)
    add("단일 군집 수", c, "int((df.groupby('value_cluster').size()==1).sum())", 29, 0)
    add("최대 군집 크기", c, "int(df.groupby('value_cluster').size().max())", 117, 0)
    add("B1 과 B0 같은 군집", c, "int(df.set_index('experiment_id').loc['B1','value_cluster']==df.set_index('experiment_id').loc['B0','value_cluster'])", 1, 0)
    f = "feature_incremental_information.csv"
    q = "df[(df.coverage_status=='OK')&(df.scale=='past_pct')&(~df.exclude_2020_train)]"
    add("Page 하방 계열 상대 MSE 개선 중앙값", f, f"{q}.query('detector_type==\"page_down\"').rel_mse_gain_pooled.median()", 0.035, 3)
    add("Page 하방 계열 개선 해 수 중앙값", f, f"{q}.query('detector_type==\"page_down\"').years_positive.median()", 4, 0)
    add("CoS 계열 상대 MSE 개선 중앙값", f, f"{q}.query('detector_type==\"rolling_cos\"').rel_mse_gain_pooled.median()", -0.017, 3)
    add("X1 양방향 상대 MSE 개선", f, f"{q}.set_index('experiment_id').loc['X1_page_two_sn','rel_mse_gain_pooled']", 0.081, 3)
    add("w252 상대 MSE 개선", f, f"{q}.set_index('experiment_id').loc['E2_w252','rel_mse_gain_pooled']", 0.039, 3)
    add("B1 상대 MSE 개선", f, f"{q}.set_index('experiment_id').loc['B1','rel_mse_gain_pooled']", -0.016, 3)
    add("Page 하방 2020 학습 제외", f, "df[(df.coverage_status=='OK')&(df.scale=='past_pct')&(df.exclude_2020_train)].set_index('experiment_id').loc['E3_page_down','rel_mse_gain_pooled']", 0.042, 3)
    cd = "feature_incremental_information_common_days.csv"
    add("공통 유효일", cd, "int(df.n_common.iloc[0])", 846, 0)
    add("공통일 Page 하방 개선 해 수", cd, "int(df[(df.feature=='E3_page_down')&(~df.exclude_2020_train)].years_positive.iloc[0])", 5, 0)
    add("공통일 Page 상방 개선", cd, "df[(df.feature=='E3_page_up')&(~df.exclude_2020_train)].rel_mse_gain_pooled.iloc[0]", -0.086, 3)
    rg = "volatility_regime_summary.csv"
    add("앵커20 EXTREME 일수", rg, "int(df[(df.anchor_w==20)&(df.level_past=='EXTREME')].days.sum())", 168, 0)
    add("앵커20 EXPANDING 일수", rg, "int(df[(df.anchor_w==20)&(df.change_past=='EXPANDING')].days.sum())", 297, 0)
    ev = "events_table.csv"
    add("이벤트 B 수", ev, "int((df.event_set=='B_onset').sum())", 6, 0)
    return C


def book() -> nbformat.NotebookNode:
    cells = [
        md("""
# 12B — KODEX 200 CUSUM × 시장변수·연환산변동성 정렬 비교

**R2H 12B (experiments.md T22)** · 계약 `12B-lock-1` (국면·이벤트·선행후행·합의·증분 정보 정의를 계산 전에 커밋) · 기준 12번 `c8998a6` (12-lock-2 동결)

12번에서 돌린 464개 통제실험 가운데 날짜별 온라인 시계열 463개(681,999행)를 KODEX 200 의 종가·수익률·연환산변동성과
**같은 날짜축**에 전수 결합하고, 한 변수씩 바꾼 부모–자식 쌍을 시장 경로 위에 겹쳐 본다. 사용자 요청에 따라 **X1 자기정규화 Page 를 실데이터 위에서**
원래 Page 와 나란히 해부한다. 경보 정책 하나를 고르는 연구가 아니다.

> 모든 관측 결과는 **서술**이다. 12번에서 N1 귀무가 관측 잔차에 부적합(`NULL_MODEL_INVALID`)으로 판정되어, h·경보·p값은 보정 참조선일 뿐 확증 결과가 아니다.

### 결론 요약 (숫자는 맨 끝 CLAIMS 셀이 결과 파일과 대조)

| 질문 | 답 |
|---|---|
| X1 은 실데이터에서? | 평가 구간 잔차만 쓰면 **2020-09-21 부터** 값이 있어 COVID 를 못 본다. 2021–2025 사건에서 상방 경보 0회 (사건 중 최대 상태/h 0.46). 하방은 COVID 뒤 정상화기(2020-12 ~ 2021-07)에 4회. 2019 표본내 잔차로 시작한 X1w(탐색)는 2020-03-18 에 경보 — 원래 Page 상방(03-23)보다 3거래일 빠르다 |
| 왜 2024-08 −9.63% 에도 X1 이 안 울렸나 | 그 날 SVR 예측분산 v^ 가 이미 5.01 이라 잔차 e = −4.30 에 그쳤다. CUSUM 은 원수익률이 아니라 SVR 이 놓친 몫만 본다 |
| 새 발견 | **SVR 예측 상한 고정**: B1 의 v^ 가 2020-02-25 ~ 08-21 의 32일 동안 1.127 에 묶였다 (실현 연변동성 29.4% vs 예측 평균 16.05%). 10개 SVR 정책 모두 상한일이 있고 2024-08 에도 4개 정책. 2020 경보 집중은 이 상한의 결과다 |
| 급증에 반응 | 원수익률 CoS(확대−안정 +0.27) · SVR 잔차 CoS(+0.19) · Page 상방. 같은 날 반응(시차 0)은 Page·X1 이 가장 강하다 |
| 높은 수준 유지에 반응 | Page 상방(+0.25, 수준 ρ 0.58) — 그러나 이것은 잔차 척도 > 1 에서 상태가 표류하는 효과가 섞인 것이다. X1 은 표류를 지워 ρ 0.26. CoS 는 수준에 무반응(+0.001) |
| 감소에 반응 | CoS(감소−안정 +0.13) · Page 하방(ρ(d5) −0.26) · X1 하방 |
| 창 길이 | 창만 바꿔도 다른 신호: w20 과 w60 의 공통일 ρ 0.07, w252 는 0.35 · 경보 159일(2021 이월) · NA 192일 추가 |
| 변화점 초기화 | CoS 에서는 **관측 공백 추가**(추가 NA 중앙값 242일, 공통일 ρ ≈ 1). Page 에서는 상태를 잘라 값을 바꾼다 |
| 2020 제외 | 수준 상관 부호가 바뀐 정책 0개 (단, 과거 전용 척도는 2020 대부분이 NA 라 약한 근거) |
| 중복성 | 값 군집 73개 · 단일 29개. 최대 군집 117개(B1·B0·변화점 초기화 CoS 대부분)는 사실상 한 신호 |
| AE 인계 | 연속형: CoS w20·w60·w120·w252 (각 1개), 원수익률 CoS, Page 하방, X1 하방·양방향(검증 후), 예측분산 + 예측 상한 표시. Page 하방 계열은 미래 20일 변동성 예측 MSE 를 3.5% 줄였다 (5개 시험연도 중 4개, 공통일 비교에서는 5개) |
"""),
        code(SETUP),
        md("## 1. 12B 계산 재실행 (새 커널, 단계별 게이트)"),
        code(RUN),
        md("""
## 2. 데이터 정렬 감사 — G1 날짜 · G2 전수 · G3 시장변수 · G7 결측

기준 날짜축 1,473일에 463개 일별 정책을 `date` m:1 · `experiment_id` m:1 로 결합했다. 사후 전체기간 CUSUM(`E3_posthoc_full`)은 날짜별 시계열이 아니므로
결합하지 않고 등록부 행으로 남긴다. 12번 Feature Store 의 rv5–rv120 은 다시 계산한 값과 **오차 0** 으로 같다 (`ddof=1`, 2019-01-03 부터의 전체 수익률로 계산 후 절단).
연환산 = √252 × 일 SD (%/년). rv252 는 2019 수익률이 245개뿐이라 2020 첫 6일이 NA 다.
"""),
        table("T['policy_market_alignment_audit.csv']", "정렬 감사표 (게이트 · 검사 · 값 · 기대 · 통과)"),
        table("T['market_daily_summary.csv'].round(2)", "연도별 시장 요약: 누적 로그수익률 · 연환산 변동성 · SVR 예측 연환산"),
        md("""
## 3. X1 자기정규화 Page — 실데이터 해부 (사용자 요청)

**재적합은 필요 없다.** X1 은 12번이 저장한 B1 잔차 e = r/√v^ 에서 ẽ_t = e_t / √m^_t (m^_t = [t−252, t−61] 평균 e², 유효 120일 이상) 로 계산된다.
노트북은 원장의 X1·Page 상태와 경보를 이 식으로 다시 만들어 14/14 항목이 비트 단위로 같음을 확인했다 (`evidence/x1_checks.json`).

- **2020 이 빈다.** 평가 구간 잔차만 쓰면 유효 120일이 2020-09-21 에야 찬다. 그래서 X1 은 COVID 를 보지 못한다.
- **X1w (12B 탐색 확장)**: 같은 식에 2019 fit 0 의 표본내 표준화 잔차를 기준창으로 허용 (2020-01-02 시점에 이미 알려진 정보, model_hash `92a29bcd08ac7f81` 대조). 보정된 h 가 없어 X1 의 h 를 참조선으로만 쓴다.
  X1w 상방은 2020-03-18 에 처음 h 를 넘는다 — 원래 Page 상방(2020-03-23)보다 3거래일 빠르다. 2021-07-28 부터는 X1 과 같다.
- **2021–2025 상방 0회.** 사건 구간 중 X1 상방 상태/h 최대는 0.46 (2024-08). 원래 Page 상방의 **자유 상태**는 2025-11 사건에서 1.56 이지만 **경보 경로**는 0.39 — 자유 상태가 h 를 넘는 것은 2020 누적이 남은 표류다.
- **하방 4회 (2020-12-03 ~ 2021-07-01).** COVID 기간 e² 가 기준창 m^ 에 남아(2020 평균 m^ X1w 2.59) 정상화기의 잔차가 상대적으로 작아 보인 결과다. 실제 분산 감소이지만 "기준창이 과거 충격을 기억하는 동안" 의 감소다.
"""),
        fig("G02_X1_자기정규화Page_실데이터"),
        fig("G03_X1_사건확대"),
        table("T['x1_event_table.csv'][['interval_id','shock_type','period','E3_up_free_max_over_h','E3_up_path_max_over_h','X1_up_path_max_over_h','X1w_up_path_max_over_h','E3_down_path_max_over_h','X1_down_path_max_over_h','E3_up_first_alarm_a05','X1w_up_first_alarm_a05','X1_valid_share']].round(2)", "사건별 [시작, 끝+20] 상태/h 최대 — 자유 상태(free)와 경보 경로(path) 분리"),
        table("T['x1_alarm_days.csv'].groupby('series').date.agg(['count','min','max'])", "α=0.05·0.20 경보일 (X1w 는 REFERENCE)"),
        md("""
## 4. 발견 — SVR 예측 상한 고정 (12번에 없던 진단)

같은 적합 안에서 예측분산이 소수점 9자리까지 같은 값으로 5일 이상 반복되는 날을 표시했다. B1 은 2020-02-25 부터 **1.127** 에 32일 묶였다.
그동안 관측 rv20² 는 2 에서 20 까지 올랐다. 입력(지연 r²·대용치)이 2019 학습 범위를 벗어나 RBF 커널 기여가 사라졌다는 해석과 맞는다 (가설).
이 기간 잔차는 원수익률 / 1.06 에 가깝고, 12번의 "경보 43일이 모두 2020" 은 이 상한과 겹친다. 2024-08-06 ~ 12 에도 학습창 정책 4개(win252·504·756·adaptive)에 상한이 나타난다.
"""),
        fig("G04_SVR_예측상한고정"),
        table("T['svr_forecast_ceiling_summary.csv'].round(3)", "정책·적합별 예측 상한 고정 구간"),
        md("""
## 5. 그림 A — 6년 시장–CUSUM 정렬 지도와 연도별 뷰

가격·수익률·연환산(20·60·120일)·SVR 예측 연환산을 같은 x축에 두고, 대표 12개 정책의 **과거 전용 백분위**(t 이전 252일 자기 분포 안 위치, 0–1)를 띠로 쌓았다.
회색은 통계량이 없는 날(NA)이다. 아래 띠는 변화점 트리거·연초 초기화·재학습·예측 상한, 맨 아래는 과거 전용 연환산 국면.
같은 날 여러 띠가 함께 높아지는지(같은 신호)와 서로 다른 날 높아지는지(다른 시간 규모)를 비교한다.
"""),
        fig("G01_6년_시장_CUSUM_정렬지도"),
        fig("G06_연도별_시장_CUSUM"),
        md("""
## 6. 그림 B — 부모–자식 OFAT 중첩 (11쌍)

각 쌍은 한 변수만 바꿨다 (E8 초기화 → 초기화+재학습은 등록부 밖에서 만든 유도 쌍). 공식이 같으면 원시 T, 다르면 과거 백분위로만 비교한다.
패널: 가격 · 수익률 · 연환산 20·60일 · 부모/자식 중첩 · 차이 · 유효 상태(부모만/자식만/둘 다 NA)와 초기화·재학습 위치.
G4: 등록부 462쌍 중 엄격 판정 불일치 5쌍은 모두 탐지기 변경에 따라 창 길이·SVR 정책이 '해당 없음(NA)' 으로 바뀐 경우다 (구조 판정 불일치 0).
"""),
        *[fig(f"G05_{i:02d}_부모자식_{p}_vs_{c}") for i, (p, c, _) in enumerate(__import__("r2h.k200_overlay.figures", fromlist=["PAIRS"]).PAIRS, start=1)],
        table("T['ofat_pair_comparison.csv'].set_index('child').loc[['B0','E2_w20','E2_w120','E2_w252','E8_reset_only','E6_win252','E7_refit21','X1_page_up_sn','X1_page_down_sn','E3_raw_rolling_cos'],['parent','changed_variable','common_valid_days','parent_only_days','child_only_days','raw_comparable','raw_spearman','pct_diff_median','pct_diff_mean_expanding','pct_diff_mean_contracting','alarm_days_parent','alarm_days_child','added_na_days']].round(3)", "대표 쌍 지표 — 공통·단독 유효일 · ρ · 국면별 백분위 차 · 경보일"),
        table("T['ofat_pair_comparison.csv'].query('~ofat_consistent')[['parent','child','changed_variable','ofat_observed','ofat_extra_cols','ofat_consistent_structural']]", "G4 엄격 불일치 5쌍 (모두 NA 구조 변경)"),
        md("""
## 7. 창 길이 — 같은 시장 움직임, 다른 기억

창 길이만 바꿔도 공통일 순위 상관이 크게 떨어진다 (w20–w60 0.07, w120 0.38, w252 0.35). 큰 하루 충격은 창에 머무는 w 일 동안 통계량을 받치고,
**이탈일 d + w** 에 계단식으로 떨어진다. w252 는 2020-03 충격이 2021-03 말까지 남아 2021 경보 159일(12번 X-D7: COVID 이월 63 + 분산 감소 96)을 만든다.
장기 고변동 상태와 단일 충격의 창 잔존을 구별하려면 창 이탈일을 함께 넘겨야 한다.
"""),
        fig("G07_창이탈_효과"),
        md("""
## 8. CUSUM 공식 · 변화점 초기화 — 관측 공백인가 정보인가

이동 CoS 의 초기화 쌍은 공통 유효일에서 부모와 **같은 값**(ρ ≈ 1)이고 차이는 초기화 직후 w−1일의 NA 뿐이다 (추가 NA 중앙값 242일).
즉 CoS 에서 초기화는 정보를 더하지 않고 관측 공백을 더한다. Page 는 결측이 생기지 않는 대신 상태를 0 으로 잘라 값 자체를 바꾼다 (상방·양방향 ρ 중앙값 0.41·0.47, 하방 0.996).
12번 위약 비교에서도 변화점 초기화가 같은 횟수 무작위 초기화보다 나은 경우는 102개 규칙 중 9·8개였다.
"""),
        fig("G13_초기화_관측공백"),
        md("""
## 9. SVR 학습·재학습 정책 — 인위적 CUSUM 반응이 생기는 날

재학습 자체가 CUSUM 을 움직이는 날은 (1) 예측 상한 고정 구간 (2020-02-25 ~, 2024-08-06 ~ 12), (2) 재적합 경계 잔차 척도 단절 (12번 `refit_boundary_breaks.csv`, 아래 표),
(3) 12번 X-D6 유예 재학습 경계의 2021 초 경보(27·26일)다. 짧은 재학습(refit21)은 상한 고정 일수를 32 → 9 로 줄이지만 0 으로 만들지는 못한다.
"""),
        fig("G14_SVR정책_비교"),
        table("pd.read_csv(ROOT / 'research/k200_cusum_controlled_12/results/refit_boundary_breaks.csv').assign(abs_log2=lambda x: x.log2_ratio.abs()).sort_values('abs_log2', ascending=False).head(10).round(3)", "재적합 경계 전후 평균 e² 비 (|log2| 상위 10, 12번 결과)"),
        md("""
## 10. 연환산변동성 국면별 반응

국면은 계산 전에 고정한 과거 전용 정의다 (앵커 연환산 20일: 수준 4 × 변화 3). 칸 값은 과거 백분위 평균, 아래 숫자는 유효일. 유효일 20 미만 칸은 흐리게 두고 해석하지 않는다.
- **확대(EXPANDING)**: CoS 계열이 가장 크게 오른다 (원수익률 CoS +0.27, B1 +0.19). Page 상방도 오른다.
- **높은 수준 유지(HIGH·EXTREME × STABLE)**: Page 상방만 높다 (+0.25). CoS 는 수준에 무반응이다 (+0.001) — CoS 는 창 안의 *변화*를 재는 통계라서다.
  Page 상방의 수준 반응은 평균 e² > 2 ln2 ≈ 1.39 이면 증분이 양수로 쌓이는 표류가 섞인 것이다 (2024–2025 평균 e² 1.46·1.57). X1 상방은 이를 지워 수준 ρ 가 0.58 → 0.26 으로 준다.
- **감소(CONTRACTING)**: CoS(+0.13)와 Page 하방·X1 하방. X1 하방은 높은 수준 유지 국면에서 오히려 낮다 (−0.18).
"""),
        fig("G08_국면별_정책반응"),
        table("T['annualized_volatility_response.csv'].set_index('experiment_id').loc[['B1','E2_w20','E2_w120','E2_w252','E3_raw_rolling_cos','E3_page_up','E3_page_down','X1_page_up_sn','X1_page_down_sn','X1_page_two_sn','E7_refit21','E6_win252','B0','E8_reset_only'],['rho_vol20','rho_vol20_ex2020','rho_d5','rho_d20','contrast_EXPANDING_minus_STABLE','contrast_CONTRACTING_minus_STABLE','contrast_HIGHEXT_STABLE_minus_LOWMID_STABLE','n_vol20']].round(3)", "대표 정책의 연환산변동성 반응 (수준·변화율 상관, 국면 대비, 2020 제외)"),
        md("""
## 11. 변동성 변화 시작점 기준 이벤트 정렬 · 단일 충격형 vs 누적형

11번 급변 구간(CUSUM 과 독립 정의) 2021–2025 7개를 시작일에 맞춰 −60 ~ +120일을 겹쳤다. 사건이 누적형 4 · 단일 충격형 3 뿐이라 평균 곡선은 사건 하나에 좌우된다.
과거 전용 국면의 '확대 시작점'(이벤트 B) 6개는 11번 구간 시작일과 같은 날이었다 (같은 20일 변동성 기반 정의라서다). 누적형 − 단일 충격형 차이는 정책 중앙값 −0.18 로 단일 충격형에서 더 높다.
"""),
        fig("G09_사건정렬_반응"),
        fig("G15_단일vs누적_충격"),
        md("""
## 12. 정책별 선행·후행 반응

일 변화끼리의 시차 상관 (Δ 과거 백분위_{t+k} vs Δ ln 연환산20_t, k > 0 = 정책이 늦음). Page·X1 은 k = 0 에서 가장 강하다 (Page 상방 +0.44, Page 하방 −0.46, X1 하방 −0.45).
CoS w60 의 최대가 k = −19 (범위 끝)에 있는 것은 정책이 앞선다는 뜻이 아니다. 20일 앵커에서 20일 전 충격이 빠지는 날의 메아리다 (D-10). 계열 상관이 있어 추론하지 않는다.
"""),
        fig("G10_선행후행"),
        md("""
## 13. 전체 정책 히트맵 · 정책 간 중복성과 합의

463개 정책 × 1,473일을 값 군집 순으로 쌓았다 (과거 백분위, 회색 NA). 군집은 공통 유효일 원시 T 의 Spearman ρ ≥ 0.9 평균 연결이다.
- 값 군집 73개, 단일 29개. 최대 군집 117개는 모두 이동 CoS — B1·B0·변화점 초기화 CoS 대부분이 하나의 신호다 (군집 내 평균 ρ 0.994).
- 107개는 Page 하방, 그다음 3개 군집(24·23·22)은 Page 상방·양방향 초기화 변형이다.
- 독립 시간 규모: CoS w20(·X_w20_reset), w30, w120, w252, 원수익률 CoS, SVR 학습창·재학습 정책(win252, refit21 등), X1 3종이 각각 단일 군집이다.
- 결측 패턴은 따로 군집화했다 (49개). 결측만 다르고 값은 같은 정책을 "다른 정보" 로 세지 않기 위해서다.
"""),
        fig("G11_전체정책_히트맵"),
        fig("G12_정책합의_중복성"),
        table("T['agreement_cluster_summary.csv'].query('cluster_kind==\"value_spearman\"').head(12)", "값 군집 상위 12개 (크기 · 계열 구성 · 대표 · 군집 내 평균 ρ)"),
        md("""
## 14. Autoencoder 피처 가치 · 연도 안정성 (G9)

원시 변동성(연환산 5·20·60·120일)과 SVR 예측변동성을 기준으로 두고, 각 정책의 과거 백분위를 더했을 때 미래 20일 실현변동성(ln SD, 사후 목표)의
**표본외** 예측이 나아지는지 연도 제외 교차검증(시험 2021–2025, 20일 엠바고)으로 쟀다. 지표는 계약의 R² 차이와 보조 지표 상대 MSE 개선(D-08).
- Page 하방 계열: 중앙값 +3.5% (2020 학습 제외 시 +4.2%). 공통 유효일 846일 비교에서도 5개 시험연도 모두 개선.
- X1 양방향 +8.1%, X1 하방 +3.8%, CoS w252 +3.9%, w120 +2.4%.
- CoS w60 계열(117개 군집)은 중앙값 −1.7% — 원시 변동성에 이미 담긴 정보다. Page 상방은 공통일 비교에서 −8.6%.
- 목표가 겹치고 2021–2025 다섯 해뿐이라 서술 결과다.
"""),
        fig("G16_AE피처_증분정보"),
        fig("G17_연도별_안정성"),
        table("T['feature_incremental_information_common_days.csv'].query('~exclude_2020_train')[['feature','n_common','gain_pooled','rel_mse_gain_pooled','years_positive','gain_2021','gain_2022','gain_2023','gain_2024','gain_2025']].round(4)", "대표 후보 공통 유효일 비교 (연도별 R² 차이 포함)"),
        md("""
## 15. 탐색 인터페이스 — 모든 정책 검색·중첩

`find()` 로 실험 ID·탐지기·SVR 정책·변화점 규칙·계열을 거르고, `show(ids, year, scale, anchor)` 로 최대 8개를 시장 위에 겹치며, `show_pair(child)` 는 등록부 부모를 자동으로 붙인다.
척도는 원시(`cusum_raw_T`)·과거 백분위(`T_past_pct`)·사후 백분위(`T_posthoc_pct`, POSTHOC)·임계값 비율(`T_over_h`) 중 고른다. 연환산 앵커는 20·60·120.
브라우저 상호작용판: `research/k200_cusum_overlay_12b/interactive/12B_시장_CUSUM_탐색기.html` (그룹 5 × 척도 3 선택, 날짜 위에 커서를 두면 같은 날 값이 함께 보인다).
"""),
        code(EXPLORER),
        code("""
# 예시 1: 2021 연도 뷰에서 Page 상방과 X1 상방·하방 (자기정규화로 척도가 달라 과거 백분위로 비교)
show(["E3_page_up", "X1_page_up_sn", "X1_page_down_sn"], year=2021, scale="T_past_pct", anchor=20)  # 2021 정상화기
"""),
        code("""
# 예시 2: 자식만 지정하면 부모를 자동 선택 — w252 와 부모 w60 의 2024 년
show_pair("E2_w252", year=2024, anchor=60)  # 2024-08 충격의 창 잔존
"""),
        md("""
## 16. 연구 질문 10개에 대한 답

1. **연환산변동성 급증에 가장 강하게 반응하는 계열**: 이동 CoS (원수익률 CoS 확대−안정 +0.27, SVR 잔차 CoS w60 +0.19). 같은 날 반응은 Page 상방(ρ0 +0.44)·Page 하방(−0.46)이 가장 크다.
2. **높은 수준 유지에 반응**: Page 상방 계열 (+0.25, 수준 ρ 0.58) — 단, 잔차 척도 > 1 에서의 상태 표류가 섞였다. 척도를 바로잡은 X1 상방은 수준 ρ 0.26. CoS 는 반응하지 않는다.
3. **감소에 반응**: CoS (감소−안정 +0.13), Page 하방(ρ(d5) −0.26), X1 하방 (COVID 뒤 정상화기 경보 4회).
4. **창 길이만 바꾸면**: 같은 날의 순위가 달라진다 (w20–w60 ρ 0.07). 긴 창은 과거 충격을 이탈일까지 기억하고(w252 경보 159일·NA 192일 추가), 짧은 창은 하루 충격에 민감하다.
5. **변화점 초기화**: 이동 CoS 에서는 관측 공백 추가가 대부분이다 (공통일 ρ ≈ 1, 추가 NA 중앙값 242일). Page 에서는 상태를 잘라 값이 바뀐다. 위약보다 나은 경우는 우연 수준.
6. **SVR 재학습·학습창 때문에 생긴 인위적 반응**: 예측 상한 고정 2020-02-25 ~ 08-21 (B1 32일), 2024-08-06 ~ 12 (학습창 정책 4개), 재적합 경계 척도 단절(refit63 2020-04-02 log2 비 −3.0, B1 2022-01-03 +0.59), 12번 X-D6 2021 초 유예 경계.
7. **2020 제거**: 수준 상관 부호가 바뀐 정책 0개, 증분 정보도 비슷하다 (Page 하방 +3.5% → +4.2%). 다만 과거 전용 척도는 2020 대부분이 NA 라 근거가 약하다.
8. **원시 변동성으로 설명되지 않는 정보**: Page 하방(감소 쪽)과 X1 하방·양방향, 긴 창(w120·w252)의 이월 정보. w60 CoS·초기화 변형은 추가 정보가 없다.
9. **유사 정책군 / 독립 시간 규모**: 117개 CoS 군집(B1·B0·변화점 초기화), 107개 Page 하방 군집, Page 상방·양방향 군집들이 중복. w20·w30·w120·w252·원수익률 CoS·SVR 학습창·X1 이 독립 군집.
10. **AE 인계**: 연속형 — CoS w20·w60·w120·w252 (변형 중 하나씩), 원수익률 CoS w60, Page 하방 1개, X1 하방·양방향(2026 이후 자료로 검증한 뒤), SVR 예측분산과 **예측 상한 표시**, 창 이탈일·초기화 후 경과일(마스크). Page 상방 원시값은 표류 때문에 넘기지 않는다. 경보·p값은 넘기지 않는다.

## 17. 한계

- 관측 귀무 부적합 → 모든 경보는 서술. 사건 7개, 시험연도 5개.
- 과거 전용 척도는 유효 120일이 필요해 2020 이 대부분 비어 있다. 2020 은 원시 T 와 사후 백분위로만 볼 수 있다.
- X1w 는 보정된 h 가 없다. 예측 상한의 원인(RBF 포화)은 관측 패턴과 맞는 가설이다.
- 명세 §8–§15 본문 누락분은 12B-lock-1 로 사전 등록했다 (D-02).
"""),
        md("## 18. CLAIMS · 재현성 · 보호 확인"),
        code(r"""
# 해석 문단의 숫자를 결과 파일에서 다시 계산해 대조한다 (불일치면 실패).
CL = json.loads((BASE / "notebook_claims.json").read_text(encoding="utf-8"))  # (주장, 결과파일, 식, 기대값)
bad = {}  # 불일치 주장
for c in CL:  # 주장마다
    df = pd.read_csv(RES / c["file"])  # 근거 결과표
    got = eval(c["expr"], {"df": df, "np": np, "pd": pd})  # 결과표에서 다시 계산한 값
    got = round(float(got), c["round"]) if isinstance(got, (int, float, np.floating, np.integer, bool)) else got  # 반올림 규칙
    exp = round(float(c["expected"]), c["round"]) if isinstance(c["expected"], (int, float)) else c["expected"]  # 기대값
    if got != exp:  # 본문 수치와 다르면
        bad[c["claim"]] = (got, exp)  # 기록
print(f"CLAIMS {len(CL) - len(bad)}/{len(CL)} 일치")  # 결과
assert not bad, bad  # 불일치가 있으면 해석 문단을 고쳐야 한다
"""),
        code(r"""
# G6 그림–원장 일치 · 12번 보호 파일 · 동결 입력을 실행 뒤에 다시 확인한다.
g6 = pd.read_csv(BASE / "evidence/g6_figure_ledger_check.csv")  # 그림 배열 대조 기록 (그림 단계가 방금 다시 씀)
assert g6["equal"].all(), g6[~g6["equal"]]  # 모두 같아야 한다
bad = [p for h, p in PROT if sha(ROOT / p) != h]  # 바뀐 12번 파일
assert not bad, f"보호 파일 변경: {bad[:5]}"  # 변경 금지
bad_in = [p for h, p in INPUTS if sha(ROOT / p) != h]  # 바뀐 입력
assert not bad_in, bad_in  # 변경 금지
print("G6", len(g6), "항목 일치 · 12번 보호", len(PROT), "개 불변 · 결과", len(list(RES.glob('*.csv*'))), "개 · PNG", len(list(FIGDIR.glob('*.png'))), "· SVG", len(list(FIGDIR.glob('*.svg'))))  # 산출물 수
"""),
    ]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"display_name": "Python 3 (R2H .venv)", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    return nb


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="노트북 파일과 CLAIMS 를 실제로 쓴다 (출력 비움)")
    a = ap.parse_args()
    nb = book()
    cl = claims()
    if a.write:
        nbformat.write(nb, NB)
        (BASE / "notebook_claims.json").write_text(json.dumps(cl, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("작성:", NB, "· CLAIMS", len(cl))
    else:
        print("검사만 (셀", len(nb.cells), "개, CLAIMS", len(cl), "개). --write 로 쓴다")


if __name__ == "__main__":
    main()
