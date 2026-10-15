// input.mjs — what the layout page's clicks and keys become in Chrome's
// DevTools protocol. Pure: the mod's tests load it as chrome.mjs does.

const KEYS = {
  return: ["Enter", 13, "\r"], enter: ["Enter", 13, "\r"], tab: ["Tab", 9, "\t"],
  backspace: ["Backspace", 8], delete: ["Delete", 46], up: ["ArrowUp", 38],
  down: ["ArrowDown", 40], left: ["ArrowLeft", 37], right: ["ArrowRight", 39],
  pageup: ["PageUp", 33], pagedown: ["PageDown", 34], home: ["Home", 36],
  end: ["End", 35], escape: ["Escape", 27],
}

/** The protocol calls for one key: `[method, params]` pairs, in order. */
export function keyCalls({ key, ctrl, shift, meta, alt }) {
  const named = KEYS[key.toLowerCase()]
  if (!named && key.length === 1 && !ctrl && !meta && !alt) return [["Input.insertText", { text: key }]]
  const modifiers = (alt ? 1 : 0) | (ctrl ? 2 : 0) | (meta ? 4 : 0) | (shift ? 8 : 0)
  const [k, code, text] = named ?? [key, key.toUpperCase().charCodeAt(0)]
  const base = { key: k, windowsVirtualKeyCode: code, modifiers }
  return [
    ["Input.dispatchKeyEvent", { type: text ? "keyDown" : "rawKeyDown", ...base, ...(text ? { text } : {}) }],
    ["Input.dispatchKeyEvent", { type: "keyUp", ...base }],
  ]
}

/** An address as typed in a cell's bar: `example.com` is https. */
export const addressOf = text => (/^[a-z][a-z0-9+.-]*:/i.test(text) ? text : `https://${text}`)

/** The protocol call for a mouse act in the page. */
export function mouseCall({ action, x, y, button, clicks, mods }) {
  return ["Input.dispatchMouseEvent", {
    type: { down: "mousePressed", up: "mouseReleased", move: "mouseMoved" }[action],
    x: typeof x === "number" ? x : 0,
    y: typeof y === "number" ? y : 0,
    button: button ?? "none",
    clickCount: action === "move" ? 0 : (clicks ?? 1),
    modifiers: mods ?? 0,
  }]
}

/** Chrome's pipe messages end with NUL: feed it chunks, get each message. */
export function nulFramer(onMessage) {
  let inbox = ""
  return chunk => {
    inbox += chunk
    let end
    while ((end = inbox.indexOf("\0")) >= 0) {
      const raw = inbox.slice(0, end)
      inbox = inbox.slice(end + 1)
      if (raw) onMessage(JSON.parse(raw))
    }
  }
}
