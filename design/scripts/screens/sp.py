# helpers for the simple pages the server serves
from g import *

def sp_row(idx, label, note, url, body, dh=820, ph=844, right=None, top=False):
    d = browser(url, page(body(False), False, right, top=top), dh)
    p = phone(page(body(True), True, right, foot=False, top=top), ph, url=url.split('/')[0] if False else url)
    return row(idx, label, note, d, p, dh, ph)

def eyebrow(t, c=None):
    return f'<div class="m" style="font-size:13px;color:{c or VI2}">{t}</div>'

def title(t, p):
    return h(t, 30 if p else 36)

def note(t):
    return f'<div class="m" style="font-size:12px;line-height:1.7;color:{MUT}">{t}</div>'

def stack(*items, gap=10):
    return f'<div style="display:flex;flex-direction:column;gap:{gap}px">{"".join(items)}</div>'

def rowx(*items, gap=8):
    return f'<div style="display:flex;gap:{gap}px;flex-wrap:wrap">{"".join(items)}</div>'

def box(inner, pad=18, border=L2, bg=INK2):
    return f'<div style="border:1px solid {border};background:{bg};padding:{pad}px">{inner}</div>'

def mark(kind):
    mood = {'ok': 'done', 'err': 'error', 'warn': 'sleepy', 'vi': 'curious'}[kind]
    return cat(mood, 64)
    c = {'ok': OK, 'err': ERR, 'warn': WARN, 'vi': VI}[kind]
    n = {'ok': 'check', 'err': 'x', 'warn': 'clock', 'vi': 'arrow'}[kind]
    return f'<div style="width:44px;height:44px;border:1px solid {L2};display:flex;align-items:center;justify-content:center">{ic(n,18,c)}</div>'

def trace(t):
    return f'<div class="m" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:{MUT}">trace <span style="color:{FG};padding:3px 8px;border:1px solid {L2}">{t}</span><button type="button" class="b3 sm" aria-label="Copy trace id">{ic("copy",13)}</button></div>'
