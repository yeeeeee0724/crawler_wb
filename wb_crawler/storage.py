"""Save rows per ISIN and day, merging with what is already on disk."""
import logging
from pathlib import Path

import pandas as pd

from .parser import QUOTE_TIME, TIME_COLUMNS

log = logging.getLogger(__name__)

KEY = "(MiFID II) TIC"  # unique trade id (both Posttrade tabs)
# Quotes (Pretrade Exchange) have no id, so a quote is identified by its time, prices and volumes
QUOTE_KEY = [
    "isin", QUOTE_TIME, "Best Ask Price", "Best Ask Volume", "Best Ask Number of Orders",
    "Best Bid Price", "Best Bid Volumne", "Best Bid Number Of Orders",
]
ID_COLUMNS = [KEY, "Trade Key"]  # long numeric ids: keep as text so they are not rounded
COMBINED = "all"


def _read(path, fmt):
    if not path.exists():
        return None
    if fmt == "parquet":
        return pd.read_parquet(path)
    columns = pd.read_csv(path, nrows=0).columns
    return pd.read_csv(
        path,
        dtype={c: str for c in ID_COLUMNS if c in columns},
        parse_dates=[c for c in TIME_COLUMNS + [QUOTE_TIME] if c in columns],
    )


def _write(df, path, fmt):
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)


def _dedupe_columns(df):
    if KEY in df:
        return [KEY]
    return [c for c in QUOTE_KEY if c in df] or None


def save(df, isin, folder, fmt="csv"):
    """Append `df` to <folder>/<isin>.<fmt>, dropping duplicate rows. Returns rows on disk."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{isin}.{fmt}"

    old = _read(path, fmt)
    if old is not None:
        df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(subset=_dedupe_columns(df), keep="last")
    for col in ("Trading Date Time", QUOTE_TIME):
        if col in df:
            df = df.sort_values(col)
            break

    _write(df, path, fmt)
    return len(df)


def save_combined(folder, fmt="csv"):
    """Rebuild all.<fmt> in `folder` from the per-ISIN files."""
    folder = Path(folder)
    parts = [_read(p, fmt) for p in sorted(folder.glob(f"*.{fmt}")) if p.stem != COMBINED]
    parts = [p for p in parts if p is not None and not p.empty]
    if not parts:
        return None
    path = folder / f"{COMBINED}.{fmt}"
    _write(pd.concat(parts, ignore_index=True), path, fmt)
    return path
