"""12B 결과 CSV 중 5 MB 초과 파일을 결정적 gzip(mtime=0)으로 바꾼다 (Git 용량, D-09). 원본 CSV 는 지운다."""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research/k200_cusum_overlay_12b/results"
LIMIT = 5 * 1024 * 1024


def main() -> int:
    for p in sorted(RES.glob("*.csv")):
        if p.stat().st_size <= LIMIT:
            continue
        gz = p.with_suffix(".csv.gz")
        with open(p, "rb") as f, open(gz, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as z:
            z.write(f.read())
        p.unlink()
        print(gz.name, gz.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
