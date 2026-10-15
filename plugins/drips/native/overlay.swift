// overlay.swift — Drips' fullscreen overlay: one effect over the whole screen.
//
// Compiled by the mod with swiftc the first time a fullscreen effect plays
// (hooks/drips/fullscreen.ts) and kept in ~/Library/Caches/glyphh-drips. The
// protocol is hooks/drips/overlay.ts's:
//
//   drips-overlay screen   prints the screen under the pointer as one JSON
//                          line: {"x":0,"y":0,"w":1512,"h":982}
//   drips-overlay play     reads {"v":1,"html":"...","screen":{...},
//                          "closeAfterMs":8000} on stdin, shows the document
//                          in a transparent, borderless, click-through window
//                          on that screen, above everything and on every Space,
//                          and prints {"t":"shown","pid":N}, then
//                          {"t":"closed","why":"signal"|"timeout"|"term"|"orphan"}
//                          as it exits; {"t":"error","message":"..."} when it
//                          cannot.
//
// It closes on the document's "__drip_close__" (console.log, or a
// postMessage to itself), after closeAfterMs (never more than 30 minutes,
// whatever it is asked), on SIGTERM, or when the process that started it is
// gone. It never takes focus or the pointer.

import AppKit
import Foundation
import WebKit

let capMs = 30 * 60_000
let minMs = 100

func emit(_ object: [String: Any]) {
  guard let data = try? JSONSerialization.data(withJSONObject: object),
    let line = String(data: data, encoding: .utf8)
  else { return }
  FileHandle.standardOutput.write((line + "\n").data(using: .utf8)!)
}

func fail(_ message: String) -> Never {
  emit(["t": "error", "message": message])
  exit(1)
}

func screenUnderPointer() -> NSScreen? {
  let point = NSEvent.mouseLocation
  return NSScreen.screens.first { NSMouseInRect(point, $0.frame, false) } ?? NSScreen.main
}

struct ScreenRect: Decodable { let x: Double; let y: Double; let w: Double; let h: Double }
struct PlayRequest: Decodable { let v: Int; let html: String; let screen: ScreenRect; let closeAfterMs: Double }

/// Hears the document's close signal: console.log("__drip_close__") is
/// forwarded here by a script added before the document's own, and so is a
/// postMessage of it to the window itself.
final class CloseListener: NSObject, WKScriptMessageHandler {
  let onClose: () -> Void
  init(onClose: @escaping () -> Void) { self.onClose = onClose }
  func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
    if (message.body as? String) == "__drip_close__" { onClose() }
  }
}

let closeBridge = """
  (function () {
    var send = function (v) { try { if (v === "__drip_close__") window.webkit.messageHandlers.drip.postMessage(v) } catch (e) {} };
    var log = console.log;
    console.log = function () { send(arguments[0]); return log.apply(console, arguments) };
    window.addEventListener("message", function (ev) { send(ev.data) });
  })();
  """

final class Overlay: NSObject, NSApplicationDelegate {
  let request: PlayRequest
  var window: NSWindow?
  var closed = false
  var signalSource: DispatchSourceSignal?
  let parent = getppid()

  init(request: PlayRequest) { self.request = request }

  func applicationDidFinishLaunching(_ note: Notification) {
    let s = request.screen
    let frame = NSRect(x: s.x, y: s.y, width: s.w, height: s.h)
    let window = NSWindow(contentRect: frame, styleMask: .borderless, backing: .buffered, defer: false)
    window.isOpaque = false
    window.backgroundColor = .clear
    window.hasShadow = false
    window.level = .screenSaver
    window.ignoresMouseEvents = true
    window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
    window.isReleasedWhenClosed = false

    let config = WKWebViewConfiguration()
    let controller = WKUserContentController()
    controller.add(CloseListener { [weak self] in self?.close("signal") }, name: "drip")
    controller.addUserScript(WKUserScript(source: closeBridge, injectionTime: .atDocumentStart, forMainFrameOnly: true))
    config.userContentController = controller
    let web = WKWebView(frame: NSRect(origin: .zero, size: frame.size), configuration: config)
    web.setValue(false, forKey: "drawsBackground")
    web.autoresizingMask = [.width, .height]
    window.contentView = web
    web.loadHTMLString(request.html, baseURL: nil)
    window.orderFrontRegardless()
    self.window = window
    emit(["t": "shown", "pid": Int(getpid())])

    let ms = min(capMs, max(minMs, Int(request.closeAfterMs.isFinite ? request.closeAfterMs : Double(capMs))))
    DispatchQueue.main.asyncAfter(deadline: .now() + .milliseconds(ms)) { [weak self] in self?.close("timeout") }
    Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
      guard let self else { return }
      if getppid() != self.parent { self.close("orphan") }
    }
    signal(SIGTERM, SIG_IGN)
    let source = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
    source.setEventHandler { [weak self] in self?.close("term") }
    source.resume()
    signalSource = source
  }

  func close(_ why: String) {
    if closed { return }
    closed = true
    window?.orderOut(nil)
    emit(["t": "closed", "why": why])
    exit(0)
  }
}

let args = CommandLine.arguments
guard args.count == 2 else { fail("usage: drips-overlay screen | play") }

switch args[1] {
case "screen":
  guard let screen = screenUnderPointer() else { fail("no screen") }
  let f = screen.frame
  emit(["x": f.origin.x, "y": f.origin.y, "w": f.size.width, "h": f.size.height])
case "play":
  let input = FileHandle.standardInput.readDataToEndOfFile()
  guard let request = try? JSONDecoder().decode(PlayRequest.self, from: input) else { fail("not a play request") }
  guard request.v == 1 else { fail("protocol version \(request.v) is not 1") }
  guard request.screen.w > 0, request.screen.h > 0 else { fail("no screen size") }
  let app = NSApplication.shared
  app.setActivationPolicy(.accessory)
  let overlay = Overlay(request: request)
  app.delegate = overlay
  app.run()
default:
  fail("unknown command \(args[1])")
}
