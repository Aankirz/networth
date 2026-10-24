"""Splitting one yfinance download into per-asset closes, offline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from networth.watcher.prices import split_closes


def download_frame() -> pd.DataFrame:
    """The shape yfinance.download(group_by="ticker") returns for two tickers."""
    days = pd.DatetimeIndex(["2026-10-21", "2026-10-22", "2026-10-23"])
    columns = pd.MultiIndex.from_product([["SPY", "^NSEI"], ["Open", "Close"]])
    frame = pd.DataFrame(1.0, index=days, columns=columns)
    frame[("SPY", "Close")] = [700.0, 710.0, 720.0]
    frame[("^NSEI", "Close")] = [22500.0, 22600.0, np.nan]  # India closed on the last US day
    return frame


def test_each_asset_gets_its_dated_closes_without_gaps() -> None:
    out = split_closes(download_frame(), ["SPY", "^NSEI"])
    assert list(out.load("SPY")) == [700.0, 710.0, 720.0]
    assert out.load("^NSEI").index[-1] == pd.Timestamp("2026-10-22")


def test_an_asset_not_in_the_download_is_a_named_failure() -> None:
    out = split_closes(download_frame(), ["SPY", "XLK"])
    assert out.failures == {"XLK": "not in the download"}
    assert "XLK" not in out.closes
