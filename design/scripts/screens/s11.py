from mp import *
PARTS = [('models','jev','picks the strongest moments'),('models','whisper','transcribes for the captions'),
         ('connections','YouTube','reads videos you give it'),('connections','Instagram','posts reels you approve'),
         ('functions','youtube.fetch','downloads the video and transcript'),('functions','clips.find','the 6 best moments, same every run'),('functions','clips.cut','cuts each to 9:16'),('functions','captions.write','burns in captions'),
         ('tasks','make-reels','fetch → find → cut → caption → post · on call'),('tasks','best-of-week','every Friday 9:00 · posts the top 3'),
         ('folders','~/reels','keeps every cut and its captions'),
         ('browsers','instagram','a signed-in browser for posting')]
def fnlist(p, states):
    if isinstance(states, int):
        n = states; states = ['done'] * n + (['doing'] if n < len(PARTS) else []) + ['todo'] * max(0, len(PARTS) - n - 1)
    out = ''; last = None
    for (grp,name,desc),st in zip(PARTS,states):
        if grp != last:
            out += f'<div class="m" style="padding:{"12px 16px 4px" if p else "14px 20px 4px"};font-size:11px;color:{MUT};border-top:1px solid {L1}">{grp}</div>'
            last = grp
        if st=='done': mk = ic('check',14,OK); c=FG
        elif st=='doing': mk = spinner(14); c=FG
        elif st=='fail': mk = ic('x',14,ERR); c=FG
        else: mk = f'<span style="width:14px;height:14px;border:1px solid {L2};flex:none;box-sizing:border-box"></span>'; c=FG2
        out += f'<div style="display:flex;gap:12px;align-items:{"flex-start" if p else "center"};padding:8px {"16px" if p else "20px"}"><span style="width:16px;display:flex;justify-content:center;flex:none">{mk}</span><div style="flex:1;min-width:0;display:flex;{"flex-direction:column;gap:2px" if p else "justify-content:space-between;gap:16px"}">{tname(name,13,c)}{sub(desc)}</div></div>'
    return out
def header(p, title, s):
    return f'<div style="padding:{"16px" if p else "20px"};display:flex;flex-direction:column;gap:8px;border-bottom:1px solid {L1}"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">{tname(gt()+"reels",16)}{s}</div>{ptxt(title,14)}</div>'
def t1(p):
    pn = panel('build · reels', header(p,'Turn a YouTube video into reels. One purpose; same steps every run.', chip('needs input')) + section_label('the plan · 2 models · 2 connections · 4 functions · 2 tasks · 1 folder · 1 browser', p) + fnlist(p, ['todo']*12) + section_label('it will need', p) + f'<div style="padding:0 {"16px" if p else "20px"} 16px;display:flex;gap:8px;flex-wrap:wrap">{chip("youtube · read","#F062D0")}{chip("instagram · post","#F062D0")}{chip("studio-mac","#3FD08F")}</div>' + foot('runs on studio-mac · private', btn('build it','b1','sm') + btn('change','b2','sm')))
    return [user('Build me a program that turns a YouTube video into reels and posts them to Instagram.', p), say('Here’s the plan. Say build it and I’ll make it on studio-mac.'), pn]
def t2(p):
    pn = panel('build · reels', header(p,'Making its parts. 7 of 12 done.', chip('working', blink=True)) + fnlist(p, 7) + f'<div style="padding:14px {"16px" if p else "20px"};border-top:1px solid {L1}">{bar(55)}</div>' + foot('step 4 of 8 · 1m 40s', btn('watch the machine','b2','sm')))
    return [user('build it', p), pn]
CH = [('manifest.js validates against the spec','pass'),('runs on a 3 minute sample video','pass'),('same input, same reels, twice','pass'),('stays inside its fence: youtube, instagram','pass'),('asks before it posts','running'),('cost per run under $0.40','todo')][:5]
def checks(p, st):
    out=''
    for (t,_),s in zip(CH,st):
        mk = {'pass':ic('check',14,OK),'running':spinner(14),'todo':f'<span style="width:14px;height:14px;border:1px solid {L2};flex:none"></span>','fail':ic('x',14,ERR)}[s]
        lab = {'pass':mono('pass',12,OK),'running':mono('running',12,VI2),'todo':mono('queued',12,MUT),'fail':mono('fail',12,ERR)}[s]
        out += f'<div style="display:flex;gap:12px;align-items:center;padding:12px {"16px" if p else "20px"};border-top:1px solid {L1}">{mk}<span class="t" style="flex:1;font-size:14px;color:{FG2}">{t}</span>{lab}</div>'
    return out
def t3(p):
    pn = panel('build · reels', header(p,'All 12 parts made. Checking it does what it says.', chip('working', blink=True)) + section_label('checks · 3 of 5 passed', p) + checks(p, ['pass','pass','pass','running','todo']) + foot('step 7 of 8'))
    return [user('build it', p), pn]
def t4(p):
    pn = panel('build · reels', header(p,'One check can’t run: reels needs to read YouTube.', chip('needs auth')) + checks(p, ['pass','pass','pass','pass','pass'])[:0] + pad(stack(ptxt('Connect YouTube once. reels may only read videos you give it; it can’t see your account or post there.',14), rowx(btn('connect YouTube','b1','sm'), btn('use a sample video instead','b2','sm')), gap=12), p) + foot('paused at step 7 of 8'))
    return [user('build it', p), say('Almost there; it needs YouTube.'), pn]
def t5(p):
    tools = ''.join(f'<div style="display:flex;justify-content:space-between;gap:10px;padding:10px {"16px" if p else "20px"};border-top:1px solid {L1}">{tname(t,13)}{mono(d,12,MUT)}</div>' for t,d in [('reels.make','url → result'),('reels.status','run id → working | result'),('reels.post','reel ids → link')])
    vis = f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:14px {"16px" if p else "20px"};border-top:1px solid {L1}">{sub("who can call it")}{seg(["private","org","public"],"private")}</div>'
    pn = panel('build · reels', header(p,'reels is ready: its manifest.js is valid and it’s installed on studio-mac. Its tools are in Claude now; no new connection.', status('installed',OK)) + checks(p, ['pass']*5) + f'<div class="m" style="margin:{"0 16px 14px" if p else "0 20px 16px"};border:1px solid {L1};background:{INK};padding:12px 14px;font-size:12px;line-height:1.9;color:{FG2};white-space:pre-wrap"><span style="color:{OK}">valid</span>      manifest.js · v1\n<span style="color:{OK}">installed</span>  studio-mac · rrotor · insulated\n<span style="color:{OK}">reachable</span>  from your Claude, anywhere, through the relay</div>' + section_label('new tools in this harness', p) + tools + vis + foot('built in 3m 12s · v1', btn('try it','b1','sm',prompt=True) + btn('open','b2','sm')))
    return [user('build it', p), pn, say('Try it: <span class="m" style="color:#F5F3FA">use reels on https://youtu.be/[VIDEO]</span>')]
def t6(p):
    pn = panel('build · reels', header(p,'A check failed, so reels wasn’t made ready.', chip('error')) + checks(p, ['pass','fail','todo','todo','todo']) + pad(stack(ptxt('clips.find picked different moments on the second run, so reels isn’t deterministic yet. I can pin the model’s seed and temperature and check again.',14), f'<div class="m" style="font-size:12px;color:{MUT}">trace <span style="color:{FG};padding:3px 8px;border:1px solid {L2}">tr_01JA8P9F2KXA</span></div>', rowx(btn('fix and check again','b1','sm'), btn('see the diff','b2','sm')), gap=12), p))
    return [user('build it', p), pn]
rows = [prow('01','The plan','its purpose, its parts, what it will need','New program',t1,1320,1760), prow('02','Making the parts','as each is made','New program',t2,1200,1560), prow('03','The checks','it does what it says, every time','New program',t3,860,980), prow('04','Needs auth','paused for a connection','New program',t4,740,900), prow('05','Ready','manifest validated, installed on the machine, tools in the harness','New program',t5,1240,1560), prow('06','A check failed','why, and the fix','New program',t6,860,1080)]
hdr = head('11','Building a program','MCP panel','returned while a program is built from any harness · Claude drawn · panel width 760 and phone','A sentence becomes a program: its parts appear as they are made (models, connections, functions, tasks, folders, browsers), the checks prove it does the same thing every time, and it ends with its manifest.js validated and the program installed, insulated, on your machine, its tools in the harness. Built wherever you build; Claude is drawn.',['the plan','making the parts','the checks','needs auth','ready','a check failed'])
html, w, hh = board('Building a program', hdr, rows)
emit('Screen11Building.dc.html','hs-11','Screen 11 · Building a program',html,w,hh,'Screen 11 · Building a program')
