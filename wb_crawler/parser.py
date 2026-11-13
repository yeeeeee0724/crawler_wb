"""Turn raw hub rows into a clean DataFrame."""
import pandas as pd

TIME_COLUMNS = ["Trading Date Time", "Publication Date Time"]
NUMERIC_COLUMNS = [
    "Traded Price", "Traded Quantity", "Quantity in measurement unit",
    "Volume Weighted Average APA", "Total Traded Volume APA",
    "Total Number Transactions APA", "Nominal Value",
]


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

    for col in NUMERIC_COLUMNS:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
