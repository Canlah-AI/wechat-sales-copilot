// Local OCR via Apple Vision. Usage: ocr <image.png>  → JSON lines {text, conf, x, y, w, h} in image pixels (top-left origin)
import AppKit
import Vision

guard CommandLine.arguments.count > 1,
      let img = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("usage: ocr <image>\n".data(using: .utf8)!); exit(1)
}
let W = CGFloat(cg.width), H = CGFloat(cg.height)
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.recognitionLanguages = ["zh-Hans", "en-US"]
req.usesLanguageCorrection = true
try VNImageRequestHandler(cgImage: cg).perform([req])
for obs in req.results ?? [] {
    guard let top = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    let row: [String: Any] = [
        "text": top.string, "conf": Double(top.confidence),
        "x": Int(b.minX * W), "y": Int((1 - b.maxY) * H), "w": Int(b.width * W), "h": Int(b.height * H),
    ]
    let d = try JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
    print(String(data: d, encoding: .utf8)!)
}
