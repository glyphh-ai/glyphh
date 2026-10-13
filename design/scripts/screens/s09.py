from sp import *
def big(code, p):
    return f'<div class="m" style="font-size:{48 if p else 64}px;font-weight:600;line-height:1;color:{FG}">{gt()}{code}<span class="cur" style="color:{VI}">█</span></div>'
def todo(items):
    return stack(note('what to do'), ''.join(f'<div style="display:flex;gap:12px;padding:10px 0;border-top:1px solid {L1}">{mono(str(i+1),12,VI2)}<span class="t" style="font-size:14px;line-height:1.5;color:{FG2}">{t}</span></div>' for i,t in enumerate(items)), gap=4)
def s1(p):
    return big('500', p) + stack(title('Something broke on our side', p), ptxt('Glyphh couldn’t finish that request. Nothing you did caused it, and nothing was changed or charged.')) + todo(['Try again in a minute.','If it fails again, check status.glyphh.ai.','Still stuck? Send us the trace id below.']) + trace('tr_01JA8KX4D9QW') + rowx(btn('try again','b1'), btn('status','b2'))
def s2(p):
    return big('expired', p) + stack(title('This link has expired', p), ptxt('Links from Glyphh work once and only for a short time, so a forwarded or old one stops working.')) + todo(['Go back to where the link came from: Claude, the email or the program.','Ask for it again there; a fresh link opens straight away.']) + rowx(btn('back to Claude','b1',prompt=True), btn('sign in','b2'))
def s3(p):
    return big('404', p) + stack(title('Nothing here', p), ptxt('That page doesn’t exist, or it moved. If you typed it, check the spelling.')) + rowx(btn('go to glyphh.ai','b1'), btn('docs','b2')) + trace('tr_01JA8KYB0S3T')
def s4(p):
    return big('403', p) + stack(title('You don’t have access to this', p), ptxt('You’re signed in as <span class="m" style="color:#F5F3FA">sam@[COMPANY].com</span>, which isn’t allowed here. It may belong to another org.')) + todo(['Switch to the account that has access.','Or ask an admin of the org to invite you.']) + rowx(btn('switch account','b1'), btn('back','b2')) + trace('tr_01JA8KZ7HC1E')
def s5(p):
    return big('wait', p) + stack(title('Too many tries', p), ptxt('For your safety we paused sign-in from here for 15 minutes [CONFIRM] after several failed attempts.')) + note('try again at 14:32') + trace('tr_01JA8M04GQ8R')
U='glyphh.ai/problem'
rows = [sp_row('01','Problem','what happened, what to do, the trace id',U,s1,dh=880,ph=920), sp_row('02','Expired link','ask again where it came from',U,s2,dh=820,ph=880), sp_row('03','Not found','the page doesn’t exist',U,s3), sp_row('04','No access','signed in as the wrong account',U,s4,dh=860,ph=900), sp_row('05','Slow down','rate limited',U,s5)]
hdr = head('09','Problem','simple page','served by the server for any page that can’t do its job · the trace id is always shown and copyable','When something goes wrong: say what happened in plain words, what to do next, and the trace id that lets us find it.',['problem','expired link','not found','no access','slow down'])
html, w, hh = board('Problem', hdr, rows)
emit('Screen09Problem.dc.html','hs-09','Screen 09 · Problem',html,w,hh,'Screen 09 · Problem')
