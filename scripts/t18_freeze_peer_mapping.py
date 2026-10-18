"""W4 Peer Mapping 동결 — 변동성·수익률을 계산하기 전에 종목명·기초지수·상장일만으로 정한다 (계약 §3).

규칙 (기계적, 결과 비의존):
1. Tier 1 = 동일 기초지수(같은 지수 계열·같은 환헤지 구조). Tier 2 = 경제적으로 설명 가능한 유사 위험.
2. 상장(첫 관측)일이 peer_listing_cutoff(2019-06-30) 이후인 후보는 LATE_LISTING 으로 제외 — 확장형 기준분포가 주 분석기간(2021–) 전에 252개를 채우도록.
3. 적격 Tier 1 이 1개 이상이면 Tier 1 만 채택. 없으면 적격 Tier 2 가 2개 이상일 때 Tier 2 채택. 둘 다 아니면 PEER_UNAVAILABLE.
4. 상관계수·변동성 등 가격에서 계산한 통계량은 선정에 쓰지 않는다.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (평가 ticker, peer ticker, peer 이름, tier, 동일지수, 자산군, 국가·통화, 환헤지, 듀레이션·만기, 레버리지, 선정 사유)
CANDIDATES = [
    # KOSPI200 1배 — 동일 기초지수 (069500·102110 서로 + 외부 6종)
    *[(e, p, n, 1, True, "국내주식_대형지수", "KR/KRW", "해당없음", "-", 1, "KOSPI200 동일 지수 1배")
      for e in ("069500", "102110")
      for p, n in [("102110" if e == "069500" else "069500", "TIGER 200" if e == "069500" else "KODEX 200"),
                   ("148020", "RISE 200"), ("105190", "ACE 200"), ("152100", "PLUS 200"),
                   ("069660", "KIWOOM 200"), ("293180", "HANARO 200"), ("152870", "파워 200")]],
    # 레버리지·인버스 — 배율 정규화 후 Core Pair 와 비교 (보조 진단)
    *[(e, p, n, 1, True, "국내주식_대형지수", "KR/KRW", "해당없음", "-", 1, "KOSPI200 Core Pair (배율 정규화 비교, 보조)")
      for e in ("122630", "114800") for p, n in [("069500", "KODEX 200"), ("102110", "TIGER 200")]],
    # 코스닥150
    *[("229200", p, n, 1, True, "국내주식_코스닥", "KR/KRW", "해당없음", "-", 1, "코스닥150 동일 지수 1배")
      for p, n in [("232080", "TIGER 코스닥150"), ("270810", "RISE 코스닥150"), ("354500", "ACE 코스닥150"),
                   ("316670", "KIWOOM 코스닥150"), ("304770", "HANARO 코스닥150"), ("450910", "SOL 코스닥150"),
                   ("301400", "PLUS 코스닥150")]],
    ("091230", "091160", "KODEX 반도체", 1, True, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KRX 반도체 동일 지수"),
    ("091170", "091220", "TIGER 은행", 1, True, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KRX 은행 동일 지수"),
    # 자동차 — 동일 지수 상장 이력 없음 → 국내 시장 전체(코스피) 대용
    ("091180", "226490", "KODEX 코스피", 2, False, "국내주식_시장전체", "KR/KRW", "해당없음", "-", 1, "자동차 업종이 속한 코스피 시장 전체 (업종 대 시장 상대 변동성)"),
    ("091180", "277630", "TIGER 코스피", 2, False, "국내주식_시장전체", "KR/KRW", "해당없음", "-", 1, "자동차 업종이 속한 코스피 시장 전체 (업종 대 시장 상대 변동성)"),
    # 2차전지 — 다른 지수의 2차전지 산업 ETF + 2차전지 대형주가 속한 에너지화학 업종
    ("305540", "305720", "KODEX 2차전지산업", 2, False, "국내주식_테마", "KR/KRW", "해당없음", "-", 1, "같은 2차전지 산업, 다른 지수 (FnGuide 2차전지산업)"),
    ("305540", "364980", "TIGER 2차전지TOP10", 2, False, "국내주식_테마", "KR/KRW", "해당없음", "-", 1, "같은 2차전지 산업, 다른 지수"),
    ("305540", "117460", "KODEX 에너지화학", 2, False, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "2차전지 셀·소재 대형주가 편입된 KRX 에너지화학 업종"),
    # 헬스케어 — KRX 헬스케어 계열 (운용사 공시 미검증: 상품명 기준)
    ("143860", "266420", "KODEX 헬스케어", 1, True, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KRX 헬스케어 동일 지수 (상품명 기준, 공시 미검증)"),
    ("143860", "253280", "RISE 헬스케어", 1, True, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KRX 헬스케어 동일 지수 (상품명 기준, 공시 미검증)"),
    ("143860", "227540", "TIGER 200 헬스케어", 2, False, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KOSPI200 헬스케어 (다른 지수, 동일 업종)"),
    # 철강 — 동일 지수 없음 → 철강소재 업종 + 국내 시장 전체
    ("117680", "139240", "TIGER 200 철강소재", 2, False, "국내주식_업종", "KR/KRW", "해당없음", "-", 1, "KOSPI200 철강소재 (다른 지수, 동일 업종)"),
    ("117680", "226490", "KODEX 코스피", 2, False, "국내주식_시장전체", "KR/KRW", "해당없음", "-", 1, "철강 업종이 속한 코스피 시장 전체"),
    ("117680", "277630", "TIGER 코스피", 2, False, "국내주식_시장전체", "KR/KRW", "해당없음", "-", 1, "철강 업종이 속한 코스피 시장 전체"),
    # 고배당 — 다른 지수의 국내 배당 전략
    *[("161510", p, n, 2, False, "국내주식_배당전략", "KR/KRW", "해당없음", "-", 1, "국내 배당 전략, 다른 지수")
      for p, n in [("279530", "KODEX 고배당주"), ("210780", "TIGER 코스피고배당"), ("266160", "RISE 고배당"),
                   ("211900", "KODEX 코리아배당성장"), ("211560", "TIGER 배당성장")]],
    # 미국 주식
    *[("133690", p, n, 1, True, "해외주식_미국", "US/USD노출", "환노출", "-", 1, "나스닥100 동일 지수, 환노출")
      for p, n in [("367380", "ACE 미국나스닥100"), ("368590", "RISE 미국나스닥100"), ("379810", "KODEX 미국나스닥100")]],
    ("133690", "304940", "KODEX 미국나스닥100선물(H)", 2, False, "해외주식_미국", "US/환헤지", "환헤지", "-", 1, "나스닥100 선물, 환헤지 (환노출 차이)"),
    ("133690", "219480", "KODEX 미국S&P500선물(H)", 2, False, "해외주식_미국", "US/환헤지", "환헤지", "-", 1, "미국 대형주 S&P500 선물, 환헤지 (지수·환노출 차이)"),
    ("219480", "449180", "KODEX 미국S&P500(H)", 1, True, "해외주식_미국", "US/환헤지", "환헤지", "-", 1, "S&P500 동일 지수, 환헤지 (현물·선물 차이)"),
    ("219480", "304940", "KODEX 미국나스닥100선물(H)", 2, False, "해외주식_미국", "US/환헤지", "환헤지", "-", 1, "미국 주가지수 선물, 환헤지 (지수 차이)"),
    ("219480", "133690", "TIGER 미국나스닥100", 2, False, "해외주식_미국", "US/USD노출", "환노출", "-", 1, "미국 대형주 (지수·환노출 차이)"),
    ("219480", "360750", "TIGER 미국S&P500", 2, False, "해외주식_미국", "US/USD노출", "환노출", "-", 1, "S&P500 동일 지수, 환노출 차이"),
    # 중국
    ("192090", "283580", "KODEX 차이나CSI300", 1, True, "해외주식_중국", "CN/CNY노출", "환노출", "-", 1, "CSI300 동일 지수"),
    ("192090", "168580", "ACE 중국본토CSI300", 1, True, "해외주식_중국", "CN/CNY노출", "환노출", "-", 1, "CSI300 동일 지수"),
    # 국고채10년 — 동일 지수 후보는 늦게 상장 → 국내 국고채 다른 만기
    ("148070", "365780", "ACE 국고채10년", 1, True, "국내채권_국고", "KR/KRW", "해당없음", "약 10년", 1, "국고채10년 동일 지수"),
    ("148070", "438570", "SOL 국고채10년", 1, True, "국내채권_국고", "KR/KRW", "해당없음", "약 10년", 1, "국고채10년 동일 지수"),
    ("148070", "302190", "TIGER 중장기국채", 2, False, "국내채권_국고", "KR/KRW", "해당없음", "중장기(약 5–10년 혼합)", 1, "국내 국고채, 듀레이션 짧음"),
    ("148070", "114260", "KODEX 국고채3년", 2, False, "국내채권_국고", "KR/KRW", "해당없음", "약 3년", 1, "국내 국고채, 듀레이션 현저히 짧음"),
    # 단기채
    *[("153130", p, n, 2, False, "국내채권_단기", "KR/KRW", "해당없음", "1년 이하", 1, "국내 단기 채권·통안채 (지수 차이)")
      for p, n in [("157450", "TIGER 단기통안채"), ("196230", "RISE 단기통안채"), ("190620", "ACE 단기통안채"),
                   ("214980", "KODEX 단기채권PLUS")]],
    # 금
    ("132030", "319640", "TIGER 골드선물(H)", 1, True, "원자재_금", "글로벌/환헤지", "환헤지", "선물 롤", 1, "S&P GSCI Gold 계열 금 선물, 환헤지 (지수 버전 차이 가능)"),
    # 원유
    ("261220", "130680", "TIGER 원유선물Enhanced(H)", 2, False, "원자재_원유", "글로벌/환헤지", "환헤지", "선물 롤(Enhanced)", 1, "WTI 원유 선물, 환헤지 (롤 방식이 다른 지수)"),
    ("261220", "219390", "RISE 미국S&P원유생산기업(합성 H)", 2, False, "해외주식_에너지", "US/환헤지", "환헤지", "-", 1, "원유 생산기업 주식 (원유 가격 민감, 자산 형태 다름 — 약한 Peer)"),
    # 달러
    ("261240", "138230", "KIWOOM 미국달러선물", 1, True, "통화_USDKRW", "USD/KRW", "해당없음", "선물 롤", 1, "미국달러선물 동일 지수"),
]


def main() -> int:
    cfg = json.loads((ROOT / "configs/t18_peer_shock_w4_v1.json").read_text(encoding="utf-8"))
    cutoff = cfg["peer_listing_cutoff"]
    first = {}
    for man in (ROOT / "data/raw/MANIFEST.csv", ROOT / "data/external/peer/MANIFEST.csv"):
        for row in csv.DictReader(man.open(encoding="utf-8")):
            first[row["ticker"]] = (row["first"], row.get("source", ""))
    groups = {r["ticker"]: r for r in csv.DictReader((ROOT / cfg["exposure_groups"]).open(encoding="utf-8"))}
    rows = []
    for e, p, n, tier, same, ac, cc, hedge, dur, lev, why in CANDIDATES:
        f, src = first.get(p, ("", "MISSING"))
        late = (not f) or f > cutoff
        rows.append(dict(eval_ticker=e, eval_name=groups[e]["name"], exposure_group=groups[e]["exposure_group"],
                         peer_ticker=p, peer_name=n, peer_in_eval20=p in groups, tier=tier, same_index=same,
                         asset_class=ac, country_ccy=cc, fx_hedge=hedge, duration_maturity=dur, leverage=lev,
                         data_source=src, first_obs=f, selection_reason=why,
                         eligible=not late, exclusion_reason="LATE_LISTING" if late else ""))
    # 채택: 적격 Tier1 ≥ peer_min_tier1 → Tier1 만, 아니면 적격 Tier2 ≥ peer_min_tier2 → Tier2, 아니면 불가
    status = {}
    for e in dict.fromkeys(r["eval_ticker"] for r in rows):
        el = [r for r in rows if r["eval_ticker"] == e and r["eligible"]]
        t1 = [r for r in el if r["tier"] == 1]
        t2 = [r for r in el if r["tier"] == 2]
        if len(t1) >= cfg["peer_min_tier1"]:
            use, st = 1, "TIER1"
        elif len(t2) >= cfg["peer_min_tier2"]:
            use, st = 2, "TIER2"
        else:
            use, st = None, "PEER_UNAVAILABLE"
        status[e] = st
        for r in rows:
            if r["eval_ticker"] != e:
                continue
            r["adopted"] = bool(r["eligible"] and use == r["tier"])
            if r["eligible"] and not r["adopted"]:
                r["exclusion_reason"] = "HIGHER_TIER_AVAILABLE"
            r["eval_peer_status"] = st
            grade = {"TIER1": "A" if len(t1) >= 2 else "B", "TIER2": "C", "PEER_UNAVAILABLE": "F"}[st]
            r["quality_grade"] = grade
    out = ROOT / cfg["peer_mapping"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    missing = sorted(set(groups) - set(status))
    for e in groups:
        print(e, groups[e]["name"], status.get(e, "NOT_MAPPED"),
              [r["peer_ticker"] for r in rows if r["eval_ticker"] == e and r["adopted"]])
    if missing:
        print("매핑 없음:", missing)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
