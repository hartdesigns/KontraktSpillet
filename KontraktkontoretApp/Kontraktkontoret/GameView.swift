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
/// - `layoutWidth`/`scale`: på iPads, der er mindre end 12,9", får spillet en fast
///   layout-bredde via viewport-tagget og skaleres ned til rammen (se `GameView`).
///   `pageZoom` kan ikke bruges til det: den tegner siden mindre, men spillets layout
///   ser stadig den smalle skærm (`width=device-width`).
struct GameWebView: UIViewRepresentable {
    /// Den bredde (CSS-px), spillet skal lægge sit layout efter. `nil` = skærmens egen bredde.
    var layoutWidth: CGFloat?
    var scale: CGFloat = 1

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
        webView.navigationDelegate = context.coordinator
        context.coordinator.webView = webView
        context.coordinator.viewport = viewportContent

        guard let url = Bundle.main.url(forResource: "game", withExtension: "html") else {
            assertionFailure("game.html ikke fundet i app-bundlen — mangler regeneratoring?")
            return webView
        }
        webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.setViewport(viewportContent)
    }

    /// Indholdet af `<meta name="viewport">`, som spillet skal have.
    private var viewportContent: String {
        guard let layoutWidth, scale < 1 else {
            return "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover"
        }
        let s = String(format: "%.4f", Double(scale))
        return "width=\(Int(layoutWidth.rounded())), initial-scale=\(s), minimum-scale=\(s), maximum-scale=\(s), user-scalable=no, viewport-fit=cover"
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        weak var webView: WKWebView?
        var viewport = ""
        private var loaded = false

        func setViewport(_ content: String) {
            guard content != viewport else { return }
            viewport = content
            apply()
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loaded = true
            apply()
        }

        /// Skriver viewport-tagget i den indlæste side (siden kender ikke selv appens ramme).
        private func apply() {
            guard loaded, let webView else { return }
            let js = "document.querySelector('meta[name=viewport]').setAttribute('content', '\(viewport)');"
            webView.evaluateJavaScript(js)
        }
    }
}

struct GameView: View {
    /// Spillets layout er designet og testet på en 12,9" iPad Pro.
    /// Størrelserne er dens safe area i punkter (uden statuslinje og home-streg).
    private static let landscapeReference = CGSize(width: 1366, height: 980)
    private static let portraitReference = CGSize(width: 1024, height: 1322)

    var body: some View {
        ZStack {
            // "Papiret" bag webviewen (synligt i safe area langs kanterne).
            Color("LaunchBackground")
                .ignoresSafeArea()
            GeometryReader { geometry in
                let size = geometry.size
                let reference = size.width > size.height ? Self.landscapeReference : Self.portraitReference
                // På mindre iPads zoomes hele spillet ned, så det har mindst lige så meget
                // plads som på 12,9" — ellers ryger knapperne ud under skærmkanten.
                // Den bredde, der er tilovers, bruger spillet selv (indholdet centreres).
                let scale = max(0.5, min(1, size.width / reference.width, size.height / reference.height))
                GameWebView(layoutWidth: (size.width / scale).rounded(.down), scale: scale)
            }
        }
        // Spillet har fastt light-tema — statuslinjens tekst skal også være mørk.
        .preferredColorScheme(.light)
    }
}
