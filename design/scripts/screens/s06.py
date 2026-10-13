from sp import *
U = 'glyphh.ai/code'
def code_in(val='', err=None, focus=True):
    bc = ERR if err else (VI if focus else L2)
    e = f'<div class="m" style="margin-top:8px;font-size:12px;color:{ERR}">{err}</div>' if err else ''
    return f'<div><label class="lb" for="code">the code on the machine</label><input id="code" class="in" placeholder="XXXX-XXXX" value="{val}" style="min-height:56px;font-size:22px;letter-spacing:.18em;border-color:{bc}">{e}</div>'
def s1(p):
    return eyebrow('approve a code') + stack(title('Enter the code', p), ptxt('Your machine or CLI shows a code like this after <span class="m" style="color:#F5F3FA">glyphh login</span>. Type it here to let it in.')) + code_in() + btn('continue','b1','w dis') + note('only enter a code you started yourself')
def s2(p):
    return eyebrow('approve a code') + title('Is this your machine?', p) + box(kv([('code','K7QD-82MX'),('what','rrotor machine · studio-mac'),('host','macOS 15 · arm64'),('from','Austin, US · 73.12.x.x'),('started','40 seconds ago'),('joins','[ORG NAME]')]),4,L1,INK) + ptxt('Approving gives it a key to run programs for [ORG NAME]. You can remove it any time from Machines.', 14) + rowx(btn('approve','b1'), btn('this isn’t me','bd'))
def s3(p):
    return eyebrow('approve a code') + title('Is this your CLI?', p) + box(kv([('code','P3WN-5TZA'),('what','Codex CLI on studio-mac'),('wants','to run programs’ steps on studio-mac'),('started','12 seconds ago')]),4,L1,INK) + rowx(btn('approve','b1'), btn('this isn’t me','bd'))
def s4(p):
    return mark('ok') + stack(title('studio-mac is in', p), ptxt('Go back to the machine; it carries on by itself. It shows in Machines as starting, then ready.')) + box(f'<div class="m" style="font-size:13px;line-height:1.8;color:{FG2}">{gt()}glyphh login<br><span style="color:{OK}">approved</span> · registering studio-mac<span class="cur" style="color:{FG}">█</span></div>',16) + note('this tab can be closed')
def s5(p):
    return eyebrow('approve a code', ERR) + title('Enter the code', p) + code_in('K7QD-0000', 'No machine is waiting with that code. Check it, or run glyphh login again.') + btn('continue','b1','w')
def s6(p):
    return mark('warn') + stack(title('That code has expired', p), ptxt('Codes last 10 minutes. Run <span class="m" style="color:#F5F3FA">glyphh login</span> on the machine again for a new one.')) + btn('enter a new code','b2') + trace('tr_01JA8GJ5S2YD')
def s7(p):
    return mark('err') + stack(title('Denied', p), ptxt('The machine wasn’t let in and the code is void. If someone else started it, tell your org admin.')) + rowx(btn('done','b2'))
rows = [sp_row('01','Enter the code','from glyphh login',U,s1), sp_row('02','Confirm a machine','what it is, where it is',U,s2,dh=880,ph=900), sp_row('03','Confirm a CLI','Codex or Claude Code on a machine',U,s3), sp_row('04','Approved','the machine carries on',U,s4), sp_row('05','Wrong code','no machine waiting',U,s5), sp_row('06','Expired','codes last 10 minutes',U,s6), sp_row('07','Denied','this isn’t me',U,s7)]
hdr = head('06','Approve a code','simple page','served by the server at glyphh.ai/code · also inline as a panel where the harness allows','A machine or a CLI signs in with a short code. You type it, see exactly what is asking, and approve or deny it.',['enter the code','confirm a machine','confirm a CLI','approved','wrong code','expired','denied'])
html, w, hh = board('Approve a code', hdr, rows)
emit('Screen06ApproveCode.dc.html','hs-06','Screen 06 · Approve a code',html,w,hh,'Screen 06 · Approve a code')
