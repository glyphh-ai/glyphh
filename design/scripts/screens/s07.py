from sp import *
U = 'glyphh.ai/result/[RESULT]'
def req(p):
    return box(kv([('program','reels'),('result','6 reels · reels-7c9e.zip · 84 MB'),('asked by','Codex · sam@[COMPANY].com'),('token','one download · 1 hour'),('asked','2 minutes ago')]),4,L1,INK)
def s1(p):
    return eyebrow('approve a result') + stack(title('Sam wants the reels result', p), ptxt('Approving gives Sam’s Codex a one-time token to download it. Nothing else of yours is shared.')) + req(p) + rowx(btn('approve','b1'), btn('deny','b2'))
def s2(p):
    return mark('ok') + stack(title('Approved', p), ptxt('Sam’s Codex has its token and is fetching the result now. The token works once, for 1 hour.')) + box(f'<div class="m" style="display:flex;justify-content:space-between;gap:10px;font-size:13px;color:{FG2}"><span>reels-7c9e.zip</span><span style="color:{OK}">fetched · 84 MB</span></div>',14) + rowx(btn('done','b2'))
def s3(p):
    return mark('err') + stack(title('Denied', p), ptxt('Sam’s Codex is told no. The result stays where it is; Sam can ask again.')) + rowx(btn('done','b2'))
def s4(p):
    return mark('warn') + stack(title('This request has expired', p), ptxt('Requests last 24 hours [CONFIRM]. Sam can ask again from Codex.')) + rowx(btn('done','b2')) + trace('tr_01JA8H0D3EV7')
def s5(p):
    return mark('warn') + stack(title('Already answered', p), ptxt('You approved this 12 minutes ago, from Needs you in Claude. Nothing more to do.')) + rowx(btn('done','b2'))
rows = [sp_row('01','Approve a result','who asks, for what, for how long',U,s1,dh=880,ph=900), sp_row('02','Approved','the caller fetches it',U,s2), sp_row('03','Denied','the caller is told',U,s3), sp_row('04','Expired','ask again',U,s4), sp_row('05','Already answered','from another place',U,s5)]
hdr = head('07','Approve a result','simple page','served by the server at glyphh.ai/result/[RESULT] · from the email or the link the program sends · also in Needs you','A program’s result sits in R2. A caller who wants it asks for a token; the owner approves or denies it here, and the token works once.',['approve','approved','denied','expired','already answered'])
html, w, hh = board('Approve a result', hdr, rows)
emit('Screen07ApproveResult.dc.html','hs-07','Screen 07 · Approve a result',html,w,hh,'Screen 07 · Approve a result')
