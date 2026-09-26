import SwiftUI
import WebKit

/// Spillet kører i en fuldskærms-webview, der loader `game.html` fra app-bundlen.
///
/// Det, der betyder noget for spillet:
/// - `WKWebsiteDataStore.default()`: vedvarende lagring, så spillerens save
///   (localStorage) overlever mellem sessioner.
/// - Ingen rubber-band, ingen scrollbar — spillet skal føles som et spil, ikke en webside.
/// - Webviewen ligger inden for safe area (ikke under statuslinje/home-streg).
///   "Papir"-baggrunden bagved matcher spillets baggrund, så kanterne blander sig.
struct GameWebView: UIViewRepresentable {
    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        // Webviews' default-lager er midlertidigt — uden denne linje
        // glemmer spillet gemt fremskridt, når appen lukkes.
        configuration.websiteDataStore = WKWebsiteDataStore.default()

        let paperColor = UIColor(red: 0xEE / 255, green: 0xFA / 255, blue: 0xF4 / 255, alpha: 1)

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.isOpaque = true
        // Samme "papir"-farve som spillet — intet hvidt blink ved start.
        webView.backgroundColor = paperColor
        webView.scrollView.backgroundColor = paperColor
        // Spillet har et fast layout: ingen gummiband, ingen scrollbar.
        webView.scrollView.bounces = false
        webView.scrollView.alwaysBounceVertical = false
        webView.scrollView.showsVerticalScrollIndicator = false
        webView.scrollView.showsHorizontalScrollIndicator = false

        guard let url = Bundle.main.url(forResource: "game", withExtension: "html") else {
            assertionFailure("game.html ikke fundet i app-bundlen — mangler regeneratoring?")
            return webView
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {}

    final class Coordinator {}
}

struct GameView: View {
    var body: some View {
        ZStack {
            // "Papiret" bag webviewen (synligt i safe area langs kanterne).
            Color("LaunchBackground")
                .ignoresSafeArea()
            GameWebView()
        }
        // Spillet har fastt light-tema — statuslinjens tekst skal også være mørk.
        .preferredColorScheme(.light)
    }
}
