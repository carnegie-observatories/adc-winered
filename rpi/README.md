# wr-mechanisms — shutter + milky flat on a Raspberry Pi

A standalone server that drives the WINERED shutter and milky-flat diffuser from
a Raspberry Pi's GPIO, with no PLC anywhere in the picture. It speaks the same
protocol as the PLC-backed server in [`../src/adc_winered`](../src/adc_winered)
**and serves the operator panel itself**, on the same port — so the whole thing
is one URL:

```
http://wr-pi:52403/
```

The point is milky flats: taking them over the usual web interface on a bench
that has the two mechanisms but no Beckhoff rack.

## Reaching it

`wr-pi` is an SSH alias, not a DNS name — a browser needs the address:

```
http://10.8.96.62:52403/          # on the LCO network / VPN
```

From anywhere that only has SSH to the Pi (e.g. through `officevpn`), forward
the port and use localhost — the panel connects back through the same tunnel,
since it targets the host it was served from:

```sh
ssh -N -L 52403:127.0.0.1:52403 wr-pi
# then: http://localhost:52403/
```

## What it exposes

| | |
|---|---|
| Panel | `http://wr-pi:52403/` — [`web/mechanisms.html`](../web/mechanisms.html), served by the service |
| Endpoint | `ws://wr-pi:52403` — same port as the ADC server |
| `hello` | `app: "ADC"`, `topics: ["mechanisms"]` |
| Topic | `mechanisms` → `{shutter: "open"\|"closed", milky_flat: "in"\|"out"}` |
| Commands | `version`, `set_shutter {pos}`, `set_milky_flat {pos}` |
| Health | `GET /healthz` → `ok` |

The page and the socket share port 52403: `websockets`' `process_request` hook
answers plain HTTP `GET`s and lets upgrade requests through
([`wr_mechanisms/http.py`](wr_mechanisms/http.py)). One service, one port,
nothing to install on the operator's machine.

The served page is not a copy — `wr_mechanisms/static/mechanisms.html` is a
symlink to the repo's `web/mechanisms.html`, resolved to a real file by
`rsync -L` at deploy time, so the Pi and the PLC deployments can't drift apart.
The page defaults its connection host to wherever it was loaded from.

Nothing else. There is no `status`, `lens`, `telescope` or `logs` topic here,
and the ADC commands (`move_lens`, `set_control_mode`, …) ack with
`invalid_argument`. That is what the advertised topic list is for: the panel
gates itself on `mechanisms` appearing in `hello.topics`, and the canonical
client won't offer ADC windows a bare Pi can't serve.

Neither mechanism has a position sensor, so a reported position is the last
thing commanded — same as on the PLC.

## Wiring

BCM pin numbering (the "D" numbers in the wiring notes are BCM GPIO numbers):

| Pin | Load | Behaviour |
|---|---|---|
| D26 | Enable — 12 V feed to both mechanisms | Asserted at startup, held for the life of the service |
| D13 | Milky-flat diffuser | Follows `set_milky_flat` |
| D6 | Shutter | Follows `set_shutter` |

Two independent polarities, both configurable, because both are physical facts
of the bench rather than something the code can discover:

- **`WR_ACTIVE_HIGH`** — electrical. True when driving a GPIO *high* energizes
  the relay. **False on `wr-pi`**, and that is the default: driving D26 high
  left the 12 V enable off, so the board is active-low, as opto-isolated relay
  boards usually are. Energized therefore reads as a *low* pin.
- **`WR_SHUTTER_ENERGIZED_POS` / `WR_MILKY_FLAT_ENERGIZED_POS`** — mechanical.
  Which position each mechanism holds while its relay is energized. On `wr-pi`,
  confirmed by eye: energizing **opens** the shutter and **retracts** the
  diffuser (`open` / `out`). The diffuser is the counter-intuitive one — it is
  driven out of the beam, not into it.

Re-check both by eye after any rewiring. There is no sensor to catch a mistake,
and a wrong polarity is silent.

**Fail state.** Stopping the service (or losing power) de-energizes the
mechanism relays and then the enable line, cutting 12 V — the bench falls back
to whatever the unpowered actuators rest in: shutter **closed**, diffuser **in
beam**. That matches the PLC rack, whose EL2084 channels are wired inverted to
land in the same place, so the panel's footer holds for both deployments. A
service restart briefly drops the enable line too.

This survives the process going away entirely, which is not automatic on an
active-low board: when the pins are released they revert to inputs, and on
`wr-pi` they then read **high** — de-energized — because the relay board pulls
them up. Measured with the service stopped (`pinctrl get 6,13,26` → `ip pn |
hi` on all three). Worth re-checking if the relay board is ever swapped: a
board without that pull-up would energize everything the moment the service
stopped.

## Deploy

From a workstation with SSH access to the Pi:

```sh
rpi/deploy/deploy.sh          # defaults to host "wr-pi"
rpi/deploy/deploy.sh some-other-host
```

That rsyncs this directory to `~/wr-mechanisms-src` on the Pi and runs
[`deploy/install.sh`](deploy/install.sh) there under sudo, which:

1. checks that apt's `python3-gpiozero` / `python3-lgpio` are importable and
   that the service user is in the `gpio` group;
2. syncs the source to `/opt/wr-mechanisms/src`;
3. builds `/opt/wr-mechanisms/venv` with `--system-site-packages` (so the venv
   sees those apt-installed GPIO libraries) and installs `websockets` from
   [`deploy/wheels/`](deploy/wheels);
4. writes `/etc/default/wr-mechanisms` **only if absent** — local edits survive
   re-deploys;
5. installs and starts `wr-mechanisms.service`.

**The install is offline.** `wr-pi` has no route to `deb.debian.org` or
`pypi.org`, so nothing here runs `apt-get update` or reaches PyPI. That is why
the pure-Python `websockets` wheel is committed under `deploy/wheels/` and
carried over by the deploy, and why the service runs from the synced source
(`PYTHONPATH=/opt/wr-mechanisms/src`) instead of being pip-installed — a build
backend would have to come from PyPI. To move to a newer `websockets`, drop a
new `websockets-*-py3-none-any.whl` in `deploy/wheels/`, delete
`/opt/wr-mechanisms/venv` on the Pi, and re-deploy.

Re-running it is the upgrade path. Then:

```sh
ssh wr-pi 'systemctl status wr-mechanisms'
ssh wr-pi 'journalctl -u wr-mechanisms -f'
ssh wr-pi 'sudo systemctl restart wr-mechanisms'
```

## Configure

All settings are environment variables, read at startup by
[`wr_mechanisms/config.py`](wr_mechanisms/config.py); on the Pi they live in
`/etc/default/wr-mechanisms` (template: [`deploy/wr-mechanisms.env`](deploy/wr-mechanisms.env)).

| Var | Default | Meaning |
|---|---|---|
| `WR_WS_HOST` | `0.0.0.0` | Bind address |
| `WR_WS_PORT` | `52403` | Bind port |
| `WR_GPIO_MODE` | `real` | `sim` drives no pins — for testing off-hardware |
| `WR_PIN_ENABLE` | `26` | 12 V enable |
| `WR_PIN_MILKY_FLAT` | `13` | Diffuser relay |
| `WR_PIN_SHUTTER` | `6` | Shutter relay |
| `WR_ACTIVE_HIGH` | `true` | GPIO high energizes the relay |
| `WR_SHUTTER_ENERGIZED_POS` | `open` | Position held while energized |
| `WR_MILKY_FLAT_ENERGIZED_POS` | `in` | Position held while energized |
| `WR_LOG_LEVEL` | `INFO` | Root log level |

A bad value is fatal at startup rather than at the first command.

## Run it by hand

On the Pi (stop the service first — two processes can't share the port):

```sh
sudo systemctl stop wr-mechanisms
cd /opt/wr-mechanisms/src && ../venv/bin/python -m wr_mechanisms serve
```

Anywhere else, with no hardware:

```sh
cd rpi && WR_GPIO_MODE=sim python3 -m wr_mechanisms serve
# then: open http://localhost:52403/
```

To confirm what the pins are actually doing, from a shell on the Pi:

```sh
pinctrl get 6,13,26          # 6 = shutter, 13 = milky flat, 26 = enable
```

That is the only independent check on the relays — nothing else on this box can
contradict a wrong polarity setting.

## Test it

```sh
uv run pytest rpi/tests        # from the repo root
```

The suite runs the real server against `SimRelays`, covering the protocol
surface (hello, subscribe, acks, unknown commands), the relay bookkeeping (pin
mapping, enable-first/enable-last ordering, both polarity knobs), and the HTTP
routes that serve the panel. No hardware, no Pi.

## Layout

| Path | Contents |
|---|---|
| `wr_mechanisms/config.py` | Env-var settings |
| `wr_mechanisms/gpio.py` | Relay backends — gpiozero and sim |
| `wr_mechanisms/mechanisms.py` | Relay state → mechanism positions |
| `wr_mechanisms/protocol.py` | Wire format, mirrored from `adc_winered.ws.envelope` |
| `wr_mechanisms/commands.py` | `version` / `set_shutter` / `set_milky_flat` |
| `wr_mechanisms/server.py` | WebSocket server for the `mechanisms` topic |
| `wr_mechanisms/http.py` | Plain-HTTP routes on the same port — the panel, `/healthz` |
| `wr_mechanisms/static/` | Symlink to `web/mechanisms.html` |
| `deploy/` | systemd unit, env template, install + deploy scripts, bundled wheel |

This package deliberately shares no imports with `adc_winered` — it installs on
a Pi that has no pyads and no PLC. The cost is `protocol.py`, a trimmed copy of
`src/adc_winered/ws/envelope.py`; if the envelope changes in the spec, both
files move together.
