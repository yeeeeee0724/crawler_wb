# Wiener Börse Posttrade OTC crawler

This crawler downloads today's **Posttrade OTC** trades from <https://prices.wienerboerse.at/#tab-content3> for a list of ISINs.

## Usage
Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`).
```bash
uv sync                                               # create .venv and install deps
uv run main.py --isins isins.txt                      # writes data/<YYYY-MM-DD>/<ISIN>.csv + all_trades.csv
uv run --extra parquet main.py --format parquet -v    # parquet output (adds pyarrow), debug logging
```

## How it works
The page fills its table through an ASP.NET SignalR hub (`/signalr`, hub `stockhub`), so the crawler talks to that hub directly. It doesn't need a browser.

| File | Job |
|---|---|
| `pyproject.toml` / `uv.lock` | Dependencies, managed by uv. |
| `isins.txt` | Input: one ISIN per line. Anything after `#` is ignored. |
| `config.py` | URLs, tab numbers, delays and retries. |
| `wb_crawler/signalr_client.py` | Generic SignalR 2 long-polling client (negotiate → connect → start → send/poll). |
| `wb_crawler/otc_api.py` | Hub calls for this site: `GetDataLength`, `GetFilter`, `GetData`, and paging. |
| `wb_crawler/parser.py` | Cleans the raw rows: splits the ISIN out, parses UTC timestamps, converts numbers. |
| `wb_crawler/storage.py` | Saves files per ISIN and day, and removes duplicates on `(MiFID II) TIC`. |
| `main.py` | CLI that ties the steps together. |

## Notes
- The site only shows the **current trading day**, 15 minutes delayed. To build a history, schedule the crawler (for example with cron, every 15–30 minutes during trading hours or once in the evening). Running it again is safe because trades are de-duplicated by TIC.
- `GetData` also works for the other tabs (1 = Posttrade Exchange, 2 = Pretrade Exchange, 4 = Pretrade OTC) via the `tab` argument in `otc_api.py`.
