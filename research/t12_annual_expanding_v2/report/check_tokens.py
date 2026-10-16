"""원고 파일의 수치 토큰을 결과표로 치환해 보고 오류를 출력한다 — ``python check_tokens.py FILE [--results DIR]``.

토큰: ``{{표|키=값,…|열|형식}}`` · 표 별칭은 build_report.ALIAS · 형식은 Python format spec (``.2f``, ``+.2f``, ``d``, ``s``, ``yn``).
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_report import TOKEN, Renderer  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--results", default=str(Path(__file__).resolve().parents[1] / "results"))
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    R = Renderer(Path(a.results))
    text = Path(a.file).read_text(encoding="utf-8")
    bad = 0
    for m in TOKEN.finditer(text):
        try:
            R.sub(m.group(0))
        except Exception as e:  # noqa: BLE001 — 보고용
            bad += 1
            print(f"ERROR {m.group(0)} → {e}")
    stray = re.findall(r"\{\{(?![a-z_0-9]+\|[^|}]*\|[A-Za-z_0-9]+\|[^}]*\}\})[^}]*\}\}", text)
    for s in stray:
        bad += 1
        print(f"MALFORMED {s}")
    print(f"tokens: {len(TOKEN.findall(text))}, errors: {bad}")
    if a.show:
        print(R.sub(text))
    sys.exit(1 if bad else 0)
