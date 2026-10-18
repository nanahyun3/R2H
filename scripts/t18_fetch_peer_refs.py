"""W4 (T18) Peer 후보 참조 ETF 일봉 수집 — 평가 20종과 같은 출처(FinanceDataReader 0.9.202), 같은 기간.

후보 목록은 상장 스냅샷(data/raw/listing_snapshot_20261003T2058.csv)의 종목명만으로 고른 것이며,
변동성·수익률 결과를 보기 전에 고정했다. 원시 파일은 data/external/peer/ (Git 제외) 에 저장하고
sha256·행수·첫날·마지막날을 MANIFEST.csv 로 남긴다.
"""
from __future__ import annotations

import csv
import hashlib
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

START, END = "2019-01-01", "2026-10-02"
CANDIDATES = {
    # KOSPI200 1배 동일 지수
    "148020": "RISE 200", "105190": "ACE 200", "152100": "PLUS 200", "069660": "KIWOOM 200",
    "293180": "HANARO 200", "152870": "파워 200",
    # 코스닥150 동일 지수
    "232080": "TIGER 코스닥150", "270810": "RISE 코스닥150", "354500": "ACE 코스닥150",
    "316670": "KIWOOM 코스닥150", "304770": "HANARO 코스닥150", "450910": "SOL 코스닥150", "301400": "PLUS 코스닥150",
    # 국내 업종·테마·전략
    "091160": "KODEX 반도체", "091220": "TIGER 은행", "226490": "KODEX 코스피", "277630": "TIGER 코스피",
    "305720": "KODEX 2차전지산업", "364980": "TIGER 2차전지TOP10", "266420": "KODEX 헬스케어",
    "253280": "RISE 헬스케어", "227540": "TIGER 200 헬스케어", "139240": "TIGER 200 철강소재",
    "117460": "KODEX 에너지화학", "279530": "KODEX 고배당주", "210780": "TIGER 코스피고배당", "266160": "RISE 고배당",
    "211900": "KODEX 코리아배당성장", "211560": "TIGER 배당성장",
    # 해외 주식
    "304940": "KODEX 미국나스닥100선물(H)", "367380": "ACE 미국나스닥100", "368590": "RISE 미국나스닥100",
    "379810": "KODEX 미국나스닥100", "360750": "TIGER 미국S&P500", "360200": "ACE 미국S&P500",
    "379800": "KODEX 미국S&P500", "449180": "KODEX 미국S&P500(H)", "283580": "KODEX 차이나CSI300",
    "168580": "ACE 중국본토CSI300",
    # 채권·원자재·통화
    "365780": "ACE 국고채10년", "438570": "SOL 국고채10년", "114260": "KODEX 국고채3년", "302190": "TIGER 중장기국채",
    "157450": "TIGER 단기통안채", "196230": "RISE 단기통안채", "190620": "ACE 단기통안채", "214980": "KODEX 단기채권PLUS",
    "319640": "TIGER 골드선물(H)", "130680": "TIGER 원유선물Enhanced(H)", "219390": "RISE 미국S&P원유생산기업(합성 H)",
    "138230": "KIWOOM 미국달러선물",
}


def main(out: Path) -> int:
    import FinanceDataReader as fdr

    out.mkdir(parents=True, exist_ok=True)
    kst = timezone(timedelta(hours=9))
    rows = []
    for tk, name in CANDIDATES.items():
        path = out / f"{tk}.csv"
        try:
            df = fdr.DataReader(tk, START, END)
            df.index.name = "Date"
            df.to_csv(path)
            rows.append(dict(ticker=tk, name=name, rows=len(df), first=df.index.min().date(), last=df.index.max().date(),
                             n_zero_volume=int((df["Volume"] == 0).sum()),
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             source=f"FinanceDataReader {fdr.__version__} DataReader",
                             fetched_at=datetime.now(kst).isoformat(timespec="seconds"), status="OK"))
        except Exception as e:  # 수집 실패도 기록한다
            rows.append(dict(ticker=tk, name=name, rows=0, first="", last="", n_zero_volume="", sha256="",
                             source="FinanceDataReader", fetched_at=datetime.now(kst).isoformat(timespec="seconds"),
                             status=f"FAILED:{type(e).__name__}"))
        print(rows[-1]["ticker"], rows[-1]["status"], rows[-1]["first"], rows[-1]["rows"], flush=True)
    with (out / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "data/external/peer")))
