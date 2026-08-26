import SwiftUI

struct ContentView: View {
    var body: some View {
        VStack(spacing: 16) { Text("VPN MVP").font(.title); Text("Disconnected"); Button("Connect") {} }
    }
}

#Preview {
    ContentView()
}
