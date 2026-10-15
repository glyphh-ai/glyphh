// Copied from shared/licence/site.ts by scripts/sync-shared.mjs: edit it there.
// The site every Glyphh mod buys and checks its licence with. Test values:
// scripts/build.mjs swaps in the live ones from release.json.
export const SITE = 'https://glyphh.ai'
export const PUBLIC_KEY = 'LBZCuL7YrfirHogb_N5Iai0lQDaig-3VP8watWltwf0'

/** How often the site is asked during checkout, and for how long. */
export const POLL_MS = 3_000
export const WAIT_MS = 10 * 60_000
