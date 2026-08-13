# Raspberry Pi shutter + milky-flat server (`rpi/`)

## Context

The shutter and the milky-flat diffuser are the two WINERED-only mechanisms. On
the instrument they hang off the Beckhoff rack's EL2084 and are driven through
`adc_winered` — PLC outputs, `mechanisms` topic, `set_shutter` /
`set_milky_flat`, and the browser panel `web/mechanisms.html`.

Milky flats also need taking on a bench that has the two mechanisms and **no
PLC**: a Raspberry Pi (`wr-pi`) with the shutter and diffuser on relays.

**Goal:** the same operator experience — same web page, same gestures — with a
Pi in place of the rack, and nothing to install on the operator's machine.

## Hardware

Relays on the Pi header, BCM numbering:

| Pin | Load | Behaviour |
|---|---|---|
| D26 | Enable — 12 V feed to both mechanisms | Asserted at startup, held for the life of the service |
| D13 | Milky-flat diffuser | Follows `set_milky_flat` |
| D6 | Shutter | Follows `set_shutter` |

Neither mechanism has a position sensor, exactly as on the PLC. Reported
positions are the commanded ones.

Two polarities are physical facts of the bench that software cannot discover,
so both are configuration, not constants:

- **Electrical** (`WR_ACTIVE_HIGH`) — whether driving a pin high energizes the
  relay. Opto-isolated relay boards are usually active-low.
- **Mechanical** (`WR_SHUTTER_ENERGIZED_POS`, `WR_MILKY_FLAT_ENERGIZED_POS`) —
  which position each mechanism holds while energized. The other value is the
  powered-down state.

## Constraints found on `wr-pi`

Checked before designing the deployment:

- Debian 13 (trixie), Python 3.13, user `pi` in group `gpio`, `/dev/gpiochip0`
  present.
- `python3-gpiozero` and `python3-lgpio` installed from apt.
- `python3-websockets` **not** installed.
- **No internet.** DNS fails for `deb.debian.org` and `pypi.org`.

So the install path cannot `apt-get update` or reach PyPI. `websockets` has to
arrive with the deployment, and it has a pure-Python wheel (`py3-none-any`) —
the workstation downloads it once, the deploy carries it over, and the Pi
installs it offline from a local `--find-links` directory.

## Design

### Server

A standalone package `rpi/wr_mechanisms/`, deliberately sharing no imports with
`adc_winered` (no pyads, no controller, no TCS on this box). It speaks the same
protocol, advertising `app: "ADC"` with `topics: ["mechanisms"]` and only the
`version` / `set_shutter` / `set_milky_flat` commands. The advertised topic list
is already the capability signal the panel gates on, so a client sees exactly
what this box can do and no more.

The cost of independence is `protocol.py`, a trimmed copy of
`src/adc_winered/ws/envelope.py`. Cheap, and the alternative — installing the
ADC server on the Pi — is not.

Modules: `config` (env vars) → `gpio` (relay backends, real + sim) →
`mechanisms` (relay state ⇄ positions) → `commands` → `server`.

### The panel ships with the server

Operators reach the Pi from any browser on the bench network, so the page has to
be served, not copied around. It is served **by the same process, on the same
port** (52403): `websockets`' `process_request` hook answers plain HTTP `GET`
and lets upgrade requests through to the WebSocket handler. One port, one
service, one thing to start.

The page is `web/mechanisms.html` itself — symlinked into the package as
`wr_mechanisms/static/mechanisms.html`, resolved to a real file by `rsync -L`
at deploy time. One page, one behaviour, both deployments; no forked copy to
drift.

For this to work when served, the page must default its connection target to
where it was loaded from. `host` becomes `location.hostname` (falling back to
`localhost` for `file://`), while the port default stays 52403 — the ADC server
is reached through a static server on a different port, so inheriting
`location.port` would break that path.

### Deployment

`rpi/deploy/deploy.sh <host>` (default `wr-pi`) rsyncs the tree to the Pi and
runs `install.sh` there under sudo. `install.sh` is offline-only:

- verify `gpiozero` / `lgpio` import; fail with the apt command if not.
- venv at `/opt/wr-mechanisms/venv` with `--system-site-packages`, so the
  apt-installed GPIO stack is visible.
- `pip install --no-index --find-links deploy/wheels websockets`.
- run from source (`PYTHONPATH=/opt/wr-mechanisms/src`) rather than installing
  the package — a build backend would need the network.
- `/etc/default/wr-mechanisms` written only when absent, so Pi-side polarity
  edits survive re-deploys.
- systemd unit, `SupplementaryGroups=gpio`, `Restart=always`.

Re-running is the upgrade path.

## Phases

1. **Server + tests + docs.** `rpi/` package, sim relay backend, protocol
   round-trip tests, `rpi/README.md`. *(landed)*
2. **Serve the panel from the service.** `process_request` HTTP handler, the
   symlinked static asset, `location`-derived default host in
   `web/mechanisms.html`, tests for both routes.
3. **Deploy and verify on `wr-pi`.** Deploy, then check the service, the page
   over HTTP, a `set_*` round-trip over WS, and the pin levels with `pinctrl`
   — the one check that proves the relays actually moved. *(done: D26 high from
   startup, D6 and D13 following `set_shutter` / `set_milky_flat`, service
   enabled and surviving restart)*

## Verification

Off-hardware: `uv run pytest rpi/tests` — protocol surface, relay bookkeeping
(pin mapping, enable-first/enable-last ordering, both polarity knobs), and the
HTTP routes, all against `SimRelays`.

On `wr-pi`: `pinctrl get 6,13,26` after each command. The relay state is the
only thing the software can be wrong about *silently*, and it is the one thing
`pinctrl` can confirm independently.

## Risks

- **Polarity.** Both knobs default to a guess (`active_high=true`, energized =
  shutter open / diffuser in). Wrong values are silent — no sensor contradicts
  them. Confirm by eye on the bench before an observing run.
- **Restart drops 12 V.** Stop, restart, or power loss de-energizes enable, so
  the mechanisms fall back to their unpowered rest positions. Deliberate: a
  stopped service should not leave a latched bench. Note this differs from the
  PLC rack, whose inverted EL2084 wiring rests at shutter closed, diffuser *in
  beam*.
- **No auth, no TLS.** Same as the ADC server (v1). Anyone on the bench network
  can drive the mechanisms.
