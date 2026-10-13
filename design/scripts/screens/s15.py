from mp import *
def mh(p, s=('online',OK)):
    return f'<div style="padding:{"14px 16px" if p else "16px 20px"};display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;border-bottom:1px solid {L1}"><span style="display:flex;flex-direction:column;gap:4px">{tname("studio-mac",15)}{sub("this computer · macOS 15 · rrotor 1.4")}</span>{status(*s)}</div>'
def cli(p, name, who, st, c, act=''):
    return item(p, tname(name), sub(who), status(st, c), act, f'<span style="color:{MUT};flex:none">{ic("term",16)}</span>' if not p else '')
def t1(p):
    rows = cli(p,'Claude Code','signed in as chris@[COMPANY].com · asked for by reels, standup','signed in',OK) + cli(p,'Codex','not signed in · asked for by invoices','not signed in',DIM, btn('sign in','b1','sm'))
    return [user('Which runtimes are set up on studio-mac?', p), say('Claude Code is signed in. Codex isn’t; only invoices’ manifest asks for it.'), panel('studio-mac · runtimes', mh(p) + rows + foot('used only when a program’s manifest.js asks for one'))]
def t2(p):
    s = pad(stack(ptxt('Open this link on any device and enter the code. Codex signs in on studio-mac; your password never touches Glyphh.',14),
        f'<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><span class="m" style="font-size:22px;letter-spacing:.16em;color:{FG};padding:8px 14px;border:1px solid {L2}">WDJB-MJHT</span><button type="button" class="b3 sm" aria-label="Copy code">{ic("copy",14)}</button></div>',
        rowx(btn('open auth.openai.com','b1','sm') + '', btn('cancel','b3','sm')),
        f'<div class="m" style="display:flex;align-items:center;gap:10px;font-size:13px;color:{VI2}">{spinner(14)}waiting for you to finish in the browser<span class="cur" style="color:{FG}">█</span></div>', gap=14), p)
    return [user('Sign Codex in on studio-mac', p), panel('studio-mac · Codex', mh(p) + s)]
def t3(p):
    term = f'<div class="m" style="margin:{"0 16px 16px" if p else "0 20px 20px"};border:1px solid {L1};background:{INK};padding:12px 14px;font-size:12px;line-height:1.9;color:{FG2};white-space:pre-wrap"><span style="color:{VI}">&gt;</span> codex login --device\n<span style="color:{OK}">signed in</span> as chris@[COMPANY].com\n<span style="color:{VI}">&gt;</span> glyphh runtimes\nclaude-code  <span style="color:{OK}">ok</span>   codex  <span style="color:{OK}">ok</span>\n<span style="color:{VI}">&gt;</span> <span class="cur" style="color:{FG}">█</span></div>'
    rows = cli(p,'Claude Code','signed in as chris@[COMPANY].com','signed in',OK) + cli(p,'Codex','signed in as chris@[COMPANY].com','signed in',OK)
    return [panel('studio-mac · runtimes', mh(p) + rows + section_label('on the machine', p) + term), say('Codex is signed in. Both runtimes are ready for programs on studio-mac.')]
def t4(p):
    rows = cli(p,'Claude Code','signed in · v[VERSION]','signed in',OK) + cli(p,'Codex','token expired 2 days ago','signed out',WARN, btn('sign in again','b1','sm'))
    return [user('Why did invoices skip its Codex step?', p), say('Codex on studio-mac signed itself out, so invoices fell back to Claude Code for that step.'), panel('studio-mac · runtimes', mh(p) + rows)]
def t5(p):
    return [user('Sign Codex in on aws-eu', p), panel('aws-eu · runtimes', mh(p, ('offline',DIM)).replace('studio-mac','aws-eu').replace('this computer · macOS 15 · rrotor 1.4','AWS · eu-west-1 · last seen 1d ago') + error_block('aws-eu is offline', 'A CLI can only sign in on a machine that’s running. Bring aws-eu back first, from Machines.', 'tr_01JA8TF0Q6WB', p, btn('open machines','b1','sm')))]
rows = [prow('01','Runtimes','Claude Code and Codex, signed in or not','studio-mac',t1,800,1000), prow('02','Signing one in','a device code; finished in the browser','Sign in Codex',t2,780,1000), prow('03','Signed in','both ready, the machine’s own terminal','Sign in Codex',t3,900,1160), prow('04','Signed out','what a program fell back to','studio-mac',t4,800,1060), prow('05','Machine offline','error with trace id','Sign in Codex',t5,700,960)]
hdr = head('15','A machine’s CLIs','MCP panel','runtimes a program can use on one machine · Claude drawn · panel width 760 and phone','Runtimes a program can use: Claude Code and Codex on the machine, needed only when a program’s manifest.js asks for one. This shows which are signed in and which programs ask for them, and signs one in with a device code.',['runtimes','signing one in','signed in','signed out','machine offline'])
html, w, hh = board('A machine’s CLIs', hdr, rows)
emit('Screen15CLIs.dc.html','hs-15','Screen 15 · A machine’s CLIs',html,w,hh,'Screen 15 · A machine’s CLIs')
