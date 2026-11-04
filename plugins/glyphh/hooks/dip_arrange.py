#!/usr/bin/env python3
"""Arranges the desktop app's panes for /dip, which no tool of the app can do.

The app's tiles each carry a keyboard Move handle. This focuses a tile's handle through the accessibility API and
sends it keys, then answers where every tile ended up. Argument: JSON {"ops": [{"tile": "plan", "keys": ["up", "up",
"enter"]}, ...]}, tile as show_pane names panes ("chat" for Claude). Answer on stdout: {"ok": bool, "error"?: str,
"tiles": {"plan": [x, y, width, height], ...}}. macOS only, standard library only; needs Accessibility permission.
"""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import Structure, byref, c_bool, c_char_p, c_double, c_int, c_long, c_uint16, c_void_p

# The name each tile's controls go by, as the app labels them.
TITLES = {
    "Session tools": "chat",
    "Background tasks controls": "tasks",
    "Plan controls": "plan",
    "Terminal controls": "terminal",
    "Files controls": "file",
    "Changes controls": "diff",
    "Browser controls": "preview",
    "Preview controls": "preview",
    "Pull request controls": "pr",
    "Artifacts controls": "artifact",
}
KEYS = {"left": 123, "right": 124, "down": 125, "up": 126, "enter": 36}
SETTLE = 0.12  # seconds between keys: the app previews a move on each
WAIT = 3.0  # seconds a pane just opened gets to draw its tile

AS = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
CF = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
CF.CFStringCreateWithCString.restype = c_void_p
CF.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_int]
CF.CFArrayGetCount.restype = c_long
CF.CFArrayGetCount.argtypes = [c_void_p]
CF.CFArrayGetValueAtIndex.restype = c_void_p
CF.CFArrayGetValueAtIndex.argtypes = [c_void_p, c_long]
CF.CFStringGetCString.restype = c_bool
CF.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_long, c_int]
CF.CFGetTypeID.restype = c_long
CF.CFGetTypeID.argtypes = [c_void_p]
CF.CFStringGetTypeID.restype = c_long
AS.AXIsProcessTrusted.restype = c_bool
AS.AXUIElementCreateApplication.restype = c_void_p
AS.AXUIElementCreateApplication.argtypes = [c_int]
AS.AXUIElementCopyAttributeValue.argtypes = [c_void_p, c_void_p, ctypes.POINTER(c_void_p)]
AS.AXUIElementCopyAttributeValue.restype = c_int
AS.AXUIElementSetAttributeValue.argtypes = [c_void_p, c_void_p, c_void_p]
AS.AXUIElementSetAttributeValue.restype = c_int
AS.AXValueGetValue.argtypes = [c_void_p, c_int, c_void_p]
AS.AXValueGetValue.restype = c_bool
AS.CGEventCreateKeyboardEvent.restype = c_void_p
AS.CGEventCreateKeyboardEvent.argtypes = [c_void_p, c_uint16, c_bool]
AS.CGEventPostToPid.argtypes = [c_int, c_void_p]
AS.CGEventPostToPid.restype = None
TRUE = c_void_p.in_dll(CF, "kCFBooleanTrue")
STRING = CF.CFStringGetTypeID()
UTF8 = 0x08000100
AX_POINT, AX_SIZE = 1, 2


class Pair(Structure):
    _fields_ = [("a", c_double), ("b", c_double)]


NAMES = {}


def attr(name):
    if name not in NAMES:
        NAMES[name] = CF.CFStringCreateWithCString(None, name.encode(), UTF8)
    return NAMES[name]


def get(e, name):
    v = c_void_p()
    return v.value if AS.AXUIElementCopyAttributeValue(e, attr(name), byref(v)) == 0 else None


def text(e, name):
    v = get(e, name)
    if not v or CF.CFGetTypeID(v) != STRING:
        return ""
    buf = ctypes.create_string_buffer(1024)
    return buf.value.decode("utf8", "ignore") if CF.CFStringGetCString(v, buf, 1024, UTF8) else ""


def children(e):
    v = get(e, "AXChildren")
    return [CF.CFArrayGetValueAtIndex(v, i) for i in range(CF.CFArrayGetCount(v))] if v else []


def pair(e, name, kind):
    v = get(e, name)
    p = Pair()
    if v:
        AS.AXValueGetValue(v, kind, byref(p))
    return p.a, p.b


def rect(handle):
    """The tile around a Move handle: its first ancestor taller than a title bar."""
    e = handle
    while True:
        e = get(e, "AXParent")
        if not e:
            return [0, 0, 0, 0]
        w, h = pair(e, "AXSize", AX_SIZE)
        if h > 200:
            x, y = pair(e, "AXPosition", AX_POINT)
            return [int(x), int(y), int(w), int(h)]


def tiles(app):
    """Each tile's Move handle by name: its title bar's label comes just before it in the tree."""
    flat = []

    def walk(e, depth):
        if depth > 45:
            return
        flat.append((e, text(e, "AXRole"), text(e, "AXDescription")))
        for k in children(e):
            walk(k, depth + 1)

    wins = get(app, "AXWindows")
    for i in range(CF.CFArrayGetCount(wins) if wins else 0):
        walk(CF.CFArrayGetValueAtIndex(wins, i), 0)
    found = {}
    for i, (e, role, desc) in enumerate(flat):
        if role != "AXButton" or desc != "Move":
            continue
        name = next((TITLES[flat[j][2]] for j in range(i, max(-1, i - 60), -1) if flat[j][2] in TITLES), None)
        if name:
            found.setdefault(name, e)
    return found


def press(pid, keys):
    for key in keys:
        for down in (True, False):
            AS.CGEventPostToPid(pid, AS.CGEventCreateKeyboardEvent(None, KEYS[key], down))
        time.sleep(SETTLE)


def answer(**fields):
    print(json.dumps(fields))
    sys.exit(0)


def main():
    ops = json.loads(sys.argv[1])["ops"]
    if not AS.AXIsProcessTrusted():
        answer(ok=False, error="accessibility", tiles={})
    script = 'tell application "System Events" to get unix id of process "Claude"'
    pid = int(subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip() or 0)
    if not pid:
        answer(ok=False, error="no-app", tiles={})
    app = AS.AXUIElementCreateApplication(pid)
    # Chromium builds its accessibility tree only when asked.
    AS.AXUIElementSetAttributeValue(app, attr("AXManualAccessibility"), TRUE)

    wanted = {op["tile"] for op in ops}
    deadline = time.time() + WAIT
    found = tiles(app)
    while not wanted <= set(found) and time.time() < deadline:
        time.sleep(0.15)
        found = tiles(app)
    missing = sorted(wanted - set(found))
    if missing:
        answer(ok=False, error="missing " + ",".join(missing), tiles={n: rect(h) for n, h in found.items()})

    for op in ops:
        handle = tiles(app).get(op["tile"])
        if not handle:
            answer(ok=False, error="missing " + op["tile"], tiles={})
        AS.AXUIElementSetAttributeValue(handle, attr("AXFocused"), TRUE)
        time.sleep(SETTLE)
        press(pid, op["keys"])
        time.sleep(SETTLE)
    time.sleep(0.8)  # the last move's animation
    answer(ok=True, tiles={n: rect(h) for n, h in tiles(app).items()})


if __name__ == "__main__":
    main()
