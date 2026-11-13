"""Minimal ASP.NET SignalR 2 client using the long-polling transport.

Protocol: negotiate -> connect -> start, then `send` hub calls and `poll`
for messages the server pushes back to the client.
"""
import json
import logging
import time

import requests

import config

log = logging.getLogger(__name__)


class SignalRError(Exception):
    pass


class SignalRClient:
    def __init__(self, url=config.SIGNALR_URL, hub=config.HUB_NAME):
        self.url = url
        self.hub = hub
        self.connection_data = json.dumps([{"name": hub}])
        self.session = None
        self.token = None
        self.message_id = None
        self.call_id = 0

    # --- connection -------------------------------------------------------

    def connect(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.call_id = 0

        nego = self._request("negotiate", {"clientProtocol": "1.5", "connectionData": self.connection_data})
        self.token = nego["ConnectionToken"]
        self.message_id = self._request("connect", self._base_params()).get("C")
        self._request("start", self._base_params())
        log.debug("SignalR connected")

    def close(self):
        if self.session is None:
            return
        try:
            self._request("abort", self._base_params(), data={})
        except Exception:
            pass
        self.session.close()
        self.session = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()

    # --- hub calls --------------------------------------------------------

    def invoke(self, method, args, expect):
        """Call a hub method and return the arguments of the `expect` callback."""
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                return self._invoke_once(method, args, expect)
            except (requests.RequestException, SignalRError, ValueError) as e:
                if attempt == config.MAX_RETRIES:
                    raise
                wait = 2 ** attempt
                log.warning("%s failed (%s), reconnecting in %ss", method, e, wait)
                time.sleep(wait)
                self.connect()

    def _invoke_once(self, method, args, expect):
        if self.session is None:
            self.connect()
        self.call_id += 1
        payload = {"H": self.hub, "M": method, "A": args, "I": self.call_id}
        reply = self._request("send", self._base_params(), data={"data": json.dumps(payload)})
        if "E" in reply:
            raise SignalRError(f"{method}: {reply['E']}")

        deadline = time.time() + config.POLL_TIMEOUT
        while time.time() < deadline:
            for msg in self._poll():
                if msg.get("M", "").lower() == expect.lower():
                    return msg["A"]
        raise SignalRError(f"no '{expect}' reply to {method} within {config.POLL_TIMEOUT}s")

    def _poll(self):
        params = {**self._base_params(), "messageId": self.message_id}
        reply = self._request("poll", params, data={})
        if reply.get("D") == 1:
            raise SignalRError("server asked to disconnect")
        self.message_id = reply.get("C", self.message_id)
        return reply.get("M", [])

    # --- helpers ----------------------------------------------------------

    def _base_params(self):
        return {
            "transport": "longPolling",
            "clientProtocol": "1.5",
            "connectionToken": self.token,
            "connectionData": self.connection_data,
        }

    def _request(self, endpoint, params, data=None):
        url = f"{self.url}/{endpoint}"
        if data is None:
            r = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        else:
            r = self.session.post(url, params=params, data=data, timeout=config.REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json() if r.content else {}
