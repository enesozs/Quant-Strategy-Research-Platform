"""In-process market-data cache shared by every endpoint.

All downloads go through ``download_data`` here. It calls
``backtester.download_data`` (looked up at call time, so tests can
monkeypatch it), caches the frame per (ticker, start, end), and hands out
copies so callers can never mutate the cached data.

``install()`` points the two core call sites that download on their own
(``comparison.prepare_market_data`` and ``pairs_trading_core.download_data``)
at this cache. It only rebinds names in the running API process; the core
files and the Streamlit app are unchanged.
"""

from __future__ import annotations

import threading
from functools import lru_cache

import pandas as pd

import backtester
import comparison
import pairs_trading_core


class MarketDataError(RuntimeError):
    """Market data could not be downloaded (mapped to HTTP 502).

    Deliberately not a ValueError: core loops that skip a pair on ValueError
    must not swallow a download failure as a research result.
    """


_DOWNLOAD_ERROR_MARKERS = ("No data was returned", "The download failed")
_lock = threading.Lock()


@lru_cache(maxsize=256)
def _cached_download(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    try:
        data = backtester.download_data(ticker, start_date, end_date)
    except ValueError as error:
        if any(marker in str(error) for marker in _DOWNLOAD_ERROR_MARKERS):
            raise MarketDataError(str(error)) from error
        raise
    except Exception as error:  # yfinance / network failures
        raise MarketDataError(
            f"Market data for '{ticker}' could not be downloaded: {error}"
        ) from error

    if data is None or data.empty:
        raise MarketDataError(f"No data was returned for ticker '{ticker}'.")
    return data


def download_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Drop-in replacement for backtester.download_data with caching."""
    key = (str(ticker).upper().strip(), str(start_date), str(end_date))
    # yfinance is not reliably thread-safe; serialise downloads (cache hits
    # are cheap, so the lock costs nothing noticeable).
    with _lock:
        data = _cached_download(*key)
    return data.copy(deep=True)


def prepare_market_data(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Cached equivalent of backtester.prepare_market_data."""
    return backtester.calculate_returns(download_data(ticker, start_date, end_date))


def install() -> None:
    comparison.prepare_market_data = prepare_market_data
    pairs_trading_core.download_data = download_data


def clear() -> None:
    _cached_download.cache_clear()
    pairs_trading_core._prepare_pair_data_cached.cache_clear()
