// browser.mjs — the terminal's browser host.
//
// Headless Chrome (chrome.mjs), one page per layout cell. Each page's PNG
// frames go to files in the run directory; every frame is a JSON line on
// stdout ({ t: "frame", cell, file, gen }) the mod blits into its Image.
// Commands come back over a Unix socket (POST /cmd, a JSON op or a list of
// them), since a mod's child gets no streaming stdin.

import { writeFileSync } from "node:fs"
import { createServer } from "node:http"
import { join } from "node:path"

import { startChrome } from "./chrome.mjs"

const RING = 4 // frame files per cell, so the terminal never reads one mid-write
const say = msg => process.stdout.write(JSON.stringify(msg) + "\n")
const safe = s => s.replace(/[^A-Za-z0-9_-]/g, "_")

let chrome
try {
  chrome = await startChrome({
    format: "png",
    onFrame(page, bytes) {
      const file = join(chrome.run, `${safe(page.cell)}-${page.gen % RING}.png`)
      writeFileSync(file, bytes)
      say({ t: "frame", cell: page.cell, file, gen: page.gen })
    },
    onNav: page => say({ t: "nav", cell: page.cell, url: page.url }),
    onTitle: page => say({ t: "title", cell: page.cell, title: page.title }),
    onExit: () => shutdown(1),
  })
} catch (err) {
  say({ t: "error", error: String(err?.message ?? err) })
  process.exit(1)
}

const sock = join(chrome.run, "ctl.sock")
const server = createServer((req, res) => {
  let body = ""
  req.on("data", c => { body += c })
  req.on("end", async () => {
    try {
      for (const cmd of [].concat(JSON.parse(body || "[]"))) await chrome.op(cmd)
      res.end("{}")
    } catch (err) {
      res.statusCode = 400
      res.end(JSON.stringify({ error: String(err?.message ?? err) }))
    }
  })
})

let done = false
function shutdown(code = 0) {
  if (done) return
  done = true
  try { server.close() } catch {}
  chrome.shutdown()
  setTimeout(() => process.exit(code), 400)
}
for (const sig of ["SIGTERM", "SIGINT", "SIGHUP"]) process.on(sig, () => shutdown(0))
// The mod kills us on unload; this catches a parent that died without saying.
const parent = process.ppid
setInterval(() => { if (process.ppid !== parent) shutdown(0) }, 2000).unref()

server.listen(sock, () => say({ t: "ready", sock, run: chrome.run }))
