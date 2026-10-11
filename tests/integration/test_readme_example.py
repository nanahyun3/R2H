"""README 의 '사용 예' 코드 블록을 그대로 실행한다 (문서 명령이 깨지면 테스트가 실패)."""

import re
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"


def test_readme_python_example_runs(capsys):
    text = README.read_text(encoding="utf-8")
    section = text.split("## 사용 예", 1)[1]
    code = re.search(r"```python\n(.*?)```", section, re.S)
    assert code, "README 사용 예 python 블록이 없다"
    exec(compile(code.group(1), str(README), "exec"), {})
    out = capsys.readouterr().out
    assert "EventMetrics(" in out and "recall=" in out
