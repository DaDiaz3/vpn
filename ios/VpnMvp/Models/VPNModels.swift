import Foundation

struct AuthenticatedUser: Codable { let id: UUID; let email: String; let status: String }
struct AuthResponse: Codable { let access_token: String; let user: AuthenticatedUser }
struct VPNServer: Codable, Identifiable { let id: UUID; let name: String; let country: String; let city: String; let status: String; let latency_ms: Double?; let load_percent: Double?; let active_users: Int? }
struct ServerList: Codable { let servers: [VPNServer] }
struct ProvisionRequest: Codable { let server_id: UUID; let public_key: String }
struct ProvisionResponse: Codable { let credential_id: UUID; let server: ProvisionedServer; let client: ClientAddress; let dns: [String]; let allowed_ips: [String]; let persistent_keepalive: Int }
struct ProvisionedServer: Codable { let id: UUID; let country: String; let city: String; let endpoint: String; let `public_key`: String }
struct ClientAddress: Codable { let address: String }
