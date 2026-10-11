"""노트북 규칙 검사 — 모든 코드 줄에 한국어 주석 (같은 줄 끝 또는 바로 위 주석 줄), 한글 폰트 설정 셀 존재.

적용 대상: ``notebooks/*.ipynb`` 전부. 규칙 근거: 사용자 노트북 규칙 · experiments.md §3 (9/18 한글 폰트).
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted((ROOT / "notebooks").glob("*.ipynb"))
HANGUL = re.compile(r"[가-힣]")


def uncommented_lines(source: str) -> list[str]:
    """주석이 없는 코드 줄 목록. 주석 = 같은 줄의 '# …한글…' 또는 바로 위(연속 주석 블록)의 한글 주석 줄."""
    bad, prev_comment = [], False
    for line in source.splitlines():
        s = line.strip()
        if not s:
            prev_comment = False
            continue
        if s.startswith("#"):
            prev_comment = bool(HANGUL.search(s))
            continue
        if s.startswith("%"):  # IPython 매직은 바로 위 주석으로 설명
            if not prev_comment:
                bad.append(line)
            prev_comment = False
            continue
        trailing = "#" in s and HANGUL.search(s.split("#", 1)[1] if not s.startswith(("'", '"')) else "")
        closing_only = s in {")", "]", "}", "),", "],", "},", ")]", "})"}
        if not (prev_comment or trailing or closing_only):
            bad.append(line)
        prev_comment = False
    return bad


@pytest.mark.parametrize("nb", NOTEBOOKS, ids=[p.name for p in NOTEBOOKS])
def test_every_code_line_has_korean_comment(nb):
    cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    bad = [ln for c in cells if c["cell_type"] == "code" for ln in uncommented_lines("".join(c["source"]))]
    assert not bad, f"{nb.name}: {len(bad)} uncommented code lines, e.g. {bad[:3]}"


@pytest.mark.parametrize("nb", NOTEBOOKS, ids=[p.name for p in NOTEBOOKS])
def test_korean_font_registered_and_no_missing_glyph(nb):
    cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    src = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
    assert "NanumGothic.ttf" in src and "addfont" in src and "axes.unicode_minus" in src
    outs = [o for c in cells if c["cell_type"] == "code" for o in c.get("outputs", [])]
    assert not any("missing from font" in "".join(o.get("text", "")) for o in outs)
    assert not any(o.get("output_type") == "error" for o in outs)


def test_uncommented_detector():
    assert uncommented_lines("# 설명\nx = 1\ny = 2") == ["y = 2"]
    assert uncommented_lines("z = 3  # 한글 주석") == []
    assert uncommented_lines("# english only\nq = 1") == ["q = 1"]
