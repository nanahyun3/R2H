"""T12 Semantic Result Fingerprint 검사 — provenance 열·행 순서에 불변, 1-ulp 변화·판정 뒤집힘은 검출.

입력은 커밋된 ``research/t12_annual_expanding_v2/results/`` (seq_golden 바이트 복사본) 와 그 변형본이다.
원본 R2H 트리 경로는 쓰지 않는다.
"""

import importlib.util
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "t12_annual_expanding_v2" / "results"
# seq_golden (= 커밋된 results/) 의 집계 Semantic 지문 — REPRO_HASHES.md 와 같은 값
SEQ_GOLDEN_SEMANTIC = "a5dca934bee19e3d843d2914c465a330cdd9d8abcd5051c3ef212de47472f883"
SEQ_GOLDEN_VERDICT = "48c8de250f72e22bc3d880e37ee762ecdec9fa2e98cd4258143cdf5c570e710f"


def _load():
    spec = importlib.util.spec_from_file_location("t12_semantic_fingerprint", ROOT / "scripts" / "t12_semantic_fingerprint.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fp = _load()


def _write(df: pd.DataFrame, path: Path) -> None:
    """파이프라인과 같은 형식(%.10g, LF)으로 쓴다."""
    path.write_bytes(df.to_csv(index=False, lineterminator="\n", float_format="%.10g").encode())


@pytest.fixture()
def copy(tmp_path):
    d = tmp_path / "run"
    shutil.copytree(RESULTS, d)
    return d


def test_committed_results_match_seq_golden_constant():
    f = fp.fingerprint_dir(RESULTS)
    assert not f["missing"]
    assert f["aggregate_semantic"] == SEQ_GOLDEN_SEMANTIC
    assert f["aggregate_verdict"] == SEQ_GOLDEN_VERDICT


def test_invariant_to_git_sha_and_row_order(copy):
    p = copy / "fold_manifest.csv"
    df = fp.read_table(p)
    df["git_sha"] = "deadbeef+dirty"
    _write(df.sample(frac=1.0, random_state=0), p)
    res = fp.compare_dirs(RESULTS, copy, "mut")
    row = res[res.table == "fold_manifest"].iloc[0]
    assert row.byte == "FAIL" and row.semantic == "PASS" and row.verdict == "PASS"
    assert row.byte_diff_provenance_cols == "git_sha"
    assert fp.overall(res[res.table != "run_manifest.json(semantic fields)"])["semantic"] == "PASS"


def test_detects_one_ulp_change(copy):
    p = copy / "annual_posthoc.csv"
    df = fp.read_table(p)
    i = int(np.flatnonzero(np.isfinite(df.annual_T.to_numpy()))[0])
    df.loc[i, "annual_T"] = np.nextafter(df.loc[i, "annual_T"], np.inf)
    # %.10g 로 쓰면 1-ulp 가 사라지므로, 이 검사는 repr 정밀도로 직접 쓴다
    p.write_bytes(df.to_csv(index=False, lineterminator="\n", float_format="%.17g").encode())
    res = fp.compare_dirs(RESULTS, copy, "ulp")
    row = res[res.table == "annual_posthoc"].iloc[0]
    assert row.semantic == "FAIL"
    assert "annual_T" in row.diff_cols
    assert 0 < row.numeric_max_abs_diff < 1e-12


def test_detects_verdict_flip(copy):
    p = copy / "annual_posthoc.csv"
    df = fp.read_table(p)
    j = df.index[df.annual_reject.notna()][0]
    df.loc[j, "annual_reject"] = not bool(df.loc[j, "annual_reject"])
    _write(df, p)
    res = fp.compare_dirs(RESULTS, copy, "flip")
    row = res[res.table == "annual_posthoc"].iloc[0]
    assert row.semantic == "FAIL" and row.verdict == "FAIL"
    assert row.verdict_cells_changed == 1


def test_duplicate_keys_rejected(copy):
    p = copy / "fit_summary.csv"
    df = fp.read_table(p)
    _write(pd.concat([df, df.iloc[[0]]], ignore_index=True), p)
    with pytest.raises(ValueError, match="duplicate keys"):
        fp.table_fingerprint(p, "fit_summary")


def test_provenance_list_is_explicit():
    assert "git_sha" in fp.PROVENANCE_COLUMNS
    for kept in ("data_version", "config_hash", "model_hash", "history_hash", "protocol_version"):
        assert kept not in fp.PROVENANCE_COLUMNS
