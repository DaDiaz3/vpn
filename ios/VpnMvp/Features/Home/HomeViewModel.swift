import Foundation

@MainActor final class HomeViewModel: ObservableObject {
    @Published private(set) var servers: [VPNServer] = []
    @Published private(set) var state = VPNState.disconnected
    @Published var errorMessage: String?
    private let api: APIClient
    private let keys = WireGuardKeyStore()
    private let vpn = VPNController()
    init(api: APIClient) { self.api = api }
    func loadServers() async { do { servers = try await api.servers().servers } catch { errorMessage = "Unable to load VPN servers" } }
    func connect(to server: VPNServer) async { state = .connecting; do { let keys = try keys.loadOrCreate(); let config = try await api.provision(serverID: server.id, publicKey: keys.publicKey); await vpn.connect(configuration: config); state = vpn.state } catch { state = .error("Unable to connect") } }
    func disconnect() { vpn.disconnect(); state = .disconnecting }
}
