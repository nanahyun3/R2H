"""데이터 버전 관리 — raw 파일 sha256 과 manifest 대조.

원시 시세는 저장소에 넣지 않는다 (재배포 권리 미확인). 대신 각 사용자가 받은 파일이 기준 연구와 같은 바이트인지
``MANIFEST.csv`` (열: ``ticker``, ``sha256``) 로 확인한다. 데이터 버전 = sorted ``ticker:sha256`` 의 sha256 —
SA_ETF Track A 의 ``input_data_version`` 과 같은 정의다.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def data_version(ticker_sha: dict[str, str]) -> str:
    """정렬된 ``ticker:sha256`` 줄의 sha256. 파일 순서·경로와 무관하다."""
    body = "\n".join(f"{t}:{s}" for t, s in sorted(ticker_sha.items()))
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class ManifestCheck:
    ticker: str
    expected: str
    actual: str | None

    @property
    def match(self) -> bool:
        return self.actual == self.expected


def verify_manifest(
    raw_dir: str | Path, manifest_csv: str | Path, suffix: str = ".csv"
) -> list[ManifestCheck]:
    """manifest 의 각 ticker 파일을 해시해 대조한다. 파일이 없으면 ``actual=None``."""
    raw = Path(raw_dir)
    out: list[ManifestCheck] = []
    with Path(manifest_csv).open(newline="") as f:
        for row in csv.DictReader(f):
            p = raw / f"{row['ticker']}{suffix}"
            out.append(ManifestCheck(row["ticker"], row["sha256"], sha256_file(p) if p.exists() else None))
    return out
