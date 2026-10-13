from sp import *
U = 'reels.glyphh.app'
def wide(body, p, right=None):
    pad = '20px' if p else '48px'
    rt0 = right if right is not None else f'<span class="m" style="font-size:12px;color:{MUT}">by [ORG NAME] · on</span>{logo(32)}'
    rt = f'<span style="display:inline-flex;align-items:center;gap:8px">{rt0}</span>' if right is None else rt0
    nav = f'<nav style="height:{64 if p else 80}px;flex:none;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 {pad};border-bottom:1px solid {L1}"><span class="m" style="font-weight:600;font-size:18px">{gt()}reels</span>{rt if not p else ""}</nav>'
    main = f'<main style="flex:1;display:flex;justify-content:center;padding:{"32px 20px" if p else "64px 48px"};min-height:0"><div style="width:100%;max-width:880px;display:flex;flex-direction:column;gap:{28 if p else 36}px">{body}</div></main>'
    ft = f'<footer class="m" style="height:64px;flex:none;display:flex;align-items:center;justify-content:space-between;padding:0 {pad};border-top:1px solid {L1};font-size:12px;color:{DIM}"><span style="display:inline-flex;align-items:center;gap:8px">runs on {logo(32)}</span><span>terms · report</span></footer>' if not p else ''
    return f'<div class="t" style="flex:1;display:flex;flex-direction:column;color:{FG};min-height:0">{nav}{main}{ft}</div>'
def wrow(idx,label,note_,body,dh=1000,ph=1100):
    dh += 40; ph += 40
    return row(idx,label,note_,browser(U,wide(body(False),False),dh),phone(wide(body(True),True),ph,url=U),dh,ph)
def intro(p):
    return stack(f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">{status("online","#3FD08F")}<span class="chip">public</span><span class="chip">6 functions</span></div>', h('Turn a YouTube video into reels.', 34 if p else 52), ptxt('Give it a YouTube link. It finds the best moments, cuts them to 9:16, writes captions and hands back ready-to-post reels.', 16 if p else 18), gap=16)
def code(lines):
    return f'<div class="m" style="border:1px solid {L2};background:{INK2};padding:16px 18px;font-size:13px;line-height:1.9;color:{FG2};overflow:hidden;white-space:pre-wrap;word-break:break-all">{lines}</div>'
def how(p):
    tabs = ''.join(f'<button type="button" class="m" style="background:none;border:0;border-bottom:1px solid {FG if i==0 else "transparent"};color:{FG if i==0 else MUT};font-size:13px;min-height:40px;padding:0 2px;cursor:pointer">{t}</button>' for i,t in enumerate(['any harness','API','CLI']))
    return stack(f'<div class="m" style="font-size:13px;color:{VI2}">how to call it</div>', f'<div style="display:flex;gap:22px;border-bottom:1px solid {L1}">{tabs}</div>',
        code(f'<span style="color:{MUT}"># in Claude, Codex, Gemini: just ask</span>\n<span style="color:{FG}">use reels on https://youtu.be/[VIDEO]</span>\n<span style="color:{MUT}"># Glyphh’s search tool finds it; no new connection</span>'),
        f'<div style="display:grid;grid-template-columns:repeat({1 if p else 3},minmax(0,1fr));gap:12px">' + ''.join(f'<div style="border:1px solid {L1};padding:14px;display:flex;flex-direction:column;gap:8px">{mono(a,12,MUT)}<span class="t" style="font-size:14px;color:{FG}">{b}</span></div>' for a,b in [('takes','a YouTube URL'),('returns','result · a zip of reels'),('may ask','needs auth · YouTube, once')]) + '</div>', gap=14)
def s1(p):
    return intro(p) + how(p) + note('reels is public: anyone with Glyphh can call it; it runs on its owner’s machine and bills the caller’s credit [CONFIRM]')
def ui(p, state='idle'):
    inp = f'<div style="display:flex;gap:8px;flex-wrap:{"wrap" if p else "nowrap"}"><div style="flex:1;min-width:0"><label class="lb" for="yt">YouTube URL</label><input id="yt" class="in" value="{"https://youtu.be/[VIDEO]" if state!="idle" else ""}" placeholder="https://youtu.be/…"></div><div style="display:flex;align-items:flex-end">{btn("make reels" if state=="idle" else "making","b1","dis" if state=="run" else "")}</div></div>'
    out = ''
    if state == 'run':
        out = stream('reels', 'reels.glyphh.app', 'watch', p, 220 if p else 300, site='youtube.com/watch?v=[VIDEO]', step='step 3 of 5 · cutting clip 4 of 6')
    if state == 'done':
        tiles = ''.join(f'<div style="display:flex;flex-direction:column;gap:8px"><div style="aspect-ratio:9/16;background:#16141D;border:1px solid {L1};display:flex;align-items:flex-end;padding:8px">{mono(f"0:{12+i*7:02d}",11,FG2)}</div>{mono(f"reel {i+1}",11,MUT)}</div>' for i in range(6 if not p else 3))
        out = stack(f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">{chip("result")}<span style="display:flex;gap:8px">{btn("download all","b1","sm")}{btn("call it again","b2","sm")}</span></div>', f'<div style="display:grid;grid-template-columns:repeat({3 if p else 6},minmax(0,1fr));gap:10px">{tiles}</div>', gap=16)
    return stack(f'<div class="m" style="font-size:13px;color:{VI2}">try it</div>', box(stack(inp, out, gap=20), 20), gap=14)
def s2(p): return intro(p) + ui(p) + how(p)
def s3(p): return intro(p) + ui(p,'run')
def s4(p): return intro(p) + ui(p,'done')
def s5(p):
    return stack(f'<div style="display:flex;gap:10px;align-items:center">{status("offline",DIM)}<span class="chip">public</span></div>', h('reels is offline right now.', 30 if p else 44), ptxt('The machine it runs on isn’t reachable. Its owner has been told. Calls made now wait up to 1 hour [CONFIRM] and then fail with a clear reason.', 16), rowx(btn('notify me when it’s back','b1'), btn('how to call it','b2')), gap=18)
def s6(p):
    return stack(mark('err'), h('reels couldn’t make those reels.', 30 if p else 44), ptxt('The video is private, so reels can’t fetch it. Use a public or unlisted video, or ask its owner to share it.', 16), trace('tr_01JA8JQ6V1BH'), rowx(btn('try another link','b1'), btn('back','b2')), gap=18)
def s7(p):
    return stack(mark('warn'), h('No program here.', 30 if p else 44), ptxt('Nothing public is called <span class="m" style="color:#F5F3FA">reel</span>. It may have been renamed or made private.', 16), rowx(btn('go to glyphh.ai','b2')), gap=18)
rows = [wrow('01','About and how to call it','a program with no UI of its own',s1,1000,1300), wrow('02','Its own UI','when the program ships one',s2,1240,1700), wrow('03','Running','the live stream on its public page',s3,1100,1180), wrow('04','Result','ready to download',s4,1000,1240), wrow('05','Offline','its machine isn’t reachable',s5,820,844), wrow('06','Error','the program’s own reason, the trace id',s6,820,844), wrow('07','Not found','no public program by that name',s7,820,844)]
hdr = head('08','A public program','simple page','served through Glyphh’s relay at &lt;program&gt;.glyphh.app from the rrotor it runs on · reels drawn','What a public program looks like to anyone: what it does and how to call it, and its own UI when it has one. The program’s name takes the place of the wordmark; Glyphh signs the footer.',['about + how to call','its own UI','running','result','offline','error','not found'])
html, w, hh = board('A public program', hdr, rows)
emit('Screen08PublicProgram.dc.html','hs-08','Screen 08 · A public program',html,w,hh,'Screen 08 · A public program')
