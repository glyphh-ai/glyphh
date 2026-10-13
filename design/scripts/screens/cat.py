# The Glyphh cat (face 1), ported from the brand's cat(face, o) script, as static SVG.
INK = '#0b0a0f'
BROW = 'M45 104 C43 89 70 66 96 64 C116 62 124 80 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z'
BROW_LOW = 'M45 104 C60 96 100 90 121 97 C118 116 100 126 86 122 C70 118 47 112 45 104 Z'
MOOD_EYE = {'idle': 'idle', 'thinking': 'thinking', 'generating': 'big', 'done': 'check', 'error': 'sleepy', 'sleepy': 'sleepy', 'curious': 'curious'}

def circ(cx, cy, r):
    return f'M{cx - r} {cy} a{r} {r} 0 1 0 {2 * r} 0 a{r} {r} 0 1 0 {-2 * r} 0 Z'

def path(d, fill, stroke='none', sw=0):
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"></path>'

def cat(mood='idle', size=64, label=None, ec='#ffffff'):
    c = '#ffffff'
    body = 'M40 62 L135 13 L123 57 C140 70 144 104 128 121 L112 133 L112 150 C126 152 136 151 145 149 C137 158 130 164 124 169 L128 179 L35 180 L44 131 C18 118 20 80 40 62 Z'
    ear = 'M28 15 L62 42 L39 54 Z'
    kind = MOOD_EYE.get(mood, 'idle')
    s = [path(body, c, c, 16), path(ear, c, c, 16), path(body, INK, INK, 1.5), path(ear, INK, INK, 1.5), path('M61 138 L99 150 L100 172 L51 171 Z', c)]
    s.append(path(BROW_LOW if kind == 'sleepy' else BROW, 'none', c, 8))
    e = []
    eyes = {'idle': (92, 94, 12, 96.2, 89.8, 3.6), 'curious': (68, 97, 12, 72.2, 92.8, 3.6), 'big': (88, 94, 19, 94.65, 87.35, 5.7), 'thinking': (94, 80, 12, 98.2, 75.8, 3.6)}
    if kind in eyes:
        k = eyes[kind]
        e += [path(circ(k[0], k[1], k[2]), ec), path(circ(k[3], k[4], k[5]), INK)]
    elif kind == 'sleepy':
        e.append(path(circ(92, 107, 9), ec))
    elif kind == 'check':
        e.append(path('M83 95 L90 102 L103 87', 'none', ec, 7))
    h = round(size * 200 / 165)
    lab = label or f'Glyphh cat, {mood}'
    blink = ' class="g-eye"' if kind in eyes else ''
    return f'<svg viewBox="0 0 165 200" width="{size}" height="{h}" role="img" aria-label="{lab}" style="flex:none;display:block">{"".join(s)}<g{blink}>{"".join(e)}</g></svg>'
