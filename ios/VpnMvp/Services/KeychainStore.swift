import Foundation
import Security

final class KeychainStore {
    static let shared = KeychainStore()
    private let service = "com.example.vpnmvp"
    private let accessGroup = "$(AppIdentifierPrefix)com.example.vpnmvp.shared"
    func save(_ value: Data, for key: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: key, kSecAttrAccessGroup as String: accessGroup, kSecValueData as String: value]
        SecItemDelete(query as CFDictionary)
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw NSError(domain: NSOSStatusErrorDomain, code: Int(errSecItemNotAdded)) }
    }
    func load(_ key: String) -> Data? { let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: key, kSecAttrAccessGroup as String: accessGroup, kSecReturnData as String: true]; var item: AnyObject?; SecItemCopyMatching(query as CFDictionary, &item); return item as? Data }
    func delete(_ key: String) { let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: key, kSecAttrAccessGroup as String: accessGroup]; SecItemDelete(query as CFDictionary) }
}
