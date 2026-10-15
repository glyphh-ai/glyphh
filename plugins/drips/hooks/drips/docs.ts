// An effect's document for a host of a given size, as the app's overlay
// windows load it: a one-shot (its opacity, when named, set on <body>) or a
// looping background; and how long a one-shot may stay before it is closed.
import { buildLoopHtml, buildOneShotHtml, oneShotSafetyMs } from './effects.ts'

export type Doc = { html: string; closeAfterMs: number }

export function oneShotDoc(effect: string, w: number, h: number, opacity: number): Doc {
  let html = buildOneShotHtml(effect, w, h)
  if (opacity > 0) html = html.replace('<body>', `<body style="opacity:${opacity}">`)
  return { html, closeAfterMs: oneShotSafetyMs(effect) }
}

export function loopDoc(effect: string, w: number, h: number, opacity: number, maxMs: number): Doc {
  return { html: buildLoopHtml(effect, w, h, opacity), closeAfterMs: maxMs }
}
