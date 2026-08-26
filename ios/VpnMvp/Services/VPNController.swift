import Foundation
import NetworkExtension

enum VPNState: Equatable { case disconnected, connecting, connected, disconnecting, error(String) }

@MainActor final class VPNController: ObservableObject {
    @Published private(set) var state: VPNState = .disconnected
    private var manager: NETunnelProviderManager?
    private var observer: NSObjectProtocol?
    func load() async throws { let managers = try await NETunnelProviderManager.loadAllFromPreferences(); manager = managers.first; observer = NotificationCenter.default.addObserver(forName: .NEVPNStatusDidChange, object: manager?.connection, queue: .main) { [weak self] _ in self?.updateState() }; updateState() }
    func connect(configuration: ProvisionResponse) async {
        state = .connecting
        do { let manager = manager ?? NETunnelProviderManager(); let proto = NETunnelProviderProtocol(); proto.providerBundleIdentifier = "com.example.vpnmvp.tunnel"; proto.serverAddress = configuration.server.endpoint; proto.providerConfiguration = ["serverPublicKey": configuration.server.public_key, "address": configuration.client.address, "dns": configuration.dns, "allowedIPs": configuration.allowed_ips, "keepalive": configuration.persistent_keepalive]; manager.protocolConfiguration = proto; manager.localizedDescription = "VPN MVP"; manager.isEnabled = true; try await manager.saveToPreferences(); try await manager.loadFromPreferences(); self.manager = manager; try manager.connection.startVPNTunnel() } catch { state = .error("Unable to start VPN") }
    }
    func disconnect() { state = .disconnecting; manager?.connection.stopVPNTunnel() }
    private func updateState() { switch manager?.connection.status { case .connected: state = .connected; case .connecting, .reasserting: state = .connecting; case .disconnecting: state = .disconnecting; default: state = .disconnected } }
}
