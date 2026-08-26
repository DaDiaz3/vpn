# iOS source layout

`VpnMvp/` is the application target and `VpnMvpTunnel/` is the Packet Tunnel Provider extension target. Add the official WireGuardKit Swift package from `https://git.zx2c4.com/wireguard-apple` to both targets in Xcode. `WireGuardKeyStore` uses WireGuardKit's `PrivateKey` and stores only its base64 private key in the shared Keychain; the backend receives only `publicKey`.

The provider receives configuration through `NETunnelProviderProtocol.providerConfiguration` and applies Network Extension settings. The production target must connect this point to WireGuardKit's `WireGuardAdapter` (the adapter and WireGuardKitGo must be embedded in the extension target); the repository intentionally does not vendor cryptographic code or generate fallback keys.
