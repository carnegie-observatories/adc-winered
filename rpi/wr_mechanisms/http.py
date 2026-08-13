"""Plain-HTTP handler bolted onto the WebSocket port.

`websockets` hands every incoming request to `process_request` before the
upgrade handshake. Returning `None` lets a WebSocket connection through;
returning a `Response` answers it as ordinary HTTP. That is enough to serve the
operator panel from the same process and the same port as the socket it talks
to — one service to install, one port to open, no static file server on the
bench.

Routes:

    GET /                    -> the mechanisms panel
    GET /mechanisms.html     -> same page
    GET /healthz             -> "ok", for `systemctl`-adjacent poking
"""

from __future__ import annotations

import http
import logging
from pathlib import Path

from websockets.datastructures import Headers
from websockets.http11 import Request, Response

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
PANEL = STATIC_DIR / "mechanisms.html"

PANEL_ROUTES = ("/", "/index.html", "/mechanisms.html")


def process_request(connection: object, request: Request) -> Response | None:
    """Return a `Response` for plain HTTP, or `None` to accept the upgrade."""
    if request.headers.get("Upgrade"):
        return None  # a WebSocket handshake — not ours to answer

    path = request.path.split("?", 1)[0]

    if path in PANEL_ROUTES:
        try:
            body = PANEL.read_bytes()
        except OSError as exc:
            # The page is packaged next to the code, so this means a broken
            # install rather than a bad request. Say which, and where.
            log.error("cannot read %s: %s", PANEL, exc)
            return _text(http.HTTPStatus.INTERNAL_SERVER_ERROR, f"panel unavailable: {exc}\n")
        return _response(http.HTTPStatus.OK, "text/html; charset=utf-8", body)

    if path == "/healthz":
        return _text(http.HTTPStatus.OK, "ok\n")

    return _text(http.HTTPStatus.NOT_FOUND, "not found\n")


def _text(status: http.HTTPStatus, body: str) -> Response:
    return _response(status, "text/plain; charset=utf-8", body.encode())


def _response(status: http.HTTPStatus, content_type: str, body: bytes) -> Response:
    headers = Headers({
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
        # The panel is edited far more often than it is deployed, and a stale
        # cached copy on a bench display is a support call.
        "Cache-Control": "no-store",
    })
    return Response(status.value, status.phrase, headers, body)
