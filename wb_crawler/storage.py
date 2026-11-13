"""Save trades per ISIN and day, merging with what is already on disk."""
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

KEY = "(MiFID II) TIC"  # unique trade id


def _read(path, fmt):
    if not path.exists():
        return None
    if fmt == "parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, parse_dates=["Trading Date Time", "Publication Date Time"])


def _write(df, path, fmt):
    if fmt == "parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)


def save(df, isin, out_dir, day, fmt="csv"):
    """Append `df` to <out_dir>/<day>/<isin>.<fmt>, dropping duplicate trades. Returns rows on disk."""
    folder = Path(out_dir) / day
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{isin}.{fmt}"

    old = _read(path, fmt)
    if old is not None:
        df = pd.concat([old, df], ignore_index=True)
    if KEY in df:
        df = df.drop_duplicates(subset=KEY, keep="last")
    df = df.sort_values("Trading Date Time") if "Trading Date Time" in df else df

    _write(df, path, fmt)
    return len(df)


def save_combined(out_dir, day, fmt="csv"):
    """Rebuild all_trades.<fmt> for the day from the per-ISIN files."""
    folder = Path(out_dir) / day
    parts = [_read(p, fmt) for p in sorted(folder.glob(f"*.{fmt}")) if not p.stem.startswith("all_trades")]
    parts = [p for p in parts if p is not None and not p.empty]
    if not parts:
        return None
    path = folder / f"all_trades.{fmt}"
    _write(pd.concat(parts, ignore_index=True), path, fmt)
    return path
