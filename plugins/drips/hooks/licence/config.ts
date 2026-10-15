// What makes the shared licence module (shared/licence) this mod's: the only
// file of hooks/licence/ that is the mod's own. The build swaps PAYMENT_LINK
// for the live one in release.json.
export const MOD = 'drips'
/** Stripe test Payment Link for Drips (the site's LICENCE_PAYMENT_LINKS holds drips:plink_1UQjAb1Vx5mZZ7Ia3Lo4wIwj). */
export const PAYMENT_LINK = 'https://buy.stripe.com/test_14A8wIaFid04caXdKJc7u02'

/** The mod's name as people read it, and its price. */
export const PRODUCT = 'Drips'
export const PRICE = '$5'

/** What the mod does, shown when the trial has ended. */
export const ABOUT = [
  'Drips plays visual effects over Claude: confetti, fireworks, hearts, a matrix rain and more.',
  '/drip confetti plays one; /drip 3 hearts stars plays several in turn; /drip -1 aurora keeps one going until /drip stop.',
  'Save your own recipes in /drips, play them by name, and let Claude play them too.',
]

export const TRIAL_DAYS = 7
