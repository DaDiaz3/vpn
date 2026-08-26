import Foundation

enum WireGuardKeyError: Error { case libraryUnavailable, invalidStoredKey }

/// WireGuardKit is the only key generator used by the app target. No Curve25519 code lives here.
struct WireGuardKeyStore {
    private let keychain = KeychainStore.shared
    func loadOrCreate() throws -> (privateKey: String, publicKey: String) {
        if let data = keychain.load("wireguard-private-key"), let value = String(data: data, encoding: .utf8) {
            #if canImport(WireGuardKit)
            let key = try WireGuardKit.PrivateKey(base64Key: value)
            return (value, key.publicKey.base64Key)
            #else
            throw WireGuardKeyError.libraryUnavailable
            #endif
        }
        #if canImport(WireGuardKit)
        let key = WireGuardKit.PrivateKey()
        let value = key.base64Key
        try keychain.save(Data(value.utf8), for: "wireguard-private-key")
        return (value, key.publicKey.base64Key)
        #else
        throw WireGuardKeyError.libraryUnavailable
        #endif
    }
}
