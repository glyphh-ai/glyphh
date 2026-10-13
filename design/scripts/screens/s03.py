from sp import *
U = 'glyphh.ai/allow'
def org_pick(p, open_=False):
    sel = f'<div><label class="lb" for="org">acts in the org</label><button type="button" id="org" class="in" style="justify-content:space-between;cursor:pointer;border-color:{VI if open_ else L2}"><span>[ORG NAME]</span>{ic("down",14,MUT)}</button>'
    if open_:
        opts = ''.join(f'<div class="m" style="display:flex;justify-content:space-between;align-items:center;min-height:44px;padding:0 14px;border-top:1px solid {L1};font-size:14px;color:{FG if i==0 else FG2}">{n}{ic("check",14,VI) if i==0 else "<span style=" + chr(34) + "font-size:12px;color:" + MUT + chr(34) + ">" + r + "</span>"}</div>' for i,(n,r) in enumerate([('[ORG NAME]','admin'),('chris (personal)','owner'),('[OTHER ORG]','member')]))
        sel += f'<div style="border:1px solid {L2};border-top:0;background:{INK2}">{opts}</div>'
    return sel + '</div>'
def can(p):
    items = [('call your programs and see their results','check'),('build programs and add their tools','check'),('show panels: machines, usage, approvals','check'),('spend from the org’s credit, within its limits','check')]
    li = ''.join(f'<div style="display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-top:1px solid {L1}">{ic(n,14,OK)}<span class="t" style="font-size:14px;line-height:1.5;color:{FG2}">{t}</span></div>' for t,n in items)
    return stack(note('it will be able to'), f'<div>{li}</div>', gap=6)
def ask(p, open_=False):
    return (eyebrow('claude.ai · Claude') + stack(title('Claude wants to use your Glyphh', p), ptxt('Signed in as <span class="m" style="color:#F5F3FA">chris@[COMPANY].com</span>. You can take this back any time from Account.'))
            + org_pick(p, open_) + can(p) + rowx(btn('allow', 'b1'), btn('deny', 'b2')))
def s1(p): return ask(p)
def s2(p): return ask(p, True)
def s3(p):
    return (mark('ok') + stack(title('Claude is connected', p), ptxt('Claude now acts in <span class="m" style="color:#F5F3FA">[ORG NAME]</span>. Go back to it; your programs are already there.'))
            + rowx(btn('back to Claude', 'b1', prompt=True)) + note('this tab closes itself in 5s<span class="cur" style="color:#F5F3FA">█</span>'))
def s4(p):
    return (mark('err') + stack(title('Claude is not connected', p), ptxt('You denied it, so Claude can’t reach your Glyphh. Nothing was shared. Ask Claude to connect again whenever you want to.'))
            + rowx(btn('back to Claude', 'b2'), btn('allow after all', 'b3')))
def s5(p):
    return (mark('warn') + stack(title('This request has expired', p), ptxt('Allow links last 10 minutes [CONFIRM]. Go back to Claude and connect Glyphh again for a fresh one.'))
            + rowx(btn('back to Claude', 'b1')) + trace('tr_01JA8CZ3PMX0'))
rows = [sp_row('01','Allow','the harness, the org it acts in, what it may do',U,s1,dh=900,ph=900), sp_row('02','Choosing the org','for members of more than one',U,s2,dh=1000,ph=1060), sp_row('03','Connected','back to the harness',U,s3), sp_row('04','Not connected','after deny',U,s4), sp_row('05','Expired','the link is stale',U,s5)]
hdr = head('03','Allow','simple page','served by the server at glyphh.ai/allow · OAuth consent for a harness','A harness asks to use your Glyphh. You see which one, pick the org it acts in, and allow or deny. Claude is drawn; Codex, Gemini and any other harness get the same page with their name.',['allow','choosing the org','connected','not connected','expired'])
html, w, hh = board('Allow', hdr, rows)
emit('Screen03Allow.dc.html','hs-03','Screen 03 · Allow',html,w,hh,'Screen 03 · Allow')
