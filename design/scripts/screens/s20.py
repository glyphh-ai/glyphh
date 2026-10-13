from mp import *
def P(p): return "16px" if p else "20px"
def prof(p):
    return f'<div style="padding:{P(p)};display:flex;gap:14px;align-items:center;border-bottom:1px solid {L1}"><span class="m" style="width:44px;height:44px;flex:none;border:1px solid {L2};display:flex;align-items:center;justify-content:center;font-size:15px">CT</span><div style="flex:1;min-width:0;display:flex;flex-direction:column;gap:4px">{tname("Chris Timmerman",15)}{sub("chris@[COMPANY].com · signed in with Google")}</div>{btn("edit","b3","sm")}</div>'
H = [('Claude','claude.ai · acts in [ORG NAME]','2m ago'),('Codex','CLI on studio-mac · acts in [ORG NAME]','1h ago'),('Gemini','gemini.google.com · acts in chris (personal)','3d ago')]
def harn(p, gone=None):
    return ''.join(item(p, tname(n), sub(d), mono('used ' + w, 12, MUT), btn('disconnect','bd','sm')) for n,d,w in H if n != gone)
def acct(p, gone=None):
    return prof(p) + kv_pad(p) + section_label('connected harnesses', p) + harn(p, gone) + section_label('sessions', p) + f'<div style="padding:4px {P(p)} 16px;display:flex;flex-direction:column;gap:10px">{sub("Signed in on 3 browsers and 2 machines.")}<div>{btn("sign out everywhere","bd","sm")}</div></div>'
def kv_pad(p):
    return f'<div style="padding:0 {P(p)}">{kv([("org","[ORG NAME] · admin"),("timezone","America/Chicago"),("emails","approvals and failures")])}</div>'
def t1(p): return [user('Show my account', p), panel('account', acct(p))]
def confirm(p, title, body, a, b='cancel'):
    return pad(stack(h(title, 18), ptxt(body, 14), rowx(btn(a,'bd','sm'), btn(b,'b3','sm')), gap=12), p)
def t2(p): return [user('Disconnect Gemini', p), panel('account · disconnect', confirm(p, 'Disconnect Gemini?', 'Gemini loses access to your Glyphh right away. Programs keep running; you can connect it again from Gemini.', 'disconnect Gemini'))]
def t3(p): return [panel('account', acct(p, 'Gemini')), say('Gemini is disconnected.')]
def t4(p): return [user('Sign me out everywhere', p), panel('account · sign out everywhere', confirm(p, 'Sign out everywhere?', 'Every browser, harness and CLI signs out, this one too. Machines and programs keep running. You’ll sign in again to use Glyphh.', 'sign out everywhere'))]
def t5(p):
    return [panel('account', pad(stack(cat('sleepy', 56), h('Signed out everywhere', 18), ptxt('3 browsers, 3 harnesses and 2 CLIs are signed out. Your machines and programs keep running.', 14), rowx(btn('sign in again','b1','sm')), gap=12), p))]
def t6(p): return [user('Show my account', p), panel('account', error_block('Your account didn’t load', 'The server didn’t answer. Nothing changed; try again.', 'tr_01JA91F2G7KC', p))]
rows = [prow('01','Account','profile, connected harnesses, sessions','Account',t1,1000,1340), prow('02','Disconnect a harness','confirm','Account',t2,600,844), prow('03','Disconnected','','Account',t3,980,1240), prow('04','Sign out everywhere','confirm','Account',t4,600,844), prow('05','Signed out everywhere','','Account',t5,600,844), prow('06','Error','with the trace id','Account',t6,640,880)]
hdr = head('20','Account','MCP panel','the member’s own account · Claude drawn · panel width 760 and phone','Who you are, which harnesses act for you and in which org, and one control to sign out everywhere.',['account','disconnect a harness','disconnected','sign out everywhere','signed out','error'])
html, w, hh = board('Account', hdr, rows)
emit('Screen20Account.dc.html','hs-20','Screen 20 · Account',html,w,hh,'Screen 20 · Account')
