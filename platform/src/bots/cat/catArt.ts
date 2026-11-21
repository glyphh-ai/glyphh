// Spike, the Glyphh cat, as the flat black-and-white mark: a copy of the Glyphh
// Bot app's catArt.ts (glyphh-bot src/renderer/src), kept apart from it. Two
// colours only, ever: white and ink. The parts are classed so CSS (cat.css)
// can make the cat breathe, blink and talk.
import type { Accessory, Look } from './look'

export const WHITE = '#ffffff'
export const INK = '#0b0a0f'

/** The mark's parts, in its own 165 x 200 drawing units. */
const HEADS: Record<Look['head'], { top: string; ear: string }> = {
  classic: { top: 'L135 13 L123 57', ear: 'M28 15 L62 42 L39 54 Z' },
  spiky: { top: 'L99 10 L111 34 L135 13 L123 57', ear: 'M28 15 L62 42 L39 54 Z' },
  tall: { top: 'L138 9 L123 57', ear: 'M22 9 L62 42 L39 54 Z' },
  folded: { top: 'L110 26 L138 26 L123 57', ear: 'M28 15 L62 42 L39 54 Z' },
  round: { top: 'C106 14 142 6 123 57', ear: 'M36 20 C26 32 32 50 39 54 L62 42 C56 30 48 18 36 20 Z' }
}

const TAILS: Record<Look['tail'], string> = {
  spike: 'L112 150 C126 152 136 151 145 149 C137 158 130 164 124 169',
  bolt: 'L112 148 L136 140 L128 152 L152 146 L126 168',
  curl: 'L112 150 C132 150 150 140 146 126 C143 138 132 158 124 169',
  long: 'L112 150 C130 152 150 150 160 140 C150 160 134 166 124 169'
}

const RING = 'M45 104 C43 89 70 66 96 64 C116 62 124 80 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z'

interface EyeDef {
  ring: string
  pupil: { c?: [number, number, number]; d?: string }
  dot?: [number, number, number]
  lashes?: string
  sparkle?: string
}

const EYES: Record<Look['eye'], EyeDef> = {
  dot: { ring: RING, pupil: { c: [92, 94, 12] }, dot: [96.2, 89.8, 3.6] },
  side: { ring: RING, pupil: { c: [68, 97, 12] }, dot: [72.2, 92.8, 3.6] },
  big: { ring: RING, pupil: { c: [88, 94, 19] }, dot: [94.65, 87.35, 5.7] },
  sleepy: {
    ring: 'M45 104 C60 96 100 90 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z',
    pupil: { c: [92, 107, 9] }
  },
  heart: {
    ring: RING,
    pupil: { d: 'M92 108 C79 99 74 92 76 86.5 C78 80 87 79 92 86 C97 79 106 80 108 86.5 C110 92 105 99 92 108 Z' },
    lashes: 'M84 65 Q81 58 78 52 M100 61 Q101 54 104 47 M114 63 Q119 56 125 51 M122 74 Q129 70 136 69',
    sparkle: 'M68 70 L70 75.5 L75.5 77.5 L70 79.5 L68 85 L66 79.5 L60.5 77.5 L66 75.5 Z'
  },
  star: {
    ring: RING,
    pupil: { d: 'M93 77 L97.8 87.6 L109 88.3 L100.4 95.6 L103 106.8 L93 100.8 L83 106.8 L85.6 95.6 L77 88.3 L88.2 87.6 Z' }
  }
}

const GAP = 'M61 138 L99 150 L100 172 L51 171 Z'
const BOLT = 'M74 142 L88 142 L82 152 L94 152 L72 170 L78 157 L68 157 Z'
const CAPE = 'M46 128 C30 140 16 162 10 182 L44 181 Z'

/** Names for the editor's pickers. */
export const PART_NAMES = {
  head: { classic: 'Classic head', spiky: 'Spiky head', tall: 'Tall ears', folded: 'Folded ear', round: 'Round ears' },
  tail: { spike: 'Spike tail', bolt: 'Bolt tail', curl: 'Curl tail', long: 'Long tail' },
  eye: { dot: 'Classic eye', side: 'Side-eye', big: 'Big eye', sleepy: 'Sleepy', heart: 'Heart eye', star: 'Star eye' },
  extra: { none: 'No extra', antenna: 'Antenna', cape: 'Cape', bolt: 'Bolt mark' },
  accessory: {
    none: 'No accessory',
    headphones: 'Headphones',
    beanie: 'Beanie',
    cap: 'Cap',
    glasses: 'Glasses',
    shades: 'Shades',
    bow: 'Bow',
    scarf: 'Scarf',
    crown: 'Crown',
    chain: 'Chain'
  },
  pose: { stand: 'Standing', lean: 'Leaning', hop: 'Hopping', turn: 'Turned' }
} as const

const W = WHITE
const K = INK

/** What each accessory adds over the cat. White shapes with ink edges, or ink with white edges. */
function accessory(a: Accessory): { back: string; front: string } {
  switch (a) {
    case 'headphones':
      return {
        back: '',
        front:
          `<path d="M30 62 C30 18 92 -6 134 30" fill="none" stroke="${W}" stroke-width="13" stroke-linecap="round"/>` +
          `<path d="M30 62 C30 18 92 -6 134 30" fill="none" stroke="${K}" stroke-width="5" stroke-linecap="round"/>` +
          `<rect x="17" y="52" width="24" height="32" rx="9" fill="${W}" stroke="${K}" stroke-width="4"/>` +
          `<rect x="124" y="24" width="24" height="32" rx="9" fill="${W}" stroke="${K}" stroke-width="4" transform="rotate(-20 136 40)"/>`
      }
    case 'beanie':
      return {
        back: '',
        front:
          `<g transform="rotate(-27 88 38)"><path d="M38 52 C40 18 136 18 138 52 Z" fill="${W}" stroke="${K}" stroke-width="5" stroke-linejoin="round"/>` +
          `<rect x="34" y="46" width="108" height="14" rx="5" fill="${W}" stroke="${K}" stroke-width="5"/>` +
          `<path d="M58 30 L58 46 M76 24 L76 46 M94 22 L94 46 M112 24 L112 46" stroke="${K}" stroke-width="3"/>` +
          `<circle cx="88" cy="14" r="9" fill="${W}" stroke="${K}" stroke-width="4"/></g>`
      }
    case 'cap':
      return {
        back: '',
        front:
          `<g transform="rotate(-27 88 40)"><path d="M44 54 C44 20 128 20 130 54 Z" fill="${W}" stroke="${K}" stroke-width="5" stroke-linejoin="round"/>` +
          `<path d="M124 50 L168 54 L164 62 L122 60 Z" fill="${W}" stroke="${K}" stroke-width="4" stroke-linejoin="round"/>` +
          `<circle cx="87" cy="24" r="4" fill="${K}"/></g>`
      }
    case 'glasses':
      return {
        back: '',
        front:
          `<circle cx="84" cy="94" r="45" fill="none" stroke="${K}" stroke-width="10"/>` +
          `<circle cx="84" cy="94" r="45" fill="none" stroke="${W}" stroke-width="5"/>` +
          `<path d="M128 84 L156 74" stroke="${W}" stroke-width="5" stroke-linecap="round"/>`
      }
    case 'shades':
      return {
        back: '',
        front:
          `<path d="M38 88 L132 76 L126 106 C108 124 64 124 46 110 Z" fill="${K}" stroke="${W}" stroke-width="6" stroke-linejoin="round"/>` +
          `<path d="M132 78 L158 70" stroke="${W}" stroke-width="6" stroke-linecap="round"/>` +
          `<path d="M60 96 L76 92 M60 104 L90 96" stroke="${W}" stroke-width="4" stroke-linecap="round"/>`
      }
    case 'bow':
      return {
        back: '',
        front:
          `<g transform="rotate(-20 46 48)"><path d="M24 34 L46 48 L24 62 Z M68 34 L46 48 L68 62 Z" fill="${W}" stroke="${K}" stroke-width="4" stroke-linejoin="round"/>` +
          `<circle cx="46" cy="48" r="7" fill="${K}" stroke="${W}" stroke-width="3"/></g>`
      }
    case 'scarf':
      return {
        back: '',
        front:
          `<path d="M34 124 C62 142 108 140 136 116 L140 132 C112 156 60 158 30 140 Z" fill="${W}" stroke="${K}" stroke-width="4" stroke-linejoin="round"/>` +
          `<path d="M52 134 L58 146 M74 140 L78 152 M96 140 L98 152 M116 132 L120 144" stroke="${K}" stroke-width="3"/>` +
          `<path d="M104 142 L124 178 L108 182 L94 146 Z" fill="${W}" stroke="${K}" stroke-width="4" stroke-linejoin="round"/>`
      }
    case 'crown':
      return {
        back: '',
        front:
          `<g transform="rotate(-27 90 34)"><path d="M66 46 L68 18 L80 32 L90 10 L100 32 L112 18 L114 46 Z" fill="${W}" stroke="${K}" stroke-width="4" stroke-linejoin="round"/>` +
          `<circle cx="90" cy="38" r="4" fill="${K}"/></g>`
      }
    case 'chain':
      return {
        back: '',
        front:
          `<path d="M40 124 C64 150 108 148 132 120" fill="none" stroke="${W}" stroke-width="5" stroke-dasharray="5 4" stroke-linecap="round"/>` +
          `<circle cx="86" cy="146" r="8" fill="${W}" stroke="${K}" stroke-width="3"/>`
      }
    default:
      return { back: '', front: '' }
  }
}

const POSE: Record<Look['pose'], string> = {
  stand: '',
  lean: 'rotate(-8 82 182)',
  hop: 'translate(0 -10) rotate(5 82 182)',
  turn: 'translate(165 0) scale(-1 1)'
}

/** The cat's SVG markup (the inside of a 165 x 200 viewBox). */
export function catMarkup(look: Look): string {
  const head = HEADS[look.head] ?? HEADS.classic
  const tail = TAILS[look.tail] ?? TAILS.spike
  const eye = EYES[look.eye] ?? EYES.dot
  const body = `M40 62 ${head.top} C140 70 144 104 128 121 L112 133 ${tail} L128 179 L35 180 L44 131 C18 118 20 80 40 62 Z`
  const antenna = look.extra === 'antenna'
  const pupil = eye.pupil.c
    ? `<circle cx="${eye.pupil.c[0]}" cy="${eye.pupil.c[1]}" r="${eye.pupil.c[2]}" fill="${W}"/>` +
      (eye.dot ? `<circle cx="${eye.dot[0]}" cy="${eye.dot[1]}" r="${eye.dot[2]}" fill="${K}"/>` : '')
    : `<path d="${eye.pupil.d}" fill="${W}"/>`
  const acc = accessory(look.accessory)
  return (
    `<g class="cat-pose" transform="${POSE[look.pose] ?? ''}">` +
    acc.back +
    (look.extra === 'cape' ? `<path class="cape" d="${CAPE}" fill="${K}" stroke="${W}" stroke-width="7" stroke-linejoin="round"/>` : '') +
    `<g class="cat-body"><g fill="${W}" stroke="${W}" stroke-width="16" stroke-linejoin="round"><path d="${body}"/><path class="ear-l" d="${head.ear}"/>` +
    (antenna ? `<path d="M86 46 L92 18" stroke-width="20" stroke-linecap="round"/><circle cx="93" cy="14" r="9"/>` : '') +
    `</g>` +
    `<path d="${body}" fill="${K}"/><path class="ear-l" d="${head.ear}" fill="${K}"/>` +
    `<path d="${GAP}" fill="${W}"/>` +
    (look.extra === 'bolt' ? `<path d="${BOLT}" fill="${K}"/>` : '') +
    (antenna ? `<path d="M86 46 L92 18" stroke="${K}" stroke-width="5" stroke-linecap="round"/><circle cx="93" cy="14" r="7" fill="${K}"/>` : '') +
    `<g class="cat-eye"><path d="${eye.ring}" fill="none" stroke="${W}" stroke-width="8"/>${pupil}` +
    (eye.lashes ? `<path d="${eye.lashes}" fill="none" stroke="${W}" stroke-width="5" stroke-linecap="round"/>` : '') +
    (eye.sparkle ? `<path d="${eye.sparkle}" fill="${W}"/>` : '') +
    `</g>` +
    acc.front +
    `</g></g>`
  )
}

/** Every colour the markup uses (the tests hold it to white and ink). */
export function coloursIn(markup: string): string[] {
  return [...new Set([...markup.matchAll(/(?:fill|stroke)="([^"]+)"/g)].map((m) => m[1]!.toLowerCase()))]
}
