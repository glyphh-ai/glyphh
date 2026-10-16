// What makes the shared one-time unlock module (shared/unlock) this mod's: the
// only file of hooks/unlock/ that is the mod's own. The build swaps
// PAYMENT_LINK for the live one in release.json.
export const MOD = 'games'
/** The command the unlock answers on: /games unlock, /games key <licence>. */
export const COMMAND = 'games'
/** Stripe test Payment Link in the sandbox, $8 (the site's LICENCE_PAYMENT_LINKS maps games to plink_1URGUO22q25FsE65GHtcYifq). */
export const PAYMENT_LINK = 'https://buy.stripe.com/test_aFacMYcONfD13zffRKbfO01'

/** The mod's name as people read it, and its price: once, per machine. */
export const PRODUCT = 'Games'
export const PRICE = '$8'

/** What the mod does, shown until it is bought. */
export const ABOUT = [
  'Games: games over Claude, with sound, that pass the time while Claude works.',
  'Missile Command, Chickn, Blocks, Rocks and Dash: endless, harder as they go, your top score to beat.',
  '/games lists them; /games blocks starts one.',
]
