Change IP address of PLC to static IP address
--------------------------------------------

ENGLAB IP (temporary): 10.7.45.150
mac: 00:01:05:ab:f7:9a

```bash
sudo nano /etc/systemd/network/10-end0-static.network
```

```
[Match]
Name=end0

[Network]
Address=10.8.104.50/24
Gateway=10.8.104.1
```


