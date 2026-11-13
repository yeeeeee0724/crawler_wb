"""Crawl Posttrade OTC trades from prices.wienerboerse.at for a list of ISINs.

Usage:
    python main.py --isins isins.txt [--out data] [--format csv|parquet]
"""
import argparse
import logging
import re
import time
from datetime import datetime, timezone

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

    summary = {}
    with SignalRClient() as client:
        api = WienerBoerseAPI(client)
        for isin in isins:
            try:
                header, rows = api.fetch_all(isin)
            except Exception as e:
                log.error("%s: failed (%s)", isin, e)
                summary[isin] = "ERROR"
                continue
            df = parser.to_dataframe(header, rows)
            summary[isin] = storage.save(df, isin, args.out, day, args.format) if not df.empty else 0
            time.sleep(config.DELAY_BETWEEN_CALLS)

    combined = storage.save_combined(args.out, day, args.format)

    print("\nISIN           rows (today, on disk)")
    for isin, n in summary.items():
        print(f"{isin}   {n}")
    if combined:
        print(f"\ncombined file: {combined}")


if __name__ == "__main__":
    main()
