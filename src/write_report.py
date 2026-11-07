#!/usr/bin/env python
"""A4 보고서 원고 (표준 마크다운) 생성 → md · pdf · docx.
본문은 노트북과 같은 원고(report_md.py)를 쓰고, 노트북 전용 문장을 빼고 그림을 넣는다.
사용: python write_report.py
"""
import json, re, subprocess, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent
sys.path.insert(0, str(HERE))
from report_md import MD  # noqa: E402

N = json.loads((REPORT / "results" / "report_numbers.json").read_text(encoding="utf-8"))
FIG = REPORT / "figures"


def fig(name, cap):
    assert (FIG / f"{name}.png").exists(), name
    return f"\n![{cap}](figures/{name}.png)\n\n*{cap}*\n"


def sup(t):  # 6.1 보충 항목을 붙임 번호로
    return t.replace("#### 다. 보충: ", "#### 가. ").replace("#### 라. 보충: ", "#### 나. ").replace("#### 마. 보충: ", "#### 다. ")


def body(key, drop=()):
    s = MD[key].strip("\n")
    for d in drop:
        assert d in s, (key, d[:40])
        s = s.replace(d, "")
    return s


cover = "\n".join(l for l in body("cover").splitlines() if not l.startswith("이 노트북은"))
cover = cover.replace("# 장기 보유 대비 매매 시점 결정 방법에 관한 실무 자문 요청\n\n**중간 연구 보고 · 2026년 11월 · 홍익대학교 졸업 프로젝트 R2H(주가 급등 국면 포착) 팀 · 국내 상장 ETF 20종 일봉 분석**",
                      "# 장기 보유를 이길 수 있는가\n\n## 매매 시점 결정 방법에 관한 실무 자문 요청 — 국내 상장 ETF 20종 일봉 분석\n\n**중간 연구 보고 · 2026년 11월 · 홍익대학교 졸업 프로젝트 R2H(주가 급등 국면 포착) 팀**")
assert cover.startswith("# 장기 보유를 이길 수 있는가")
cover = cover.split("---\n\n### 보고서 구성")[0].rstrip().rstrip("-").rstrip()  # PDF 에서는 목차 표 생략

t = pd.read_csv(REPORT / "results" / "t_tests.csv")
tests = "| 핵심 검정 | 효과 크기 [95% 신뢰구간] | 보정 전 p | Holm 보정 p | 결론 |\n|---|---|---|---|---|\n" + "\n".join(
    f"| {r.검정} | {r.효과} | {r.p:.2f} | {r.보정p:.2f} | {r.결론} |" for r in t.itertuples())

parts = [
    cover,
    body("ch1"), fig("f1_zigzag", "그림 1. KODEX 200 의 상승 구간 (초록: 저점 대비 15% 이상, 회색: 15% 미만 반등, 빨간 점: 사후 확정 고점)"),
    body("ch2"),
    body("ch3"),
    body("ch3_fill"),
    body("ch4"), fig("f4_rule", "그림 2. 20일 신고가 돌파 전략의 실제 매매 (KODEX 200, 2024-01 ~ 2025-09, 초록 음영 = 보유 기간)"),
    body("ch5"), fig("f5_strategies", "그림 3. 장기 보유와 매매 규칙의 누적 수익(왼쪽)과 수익 × 최대낙폭(오른쪽). 노란 점선은 보유와 규칙 사이에서 고를 수 있는 노출 선택지"),
    body("ch5_res"), body("ch5_id"), fig("f5_identity", "그림 4. 현금 보유 구간의 손익 분해 (왼쪽: 종목 평균, 오른쪽: 종목별 보유 대비 격차)"),
    body("ch6"), fig("two_labels", "그림 5. 같은 GBM 점수를 상승 구간 라벨과 거래 성공 라벨로 채점한 표본 외 AUC"),
    fig("x3_null", "그림 6. 실제 매수의 거래 성공 비율과 조건 맞춤 무작위 매수 1,000회의 범위"),
    body("ch6_res"), fig("x3_bands", "그림 7. 위치별 거래 성공 비율(왼쪽)과 가격 순서를 섞은 경로에서의 성공률 격차(오른쪽)"),
    body("ch7"), fig("c_peak", "그림 8. 고점 기준 위치별 매수 건당 평균 손익 (모든 거래일 가상 매수, 같은 매도 규칙, 2021년 이후)"),
    body("ch7_peak"), fig("c_mean_sum", "그림 9. 매수 건당 손익과 손실 합에서 차지하는 몫"),
    body("ch7_loss"), fig("f7_loss", "그림 10. 상승 구간 안에서 산 거래(501건)의 손실 분해"),
    body("ch7_c4"), fig("f7_overheat", "그림 11. 과열 지표(이격도 · RSI)의 고점 직전 판별력 — 실제 자료 vs 가격 순서를 섞은 경로 200개"),
    body("ch8"), fig("f8_exits", "그림 12. 매도 규칙별 누적 수익 · 최대낙폭 · 샤프 비율 (매수는 모두 20일 신고가 돌파)"),
    body("ch8_res"),
    body("ch9"), fig("x2_rebuy", "그림 13. 재진입 조건별 누적 수익(왼쪽)과 재진입 뒤 2거래일 안 재청산 건수(오른쪽)"),
    body("ch9_res"),
    "## 7. 남은 쟁점과 질의 사항\n\n### 7.1 검토 결과 종합\n\n- 핵심 검정 네 개를 다중 검정 보정(Holm)한 결과, 넷 모두 통계적으로 유의하지 않습니다\n\n" + tests + "\n",
    fig("f10_scorecard", "그림 14. 판단 기준 세 가지로 본 현행 규칙과 장기 보유의 비교"),
    body("ch10_q"),
    body("appA"), fig("x6_matrix", "그림 A-1. 학습 종목군 × 평가 종목군별 누적 수익 (편도 0.1%)"), fig("x6_decomp", "그림 A-2. 학습만 바꾼 효과 vs 평가만 바꾼 효과, 그리고 종목별 수익"),
    body("appA_res"),
    "## 붙임 2. 국면 판별 모델 보충 검토",
    sup(body("ch6_shuffle")), sup(body("ch6_x4")), fig("x4_auc", "그림 B-1. 수익 나는 날을 직접 학습한 모델의 표본 외 AUC (회색 띠: 20종 대조 모델 범위)"),
    body("ch6_x4_res"), sup(body("ch6_grid")), fig("x5_grid", "그림 B-2. 진입 · 해제 임계값 24개 조합의 누적 수익 · 신호 유지 기간 · 재진입 건수 (종목 동일 비중)"),
    body("ch6_grid_res"),
    body("appB").replace("## 붙임 2. 용어", "## 붙임 3. 용어"),
    "\n---\n\n*자료: FinanceDataReader 일봉 (2017-01-02 ~ 2026-10-29). 모든 수치는 함께 제공하는 노트북 `1107_중간연구보고.ipynb` 에서 다시 계산할 수 있습니다. 과거 성과는 미래 수익을 보장하지 않으며, 이 보고서는 투자 권유가 아닙니다.*\n",
]
md = "\n\n".join(p.strip("\n") for p in parts) + "\n"
md = re.sub(r"\n{3,}", "\n\n", md)
for bad in ["v1", "v2", "v3", "1차 연구", "동료 검증", "독립 검수", "페르소나", "FREEZE", "막차", "곡선 회계", "체결 회계", "오탐", "정탐", "크리티컬", "베이스라인", "이 노트북은"]:
    hits = [l for l in md.splitlines() if bad in l and "notebook" not in l]
    assert not hits, (bad, hits[:2])
out = REPORT / "1107_중간연구보고.md"
out.write_text(md, encoding="utf-8")
print("md", out, len(md.splitlines()), "줄")

# PDF
subprocess.run([sys.executable, str(HERE / "build_pdf.py"), str(out), str(REPORT / "1107_중간연구보고.pdf"), "장기 보유를 이길 수 있는가 — 중간 연구 보고"], check=True)
# DOCX (pandoc)
import pypandoc  # noqa: E402
pypandoc.convert_file(str(out), "docx", outputfile=str(REPORT / "1107_중간연구보고.docx"), extra_args=["--resource-path", str(REPORT), "--toc", "--toc-depth=2", "-M", "title=장기 보유를 이길 수 있는가", "-M", "lang=ko-KR"] + (["--reference-doc", str(HERE / "reference.docx")] if (HERE / "reference.docx").exists() else []))
print("pdf · docx 완료")
