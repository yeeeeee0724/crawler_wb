"""Site-specific calls to the Wiener Börse `stockhub`."""
import json
import logging
import time

import config
from .signalr_client import SignalRClient

log = logging.getLogger(__name__)


class WienerBoerseAPI:
    def __init__(self, client: SignalRClient):
        self.client = client
        self._lengths = None

    def get_lengths(self, refresh=False):
        """Row count per tab; the server expects it back in GetData."""
        if self._lengths is None or refresh:
            (raw,) = self.client.invoke("GetDataLength", [], expect="saveLength")
            self._lengths = [int(x) for x in raw.split(";")]
        return self._lengths

    def get_filters(self, tab=config.TAB_POSTTRADE_OTC):
        (raw,) = self.client.invoke("GetFilter", [tab], expect="showFilter")
        return json.loads(raw)

    def fetch_page(self, isin, page=1, tab=config.TAB_POSTTRADE_OTC):
        length = self.get_lengths()[tab]
        filter_str = f"{config.FILTER_ISIN}{isin};"
        (raw,) = self.client.invoke("GetData", [tab, 0, filter_str, page, length], expect="handleStock")
        return json.loads(raw)

    def fetch_all(self, isin, tab=config.TAB_POSTTRADE_OTC):
        """Return (header, rows) for every page of trades for one ISIN."""
        first = self.fetch_page(isin, 1, tab)
        header, rows = first["Data"][0], first["Data"][1:]
        total, pages = first["AllDataCount"], first["AllPages"]
        log.info("%s: %d trades on %d page(s)", isin, total, pages)

        for page in range(2, pages + 1):
            time.sleep(config.DELAY_BETWEEN_CALLS)
            rows.extend(self.fetch_page(isin, page, tab)["Data"][1:])

        if total and len(rows) != total:
            log.warning("%s: expected %d rows, got %d", isin, total, len(rows))
        return header, rows
