# Glyphh headless screens: shared building blocks for the canvas artboards.
import json, os, sys
from cat import cat

ROOT = '/private/tmp/claude-501/-Users-timmetim-development-glyphh/15089e72-bc39-406d-bfb7-5db569efe89e/scratchpad/canvas'
FRESH = '/private/tmp/claude-501/-Users-timmetim-development-glyphh/15089e72-bc39-406d-bfb7-5db569efe89e/scratchpad/artifact-files/641219af-6c79-45ab-91c9-6dc88d8f5c2a/project/canvas.json'

INK = '#07060A'; INK2 = '#0B0A10'; L1 = '#1E1C26'; L2 = '#2C2938'
FG = '#F5F3FA'; FG2 = '#A9A4B8'; MUT = '#8E89A0'; DIM = '#6E6980'
VI = '#7C4DFF'; VI2 = '#B49CFF'
OK = '#3FD08F'; WARN = '#FFB547'; AUTH = '#F062D0'; ERR = '#FF6B6B'; CYAN = '#6FD8FF'

CSS = """body{margin:0}
a{color:#A9A4B8}a:hover{color:#F5F3FA}
.m{font-family:'Red Hat Mono',monospace}
.d{font-family:'Red Hat Display',sans-serif;font-weight:600;letter-spacing:-0.025em}
.t{font-family:'Red Hat Text',sans-serif}
.b1,.b2,.b3,.bd{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 18px;font-family:'Red Hat Mono',monospace;font-size:14px;border-radius:0;text-decoration:none;cursor:pointer;box-sizing:border-box;white-space:nowrap;margin:0}
.b1{color:#07060A;background:#F5F3FA;border:1px solid #F5F3FA}
.b2{color:#F5F3FA;background:transparent;border:1px solid #2C2938}
.b3{color:#A9A4B8;background:transparent;border:1px solid transparent;padding:0 10px}
.bd{color:#FF8A8A;background:transparent;border:1px solid #4A2630}
.sm{min-height:34px;padding:0 12px;font-size:13px}
.w{width:100%}
.dis{opacity:.4;cursor:default}
.in{display:flex;align-items:center;width:100%;min-height:44px;padding:0 14px;box-sizing:border-box;background:#0B0A10;border:1px solid #2C2938;color:#F5F3FA;font-family:'Red Hat Mono',monospace;font-size:14px;border-radius:0;outline:none}
.lb{display:block;font-family:'Red Hat Mono',monospace;font-size:12px;color:#8E89A0;margin-bottom:8px}
.chip{display:inline-flex;align-items:center;gap:8px;min-height:26px;padding:0 10px;border:1px solid #2C2938;font-family:'Red Hat Mono',monospace;font-size:12px;color:#C9C4D8;white-space:nowrap;box-sizing:border-box}
.chip i{display:inline-block;width:6px;height:6px;flex:none}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;flex:none}
.cur{animation:g-blink 1s steps(1) infinite}
.spin{animation:g-spin 1s linear infinite}
.sk{background:#16141D}
@keyframes g-blink{0%,49%{opacity:1}50%,100%{opacity:0}}
.g-eye{transform-origin:center;transform-box:fill-box;animation:g-eyeblink 5s infinite}
@keyframes g-eyeblink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.1)}}
@keyframes g-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.cur,.spin,.g-eye{animation:none}}"""

FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400..800&amp;family=Red+Hat+Text:wght@400..700&amp;family=Red+Hat+Mono:wght@400..700&amp;display=swap">'


def wm(size=18, color=FG):
    return f'<span class="m" style="font-weight:600;font-size:{size}px;color:{color};white-space:nowrap"><span style="color:{VI};margin-right:.12em">&gt;</span>glyphh</span>'


LOGO = '/_blob/833e75fa859a5c754dce0955ac5b788c'


def logo(hh=28):
    return f'<img src="{LOGO}" alt="Glyphh" style="height:{hh}px;width:auto;display:block;flex:none">'


def gt():
    return f'<span style="color:{VI};margin-right:.12em">&gt;</span>'


def btn(label, kind='b1', extra='', href=None, prompt=False, aria=None):
    pre = f'<span style="color:{VI}">&gt;</span>' if prompt else ''
    a = f' aria-label="{aria}"' if aria else ''
    if href is not None:
        return f'<a href="{href}" class="{kind} {extra}"{a}>{pre}{label}</a>'
    return f'<button type="button" class="{kind} {extra}"{a}>{pre}{label}</button>'


TYPES = {
    'text': MUT, 'panel': CYAN, 'link': FG, 'needs input': WARN,
    'needs auth': AUTH, 'working': VI, 'result': VI2, 'error': ERR,
}


def chip(label, color=None, blink=False):
    c = color or TYPES.get(label, MUT)
    cl = ' class="cur"' if blink else ''
    return f'<span class="chip"><i{cl} style="background:{c}"></i>{label}</span>'


def status(label, color, size=12):
    return f'<span class="m" style="display:inline-flex;align-items:center;gap:8px;font-size:{size}px;color:{FG2};white-space:nowrap"><span class="dot" style="background:{color}"></span>{label}</span>'


def mono(text, size=12, color=MUT, extra=''):
    return f'<span class="m" style="font-size:{size}px;color:{color};{extra}">{text}</span>'


def h(text, size=28, extra=''):
    return f'<div class="d" style="font-size:{size}px;line-height:1.15;color:{FG};{extra}">{text}</div>'


def ptxt(text, size=15, color=FG2, extra=''):
    return f'<p class="t" style="margin:0;font-size:{size}px;line-height:1.6;color:{color};{extra}">{text}</p>'


def spinner(size=16):
    return f'<svg class="spin" width="{size}" height="{size}" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="6.5" stroke="{L2}" stroke-width="1.5"/><path d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5" stroke="{VI}" stroke-width="1.5"/></svg>'


ICONS = {
    'check': '<path d="M3 8.5l3 3 7-7"/>',
    'x': '<path d="M4 4l8 8M12 4l-8 8"/>',
    'search': '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>',
    'copy': '<rect x="5" y="5" width="8" height="8"/><path d="M3 10V3h7"/>',
    'arrow': '<path d="M3 8h10M9 4l4 4-4 4"/>',
    'back': '<path d="M13 8H3M7 4L3 8l4 4"/>',
    'plus': '<path d="M8 3v10M3 8h10"/>',
    'alert': '<path d="M8 2l6.5 12h-13z"/><path d="M8 6.5v3.5M8 11.6v.4"/>',
    'lock': '<rect x="3" y="7" width="10" height="7"/><path d="M5 7V5a3 3 0 0 1 6 0v2"/>',
    'clock': '<circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/>',
    'ext': '<path d="M9 3h4v4M13 3L7 9M11 9.5V13H3V5h3.5"/>',
    'more': '<circle cx="3.5" cy="8" r=".6"/><circle cx="8" cy="8" r=".6"/><circle cx="12.5" cy="8" r=".6"/>',
    'chev': '<path d="M6 4l4 4-4 4"/>',
    'down': '<path d="M4 6l4 4 4-4"/>',
    'globe': '<circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12"/>',
    'term': '<rect x="1.5" y="2.5" width="13" height="11"/><path d="M4.5 6.5l2 1.5-2 1.5M8 10h3.5"/>',
    'key': '<circle cx="5" cy="10" r="2.5"/><path d="M7 8.5l6-6M11 4.5l1.5 1.5"/>',
    'pause': '<path d="M5.5 3.5v9M10.5 3.5v9"/>',
    'play': '<path d="M5 3.5l7 4.5-7 4.5z"/>',
    'cursor': '<path d="M3.5 2.5l9 5-4 1-1.5 4z"/>',
    'eye': '<path d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8z"/><circle cx="8" cy="8" r="2"/>',
    'refresh': '<path d="M13 3v3.5H9.5"/><path d="M13 6.5A5.5 5.5 0 1 0 13.5 9"/>',
    'filter': '<path d="M2 3.5h12M4.5 8h7M7 12.5h2"/>',
}


def ic(name, size=16, color='currentColor', label=None):
    lab = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return f'<svg width="{size}" height="{size}" viewBox="0 0 16 16" fill="none" stroke="{color}" stroke-width="1.4" stroke-linecap="square" {lab} style="flex:none">{ICONS[name]}</svg>'


def google_g():
    return f'<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true" style="flex:none"><path d="M13.5 8.2H8.2v2.1h3.1c-.4 1.4-1.6 2.3-3.1 2.3a3.6 3.6 0 1 1 2.3-6.4l1.5-1.5A5.7 5.7 0 1 0 13.6 8z"/></svg>'


def github_g():
    return f'<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true" style="flex:none"><path d="M6 13.5c-3 .9-3-1.5-4.2-1.8M10 15v-2.3c0-.7.1-1.1-.4-1.6 1.9-.2 3.9-.9 3.9-4.2 0-.9-.3-1.7-.9-2.3.1-.2.4-1.1-.1-2.3 0 0-.7-.2-2.4.9a8 8 0 0 0-4.2 0C4.2 1.1 3.5 1.3 3.5 1.3c-.5 1.2-.2 2.1-.1 2.3-.6.6-.9 1.4-.9 2.3 0 3.3 2 4 3.9 4.2-.4.4-.5.9-.4 1.6V15"/></svg>'


# ---------- frames ----------

def dots(c='#2C2938'):
    return ''.join(f'<span style="width:10px;height:10px;border-radius:50%;background:{c};flex:none"></span>' for _ in range(3))


def browser(url, inner, hh=820):
    return (f'<div style="width:1440px;height:{hh}px;flex:none;border:1px solid {L2};background:{INK};overflow:hidden;display:flex;flex-direction:column;box-sizing:border-box">'
            f'<div class="m" style="height:40px;flex:none;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid {L1};background:{INK2};font-size:12px;color:{MUT}">{dots()}'
            f'<span style="margin-left:14px;width:520px;height:24px;display:flex;align-items:center;gap:8px;padding:0 10px;border:1px solid {L1}">{ic("lock",12,MUT)}{url}</span></div>'
            f'<div style="flex:1;display:flex;flex-direction:column;min-height:0">{inner}</div></div>')


def phone(inner, hh=844, url=None, bg=INK):
    bar = ''
    if url:
        bar = (f'<div class="m" style="flex:none;padding:16px 20px 10px;display:flex;justify-content:center"><span style="height:28px;padding:0 12px;display:flex;align-items:center;gap:6px;border:1px solid {L1};font-size:12px;color:{MUT}">{ic("lock",11,MUT)}{url}</span></div>')
    return (f'<div style="width:390px;height:{hh}px;flex:none;border:1px solid {L2};border-radius:44px;background:{bg};overflow:hidden;display:flex;flex-direction:column;box-sizing:border-box;padding-top:10px">'
            f'{bar}<div style="flex:1;display:flex;flex-direction:column;min-height:0">{inner}</div></div>')


def page(body, p=False, right=None, foot=True, top=False):
    """A simple page the server serves: nav, centred column, footer."""
    pad = '20px' if p else '48px'
    rt = right if right is not None else f'<a href="#" class="m" style="font-size:13px;text-decoration:none">docs</a>'
    nav = (f'<nav style="height:{56 if p else 64}px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 {pad};border-bottom:1px solid {L1}">{logo(26 if p else 30)}{rt}</nav>')
    al = 'flex-start' if (top or p) else 'center'
    main = (f'<main style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:{al};padding:{"40px 20px" if p else "48px"};min-height:0">'
            f'<div style="width:100%;max-width:{440}px;display:flex;flex-direction:column;gap:24px">{body}</div></main>')
    ft = ''
    if foot:
        ft = (f'<footer class="m" style="height:{52 if p else 56}px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 {pad};border-top:1px solid {L1};font-size:12px;color:{DIM}"><span>© 2026 glyphh ai</span><span>terms · privacy · status</span></footer>')
    return f'<div class="t" style="flex:1;display:flex;flex-direction:column;color:{FG};min-height:0">{nav}{main}{ft}</div>'


# ----- the harness (Claude window) -----

def user(text, p=False):
    return f'<div class="t" style="align-self:flex-end;max-width:{300 if p else 560}px;padding:12px 16px;border-radius:14px;background:#2B2A28;font-size:15px;line-height:1.5;color:#ECEAE4">{text}</div>'


def say(text):
    return f'<div class="t" style="font-size:15px;line-height:1.6;color:#ECEAE4">{text}</div>'


def prog(name):
    return f'<span class="m" style="color:{VI2}">&gt;{name}</span>'


def panel(name, body, right='', live=False):
    """An MCP panel as the harness renders it inline."""
    if live:
        right = f'<span style="display:inline-flex;align-items:center;gap:8px"><span class="cur dot" style="background:#FF4D4D"></span>live · fenced</span>'
    return (f'<div style="border:1px solid #3A3648;border-radius:12px;overflow:hidden;background:{INK2};color:{FG}">'
            f'<div class="m" style="min-height:40px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 14px;border-bottom:1px solid {L1};font-size:12px;color:{MUT}"><span style="display:inline-flex;align-items:center;gap:8px;white-space:nowrap">{logo(18)}<span>· {name}</span></span><span style="display:inline-flex;gap:10px;align-items:center">{right}</span></div>'
            f'{body}</div>')


def reply(p=False):
    return f'<div class="t" style="flex:none;height:46px;border-radius:12px;border:1px solid #3A3937;display:flex;align-items:center;padding:0 16px;font-size:14px;color:#8A8780">Reply to Claude…</div>'


def harness(conv, turns, hh=900):
    t = ''.join(turns)
    return (f'<div style="width:1440px;height:{hh}px;flex:none;border:1px solid {L2};border-radius:14px;background:#1F1E1D;overflow:hidden;display:flex;flex-direction:column;box-sizing:border-box">'
            f'<div class="t" style="height:44px;flex:none;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid #2E2D2B">{dots("#3A3937")}<span style="margin-left:14px;font-size:13px;color:#A3A19B">Claude · {conv}</span></div>'
            f'<div style="flex:1;display:flex;justify-content:center;padding:28px 0 24px;min-height:0;overflow:hidden">'
            f'<div style="width:760px;display:flex;flex-direction:column;gap:20px">{t}<div style="margin-top:auto">{reply()}</div></div></div></div>')


def harness_phone(conv, turns, hh=844):
    t = ''.join(turns)
    return (f'<div style="width:390px;height:{hh}px;flex:none;border:1px solid {L2};border-radius:44px;background:#1F1E1D;overflow:hidden;display:flex;flex-direction:column;box-sizing:border-box;padding-top:12px">'
            f'<div class="t" style="height:48px;flex:none;display:flex;align-items:center;justify-content:center;border-bottom:1px solid #2E2D2B;font-size:14px;color:#ECEAE4">{conv}</div>'
            f'<div style="flex:1;display:flex;flex-direction:column;gap:16px;padding:18px 12px 22px;min-height:0;overflow:hidden">{t}<div style="margin-top:auto">{reply(True)}</div></div></div>')


# ----- shared states -----

def waiting(title, body, p=False, extra=''):
    return (f'<div style="padding:{"20px" if p else "28px"};display:flex;gap:{16 if p else 22}px;align-items:flex-start">{cat("thinking", 44 if p else 56)}<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:12px">'
            f'<div class="m" style="display:flex;align-items:center;gap:10px;font-size:13px;color:{VI2}">{spinner()}<span>{title}</span><span class="cur" style="color:{FG}">█</span></div>'
            f'{ptxt(body, 14)}{extra}</div></div>')


def empty(title, body, action='', p=False):
    return (f'<div style="padding:{"36px 20px" if p else "48px 28px"};display:flex;flex-direction:column;align-items:center;text-align:center;gap:12px">'
            f'{cat("curious", 64)}{h(title, 20)}{ptxt(body, 14, extra="max-width:420px")}'
            f'{("<div style=" + chr(34) + "margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;justify-content:center" + chr(34) + ">" + action + "</div>") if action else ""}</div>')


def skel(w='100%', hh=12):
    return f'<div class="sk" style="width:{w};height:{hh}px"></div>'


def loading_rows(n=4, p=False):
    rows = ''.join(f'<div style="display:flex;align-items:center;gap:14px;padding:14px {"16px" if p else "20px"};border-top:1px solid {L1}">{skel("8px",8)}<div style="flex:1;display:flex;flex-direction:column;gap:8px">{skel(f"{40+(i*13)%35}%",12)}{skel(f"{20+(i*7)%20}%",8)}</div>{skel("60px",10)}</div>' for i in range(n))
    return f'<div><div class="m" style="display:flex;align-items:center;gap:12px;padding:14px {"16px" if p else "20px"};font-size:12px;color:{MUT}">{cat("generating", 30)}{spinner(14)}loading<span class="cur" style="color:{FG}">█</span></div>{rows}</div>'


def error_block(title, body, trace, p=False, action=None):
    act = action if action is not None else btn('try again', 'b2', 'sm') + btn('copy trace id', 'b3', 'sm')
    return (f'<div style="padding:{"20px" if p else "28px"};display:flex;gap:{16 if p else 22}px;align-items:flex-start">{cat("sleepy", 44 if p else 56, "Glyphh cat, error")}<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:12px">'
            f'<div class="m" style="display:flex;align-items:center;gap:10px;font-size:13px;color:{ERR}">{ic("alert",14,ERR)}error</div>'
            f'{h(title, 20)}{ptxt(body, 14)}'
            f'<div class="m" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:{MUT}">trace <span style="color:{FG};padding:3px 8px;border:1px solid {L2}">{trace}</span></div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap">{act}</div></div></div>')


def kv(rows, p=False):
    out = ''
    for k, v in rows:
        out += f'<div style="display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-top:1px solid {L1}"><span class="m" style="font-size:12px;color:{MUT}">{k}</span><span class="t" style="font-size:14px;color:{FG};text-align:right">{v}</span></div>'
    return f'<div>{out}</div>'


def screen_area(hh, mode='watch', p=False, site='youtube.com/watch?v=dQw4w9WgXcQ', step='step 2 of 5 · finding the clips'):
    """The machine's live screen inside the stream frame."""
    cards = ''.join(f'<div style="background:#fff;border:1px solid #E5E2DB;{"outline:2px solid #7C4DFF;" if i==1 else ""}"><div style="height:{60 if p else 96}px;background:{["#D9D3C7","#C9D3CB","#D3CCDB"][i]}"></div><div style="padding:{"8px" if p else "10px"};display:flex;flex-direction:column;gap:6px"><div style="height:8px;width:80%;background:#CFCAC0"></div><div style="height:6px;width:55%;background:#E2DED6"></div></div></div>' for i in range(3))
    bar_btns = ''
    over = ''
    if mode == 'watch':
        bar_btns = btn('watch', 'b2', 'sm', aria='Watching') + btn('take control', 'b1', 'sm')
    elif mode == 'control':
        bar_btns = btn('give back', 'b1', 'sm')
        over = f'<div class="m" style="position:absolute;left:0;right:0;top:36px;padding:8px 14px;background:{VI};color:#fff;font-size:12px;display:flex;justify-content:space-between;gap:8px"><span>you have control · the program is paused</span><span>esc to give back</span></div>'
    elif mode == 'ended':
        over = f'<div style="position:absolute;inset:0;background:rgba(11,10,16,.86);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px"><span class="m" style="font-size:13px;color:{FG2}">stream ended · 4m 12s</span>{btn("replay", "b2", "sm")}</div>'
    cursor = '' if mode == 'ended' else f'<div style="position:absolute;left:{46 if p else 52}%;top:{hh//2+10}px;width:14px;height:14px;border-radius:50%;background:rgba(124,77,255,.35);border:2px solid {VI}"></div>'
    stepline = 'you · driving' if mode == 'control' else step
    return (f'<div style="position:relative;height:{hh}px;background:#F7F6F3;overflow:hidden">'
            f'<div style="height:36px;display:flex;align-items:center;padding:0 12px;background:#ECEAE6;border-bottom:1px solid #DDDAD3"><span class="t" style="flex:1;height:22px;background:#fff;display:flex;align-items:center;padding:0 10px;font-size:12px;color:#6B6862;overflow:hidden;white-space:nowrap">{site}</span></div>'
            f'<div style="padding:{"12px" if p else "18px 22px"};display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:{"8px" if p else "14px"}">{cards}</div>'
            f'{cursor}{over}'
            + ('' if mode == 'ended' else f'<div class="m" style="position:absolute;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 12px;background:rgba(11,10,16,.94);font-size:12px;color:#B9B4C8"><span>{stepline}</span><span style="display:flex;gap:8px">{bar_btns}</span></div>')
            + '</div>')


def stream(name, machine, mode='watch', p=False, hh=None, site=None, step=None):
    hh = hh or (260 if p else 380)
    kw = {}
    if site: kw['site'] = site
    if step: kw['step'] = step
    right = None
    lab = f'{name} · {machine}'
    if mode == 'ended':
        right = 'ended'
    head_r = (f'<span style="display:inline-flex;align-items:center;gap:8px"><span class="cur dot" style="background:#FF4D4D"></span>live · fenced</span>' if mode != 'ended' else f'<span>ended</span>')
    return (f'<div style="border:1px solid #3A3648;border-radius:12px;overflow:hidden;background:{INK2}">'
            f'<div class="m" style="height:40px;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:0 14px;border-bottom:1px solid {L1};font-size:12px;color:{MUT}"><span style="display:inline-flex;align-items:center;gap:8px;white-space:nowrap;overflow:hidden">{logo(18)}<span>· {lab}</span></span>{head_r}</div>'
            f'{screen_area(hh, mode, p, **kw)}</div>')


# ----- board assembly -----

def row(idx, label, note, desk, ph, dh, phh):
    return dict(html=(f'<section style="display:flex;flex-direction:column;gap:20px">'
                      f'<div style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap"><span class="m" style="font-size:13px;color:{VI2}">{idx}</span><span class="d" style="font-size:28px;color:{FG}">{label}</span><span class="t" style="font-size:15px;color:{MUT}">{note}</span></div>'
                      f'<div style="display:flex;gap:64px;align-items:flex-start">{desk}{ph}</div></section>'),
                h=60 + max(dh, phh))


def head(num, name, kind, where, desc, states):
    st = ''.join(f'<span class="chip">{s}</span>' for s in states)
    return (f'<header style="display:flex;flex-direction:column;gap:18px;padding-bottom:40px;border-bottom:1px solid {L1}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">{logo(36)}<span class="m" style="font-size:13px;color:{MUT}">headless first · desktop 1440 · phone 390 · dark</span></div>'
            f'<div class="m" style="margin-top:28px;font-size:14px;color:{VI2}">screen {num} · {kind}</div>'
            f'<h1 class="d" style="margin:0;font-size:64px;line-height:1.04;color:{FG}">{name}</h1>'
            f'<p class="t" style="margin:0;max-width:980px;font-size:18px;line-height:1.6;color:{FG2}">{desc}</p>'
            f'<div class="m" style="font-size:13px;color:{MUT}">{where}</div>'
            f'<div style="display:flex;gap:8px;flex-wrap:wrap">{st}</div></header>')


HEAD_H = 420
PAD = 80
GAP = 112


def board(title, header, rows, extra_h=0):
    one_w = 1440 + 64 + 390
    total = PAD + HEAD_H + 64 + sum(r['h'] for r in rows) + GAP * (len(rows) - 1) + PAD + extra_h
    if total > 7900:
        cols = 2
        pairs = [rows[i:i + 2] for i in range(0, len(rows), 2)]
        total = PAD + HEAD_H + 64 + sum(max(x['h'] for x in pr) for pr in pairs) + GAP * (len(pairs) - 1) + PAD + extra_h
        width = PAD * 2 + one_w * 2 + 160
        body = f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:160px;row-gap:{GAP}px;align-items:start">' + ''.join(r['html'] for r in rows) + '</div>'
    else:
        width = PAD * 2 + one_w
        body = f'<div style="display:flex;flex-direction:column;gap:{GAP}px">' + ''.join(r['html'] for r in rows) + '</div>'
    total += 40
    inner = f'<div class="t" style="width:{width}px;min-height:{total}px;box-sizing:border-box;padding:{PAD}px;background:{INK};color:{FG};display:flex;flex-direction:column;gap:64px">{header}{body}</div>'
    return doc(title, inner, width, total), width, total


def doc(title, inner, w, hh):
    props = json.dumps({"$preview": {"width": w, "height": hh}})
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
{FONTS}
<style>
{CSS}
</style>
</helmet>
{inner}
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{props}'>
class Component extends DCLogic {{
renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
'''


META = ROOT + '/../gen/meta.json'


def emit(fname, page_id, page_name, html, w, hh, title):
    """Write the artboard locally and record its index entry (merged into the fresh index at publish)."""
    os.makedirs(ROOT + '/project', exist_ok=True)
    open(f'{ROOT}/project/{fname}', 'w').write(html)
    m = json.load(open(META)) if os.path.exists(META) else []
    m = [x for x in m if x['file'] != fname]
    m.append(dict(file=fname, page=page_id, name=page_name, w=w, h=hh, title=title))
    m.sort(key=lambda x: x['page'])
    json.dump(m, open(META, 'w'), indent=1)
    print(fname, w, hh, len(html))


def index(files):
    """Merge the named boards into the freshly read index; write it under ROOT."""
    d = json.load(open(FRESH))
    m = [x for x in json.load(open(META)) if x['file'] in files]
    ids = [p['id'] for p in d['pages']]
    for x in m:
        if x['page'] not in ids:
            mine = [i for i, p in enumerate(d['pages']) if p['id'].startswith('hs-') and p['id'] < x['page']]
            if mine:
                at = mine[-1] + 1
            elif 'brand-terminal' in ids:
                at = ids.index('brand-terminal') + 1
            else:
                at = len(d['pages'])
            d['pages'].insert(at, {'id': x['page'], 'name': x['name']})
            ids = [p['id'] for p in d['pages']]
        d['boards'][x['file']] = {'x': 0, 'y': 0, 'w': x['w'], 'h': x['h'], 'page': x['page'], 'title': x['title']}
        if x['file'] not in d['order']:
            d['order'].append(x['file'])
    json.dump(d, open(f'{ROOT}/project/canvas.json', 'w'), ensure_ascii=False, indent=1)
    print([p['id'] for p in d['pages']])
