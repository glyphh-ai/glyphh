from sp import *
U = 'glyphh.ai/join/[INVITE]'
def inv(p):
    return box(kv([('org','[ORG NAME]'),('invited by','Chris Timmerman'),('your role','member'),('for','sam@[COMPANY].com')]), 4, L1, INK)
def s1(p):
    return eyebrow('invite') + stack(title('Join [ORG NAME] on Glyphh', p), ptxt('Chris invited you. Members call the org’s programs from their own harness and share its credit and machines.')) + inv(p) + rowx(btn('accept','b1'), btn('decline','b2')) + note('signed in as sam@[COMPANY].com · not you? <a href="#">switch</a>')
def s0(p):
    return eyebrow('invite') + stack(title('Join [ORG NAME] on Glyphh', p), ptxt('Sign in with the email the invite was sent to, <span class="m" style="color:#F5F3FA">sam@[COMPANY].com</span>, to accept it.')) + stack(f'<button type="button" class="b1 w" style="justify-content:flex-start;gap:12px">{google_g()}continue with Google</button>', f'<button type="button" class="b2 w" style="justify-content:flex-start;gap:12px">{github_g()}continue with GitHub</button>')
def s2(p):
    return mark('ok') + stack(title('You’ve joined [ORG NAME]', p), ptxt('Its programs are in your harness now. Ask Claude for them, or connect Claude first if you haven’t.')) + rowx(btn('open Claude','b1',prompt=True), btn('connect a harness','b2'))
def s3(p):
    return mark('err') + stack(title('Invite declined', p), ptxt('We told Chris. If that was a mistake, ask Chris to send a new invite.')) + rowx(btn('go to glyphh.ai','b2'))
def s4(p):
    return mark('warn') + stack(title('This invite has expired', p), ptxt('Invites last 7 days [CONFIRM]. Ask Chris, or another admin of [ORG NAME], to send a new one.')) + rowx(btn('go to glyphh.ai','b2')) + trace('tr_01JA8FA0NN6C')
def s5(p):
    return mark('warn') + stack(title('This invite is for another email', p), ptxt('It was sent to <span class="m" style="color:#F5F3FA">sam@[COMPANY].com</span>; you’re signed in as <span class="m" style="color:#F5F3FA">sam@[PERSONAL].com</span>.')) + rowx(btn('switch account','b1'), btn('decline','b2'))
rows = [sp_row('01','Sign in to accept','not signed in yet',U,s0), sp_row('02','Invite','accept or decline',U,s1), sp_row('03','Joined','into the org',U,s2), sp_row('04','Declined','the inviter is told',U,s3), sp_row('05','Expired','ask for a new one',U,s4), sp_row('06','Wrong account','signed in as someone else',U,s5)]
hdr = head('05','Join','simple page','served by the server at glyphh.ai/join/[INVITE] · from the invite email','An invite to an org. Accept it and the org’s programs, machines and credit are yours to use from any harness.',['sign in to accept','invite','joined','declined','expired','wrong account'])
html, w, hh = board('Join', hdr, rows)
emit('Screen05Join.dc.html','hs-05','Screen 05 · Join',html,w,hh,'Screen 05 · Join')
