# Diagnostic UIs

Two ways to drive the server from a browser:

## 1. Canonical client — `lco-instrument-web`

The site-wide UI. Use this when you're at a workstation that has `lco-instrument-web` checked out and running.

```sh
cd /Users/william/workspace/lco-instrument-web
python3 server.py            # serves the SPA on http://localhost:8080/
# open http://localhost:8080/?host=<adc-host>&port=52403
```

The client's `APP_REGISTRY` (`diagnostic.js`) already has an entry keyed `ADC` with the canonical command list. The server's `hello` frame announces `app: "ADC"`, so the diagnostic and main-window views pick up the right registry without further configuration.

## 2. Standalone — `web/diagnostic.html`

A single self-contained HTML file in this repo. No build, no framework, no dependencies. Use this on the bench, in a tmux session, or any time you don't want to spin up the full canonical client.

```sh
# from the repo root:
python3 -m http.server 8000 --directory web
# open http://localhost:8000/diagnostic.html?host=<host>&port=52403
```

Or just open `web/diagnostic.html` directly in a browser — the page reads `host` / `port` from the URL query (or from the input fields at the top).

What it gives you:

- Connection status (`hello` info on connect).
- Live snapshots of the `status`, `lens`, and `telescope` topics.
- A button row per command from the canonical APP_REGISTRY, with the same arg-input shapes (select / number / bool) as `lco-instrument-web`.
- A scrolling log pane showing every sent / received frame.

It is **diagnostic only** — no main-window layout, no per-app polish. If you need the instrument-faithful UI, use the canonical client.

## When the two diverge

The standalone page is hand-mirrored from `lco-instrument-web/diagnostic.js`. If a new command lands in the canonical registry, mirror it in `web/diagnostic.html`'s `COMMANDS` array. The server side is the source of truth for what's actually implemented — keep `ws/commands.py` aligned with both UIs.
