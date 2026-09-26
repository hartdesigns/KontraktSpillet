// Tegner app-ikonet (1024×1024).
// App Store vil have et kvadrat, der fylder hele lærredet (ingen afrunding, ingen alpha) —
// det er Apple, der selv afrunder. Designet matcher spillet: kontraktkort med clip og check.
//
// Brug: swift Tools/make-icon.swift [out.png]

import CoreGraphics
import Foundation
import ImageIO

let S = 1024

func c(_ r: Int, _ g: Int, _ b: Int, _ a: CGFloat = 1) -> CGColor {
    CGColor(red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255, alpha: a)
}

let dark = c(0x1d, 0x2b, 0x3a)
let berry = c(0xc2, 0x18, 0x5b)
let yellow = c(0xff, 0xd8, 0x4d)
let white = c(0xff, 0xff, 0xff)

let space = CGColorSpace(name: CGColorSpace.sRGB)!
guard let ctx = CGContext(
    data: nil, width: S, height: S,
    bitsPerComponent: 8, bytesPerRow: 0,
    space: space,
    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
) else {
    fatalError("Kunne ikke oprette billedkontekst")
}

// Skærmkoordinationer (y vokser nedad)
ctx.translateBy(x: 0, y: CGFloat(S))
ctx.scaleBy(x: 1, y: -1)

// Baggrund: fuldt fladebærret berry
ctx.setFillColor(berry)
ctx.fill(CGRect(x: 0, y: 0, width: S, height: S))

ctx.saveGState()
ctx.translateBy(x: CGFloat(S) / 2, y: CGFloat(S) / 2)
ctx.rotate(by: -6 * .pi / 180)

// Skygge under kortet
ctx.setShadow(offset: CGSize(width: 12, height: 18), blur: 30, color: c(0, 0, 0, 0.28))

// Kontrakten: hvidt kort med tyk kant
let card = CGRect(x: -285, y: -330, width: 570, height: 660)
let cardPath = CGPath(roundedRect: card, cornerWidth: 60, cornerHeight: 60, transform: nil)
ctx.addPath(cardPath)
ctx.setFillColor(white)
ctx.fillPath()
ctx.addPath(cardPath)
ctx.setStrokeColor(dark)
ctx.setLineWidth(22)
ctx.strokePath()

ctx.setShadow(offset: .zero, blur: 0, color: nil)

// Bindsnabel i toppen
let tab = CGRect(x: -75, y: -372, width: 150, height: 84)
let tabPath = CGPath(roundedRect: tab, cornerWidth: 24, cornerHeight: 24, transform: nil)
ctx.addPath(tabPath)
ctx.setFillColor(berry)
ctx.fillPath()
ctx.addPath(tabPath)
ctx.setStrokeColor(dark)
ctx.setLineWidth(18)
ctx.strokePath()

// Linjerede tekst
ctx.setLineCap(.round)
func hline(_ x0: CGFloat, _ y: CGFloat, _ x1: CGFloat, _ w: CGFloat) {
    let p = CGMutablePath()
    p.move(to: CGPoint(x: x0, y: y))
    p.addLine(to: CGPoint(x: x1, y: y))
    ctx.addPath(p)
    ctx.setStrokeColor(dark)
    ctx.setLineWidth(w)
    ctx.strokePath()
}
hline(-185, -195, 185, 30)
hline(-185, -125, 60, 30)

// Stor gul check med tyk mørk kant — icoets hjerte
let check = CGMutablePath()
check.move(to: CGPoint(x: -150, y: 45))
check.addLine(to: CGPoint(x: -40, y: 155))
check.addLine(to: CGPoint(x: 165, y: -70))
ctx.setLineJoin(.round)
ctx.addPath(check)
ctx.setStrokeColor(dark)
ctx.setLineWidth(185)
ctx.strokePath()
ctx.addPath(check)
ctx.setStrokeColor(yellow)
ctx.setLineWidth(110)
ctx.strokePath()

ctx.restoreGState()

guard let image = ctx.makeImage() else { fatalError("Kunne ikke rendere ikonet") }
let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "AppIcon.png"
let url = URL(fileURLWithPath: (out as NSString).expandingTildeInPath)
guard let dest = CGImageDestinationCreateWithURL(url as CFURL, "public.png" as CFString, 1, nil) else {
    fatalError("Kunne ikke oprette PNG-fil")
}
CGImageDestinationAddImage(dest, image, nil)
guard CGImageDestinationFinalize(dest) else { fatalError("Kunne ikke skrive PNG") }
print("OK: skrev \(url.path) (\(image.width)x\(image.height))")
