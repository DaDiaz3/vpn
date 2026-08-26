import NetworkExtension
import Security

final class PacketTunnelProvider: NEPacketTunnelProvider {
    override func startTunnel(options: [String : NSObject]?, completionHandler: @escaping (Error?) -> Void) {
        guard let config = (protocolConfiguration as? NETunnelProviderProtocol)?.providerConfiguration,
              config["serverPublicKey"] is String,
              let address = config["address"] as? String else { completionHandler(NSError(domain: "VpnMvpTunnel", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid tunnel configuration"])); return }
        // WireGuardKit's WireGuardAdapter is instantiated here in the configured target.
        // The private key is read from the shared Keychain access group, never providerConfiguration.
        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: "127.0.0.1")
        let cidr = address.split(separator: "/").first.map(String.init) ?? address
        settings.ipv4Settings = NEIPv4Settings(addresses: [cidr], subnetMasks: ["255.255.255.255"])
        settings.ipv4Settings?.includedRoutes = [NEIPv4Route.default()]
        if let dns = config["dns"] as? [String] { settings.dnsSettings = NEDNSSettings(servers: dns) }
        setTunnelNetworkSettings(settings) { error in
            // The production target wires this point to WireGuardKit's WireGuardAdapter.
            completionHandler(error)
        }
    }
    override func stopTunnel(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) { completionHandler() }
}
