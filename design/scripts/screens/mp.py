# helpers for MCP panels inside the harness
from sp import *

def prow(idx, label, note_, conv, turns, dh=900, ph=844):
    return row(idx, label, note_, harness(conv, turns(False), dh), harness_phone(conv, turns(True), ph), dh, ph)

def pad(inner, p, v=None):
    return f'<div style="padding:{v or ("16px" if p else "20px")}">{inner}</div>'

def toolbar(left, right='', p=False):
    return f'<div style="display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;padding:{"12px 16px" if p else "14px 20px"};border-bottom:1px solid {L1}">{left}<div style="display:flex;gap:8px;flex-wrap:wrap">{right}</div></div>'

def search(ph_, val='', p=False, w=None):
    v = f' value="{val}"' if val else ''
    return f'<div style="position:relative;flex:1;min-width:{160 if p else 240}px;{"max-width:" + str(w) + "px;" if w else ""}"><span style="position:absolute;left:12px;top:15px;color:{MUT}">{ic("search",14)}</span><input class="in" aria-label="Search" placeholder="{ph_}"{v} style="padding-left:34px;min-height:44px"></div>'

def item(p, title, sub, right='', meta='', lead=''):
    """one list row; on the phone the right side drops under."""
    if p:
        return (f'<div style="display:flex;flex-direction:column;gap:8px;padding:14px 16px;border-top:1px solid {L1}">'
                f'<div style="display:flex;justify-content:space-between;gap:10px;align-items:center">{lead}<div style="flex:1;min-width:0">{title}</div>{ic("chev",14,MUT)}</div>'
                f'{sub}{("<div style=" + chr(34) + "display:flex;gap:8px;flex-wrap:wrap;align-items:center" + chr(34) + ">" + right + meta + "</div>") if (right or meta) else ""}</div>')
    return (f'<div style="display:flex;gap:16px;align-items:center;padding:14px 20px;border-top:1px solid {L1}">{lead}'
            f'<div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:6px">{title}{sub}</div>'
            f'<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex:none">{right}{meta}</div></div>')

def tname(t, size=14, c=FG):
    return f'<span class="m" style="font-size:{size}px;color:{c};font-weight:500">{t}</span>'

def sub(t):
    return f'<span class="t" style="font-size:13px;line-height:1.5;color:{MUT}">{t}</span>'

def foot(left, right=''):
    return f'<div class="m" style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 20px;border-top:1px solid {L1};font-size:12px;color:{MUT}"><span>{left}</span><span style="display:flex;gap:8px">{right}</span></div>'

def section_label(t, p=False):
    return f'<div class="m" style="padding:{"14px 16px 8px" if p else "16px 20px 8px"};font-size:12px;color:{MUT}">{t}</div>'

def tabs(names, sel=0, p=False):
    t = ''.join(f'<button type="button" class="m" style="background:none;border:0;border-bottom:1px solid {FG if i==sel else "transparent"};color:{FG if i==sel else MUT};font-size:13px;min-height:44px;padding:0 2px;cursor:pointer;white-space:nowrap">{n}</button>' for i,n in enumerate(names))
    return f'<div style="display:flex;gap:{16 if p else 22}px;padding:0 {"16px" if p else "20px"};border-bottom:1px solid {L1};overflow:hidden">{t}</div>'

def bar(pct, c=VI):
    return f'<div style="height:6px;background:#16141D"><div style="width:{pct}%;height:6px;background:{c}"></div></div>'

def stat(label, val, subt='', p=False):
    return f'<div style="display:flex;flex-direction:column;gap:6px;padding:{"14px 16px" if p else "16px 20px"};border:1px solid {L1}">{mono(label,12,MUT)}<span class="d" style="font-size:{24 if p else 28}px">{val}</span>{sub(subt) if subt else ""}</div>'

def grid(n, items, gap=10):
    return f'<div style="display:grid;grid-template-columns:repeat({n},minmax(0,1fr));gap:{gap}px">{"".join(items)}</div>'

def seg(opts, sel):
    return '<div style="display:inline-flex;border:1px solid ' + L2 + '">' + ''.join(f'<button type="button" class="m" style="min-height:34px;padding:0 10px;border:0;{"background:" + FG + ";color:" + INK if o==sel else "background:transparent;color:" + FG2};font-size:12px;cursor:pointer">{o}</button>' for o in opts) + '</div>'
