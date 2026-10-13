from g import *

def sec(n, title, note, body):
    return (f'<section style="display:flex;flex-direction:column;gap:28px;padding-top:56px;border-top:1px solid {L1}">'
            f'<div style="display:flex;align-items:baseline;gap:16px;flex-wrap:wrap"><span class="m" style="font-size:13px;color:{VI2}">{n}</span><span class="d" style="font-size:32px">{title}</span><span class="t" style="font-size:15px;color:{MUT}">{note}</span></div>{body}</section>')

def cap(t):
    return f'<div class="m" style="font-size:12px;color:{MUT}">{t}</div>'

def tile(inner, label, w=None, bg=INK, hh=None):
    ws = f'width:{w}px;' if w else ''
    hs = f'height:{hh}px;' if hh else ''
    return f'<div style="{ws}display:flex;flex-direction:column;gap:12px"><div style="{hs}background:{bg};border:1px solid {L2};display:flex;align-items:center;justify-content:center;padding:32px;box-sizing:border-box">{inner}</div>{cap(label)}</div>'

# 01 logo
wmk = (f'<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:32px">'
       + tile(f'<img src="{LOGO}" alt="Glyphh" style="width:320px;height:auto;display:block">', 'the full logo · cat and glyphh in its white sticker border', hh=260)
       + tile(logo(48), 'page head · 48 high', hh=260)
       + tile(f'<div style="width:100%;height:64px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid {L1}">{logo(30)}<span class="m" style="font-size:13px;color:{FG2}">docs</span></div>', 'nav · 30 high · hairline under', hh=260)
       + tile(f'<span class="m" style="display:inline-flex;align-items:center;gap:8px;font-size:12px;color:{MUT}">{logo(18)}<span>· venues · studio-mac</span></span>', 'panel and stream head · 18 high', hh=260)
       + '</div>'
       + ptxt('One logo everywhere it lands: nav, page head, panel head. Always the uploaded sticker artwork, never redrawn or recoloured; on ink only.', 15, extra='max-width:900px'))

# 01b mascot
def mood(m, lab, use):
    return f'<div style="display:flex;flex-direction:column;gap:12px"><div style="height:220px;background:{INK};border:1px solid {L2};display:flex;align-items:center;justify-content:center">{cat(m, 96)}</div><div class="m" style="font-size:12px;color:{FG}">{lab}</div>{cap(use)}</div>'
masc = (f'<div style="display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:24px">'
        + mood('idle','idle','at rest') + mood('curious','curious','empty') + mood('thinking','thinking','waiting') + mood('generating','big eye','loading') + mood('done','done','success, approved, paid') + mood('sleepy','sleepy','error, expired, offline')
        + '</div>' + ptxt('The cat alone is the mascot, face 1: ink body, white sticker border, white eye. Its eye says the state; nothing orbits it. It blinks every few seconds, still under reduced motion.', 15, extra='max-width:900px'))

# 02 type
typ = (f'<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:48px">'
       f'<div style="display:flex;flex-direction:column;gap:14px">{h("Programs that get real work done.",44)}{cap("red hat display 600 · headings · tracking -0.025em · 64 / 44 / 28 / 20")}</div>'
       f'<div style="display:flex;flex-direction:column;gap:14px">{ptxt("Your reels program is waiting on YouTube. Approve it once and it carries on where it stopped; nothing else is shared.",17,FG2)}{cap("red hat text 400 · reading · 17 / 15 / 14 · line 1.6")}</div>'
       f'<div style="display:flex;flex-direction:column;gap:14px"><div class="m" style="font-size:15px;line-height:1.9;color:{FG2}">{gt()}<span style="color:{FG}">reels</span> https://youtu.be/[ID]<br><span style="color:{MUT}">labels · nav · buttons · chips · code</span></div>{cap("red hat mono 400–600 · 15 / 14 / 13 / 12")}</div></div>')

# 03 colour
def sw(c, n, use, border=False):
    b = f'border:1px solid {L2};' if border else ''
    return f'<div style="display:flex;flex-direction:column;gap:10px"><div style="height:88px;background:{c};{b}"></div><div class="m" style="font-size:12px;color:{FG}">{n}</div><div class="m" style="font-size:12px;color:{MUT}">{c} · {use}</div></div>'
col = (f'<div style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:24px">'
       + sw(INK, 'ink', 'ground', True) + sw(INK2, 'ink 2', 'panels, fields', True) + sw(L1, 'line 1', 'hairlines') + sw(L2, 'line 2', 'outlines') + sw(FG, 'paper', 'text, primary fill') + sw(FG2, 'mist', 'reading text') + sw(MUT, 'dust', 'labels')
       + sw(VI, 'violet', 'the one accent') + sw(VI2, 'violet light', 'accent text on ink') + sw(OK, 'ready', 'online, paid, approved') + sw(WARN, 'waiting', 'needs input') + sw(AUTH, 'auth', 'needs auth') + sw(CYAN, 'panel', 'panel returns') + sw(ERR, 'error', 'refused, failed')
       + '</div>' + ptxt('Status colours only ever mark a state, as a 6–8px square or dot beside mono text; they never fill a button or a surface. Violet is the one accent.', 15, extra='max-width:900px'))

# 04 buttons + fields
bt = (f'<div style="display:flex;gap:56px;align-items:flex-start;flex-wrap:wrap">'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("start building","b1",prompt=True)}{cap("primary · paper fill · ink text")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("continue")}{cap("primary")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("read the docs","b2")}{cap("secondary · hairline outline")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("cancel","b3")}{cap("quiet · text only")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("remove machine","bd")}{cap("destructive · outlined")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px"><div style="display:flex;gap:8px">{btn("approve","b1","sm")}{btn("deny","b2","sm")}</div>{cap("small · 34 · in panels")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px">{btn("pay $20.00","b1","dis")}{cap("disabled · 40%")}</div>'
      f'<div style="display:flex;flex-direction:column;gap:12px"><button type="button" class="b1" style="gap:10px">{spinner(14)}paying</button>{cap("busy")}</div>'
      '</div>'
      f'<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:32px;max-width:1200px">'
      f'<div><label class="lb" for="f1">machine code</label><input id="f1" class="in" value="" placeholder="XXXX-XXXX">{cap("<span style=" + chr(39) + "display:block;margin-top:8px" + chr(39) + ">field · ink 2 · hairline</span>")}</div>'
      f'<div><label class="lb" for="f2">machine code</label><input id="f2" class="in" value="K7QD-" style="border-color:{VI}">{cap("<span style=" + chr(39) + "display:block;margin-top:8px" + chr(39) + ">focused · violet line</span>")}</div>'
      f'<div><label class="lb" for="f3">machine code</label><input id="f3" class="in" value="K7QD-0000" style="border-color:{ERR}"><div class="m" style="margin-top:8px;font-size:12px;color:{ERR}">no machine is waiting with that code</div></div>'
      '</div>'
      + ptxt('Square corners everywhere in Glyphh; the only rounding is the harness drawing its own panel. Touch targets 44px; small buttons only inside panels on desktop.', 15, extra='max-width:900px'))

# 05 chips
rows5 = [('text','plain words back; the harness shows them as the answer'),('panel','HTML rendered inline: a list, a form, the live machine'),('link','a page to open, e.g. Pay or a public program'),('needs input','one value it cannot go on without, e.g. a YouTube URL'),('needs auth','a connection to approve; it carries on after'),('working','running; check back, or it reports when done'),('result','the output in R2, fetched with a token the owner approves'),('error','what failed, with the trace id')]
chips = (f'<div style="display:flex;gap:10px;flex-wrap:wrap">' + ''.join(chip(k, blink=(k=='working')) for k,_ in rows5) + '</div>'
         f'<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:64px;max-width:1500px">'
         + ''.join(f'<div style="display:flex;gap:20px;align-items:center;padding:14px 0;border-top:1px solid {L1}"><span style="width:140px;flex:none">{chip(k, blink=(k=="working"))}</span>{ptxt(v,14)}</div>' for k,v in rows5) + '</div>')

# 06 states: panel width and phone
def pair(desk, ph):
    return f'<div style="display:flex;gap:48px;align-items:flex-start"><div style="width:760px;flex:none">{desk}</div><div style="width:366px;flex:none">{ph}</div></div>'

def stcol(label, d, p):
    return f'<div style="display:flex;flex-direction:column;gap:14px">{cap(label + " · panel 760 · phone 366")}{pair(d, p)}</div>'

wt = lambda p: panel('reels', waiting('waiting for you to approve YouTube', 'The program is paused at step 2 of 5. It goes on by itself the moment you approve, here or from the link we emailed you.', p, f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">{btn("approve YouTube","b1","sm")}{btn("not now","b2","sm")}</div>'), chip('needs auth'))
em = lambda p: panel('programs', empty('No programs yet', 'Describe a job to Claude and Glyphh builds it into a program you can call from anywhere.', btn('build one', 'b1', 'sm', prompt=True) + btn('see examples', 'b2', 'sm'), p))
ld = lambda p: panel('programs', loading_rows(3, p))
er = lambda p: panel('usage', error_block('Usage didn’t load', 'The server didn’t answer in time. Nothing changed; try again, and if it keeps happening send us the trace id.', 'tr_01JA7Q3K9X2M', p))
states = (f'<div style="display:grid;grid-template-columns:repeat(1,minmax(0,1fr));gap:56px">'
          + stcol('waiting', wt(False), wt(True)) + stcol('empty', em(False), em(True)) + stcol('loading', ld(False), ld(True)) + stcol('error with trace id', er(False), er(True)) + '</div>')

# 07 live stream
lv = (f'<div style="display:flex;flex-direction:column;gap:56px">'
      + stcol('watching · watch is on by default, take control is one press', stream('reels', 'studio-mac', 'watch'), stream('reels', 'studio-mac', 'watch', True))
      + stcol('you have control · the program pauses until you give it back', stream('reels', 'studio-mac', 'control'), stream('reels', 'studio-mac', 'control', True))
      + stcol('ended · the run finished; a replay stays for 7 days [CONFIRM RETENTION]', stream('reels', 'studio-mac', 'ended'), stream('reels', 'studio-mac', 'ended', True))
      + '</div>')

hdr = head('00', 'Shared parts', 'shared', 'used by every simple page and every MCP panel', 'The parts every screen is built from: the logo, the cat mascot, type, colour, buttons and fields, the chips for the types a call returns, the four states every panel has, and the frame that streams a program’s machine live with watch and take control.', ['logo','mascot','type','colour','buttons','fields','return types','waiting','empty','loading','error + trace id','live stream'])

secs = [sec('01','Logo','the full Glyphh logo, the uploaded sticker',wmk), sec('01b','Mascot','the cat, its eye says the state',masc), sec('02','Type','Red Hat Display, Text, Mono',typ), sec('03','Colour','ink ground, one violet accent, status as marks',col), sec('04','Buttons and fields','square, mono, light fill primary, outlined secondary',bt), sec('05','Every call returns a type','the chip a panel and the stream show for each',chips), sec('06','States','every panel has them, drawn at the harness’s panel width and on a phone',states), sec('07','The live stream frame','a program’s machine, live wherever it was called',lv)]
W = 2054; H = 7300
inner = f'<div class="t" style="width:{W}px;min-height:{H}px;box-sizing:border-box;padding:80px;background:{INK};color:{FG};display:flex;flex-direction:column;gap:64px">{hdr}{"".join(secs)}</div>'
emit('Screen00Shared.dc.html', 'hs-00', 'Screen 00 · Shared parts', doc('Shared parts', inner, W, H), W, H, 'Screen 00 · Shared parts')
