"""Turn raw hub rows into a clean DataFrame."""
import pandas as pd

TIME_COLUMNS = ["Trading Date Time", "Publication Date Time"]
NUMERIC_COLUMNS = [
    "Traded Price", "Traded Quantity", "Quantity in measurement unit",
    "Volume Weighted Average APA", "Total Traded Volume APA",
    "Total Number Transactions APA", "Nominal Value",
    # Pretrade Exchange (the "Volumne" typo is the site's own column name)
    "Best Ask Price", "Best Ask Volume", "Best Ask Number of Orders",
    "Best Bid Price", "Best Bid Volumne", "Best Bid Number Of Orders",
]
QUOTE_TIME = "Quote Date Time"  # Pretrade Exchange: built from its separate Date and Time columns


def to_dataframe(header, rows):
    df = pd.DataFrame(rows, columns=header)
    if df.empty:
        return df

    df = df.replace("-", pd.NA)

    # "-/FR0000120578" -> name="-" (missing), isin="FR0000120578"
    name_isin = df.pop("NameISIN").fillna("")
    df.insert(0, "isin", name_isin.str.split("/").str[-1])
    name = name_isin.str.rpartition("/")[0]
    df.insert(1, "name", name.where(~name.isin(["", "-"])))

    # "(2026-11-12)T10:26:14.013000Z" -> UTC timestamp
    for col in TIME_COLUMNS:
        if col in df:
            df[col] = pd.to_datetime(df[col].str.replace(r"[()]", "", regex=True), utc=True, errors="coerce", format="ISO8601")

    # Pretrade Exchange: "11/13/2026" + "14:36:33.820" -> one UTC timestamp
    if "Date" in df and "Time" in df:
        stamp = pd.to_datetime(df.pop("Date") + " " + df.pop("Time"), utc=True, errors="coerce", format="%m/%d/%Y %H:%M:%S.%f")
        df.insert(2, QUOTE_TIME, stamp)

    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def time_column(df):
    """The column that orders rows in time ("Trading Date Time" or the quote time), or None."""
    for col in (TIME_COLUMNS[0], QUOTE_TIME):
        if col in df:
            return col
    return None


def oldest_time(header, rows):
    """Earliest row time in one raw page, or None."""
    df = to_dataframe(header, rows)
    col = time_column(df)
    return df[col].min() if col and not df.empty else None
