"""Crawl prices.wienerboerse.at for a list of ISINs.

Tabs: posttrade-exchange, pretrade-exchange and posttrade-otc (all three by default).

Usage:
    python main.py --isins isins.txt [--tabs posttrade-otc ...] [--out data] [--format csv|parquet]
"""
import argparse
import logging
import re
import time
from datetime import datetime, timezone
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--isins", default="isins.txt", help="file with one ISIN per line")
    ap.add_argument("--tabs", nargs="+", choices=list(config.TABS), default=list(config.TABS),
                    help="which tabs to crawl (default: all)")
    ap.add_argument("--out", default=config.OUTPUT_DIR, help="output folder")
    ap.add_argument("--format", choices=["csv", "parquet"], default="csv")
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
    combined = []
    with SignalRClient() as client:
        api = WienerBoerseAPI(client)
        for tab_name in args.tabs:
            tab = config.TABS[tab_name]
            folder = Path(args.out) / day / tab_name
            for isin in isins:
                try:
                    header, rows = api.fetch_all(isin, tab)
                except Exception as e:
                    log.error("%s (%s): failed (%s)", isin, tab_name, e)
                    summary[isin][tab_name] = "ERROR"
                    continue
                df = parser.to_dataframe(header, rows)
                summary[isin][tab_name] = storage.save(df, isin, folder, args.format) if not df.empty else 0
                time.sleep(config.DELAY_BETWEEN_CALLS)
            path = storage.save_combined(folder, args.format)
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
