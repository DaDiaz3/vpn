# iOS real-device test checklist

- Configure Apple Developer signing and unique development bundle IDs.
- Add the official `wireguard-apple` Swift package to the app and tunnel targets.
- Enable Network Extension `packet-tunnel-provider` and a shared App Group/Keychain access group.
- Set the backend base URL to an HTTPS deployment and ensure a real WireGuard node is reachable.
- Register/login, choose a server, provision, and accept the VPN permission prompt.
- Connect and verify `NEVPNStatus.connected`, public IP change, and traffic through the tunnel.
- Disconnect, reconnect using the same credential, and restart the app while connected.
- Confirm no private key appears in backend requests, logs, UserDefaults, or API responses.
