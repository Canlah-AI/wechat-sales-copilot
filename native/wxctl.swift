// Minimal input/window primitives for driving WeChat for Mac like a person would.
// No injection, no debugger, no re-signing: only window lookup, app activation, synthetic keys/clicks, pasteboard.
// Usage:
//   wxctl locked                     → 1 if the lock screen is up, else 0 (activate/key/click refuse while locked)
//   wxctl front                      → bundle id of the frontmost app
//   wxctl activate [bundleId]        → bring app to front (default WeChat); for WeChat, wait for main window
//   wxctl win [title]                → JSON {id, x, y, w, h, scale} of WeChat's main window, or of the window with that title
//   wxctl key <combo>                → e.g. cmd+f, enter, esc, cmd+v, cmd+a, backspace
//   wxctl click <x> <y>              → left click at screen point
//   wxctl rclick <x> <y>             → right click (context menu) at screen point
//   wxctl scroll <x> <y> <dy>        → move the pointer to x,y and scroll dy pixels (negative = further down the list)
//   wxctl clip-get / clip-set <text> → read / write the general pasteboard (plain text)
//   wxctl clip-image <png path>      → put an image file on the pasteboard (paste sends it as a picture)
//   wxctl clip-file <path>           → put a file on the pasteboard as Finder's Copy does (paste attaches the file itself)
//   wxctl nudge                      → a zero-distance pointer move: counts as activity so the screen does not lock
//   wxctl windows                    → title and size of every WeChat window (window-level AX; content AX is blind)
//   wxctl fit                        → move WeChat's main window to the top-left and make it 1300 wide, full height
//   wxctl close-window <title>       → press the close button of a popped-out chat window (never the main window)
//   wxctl perms                      → JSON {accessibility, screen_recording}: the grants this process inherited
import AppKit
import ApplicationServices
import CoreGraphics

let wechat = "com.tencent.xinWeChat"
let args = Array(CommandLine.arguments.dropFirst())
func fail(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }

let mainTitles: Set<String> = ["Weixin", "微信", "WeChat"]
func mainWindow(_ title: String? = nil) -> [String: Any]? {
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: wechat).first else { return nil }
    let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    var mine = list.filter {
        ($0[kCGWindowOwnerPID as String] as? Int32) == app.processIdentifier && ($0[kCGWindowLayer as String] as? Int) == 0
    }
    let named = mine.filter { title == nil ? mainTitles.contains($0[kCGWindowName as String] as? String ?? "") : ($0[kCGWindowName as String] as? String) == title }
    if title != nil || !named.isEmpty { mine = named }  // without names (no screen-recording access) fall back to the largest
    func area(_ w: [String: Any]) -> Double {
        let b = w[kCGWindowBounds as String] as? [String: Double] ?? [:]
        return (b["Width"] ?? 0) * (b["Height"] ?? 0)
    }
    guard let best = mine.max(by: { area($0) < area($1) }), area(best) > 400 * 300 else { return nil }
    let b = best[kCGWindowBounds as String] as? [String: Double] ?? [:]
    let rect = CGRect(x: b["X"] ?? 0, y: b["Y"] ?? 0, width: b["Width"] ?? 0, height: b["Height"] ?? 0)
    // backing scale of the screen holding the window centre (Cocoa screens are bottom-left based)
    let primaryH = NSScreen.screens.first?.frame.height ?? 0
    let centre = CGPoint(x: rect.midX, y: primaryH - rect.midY)
    let scale = NSScreen.screens.first(where: { $0.frame.contains(centre) })?.backingScaleFactor ?? 1
    return ["id": best[kCGWindowNumber as String] as? Int ?? 0, "x": rect.minX, "y": rect.minY,
            "w": rect.width, "h": rect.height, "scale": scale]
}

let keyCodes: [String: CGKeyCode] = [
    "a": 0, "f": 3, "v": 9, "c": 8, "w": 13, "enter": 36, "return": 36, "tab": 48, "space": 49,
    "backspace": 51, "esc": 53, "down": 125, "up": 126, "left": 123, "right": 124,
]
func key(_ combo: String) {
    let parts = combo.lowercased().split(separator: "+").map(String.init)
    guard let name = parts.last, let code = keyCodes[name] else { fail("unknown key \(combo)") }
    var flags: CGEventFlags = []
    for m in parts.dropLast() {
        switch m {
        case "cmd": flags.insert(.maskCommand)
        case "shift": flags.insert(.maskShift)
        case "alt", "opt": flags.insert(.maskAlternate)
        case "ctrl": flags.insert(.maskControl)
        default: fail("unknown modifier \(m)")
        }
    }
    let src = CGEventSource(stateID: .hidSystemState)
    for down in [true, false] {
        let e = CGEvent(keyboardEventSource: src, virtualKey: code, keyDown: down)
        e?.flags = flags
        e?.post(tap: .cghidEventTap)
        usleep(30_000)
    }
}
func scroll(_ x: Double, _ y: Double, _ dy: Int32) {
    let p = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
    usleep(80_000)
    // many small ticks at a steady pace, like a slow two-finger drag: keeps the distance proportional to dy
    var left = dy
    while left != 0 {
        let part = left > 0 ? min(left, 8) : max(left, -8)
        let e = CGEvent(scrollWheelEvent2Source: src, units: .pixel, wheelCount: 1, wheel1: part, wheel2: 0, wheel3: 0)
        e?.location = p
        e?.post(tap: .cghidEventTap)
        left -= part
        usleep(10_000)
    }
}
func click(_ x: Double, _ y: Double, right: Bool = false) {
    let p = CGPoint(x: x, y: y)
    let src = CGEventSource(stateID: .hidSystemState)
    CGEvent(mouseEventSource: src, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)?.post(tap: .cghidEventTap)
    usleep(60_000)
    let (down, up, button): (CGEventType, CGEventType, CGMouseButton) = right ? (.rightMouseDown, .rightMouseUp, .right) : (.leftMouseDown, .leftMouseUp, .left)
    for t in [down, up] {
        CGEvent(mouseEventSource: src, mouseType: t, mouseCursorPosition: p, mouseButton: button)?.post(tap: .cghidEventTap)
        usleep(50_000)
    }
}

// WeChat's windows through window-level AX (works even though the chat content is invisible to AX)
func axWindows() -> [(el: AXUIElement, title: String, size: CGSize)] {
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: wechat).first else { fail("not running: \(wechat)") }
    var v: CFTypeRef?
    AXUIElementCopyAttributeValue(AXUIElementCreateApplication(app.processIdentifier), kAXWindowsAttribute as CFString, &v)
    return ((v as? [AXUIElement]) ?? []).map { w in
        var t: CFTypeRef?, s: CFTypeRef?
        AXUIElementCopyAttributeValue(w, kAXTitleAttribute as CFString, &t)
        AXUIElementCopyAttributeValue(w, kAXSizeAttribute as CFString, &s)
        var sz = CGSize.zero
        if let s { AXValueGetValue(s as! AXValue, .cgSize, &sz) }
        return (w, t as? String ?? "", sz)
    }
}

func screenLocked() -> Bool {
    let d = CGSessionCopyCurrentDictionary() as? [String: Any] ?? [:]
    return (d["CGSSessionScreenIsLocked"] as? Bool ?? false)
        || NSWorkspace.shared.frontmostApplication?.bundleIdentifier == "com.apple.loginwindow"
}
// never type or click while the lock screen is up: keys would land in the password field
if ["activate", "key", "click", "rclick", "scroll", "fit", "close-window"].contains(args.first ?? ""), screenLocked() { fail("screen locked") }

switch args.first {
case "locked":
    print(screenLocked() ? "1" : "0")
case "perms":
    // both grants belong to the app that started this process (Terminal, iTerm, ...), not to wxctl itself
    print("{\"accessibility\": \(AXIsProcessTrusted()), \"screen_recording\": \(CGPreflightScreenCaptureAccess())}")
case "front":
    print(NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? "")
case "activate":
    let bid = args.count > 1 ? args[1] : wechat
    guard let app = NSRunningApplication.runningApplications(withBundleIdentifier: bid).first else { fail("not running: \(bid)") }
    if bid == wechat {
        // same as clicking the Dock icon: reopens the hidden main window of the running instance (never a new instance)
        let cfg = NSWorkspace.OpenConfiguration()
        cfg.activates = true
        cfg.createsNewApplicationInstance = false
        let url = NSWorkspace.shared.urlForApplication(withBundleIdentifier: bid)!
        let sem = DispatchSemaphore(value: 0)
        NSWorkspace.shared.openApplication(at: url, configuration: cfg) { _, _ in sem.signal() }
        _ = sem.wait(timeout: .now() + 5)
        for _ in 0..<40 {
            if NSWorkspace.shared.frontmostApplication?.bundleIdentifier == bid, mainWindow() != nil { break }
            usleep(100_000)
        }
        guard mainWindow() != nil else { fail("main window did not appear") }
    } else {
        app.activate()
        usleep(300_000)
    }
    print("ok")
case "win":
    guard let w = mainWindow(args.count > 1 ? args[1] : nil) else { fail("no onscreen window") }
    print(String(data: try JSONSerialization.data(withJSONObject: w, options: [.sortedKeys]), encoding: .utf8)!)
case "key":
    guard args.count > 1 else { fail("key <combo>") }
    key(args[1])
case "click", "rclick":
    guard args.count > 2, let x = Double(args[1]), let y = Double(args[2]) else { fail("\(args[0]) <x> <y>") }
    click(x, y, right: args[0] == "rclick")
case "scroll":
    guard args.count > 3, let x = Double(args[1]), let y = Double(args[2]), let dy = Int32(args[3]) else { fail("scroll <x> <y> <dy>") }
    scroll(x, y, dy)
case "clip-image":
    guard args.count > 1, let img = NSImage(contentsOfFile: args[1]) else { fail("clip-image <png path>") }
    NSPasteboard.general.clearContents()
    NSPasteboard.general.writeObjects([img])
case "clip-file":
    guard args.count > 1, FileManager.default.fileExists(atPath: args[1]) else { fail("clip-file <path>") }
    // a bare file URL pastes nothing in WeChat 4.1.15; Finder's Copy also declares the legacy filename list
    let url = URL(fileURLWithPath: args[1]).standardizedFileURL
    let names = NSPasteboard.PasteboardType("NSFilenamesPboardType")
    NSPasteboard.general.declareTypes([.fileURL, names], owner: nil)
    NSPasteboard.general.setString(url.absoluteString, forType: .fileURL)
    NSPasteboard.general.setPropertyList([url.path], forType: names)
case "nudge":
    let here = CGEvent(source: nil)?.location ?? .zero
    CGEvent(mouseEventSource: CGEventSource(stateID: .hidSystemState), mouseType: .mouseMoved, mouseCursorPosition: here,
            mouseButton: .left)?.post(tap: .cghidEventTap)
case "clip-get":
    print(NSPasteboard.general.string(forType: .string) ?? "", terminator: "")
case "clip-set":
    guard args.count > 1 else { fail("clip-set <text>") }
    NSPasteboard.general.clearContents()
    NSPasteboard.general.setString(args[1], forType: .string)
case "windows":
    for w in axWindows() { print("\(w.title)\t\(Int(w.size.width))x\(Int(w.size.height))") }
case "fit":
    // the main window is the only wide one; 880x640 (4.1.15 default) is too small for the search popup and input box
    guard let w = axWindows().first(where: { $0.size.width > 500 }), let screen = NSScreen.main?.visibleFrame else { fail("no main window") }
    var p = CGPoint(x: screen.minX + 20, y: NSScreen.screens[0].frame.height - screen.maxY + 10)
    var z = CGSize(width: min(1300, screen.width - 40), height: screen.height - 20)
    AXUIElementSetAttributeValue(w.el, kAXPositionAttribute as CFString, AXValueCreate(.cgPoint, &p)!)
    AXUIElementSetAttributeValue(w.el, kAXSizeAttribute as CFString, AXValueCreate(.cgSize, &z)!)
    guard let now = mainWindow() else { fail("main window not on screen") }
    print(String(data: try JSONSerialization.data(withJSONObject: now, options: [.sortedKeys]), encoding: .utf8)!)
case "close-window":
    guard args.count > 1, !mainTitles.contains(args[1]) else { fail("close-window <title of a popped-out chat> (not the main window)") }
    guard let w = axWindows().first(where: { $0.title == args[1] }) else { fail("no window titled \(args[1])") }
    var b: CFTypeRef?
    AXUIElementCopyAttributeValue(w.el, kAXCloseButtonAttribute as CFString, &b)
    guard let b, AXUIElementPerformAction(b as! AXUIElement, kAXPressAction as CFString) == .success else { fail("close button failed") }
    print("ok")
default:
    fail("usage: wxctl locked|perms|front|activate|win|key|click|rclick|scroll|clip-get|clip-set|clip-image|clip-file|nudge|windows|fit|close-window")
}
