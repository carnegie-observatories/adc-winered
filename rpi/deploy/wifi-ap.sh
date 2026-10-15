#!/usr/bin/env bash
# Turn the Pi's Wi-Fi into a local-only access point, so the panel can be
# reached with no network cable. Runs *on the Pi*, as root:
#
#   ssh -t wr-pi 'sudo bash ~/wr-mechanisms-src/deploy/wifi-ap.sh'
#
# The WPA2 passphrase is never stored in this repo: the script prompts for it
# (hence ssh -t), or takes it from PSK in the environment.
#
# Safe to re-run: the connection and the DHCP unit are rewritten in place.
#
# Local-only by construction. The AP is a plain `manual` NetworkManager
# connection, not `shared`: shared would switch on net.ipv4.ip_forward and NAT
# Wi-Fi clients onto the LCO network. Instead DHCP comes from a dedicated
# dnsmasq that serves addresses and nothing else (no DNS), and the Pi never
# forwards a packet between wlan0 and eth0.
#
# 10.8.96.62 (the Pi's wired address) is added to wlan0 as a /32, so the usual
# URL keeps working from the Wi-Fi side even when eth0 has no cable and so no
# address of its own.
set -euo pipefail

SSID=${SSID:-wr_mech}
PSK=${PSK:-}
CON=${CON:-wr_mech}
IFACE=${IFACE:-wlan0}
AP_ADDR=${AP_ADDR:-192.168.52.1}
WIRED_ADDR=${WIRED_ADDR:-10.8.96.62}
DHCP_RANGE=${DHCP_RANGE:-192.168.52.10,192.168.52.100,255.255.255.0,12h}
CHANNEL=${CHANNEL:-6}
DHCP_UNIT=wr-mech-dhcp

if [[ $EUID -ne 0 ]]; then
  echo "wifi-ap.sh must run as root (try: sudo $0)" >&2
  exit 1
fi

if [[ -z $PSK ]]; then
  if [[ ! -t 0 ]]; then
    echo "no passphrase: set PSK, or run with a terminal (ssh -t) to be prompted" >&2
    exit 1
  fi
  read -rsp "WPA2 passphrase for '$SSID': " PSK; echo
fi
if (( ${#PSK} < 8 || ${#PSK} > 63 )); then
  echo "WPA2 passphrase must be 8-63 characters" >&2
  exit 1
fi

echo "==> Wi-Fi radio on"
# Raspberry Pi OS ships with Wi-Fi soft-blocked until a country is set; the
# country (CL) is already on the kernel command line, the radio just needs
# enabling. NetworkManager persists this across reboots.
nmcli radio wifi on

echo "==> NetworkManager connection '$CON' (SSID $SSID on $IFACE)"
nmcli connection delete "$CON" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name "$CON" ssid "$SSID" \
  connection.autoconnect yes \
  connection.autoconnect-priority 100 \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel "$CHANNEL" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.proto rsn \
  wifi-sec.pairwise ccmp \
  wifi-sec.group ccmp \
  wifi-sec.pmf disable \
  wifi-sec.psk "$PSK" \
  ipv4.method manual \
  ipv4.addresses "$AP_ADDR/24,$WIRED_ADDR/32" \
  ipv4.never-default yes \
  ipv6.method disabled

echo "==> $DHCP_UNIT.service (dnsmasq, DHCP only)"
# port=0 disables DNS entirely. The router option points clients at the Pi so
# that 10.8.96.62 — off their subnet — is still sent here; with forwarding
# off, the Pi answers for its own addresses and drops everything else.
cat > /etc/systemd/system/$DHCP_UNIT.service <<EOF
[Unit]
Description=DHCP for the $SSID Wi-Fi access point (local only, no DNS)
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/dev/null \\
  --port=0 --interface=$IFACE --bind-dynamic --except-interface=lo \\
  --dhcp-range=$DHCP_RANGE --dhcp-option=option:router,$AP_ADDR \\
  --dhcp-authoritative --dhcp-leasefile=/var/lib/misc/$DHCP_UNIT.leases \\
  --log-dhcp
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 /etc/systemd/system/$DHCP_UNIT.service

systemctl daemon-reload
systemctl enable "$DHCP_UNIT"

echo "==> bringing the AP up"
nmcli connection up "$CON"
systemctl restart "$DHCP_UNIT"

sleep 2
nmcli -f GENERAL.STATE,IP4.ADDRESS device show "$IFACE" || true
systemctl --no-pager --lines=5 status "$DHCP_UNIT" || true
echo
echo "ip_forward = $(cat /proc/sys/net/ipv4/ip_forward)  (must be 0)"
echo "Done. Join '$SSID', then open http://$WIRED_ADDR:52403/"
echo "      (or http://$AP_ADDR:52403/ if a phone routes the other one over mobile data)"
