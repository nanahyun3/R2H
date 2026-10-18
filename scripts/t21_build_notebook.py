# ruff: noqa: E501
"""12번 노트북 생성기 (12-lock-2) — KODEX 200 CUSUM 연속성 · 변화점 · SVR 통제실험.

--write 로만 쓴다. 모든 코드 줄에 한국어 주석 (빠지면 멈춤). 해석 문단은 ``notebook_interpretation.json`` 에서,
해석 수치 대조(CLAIMS)는 ``notebook_claims.json`` 의 (주장, 결과파일, 질의식, 기대값) 으로 마지막 셀이 검사한다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "12_KODEX200_CUSUM_연속성_변화점_SVR통제실험.ipynb"
BASE = ROOT / "research/k200_cusum_controlled_12"
HANGUL = re.compile(r"[가-힣]")
CLOSERS = {")", "]", "}", "),", "],", "},", ")]", "})"}


def md(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    """주석이 빠진 코드 줄이 있으면 멈춘다 (t20 생성기와 같은 검사)."""
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
print(json.dumps(CAP.get("{name}", {{}}), ensure_ascii=False, default=str)[:600])  # 캡션 수치 (결과 파일에서 계산)
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
ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "configs/t21_k200_cusum_controlled_v1.json").is_file())  # 저장소 루트 탐색
sys.path.insert(0, str(ROOT / "src"))  # 이 작업트리의 r2h 패키지를 우선 사용

import hashlib  # 파일 지문
import importlib.metadata as metadata  # 설치 패키지 버전 조회
import json  # 설정·캡션
import platform  # Python 버전

import matplotlib  # 그림 백엔드
matplotlib.use("Agg")  # 화면 없이 파일로 저장
import numpy as np  # 수치 배열
import pandas as pd  # 결과표
from IPython.display import Image, Markdown, display  # 표·그림·문단 출력

# 11번과 같은 고정 환경이어야 한다 (user-site 차단 포함).
EXPECTED_ENV = {"python": "3.12.3", "numpy": "2.5.4", "pandas": "3.0.6", "scipy": "1.18.1", "matplotlib": "3.11.2", "scikit-learn": "1.9.1"}  # 고정 환경
ACTUAL_ENV = {"python": platform.python_version(), **{k: metadata.version(k) for k in ("numpy", "pandas", "scipy", "matplotlib", "scikit-learn")}}  # 실제 커널
assert ACTUAL_ENV == EXPECTED_ENV, f"실행 환경 불일치: {ACTUAL_ENV}"  # 버전 불일치는 재현 실패
assert ".local" not in np.__file__, np.__file__  # user-site 패키지 차단
pd.set_option("display.width", 220)  # 표 줄바꿈 완화
pd.set_option("display.max_columns", 40)  # 열 생략 완화
pd.set_option("display.max_rows", 80)  # 행 생략 완화

from r2h.k200_controlled import figures as F  # 12번 그림
from r2h.k200_controlled import report as RP  # 12번 계산·결과 조립

assert Path(sys.modules["r2h"].__file__).resolve().is_relative_to((ROOT / "src").resolve())  # 다른 트리의 r2h 금지
BASE = ROOT / "research/k200_cusum_controlled_12"  # 12번 산출물 폴더
RES = BASE / "results"  # 결과표
FIGDIR = BASE / "figures"  # 그림 (PNG 320dpi + SVG)


def sha(p):  # 파일 SHA256
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()  # 바이트 단위 지문


def preview(path, width=1100):  # 노트북 용량을 줄이는 축소 미리보기 (원본은 figures/)
    from io import BytesIO  # 메모리 버퍼
    from PIL import Image as PILImage  # 이미지 축소
    im = PILImage.open(path)  # 320dpi 원본
    im.thumbnail((width, width * 3))  # 가로 1100px 이하로 축소
    buf = BytesIO()  # 출력 버퍼
    im.save(buf, format="PNG", optimize=True)  # PNG 로 다시 저장
    return buf.getvalue()  # 바이트 반환


# 계약(lock-1·lock-2)·설정 동결 지문 — 파일 이름별 마지막 기록이 현재 파일과 같아야 한다.
FREEZE = {}  # 파일 이름 → 마지막 지문 (lock-2 가 설정을 다시 동결)
for line in (BASE / "CONTRACT_FREEZE_SHA256.txt").read_text().splitlines():  # 동결 기록 (시간순)
    digest, name = line.split(maxsplit=1)  # 해시·경로
    FREEZE[Path(name).name] = digest  # 같은 이름은 나중 기록이 우선
CURRENT = {"RESEARCH_CONTRACT.md": BASE / "RESEARCH_CONTRACT.md", "RESEARCH_CONTRACT_LOCK2.md": BASE / "RESEARCH_CONTRACT_LOCK2.md", "t21_k200_cusum_controlled_v1.json": ROOT / "configs/t21_k200_cusum_controlled_v1.json"}  # 검사 대상
assert all(sha(p) == FREEZE[k] for k, p in CURRENT.items()), "동결 계약·설정 변경"  # 결과 계산 전 동결본과 같아야 한다
# 00–11 보호 파일 지문 (12번 시작 시점 기록) — 실행 전후 모두 같아야 한다 (G8).
PROT = [line.split(maxsplit=1) for line in (BASE / "evidence/PROTECTED_SHA256.txt").read_text().splitlines()]  # (해시, 경로)
bad = [p for h, p in PROT if sha(ROOT / p) != h]  # 바뀐 보호 파일
assert not bad, f"보호 파일 변경: {bad[:5]}"  # 기존 연구는 읽기만
print("작업트리:", ROOT, "| 보호 파일", len(PROT), "개 불변 | 환경", ACTUAL_ENV)  # 검증 요약
"""

RUN = r"""
# 관측 계산 전부: 069500 수익률 → SVR 정책 10종 → 실험 464종 원시 통계량 → N1 귀무표 부착 → 원장·결과표·감사.
# 합성·귀무 MC(약 3.6시간)는 outputs/t21/mc/ 의 저장 배열을 읽는다 (Git 제외, 해시는 RELEASE_MANIFEST 에).
R = RP.run(ROOT, ROOT / "outputs/t21/calib_n1", ROOT / "outputs/t21/mc/n1_null", RES)  # 결과는 results/ 에 결정적으로 쓴다
T = R["tables"]  # 결과표 dict
OB = R["ob"]  # 관측 계산 객체
CAP = F.Figures12(R, ROOT).make_all()  # 그림 전부 다시 그리고 캡션 수치를 받는다
print("결과 CSV", len(R["written"]), "개 | 원장 행", R["ledger_rows"], "| 실험", len(OB.reg), "| SVR 적합", OB.n_fits, "회")  # 실행 요약
"""


def interp(key: str) -> nbformat.NotebookNode:
    data = json.loads((BASE / "notebook_interpretation.json").read_text(encoding="utf-8"))
    return md(data[key])


def book() -> nbformat.NotebookNode:
    S = "T['experiment_summary.csv']"
    cols = "['experiment_id','changed_variable','value_after','valid_days','T_max','crit_a05','alarm_days_a05','alarm_days_a05_2020','alarm_days_a05_2021_2025','event_alarm_days_a20','event_mean_pctile']"
    cells = [
        interp("title"),
        code(SETUP),
        interp("design"),
        code(RUN),
        md("## 1. 기준선 — B0 재현(08 W3 대조)과 B1 연도 관통"),
        interp("baseline"),
        table(f"{S}[{S}.family=='BASE'][{cols}]", "B0·B1 요약 (α=0.05·0.20 경보, 사건 반응)"),
        fig("F01_관측_타임라인"),
        fig("F02_B0_B1_연초초기화"),
        md("## 2. E1 시간 분할 · E2 창 길이"),
        interp("e1_e2"),
        table(f"{S}[{S}.family.isin(['E1_time_split','E2_window'])][{cols}]", "E1·E2: 부모 B1 대비 하나만 바꾼 결과"),
        fig("F03_창길이_비교"),
        fig("F12_긴창_과거충격_이월"),
        md("## 3. E3 CUSUM 공식 — 이동 CoS · Page · 사후 · 원수익률"),
        interp("e3"),
        table(f"{S}[{S}.family.isin(['E3_statistic','EXPLORATORY_EXTENSION'])][{cols}]", "E3 + X1 자기정규화 Page"),
        fig("F04_Page_CUSUM"),
        md("## 4. E4 변화점 네 계열 · E5 변화점 초기화와 위약"),
        interp("e4_e5"),
        table("T['change_point_summary.csv'].query('q==0.99 and gap==20')", "E4 규칙별 트리거 수·연도 집중·사건 근접 (q=0.99, 불응기 20)"),
        fig("F05_변화점_트리거"),
        table("T['placebo_comparison.csv'].query('metric==\"event_mean_pctile\" and q==0.99 and gap==20')", "E5 실제 변화점 초기화 vs 무작위·이동 위약 (사건일 백분위)"),
        fig("F06_변화점초기화_위약"),
        md("## 5. E6–E10 SVR 학습기간 · 재학습 빈도 · 변화점 반응 · 유예 · 적응형"),
        interp("svr"),
        table(f"{S}[{S}.family.str.match('E(6|7|8|9|10)_')][{cols}]", "E6–E10 관측 경보 (부모 B1 또는 E3 Page)"),
        table("T['svr_training_summary.csv'].query('year==\"all\"')", "정책별 QLIKE · 평균 e^2 · 재적합 단절비"),
        fig("F07_SVR_정책"),
        fig("F11_재적합경계_단절"),
        md("## 6. E11 임계값·귀무 보정 · 귀무 적합성 · 크기 감사"),
        interp("calibration"),
        table("T['null_validity.csv'].query('outside')", "관측 잔차가 N1 귀무 99% 범위 밖인 (파이프라인, 연도, 통계)"),
        table("T['size_fail_decomposition.csv'].query('n_fail_wilson>0').head(40)", "홀드아웃 크기 실패 분해 (통계량·창·SVR·초기화 계열)"),
        table("pd.read_csv(RES / 'size_calibration_uncertainty.csv')", "X-D5 보정 표본오차 · 역할 교환 검사"),
        md("## 7. 합성 검정 — 같은 오경보 부담(α)에서 13 시나리오 검출률·지연"),
        interp("synthetic"),
        table("T['synthetic_size_power.csv'].query('alpha==0.05 and reset==\"none\" and svr in [\"B1\",\"NA\"]').pivot_table(index=['detector','w'], columns='scenario', values='detection_rate')", "B1 잔차·원수익률 탐지기의 시나리오별 검출률 (α=0.05)"),
        fig("F08_합성_검출률"),
        md("## 8. 실제 사건 상세 · 사건 유형별 반응"),
        interp("events"),
        fig("F10_사건_확대"),
        fig("F13_사건유형별_반응"),
        md("## 9. Autoencoder 피처 인계 — 중복성 · 추가 정보 · 관측 가능 시점"),
        interp("ae"),
        table("T['ae_redundancy.csv'].sort_values('incremental_r2_future_rv20_over_rv20', ascending=False)", "후보 피처: 다른 피처로 설명되는 R² · 가장 비슷한 피처 · 미래 RV20 증분 R²(사후)"),
        fig("F09_AE_피처_중복성"),
        md("## 10. 결론 · 한계 · 다음 실험"),
        interp("conclusion"),
        md("## 11. CLAIMS 및 재현성 검증"),
        code(r"""
# 해석 문단의 숫자를 결과 파일에서 다시 계산해 대조한다 (불일치면 실패).
CL = json.loads((BASE / "notebook_claims.json").read_text(encoding="utf-8"))  # (주장, 결과파일, 식, 기대값)
bad = {}  # 불일치 주장
for c in CL:  # 주장마다
    df = pd.read_csv(RES / c["file"]) if c["file"].endswith(".csv") else None  # 근거 결과표
    got = eval(c["expr"], {"df": df, "np": np, "pd": pd, "RES": RES})  # 결과표에서 다시 계산한 값
    got = round(float(got), c.get("round", 6)) if isinstance(got, (int, float, np.floating, np.integer)) else got  # 반올림 규칙
    if got != c["expected"]:  # 본문 수치와 다르면
        bad[c["claim"]] = (got, c["expected"])  # 기록
print(f"CLAIMS {len(CL) - len(bad)}/{len(CL)} 일치")  # 결과
assert not bad, bad  # 불일치가 있으면 해석 문단을 고쳐야 한다
"""),
        code(r"""
# 00–11 보호 파일이 실행 뒤에도 같은지 다시 확인한다 (G8).
bad = [p for h, p in PROT if sha(ROOT / p) != h]  # 바뀐 보호 파일
assert not bad, f"보호 파일 변경: {bad[:5]}"  # 변경 금지
print("보호 파일", len(PROT), "개 불변 · 결과 CSV", len(R["written"]), "개 · PNG", len(list(FIGDIR.glob('*.png'))), "· SVG", len(list(FIGDIR.glob('*.svg'))))  # 산출물 수
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
