from mp import *
def ask_(p, kind, progn, when, q, acts, extra='', done=None):
    c = {'needs auth':AUTH,'needs input':WARN,'approve':VI2,'result':VI2,'spend':WARN}[kind]
    top = f'<div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">{chip(kind, c)}{mono(gt()+progn+" · "+when,12,MUT)}</div>'
    body = f'<span class="t" style="font-size:14px;line-height:1.5;color:{FG}">{q}</span>'
    if done:
        a = f'<div class="m" style="display:flex;align-items:center;gap:8px;font-size:12px;color:{OK}">{ic("check",13,OK)}{done}</div>'
    else:
        a = f'<div style="display:flex;gap:8px;flex-wrap:wrap">{acts}</div>'
    return f'<div style="display:flex;flex-direction:column;gap:10px;padding:{"14px 16px" if p else "16px 20px"};border-top:1px solid {L1};{"opacity:.6;" if done else ""}">{top}{body}{extra}{a}</div>'
def items(p, answered=False):
    return (ask_(p,'approve','reels','2m','Sam’s Codex wants the reels result (84 MB). Give it a one-time token?', btn('approve','b1','sm')+btn('deny','b2','sm'), done='approved · Sam is fetching it' if answered else None)
          + ask_(p,'needs auth','venues','12m','venues needs your OpenTable account to hold Emmer &amp; Rye before 6 pm.', btn('connect OpenTable','b1','sm')+btn('not now','b2','sm'))
          + ask_(p,'needs input','invoices','1h','Acme’s invoice [NO.] is 60 days late. Send the final reminder, or hand it to you?', btn('send reminder','b1','sm')+btn('I’ll handle it','b2','sm'))
          + ask_(p,'spend','standup','3h','standup would go over its $5 daily limit to finish. Allow $2 more today?', btn('allow $2','b1','sm')+btn('stop it','b2','sm')))
def tb(p, n):
    return toolbar(f'<span class="m" style="font-size:13px;color:{FG}">{n} waiting</span>', seg(['all','approvals','questions'],'all') if not p else '', p)
def t1(p):
    return [user('Anything need me?', p), say('Four things, across four programs. Answer them here.'), panel('needs you', tb(p,4) + items(p) + foot('oldest first · also emailed to chris@[COMPANY].com'), '4')]
def t2(p):
    return [user('Anything need me?', p), panel('needs you', tb(p,3) + items(p, True) + foot('oldest first'), '3')]
def t3(p):
    return [user('Anything need me?', p), say('Nothing. Every program is running on its own.'), panel('needs you', empty('Nothing needs you', 'When a program needs an answer, an approval or a connection, it shows up here and in your email.', '', p))]
def t4(p):
    return [user('Anything need me?', p), panel('needs you', loading_rows(3, p))]
def t5(p):
    return [user('Anything need me?', p), panel('needs you', error_block('Couldn’t load what needs you', 'The server didn’t answer. Programs that are waiting stay paused, nothing is lost; try again.', 'tr_01JA8RB7M0NC', p))]
def t6(p):
    a = ask_(p,'approve','reels','just now','Sam’s Codex wants the reels result (84 MB). Give it a one-time token?', '', done='approved · Sam is fetching it')
    return [user('approve it', p), panel('needs you', a + foot('answered from Claude · the email link now says already answered'))]
rows = [prow('01','Needs you','approvals and questions from every program','Needs you',t1,1060,1320), prow('02','Answered in place','the row settles, the program carries on','Needs you',t2,1040,1320), prow('03','A single one, inline','when a program asks mid-conversation','Needs you',t6,600,844), prow('04','All clear','nothing waiting','Needs you',t3,680,844), prow('05','Loading','','Needs you',t4,640,844), prow('06','Error','with the trace id','Needs you',t5,680,844)]
hdr = head('13','Needs you','MCP panel','one panel for every program’s approvals and questions · each also reaches you by email with a link to the simple page','Programs only stop when they need you. Everything they’re waiting on, from every program, in one place, answered right here.',['needs you','answered in place','a single one, inline','all clear','loading','error'])
html, w, hh = board('Needs you', hdr, rows)
emit('Screen13NeedsYou.dc.html','hs-13','Screen 13 · Needs you',html,w,hh,'Screen 13 · Needs you')
