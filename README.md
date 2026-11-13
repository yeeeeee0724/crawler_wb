# Wiener Börse crawler

This crawler downloads today's data from <https://prices.wienerboerse.at/> for a list of ISINs, from three tabs:

| Tab (`--tabs` name) | What one row is | Duplicates removed by |
|---|---|---|
| `posttrade-exchange` | A trade on the Vienna exchange | `(MiFID II) TIC` |
| `pretrade-exchange` | A best bid/ask quote on the Vienna exchange | Quote time, prices and volumes (quotes have no id) |
| `posttrade-otc` | A trade outside the exchange (OTC) | `(MiFID II) TIC` |

## Usage
Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`).
```bash
uv sync                                               # create .venv and install deps
uv run main.py --isins isins.txt                      # all three tabs
uv run main.py --tabs posttrade-otc posttrade-exchange  # skip the large pretrade tab
uv run --extra parquet main.py --format parquet -v    # parquet output (adds pyarrow), debug logging
```

Output goes to one folder per day and tab:
```
data/<YYYY-MM-DD>/<tab>/<ISIN>.csv   # one file per ISIN
data/<YYYY-MM-DD>/<tab>/all.csv      # all ISINs combined
```

## How it works
The page fills its tables through an ASP.NET SignalR hub (`/signalr`, hub `stockhub`), so the crawler talks to that hub directly. It doesn't need a browser. Every tab uses the same `GetData` call. Only the tab number changes.

| File | Job |
|---|---|
| `pyproject.toml` / `uv.lock` | Dependencies, managed by uv. |
| `isins.txt` | Input: one ISIN per line. Anything after `#` is ignored. |
| `config.py` | URLs, tab numbers, delays and retries. |
| `wb_crawler/signalr_client.py` | Generic SignalR 2 long-polling client (negotiate → connect → start → send/poll). |
| `wb_crawler/otc_api.py` | Hub calls for this site (any tab): `GetDataLength`, `GetFilter`, `GetData`, and paging. |
| `wb_crawler/parser.py` | Cleans the raw rows: splits the ISIN out, parses UTC timestamps, converts numbers. |
| `wb_crawler/storage.py` | Saves files per tab, ISIN and day, and removes duplicates. |
| `main.py` | CLI that ties the steps together. |

## Notes
- The site only shows the **current trading day**, 15 minutes delayed, in UTC. To build a history, schedule the crawler (for example with cron, every 15–30 minutes during trading hours or once in the evening). Running it again is safe because duplicates are removed.
- The exchange tabs only list instruments traded on the Vienna exchange. An ISIN that only trades OTC has 0 rows there.
- **`pretrade-exchange` is large and slow.** Each quote change is a row, and the server takes several seconds per page of 100. A liquid stock can have thousands of quotes a day (for example, Sanofi had about 6,000 by mid-afternoon, which took about 8 minutes). Use `--tabs` to skip it when you don't need quotes.
