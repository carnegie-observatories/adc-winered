# Browser UIs

Three ways to drive the server from a browser. The first two are general
diagnostic surfaces; the third is a single-purpose operations page.

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

## 3. Mechanisms panel — `web/mechanisms.html`

A dedicated control page for the two WINERED-only mechanisms: the shutter and the milky-flat diffuser. Nothing else — no rotators, no slides, no tracking — so it can be left open on a bench display or a phone during calibrations.

```sh
python3 -m http.server 8000 --directory web
# open http://localhost:8000/mechanisms.html?host=<host>&port=52403
```

Same conventions as the diagnostic page: single self-contained file, no build, `host` / `port` from the URL query or the input fields.

What it does:

- Subscribes to the `mechanisms` topic only, and drives `set_shutter` / `set_milky_flat`.
- Shows each mechanism's state as a word plus an indicator dot, lit in the light-blocking position (shutter closed, diffuser in beam).
- Marks a button *pending* between the command and the server's echo, and reports it if no confirmation arrives within 6 s.
- Surfaces `ack.ok == false` errors (e.g. `plc_unreachable`) in place rather than failing silently.
- Reconnects on its own with a capped backoff, so a server restart doesn't need a page reload.
- Refuses to pretend: if the connected server doesn't advertise the `mechanisms` topic it shows a banner and disables the controls. Every ADC server shares the `adc` app tag and port 52403, so that advertisement is the only honest signal that these mechanisms exist on the instrument you're talking to.

Because neither mechanism has a position sensor, everything on the page reflects the *commanded* state. The footer says so, along with the de-energized fail state (shutter closed, diffuser in beam).

## When the UIs diverge

The standalone diagnostic page is hand-mirrored from `lco-instrument-web/diagnostic.js`. If a new command lands in the canonical registry, mirror it in `web/diagnostic.html`'s `COMMANDS` array. The server side is the source of truth for what's actually implemented — keep `ws/commands.py` aligned with all three UIs.

`web/mechanisms.html` is deliberately *not* mirrored from the canonical client: the canonical client covers what every ADC has, and these two mechanisms exist only here.
