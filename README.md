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
- **Runs are incremental.** Rows come newest first, so once an ISIN is saved for the day, later runs stop paging at rows older than the newest saved row minus `OVERLAP_MINUTES` (15, in `config.py`). The overlap catches rows published a little late; the duplicates it brings are removed. The first run of the day is always full. Use `--full` to fetch every page anyway, for example at the end of the day.
- **Jobs run in parallel.** Each (tab, ISIN) pair is one job, spread over `WORKERS` (3, in `config.py`, or `--workers N`) connections; each connection still pages one ISIN in order. The server gets slower when it has more requests at once (a pretrade page took ~5.5 s alone and ~11.5 s with 3 workers), so 3 workers are about 1.6× faster than 1, and more workers mostly add load on the exchange's server.
- Pretrade can send identical quote rows (about 20–30% of a page for liquid Vienna stocks). They are indistinguishable, so they are stored once; rows on disk can therefore be fewer than the site's row count.
- The exchange tabs only list instruments traded on the Vienna exchange. An ISIN that only trades OTC has 0 rows there.
- **`pretrade-exchange` is large and slow.** Each quote change is a row, and the server takes several seconds per page of 100. A liquid stock can have thousands of quotes a day (for example, Sanofi had about 6,000 by mid-afternoon, which took about 8 minutes). Use `--tabs` to skip it when you don't need quotes.
