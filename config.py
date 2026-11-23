"""Settings for the Wiener Börse crawler."""

BASE_URL = "https://prices.wienerboerse.at"
SIGNALR_URL = BASE_URL + "/signalr"
HUB_NAME = "stockhub"

# Tab indices on the page (#tab-content<N>)
TAB_POSTTRADE_EXCHANGE = 1
TAB_PRETRADE_EXCHANGE = 2
TAB_POSTTRADE_OTC = 3
TAB_PRETRADE_OTC = 4

# Tabs the crawler can download: name (used for --tabs and the output folder) -> tab index
TABS = {
    "posttrade-exchange": TAB_POSTTRADE_EXCHANGE,
    "pretrade-exchange": TAB_PRETRADE_EXCHANGE,
    "posttrade-otc": TAB_POSTTRADE_OTC,
}

# Filter key for the ISIN text field (from GetFilter)
FILTER_ISIN = "ISn"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
REQUEST_TIMEOUT = 40        # seconds; long-poll can hold a request open
POLL_TIMEOUT = 60           # max seconds to wait for a hub reply
DELAY_BETWEEN_CALLS = 1.5   # seconds between hub calls on one connection, be polite
MAX_RETRIES = 4
WORKERS = 3                 # parallel connections; each pretrade page costs the server ~5s, keep this small
# Incremental runs: stop paging once a page is older than the newest row on disk minus this
OVERLAP_MINUTES = 15

OUTPUT_DIR = "data"
