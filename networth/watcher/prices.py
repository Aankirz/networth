"""Recent daily closes for price-first, fetched fresh every cycle.

    recent = recent_closes(["^NSEI", "SPY"], deadline_s=60)
    recent.load("SPY")   # a Series of closes indexed by date; KeyError when it failed

One yfinance download for every asset, over an IPv4-only session, under a wall-clock deadline.
Nothing is written to data/prices: that cache belongs to the engine and can be days old.
"""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

from networth import net

PERIOD: Final = "6mo"  # comfortably more than the 60-session volatility window plus one day


class PricesUnavailable(Exception):
    """The download as a whole failed or timed out, so price-first is skipped this cycle."""


@dataclass(frozen=True)
class RecentCloses:
    closes: Mapping[str, pd.Series]
    failures: Mapping[str, str]  # asset -> why it has no closes

    def load(self, asset: str) -> pd.Series:
        if asset not in self.closes:
            raise KeyError(self.failures.get(asset, f"{asset} was not requested"))
        return self.closes[asset]


def _session():
    from curl_cffi import CurlOpt
    from curl_cffi import requests as curl_requests
    from curl_cffi.const import CurlIpResolve

    return curl_requests.Session(
        impersonate="chrome", curl_options={CurlOpt.IPRESOLVE: CurlIpResolve.V4}
    )


def _download(assets: Sequence[str]) -> pd.DataFrame:
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # yfinance trips pandas deprecation warnings on every call
        frame = yf.download(list(assets), period=PERIOD, auto_adjust=True, progress=False,
                            group_by="ticker", threads=False, session=_session())  # fmt: skip
    if frame is None or frame.empty:
        raise ValueError("yfinance returned no data")
    return frame


def split_closes(frame: pd.DataFrame, assets: Sequence[str]) -> RecentCloses:
    """Per-asset closes from a group_by="ticker" frame, indexed by plain dates like the
    engine's own series."""
    closes: dict[str, pd.Series] = {}
    failures: dict[str, str] = {}
    for asset in assets:
        if (asset, "Close") not in frame.columns:
            failures[asset] = "not in the download"
            continue
        series = frame[(asset, "Close")].dropna().astype(float)
        if series.empty:
            failures[asset] = "no closes in the download"
            continue
        series.index = pd.to_datetime(series.index.date)
        closes[asset] = series[~series.index.duplicated(keep="last")].rename(asset)
    return RecentCloses(closes, failures)


def recent_closes(assets: Sequence[str], deadline_s: float) -> RecentCloses:
    try:
        frame = net.call_with_deadline(lambda: _download(assets), deadline_s, "yfinance closes")
    except Exception as exc:  # yfinance and curl raise many types; each means no prices now
        raise PricesUnavailable(f"{type(exc).__name__}: {exc}") from exc
    return split_closes(frame, assets)
