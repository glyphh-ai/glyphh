// What makes the shared licence module (shared/licence) this mod's: the only
// file of hooks/licence/ that is the mod's own. The build swaps PAYMENT_LINK
// for the live one in release.json.
export const MOD = 'workspaces'
export const PAYMENT_LINK = 'https://buy.stripe.com/test_8x228k14I6BG7UHayxc7u01'

/** The mod's name as people read it, and its price. */
export const PRODUCT = 'Workspaces'
export const PRICE = '$5'

/** What the mod does, shown when the trial has ended. */
export const ABOUT = [
  'Workspaces sets up the Claude desktop app for a kind of work in one command.',
  '/dip Comms lays Gmail, Slack and Calendar out live, side by side, in one page; /dip IDE opens Files, Changes and Terminal.',
  'Each workspace is a grid of your favourite pages and the app\'s panes, and /dip back returns to the one before.',
]

export const TRIAL_DAYS = 7
