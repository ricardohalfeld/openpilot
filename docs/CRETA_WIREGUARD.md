# WireGuard on comma 3X — experimental

Branch: `creta-v11-wireguard`, created directly from `creta-v11`.

## Design
- A managed, optional supervisor runs on comma hardware.
- It attempts `wg-quick up /data/wireguard/wg0.conf` only if both `wg` and `wg-quick` are present and the configuration exists with permissions 0600.
- If `wg0` already exists, it does not touch the interface.
- No private key, VPN password, or VPN endpoint is checked into Git.
- It does not change openpilot lateral or longitudinal control.
- This prototype does **not** install WireGuard kernel support, `wg`, or `wg-quick`; whether they are available under AGNOS must be checked on the device.
- This has **not** been tested on comma 3X, and wg-quick may require additional privileges.

## Example client configuration (illustrative; do not commit secrets)

Your existing WireGuard VPN reportedly uses an Oracle server at `10.10.0.1/24` and a WSL peer at `10.10.0.2`. If still accurate, allocate the comma a **new, unused address**, for example `10.10.0.3/32`:

```ini
[Interface]
PrivateKey = <COMMA_PRIVATE_KEY>
Address = 10.10.0.3/32

[Peer]
PublicKey = <ORACLE_SERVER_PUBLIC_KEY>
Endpoint = <ORACLE_PUBLIC_HOST_OR_IP>:<UDP_PORT>
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
```

Use `AllowedIPs = 10.10.0.0/24` for split tunneling so normal comma connectivity is not diverted into your VPN. Check that this matches the server's actual configuration. On the Oracle server add the comma's *public* key with `AllowedIPs = 10.10.0.3/32`. Open the relevant UDP port on the server/firewall. Never reuse WSL private keys or duplicate its VPN address.

Place the configuration at `/data/wireguard/wg0.conf` with `chmod 600` (and a private parent directory). Keeping the configuration in `/data` avoids shipping secrets with branch updates.

## Validation while stationary
1. Confirm WireGuard support: `command -v wg; command -v wg-quick; uname -a`.
2. Confirm interface: `wg show`.
3. Confirm a handshake with Oracle: `wg show wg0 latest-handshakes`.
4. Test reachability to `10.10.0.1` while checking normal internet access remains operational.
5. If the configuration, binaries or privileges are absent, the service stays inactive.

This initial branch is a development prototype, **not yet a one-tap installer**. Do not replace the daily-driving branch until testing.
