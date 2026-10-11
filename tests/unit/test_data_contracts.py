from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from r2h.data import (
    ContractViolation,
    data_version,
    sha256_file,
    slice_as_of,
    to_wide,
    validate_observations,
    verify_manifest,
)


def obs(n: int = 5, tickers: tuple[str, ...] = ("069500", "148070")) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=n)
    rows = [
        {"ticker": t, "date": d, "adj_close": 100.0 + i, "volume": 1000.0}
        for t in tickers
        for i, d in enumerate(dates)
    ]
    return pd.DataFrame(rows)


def test_valid_table_passes():
    rep = validate_observations(obs())
    assert rep.ok and rep.n_tickers == 2 and rep.n_rows == 10


def test_missing_column():
    with pytest.raises(ContractViolation, match="missing required"):
        validate_observations(obs().drop(columns="volume"))


@pytest.mark.parametrize("bad", [np.nan, np.inf, 0.0, -1.0])
def test_bad_prices_reported(bad):
    df = obs()
    df.loc[3, "adj_close"] = bad
    rep = validate_observations(df, strict=False)
    assert not rep.ok


def test_duplicate_and_unsorted_dates():
    df = obs()
    dup = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    assert any("duplicate" in i for i in validate_observations(dup, strict=False).issues)
    shuffled = df.iloc[[1, 0, 2, 3, 4, 5, 6, 7, 8, 9]]
    assert any("not sorted" in i for i in validate_observations(shuffled, strict=False).issues)


def test_tz_aware_date_rejected_and_numeric_ticker_rejected():
    df = obs()
    df["date"] = df["date"].dt.tz_localize("Asia/Seoul")
    assert any("timezone-naive" in i for i in validate_observations(df, strict=False).issues)
    df2 = obs()
    df2["ticker"] = 69500
    assert any("ticker must be string" in i for i in validate_observations(df2, strict=False).issues)


def test_observed_at_must_be_tz_aware():
    df = obs()
    df["observed_at"] = df["date"]
    assert any("observed_at" in i for i in validate_observations(df, strict=False).issues)
    df["observed_at"] = df["date"].dt.tz_localize("Asia/Seoul") + pd.Timedelta(hours=15, minutes=30)
    assert validate_observations(df).ok


def test_to_wide_preserves_leading_zero_and_rejects_duplicates():
    w = to_wide(obs())
    assert list(w.columns) == ["069500", "148070"]
    with pytest.raises(ContractViolation):
        to_wide(pd.concat([obs(), obs().iloc[[0]]]))


def test_slice_as_of_inclusive_both_layouts():
    df = obs()
    cut = df["date"].iloc[2]
    assert df.pipe(slice_as_of, cut)["date"].max() == cut
    w = to_wide(df)
    assert slice_as_of(w, cut).index.max() == cut
    tz = df.assign(observed_at=df["date"].dt.tz_localize("UTC"))
    with pytest.raises(ValueError):
        slice_as_of(tz, "2024-01-02", time_col="observed_at")


def test_manifest_roundtrip(tmp_path: Path):
    (tmp_path / "AAA.csv").write_text("x\n1\n")
    (tmp_path / "BBB.csv").write_text("x\n2\n")
    good = sha256_file(tmp_path / "AAA.csv")
    (tmp_path / "MANIFEST.csv").write_text(f"ticker,sha256\nAAA,{good}\nBBB,{'0' * 64}\nCCC,{'1' * 64}\n")
    res = {c.ticker: c for c in verify_manifest(tmp_path, tmp_path / "MANIFEST.csv")}
    assert res["AAA"].match and not res["BBB"].match and res["CCC"].actual is None


def test_data_version_order_invariant():
    a = {"069500": "aa", "148070": "bb"}
    assert data_version(a) == data_version(dict(reversed(list(a.items()))))
    assert data_version(a) != data_version({"069500": "aa", "148070": "bc"})
