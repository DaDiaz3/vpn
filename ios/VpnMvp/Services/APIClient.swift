import Foundation

actor APIClient {
    let baseURL: URL
    private let session: URLSession
    private let keychain: KeychainStore
    init(baseURL: URL, session: URLSession = .shared, keychain: KeychainStore = .shared) { self.baseURL = baseURL; self.session = session; self.keychain = keychain }
    private func request<T: Decodable, B: Encodable>(_ path: String, method: String = "GET", body: B? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path)); request.httpMethod = method; request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = keychain.load("access-token").flatMap({ String(data: $0, encoding: .utf8) }) { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body { request.httpBody = try JSONEncoder().encode(body) }
        let (data, response) = try await session.data(for: request); guard let http = response as? HTTPURLResponse, 200..<300 ~= http.statusCode else { throw URLError(.badServerResponse) }; return try JSONDecoder().decode(T.self, from: data)
    }
    func login(email: String, password: String) async throws -> AuthResponse { let result: AuthResponse = try await request("api/v1/auth/login", method: "POST", body: ["email": email, "password": password]); try keychain.save(Data(result.access_token.utf8), for: "access-token"); return result }
    func register(email: String, password: String) async throws -> AuthResponse { let result: AuthResponse = try await request("api/v1/auth/register", method: "POST", body: ["email": email, "password": password]); try keychain.save(Data(result.access_token.utf8), for: "access-token"); return result }
    func me() async throws -> AuthenticatedUser { try await request("api/v1/users/me") }
    func servers() async throws -> ServerList { try await request("api/v1/servers") }
    func provision(serverID: UUID, publicKey: String) async throws -> ProvisionResponse { try await request("api/v1/vpn/provision", method: "POST", body: ProvisionRequest(server_id: serverID, public_key: publicKey)) }
    func logout() { keychain.delete("access-token") }
}
