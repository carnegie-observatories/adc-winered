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

### Over Wi-Fi, with no cable

The Pi also runs its own Wi-Fi access point, so it can be used at the
instrument with nothing plugged into its Ethernet port:

| | |
|---|---|
| Network (SSID) | `wr_mech` |
| Password | WPA2; ask the instrument team (not kept in this repo) |
| Panel | `http://10.8.96.62:52403/` — the same URL as on the wire |
| Fallback | `http://192.168.52.1:52403/` |

Join `wr_mech` from a laptop or phone and open the panel. The device gets an
address in `192.168.52.10–100` from the Pi.

**Local only.** The network reaches the Pi and nothing else: there is no
internet and no LCO network behind it, and no DNS server, so expect the device
to report "no internet connection" and stay joined anyway. The Pi does not
route between Wi-Fi and Ethernet (`net.ipv4.ip_forward` stays `0`), even with
the cable plugged in.

**Why the wired address works over Wi-Fi.** The Pi carries `10.8.96.62` on
the Wi-Fi interface as well (a `/32` alongside `192.168.52.1/24`), and DHCP
hands out the Pi as the default gateway. Requests for `10.8.96.62` therefore go
to the Pi, which answers them because the address is its own. This still works
with no cable, when the Ethernet port has no address. The panel opens its
WebSocket back to whichever host it was loaded from, so either URL works.

**If `10.8.96.62` doesn't load on a phone**, use `http://192.168.52.1:52403/`.
Phones on a Wi-Fi network with no internet often keep mobile data as the
default route, so traffic for any address outside the Wi-Fi subnet (and
`10.8.96.62` is outside it) goes over mobile data. Turning mobile data off
fixes that too. A laptop with only the Wi-Fi up has no such problem.

The access point is always on, whether or not the cable is in. SSH works over
it too (`ssh pi@192.168.52.1`), so anyone with the Wi-Fi password can reach the
Pi's login prompt.

It is set up by [`deploy/wifi-ap.sh`](deploy/wifi-ap.sh), which runs once on
the Pi and is safe to re-run (see [Deploy](#deploy)). Its parts:

- NetworkManager connection `wr_mech`: AP mode on `wlan0`, 2.4 GHz channel 6,
  WPA2-PSK, method `manual` with `192.168.52.1/24` + `10.8.96.62/32`, IPv6
  off. It is deliberately not NetworkManager's `shared` method, because that
  method turns on IP forwarding and NAT to the Ethernet side.
- `wr-mech-dhcp.service` runs a dnsmasq instance that does DHCP only
  (`--port=0` turns off DNS), bound to `wlan0`. Leases are in
  `/var/lib/misc/wr-mech-dhcp.leases`.
- The Wi-Fi radio is switched on (`nmcli radio wifi on`). Raspberry Pi OS ships
  with it off, and NetworkManager remembers the setting across reboots. The
  regulatory country (`CL`) comes from the kernel command line.

**Booting with no cable.** The wired address is set by the kernel itself
(`ip=10.8.96.62::…` in `/boot/firmware/cmdline.txt`), and by default the
kernel then waits up to 120 s for an Ethernet link ("Waiting up to 100 more
seconds for network"). That would hold the access point back for two minutes
on every cable-less boot, so `carrier_timeout=5` is added to the same line. A
plugged-in cable gets a link well within 5 s. The original file is kept as
`cmdline.txt.bak-pre-carrier-timeout`. This is a one-off edit on the Pi, not
something `wifi-ap.sh` does. `cmdline.txt` must stay a single line.

To check on it, or to switch it off:

```sh
ssh wr-pi 'nmcli -f GENERAL.STATE,IP4.ADDRESS device show wlan0'
ssh wr-pi 'journalctl -u wr-mech-dhcp -f'      # who joined, which address
ssh wr-pi 'sudo nmcli connection down wr_mech'  # off until next boot
ssh wr-pi 'sudo nmcli connection delete wr_mech && sudo systemctl disable --now wr-mech-dhcp'  # off for good
```

The script prompts for the WPA2 passphrase, which is never stored in this
repo; set `PSK=` in the environment to skip the prompt. To change the SSID,
passphrase or channel, re-run it (with `SSID=` or `CHANNEL=` set as needed).
It deletes the old connection and creates a new one.

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
  Which position each mechanism holds while its relay **coil** is energized.
  Both mechanisms run through their **normally-closed** contacts, so energizing
  the coil *removes* 12 V: the shutter closes and the diffuser drops into the
  beam (`closed` / `in`). Flip both if the contacts ever go back to
  normally-open.
- **`WR_ENABLE_ENERGIZED`** — whether the enable relay has to be energized to
  pass 12 V. `true` for a normally-open contact (the default, and what D26 is
  wired to); `false` for normally-closed, where the 12 V is live whenever the
  coil is off — including while this service is stopped.

Re-check by eye after any rewiring. There is no sensor to catch a mistake, and
a wrong polarity is silent.

**Fail state.** Stopping the service (or losing power) de-energizes the
mechanism coils and then the enable coil. Because enable is normally-open, that
cuts 12 V to both mechanisms whatever their own contacts are doing, and the
bench falls back to what the unpowered actuators rest in: shutter **closed**,
diffuser **in beam**. That matches the PLC rack, whose EL2084 channels are
wired inverted to land in the same place, so the panel's footer holds for both
deployments. A service restart briefly drops the enable line too.

Note the enable relay is what makes this true. Moving it to a normally-closed
contact would leave 12 V live with the service stopped, and the mechanisms'
own NC contacts would then hold them *powered* — shutter open, diffuser out —
which is the opposite fail state. Set `WR_ENABLE_ENERGIZED=false` if that
rewiring ever happens, and re-read this paragraph.

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

The Wi-Fi access point ([Over Wi-Fi](#over-wi-fi-with-no-cable)) is a
separate, one-time step, because it is network configuration rather than part
of the service. `deploy.sh` copies the script over but doesn't run it:

```sh
ssh -t wr-pi 'sudo bash ~/wr-mechanisms-src/deploy/wifi-ap.sh'
```

Re-running `deploy.sh` is the upgrade path. Then:

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
| `deploy/` | systemd unit, env template, install + deploy scripts, bundled wheel, Wi-Fi AP script |

This package deliberately shares no imports with `adc_winered` — it installs on
a Pi that has no pyads and no PLC. The cost is `protocol.py`, a trimmed copy of
`src/adc_winered/ws/envelope.py`; if the envelope changes in the spec, both
files move together.
