"""Crawl prices.wienerboerse.at for a list of ISINs.

Tabs: posttrade-exchange, pretrade-exchange and posttrade-otc (all three by default).

Usage:
    python main.py --isins isins.txt [--tabs posttrade-otc ...] [--out data] [--format csv|parquet] [--full] [--workers N]

Runs are incremental: for an ISIN already saved today, paging stops once it reaches
rows older than the newest saved row minus config.OVERLAP_MINUTES. --full fetches every page.
(tab, ISIN) jobs run on --workers parallel connections.
"""
import argparse
import logging
import queue
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
from wb_crawler import parser, storage
from wb_crawler.otc_api import WienerBoerseAPI
from wb_crawler.signalr_client import SignalRClient

ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
log = logging.getLogger("crawler")


def read_isins(path):
    isins = []
    with open(path) as f:
        for line in f:
            isin = line.split("#", 1)[0].strip().upper()
            if not isin:
                continue
            if not ISIN_RE.match(isin):
                log.warning("skipping invalid ISIN: %r", isin)
                continue
            if isin not in isins:
                isins.append(isin)
    return isins


def crawl_one(api, isin, tab_name, folder, args):
    """Fetch and save one ISIN on one tab. Returns rows on disk, or "ERROR"."""
    stop_before = None
    if not args.full:
        latest = storage.latest_time(isin, folder, args.format)
        if latest is not None:
            stop_before = latest - timedelta(minutes=config.OVERLAP_MINUTES)
    try:
        header, rows = api.fetch_all(isin, config.TABS[tab_name], stop_before)
    except Exception as e:
        log.error("%s (%s): failed (%s)", isin, tab_name, e)
        return "ERROR"
    df = parser.to_dataframe(header, rows)
    return storage.save(df, isin, folder, args.format) if not df.empty else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--isins", default="isins.txt", help="file with one ISIN per line")
    ap.add_argument("--tabs", nargs="+", choices=list(config.TABS), default=list(config.TABS),
                    help="which tabs to crawl (default: all)")
    ap.add_argument("--out", default=config.OUTPUT_DIR, help="output folder")
    ap.add_argument("--format", choices=["csv", "parquet"], default="csv")
    ap.add_argument("--full", action="store_true", help="fetch every page, even for ISINs already saved today")
    ap.add_argument("--workers", type=int, default=config.WORKERS,
                    help=f"parallel connections (default: {config.WORKERS})")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

    isins = read_isins(args.isins)
    if not isins:
        log.error("no valid ISINs in %s", args.isins)
        return
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    summary = {isin: {} for isin in isins}
    jobs = queue.Queue()
    # Slow pretrade jobs first, so the quick ones fill in at the end instead of one long job running alone
    for tab_name in sorted(args.tabs, key=lambda t: t != "pretrade-exchange"):
        for isin in isins:
            jobs.put((tab_name, isin))

    def worker():
        # Each worker has its own SignalR connection; one connection can't be shared between threads
        try:
            client = SignalRClient()
            client.connect()
        except Exception as e:
            log.error("worker could not connect (%s)", e)
            return
        try:
            api = WienerBoerseAPI(client)
            while True:
                try:
                    tab_name, isin = jobs.get_nowait()
                except queue.Empty:
                    return
                folder = Path(args.out) / day / tab_name
                summary[isin][tab_name] = crawl_one(api, isin, tab_name, folder, args)
                time.sleep(config.DELAY_BETWEEN_CALLS)
        finally:
            client.close()

    threads = [threading.Thread(target=worker) for _ in range(min(args.workers, jobs.qsize()))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    combined = []
    for tab_name in args.tabs:
        path = storage.save_combined(Path(args.out) / day / tab_name, args.format)
        if path:
            combined.append(path)

    print("\nRows today, on disk:")
    print(f"{'ISIN':<14}" + "".join(f"{t:>20}" for t in args.tabs))
    for isin, counts in summary.items():
        print(f"{isin:<14}" + "".join(f"{counts.get(t, '-'):>20}" for t in args.tabs))
    if combined:
        print("\ncombined files:")
        for path in combined:
            print(f"  {path}")


if __name__ == "__main__":
    main()
