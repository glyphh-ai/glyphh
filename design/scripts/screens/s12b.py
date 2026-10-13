from mp import *
def P(p): return "16px" if p else "20px"
def grp(p, title, count, rows, act=''):
    return (f'<div style="border-top:1px solid {L1}"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:14px {P(p)} 6px"><span style="display:flex;gap:10px;align-items:baseline">{mono(title,12,FG)}{mono(count,11,MUT)}</span>{act}</div>{rows}</div>')
def line(p, name, desc, right=''):
    return f'<div style="display:flex;gap:12px;align-items:{"flex-start" if p else "center"};justify-content:space-between;padding:7px {P(p)}"><div style="flex:1;min-width:0;display:flex;{"flex-direction:column;gap:2px" if p else "gap:16px;align-items:baseline"}">{tname(name,13)}{sub(desc)}</div>{right}</div>'
def perm(a): 
    c = {'allow':OK,'ask':WARN,'deny':ERR}[a]
    return f'<span class="m" style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:{FG2};flex:none"><i style="display:inline-block;width:6px;height:6px;background:{c}"></i>{a}</span>'
def phead(p, extra=''):
    return (f'<div style="padding:{"16px" if p else "20px"};display:flex;flex-direction:column;gap:10px;border-bottom:1px solid {L1}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">{tname(gt()+"inbox-zero",18)}<span style="display:flex;gap:8px;align-items:center">{status("ready",OK)}<span class="chip">private</span></span></div>'
            f'{ptxt("Keeps the inbox at zero: sorts every new mail, drafts replies in our voice, files receipts, and asks before writing to anyone new.",14)}'
            f'{mono("installed on studio-mac · insulated · v7 · built in Claude · owner chris@[COMPANY].com",11,MUT)}{extra}</div>')
def parts(p):
    return (grp(p,'models','3', line(p,'jev','sorts and labels') + line(p,'claude-sonnet-[VER]','drafts replies · your key') + line(p,'claude-haiku-[VER]','summaries · your key'))
        + grp(p,'connections','4', line(p,'Gmail','read, label: allow · send: ask', perm('ask')) + line(p,'Google Calendar','read: allow', perm('allow')) + line(p,'Google Drive','write to /Receipts: allow', perm('allow')) + line(p,'Salesforce','update contacts: ask · delete: deny', perm('ask')), btn('permissions · 9 allow, 2 ask, 1 deny','b3','sm'))
        + grp(p,'functions','4', line(p,'triage-rules','how this inbox sorts: labels, VIPs, what can wait') + line(p,'how-we-write','short, plain, warm') + line(p,'receipt-filer','finds receipts and files them in Drive') + line(p,'inbox-dashboard','a panel of what’s waiting · 6 tools'))
        + grp(p,'tasks','3', line(p,'morning-briefing','unread mail and the calendar, as one note', mono('weekdays 8:00',11,VI2)) + line(p,'triage','sort, label, draft', mono('every 15 min',11,VI2)) + line(p,'file-receipts','on new mail with a receipt', mono('on event',11,VI2)))
        + grp(p,'folders','1', line(p,'~/work/inbox-zero','drafts, notes and its own data · works here'))
        + grp(p,'browsers','1', line(p,'gmail','a signed-in browser for what the API can’t do', btn('watch','b3','sm')))
        + grp(p,'who can call it','', f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:8px {P(p)}">{sub("you, from Claude, Codex, email and the API")}{seg(["private","org","public"],"private")}</div>')
        + grp(p,'manifest.js','v7', manifest(p), btn('open in Claude','b3','sm'))
        + grp(p,'recent runs','5 today', runs(p, 3), btn('all runs','b3','sm')))
RUNS = [('triage','2m ago','result','14 sorted · 3 drafts',VI2),('file-receipts','40m ago','result','2 receipts filed',VI2),('triage','1h ago','needs you','new recipient: [NAME]',WARN),('morning-briefing','8:00','result','briefing sent',VI2),('triage','yesterday','error','Gmail rate limit · retried',ERR),('triage','yesterday','result','22 sorted',VI2)]
def runs(p, n):
    return ''.join(line(p, t, f'{when} · {d}', chip(k, c)) for t,when,k,d,c in RUNS[:n])
def kw(k): return f'<span style="color:{FG}">{k}</span>'
def st(v): return f'<span style="color:{VI2}">{v}</span>'
def manifest(p):
    L = [f'<span style="color:{MUT}">// manifest.js · the spec is being written; this shape is a [DRAFT]</span>',
         f'<span style="color:{VI}">export default</span> {{',
         f'  {kw("name")}: {st(chr(39)+"inbox-zero"+chr(39))},',
         f'  {kw("purpose")}: {st(chr(39)+"Keep the inbox at zero"+chr(39))},',
         f'  {kw("runs")}: {{ {kw("on")}: {st(chr(39)+"rrotor"+chr(39))}, {kw("machine")}: {st(chr(39)+"studio-mac"+chr(39))}, {kw("insulated")}: <span style="color:{OK}">true</span> }},',
         f'  {kw("models")}: [{st(chr(39)+"jev"+chr(39))}, {st(chr(39)+"claude-sonnet-[VER]"+chr(39))}, {st(chr(39)+"claude-haiku-[VER]"+chr(39))}],',
         f'  {kw("connections")}: {{',
         f'    {kw("gmail")}: {{ {kw("read")}: {st(chr(39)+"allow"+chr(39))}, {kw("send")}: {st(chr(39)+"ask"+chr(39))} }},',
         f'    {kw("calendar")}: {{ {kw("read")}: {st(chr(39)+"allow"+chr(39))} }},',
         f'    {kw("drive")}: {{ {kw("write")}: {st(chr(39)+"/Receipts"+chr(39))} }},',
         f'    {kw("salesforce")}: {{ {kw("update")}: {st(chr(39)+"ask"+chr(39))}, {kw("delete")}: {st(chr(39)+"deny"+chr(39))} }},',
         f'  }},',
         f'  {kw("functions")}: [{st(chr(39)+"triage-rules"+chr(39))}, {st(chr(39)+"how-we-write"+chr(39))}, {st(chr(39)+"receipt-filer"+chr(39))}, {st(chr(39)+"inbox-dashboard"+chr(39))}],',
         f'  {kw("tasks")}: {{',
         f'    {kw(chr(39)+"morning-briefing"+chr(39))}: {{ {kw("schedule")}: {st(chr(39)+"weekdays 08:00"+chr(39))} }},',
         f'    {kw("triage")}: {{ {kw("every")}: {st(chr(39)+"15m"+chr(39))} }},',
         f'    {kw(chr(39)+"file-receipts"+chr(39))}: {{ {kw("on")}: {st(chr(39)+"gmail.receipt"+chr(39))} }},',
         f'  }},',
         f'  {kw("folders")}: [{st(chr(39)+"~/work/inbox-zero"+chr(39))}],',
         f'  {kw("browsers")}: [{st(chr(39)+"gmail"+chr(39))}],',
         f'  {kw("callers")}: {{ {kw("who")}: {st(chr(39)+"private"+chr(39))}, {kw("from")}: [{st(chr(39)+"claude"+chr(39))}, {st(chr(39)+"codex"+chr(39))}, {st(chr(39)+"email"+chr(39))}, {st(chr(39)+"api"+chr(39))}] }},',
         '}']
    code = chr(10).join(L)
    how = sub("How it runs: installed, insulated, in rrotor on studio-mac, your private place to run AI. Your Claude reaches it from anywhere through the relay; nothing listens on the machine.")
    return f'<div style="padding:4px {P(p)} 12px;display:flex;flex-direction:column;gap:10px">{how}<div class="m" style="border:1px solid {L1};background:{INK};padding:12px 14px;font-size:12px;line-height:1.75;color:{FG2};white-space:pre-wrap;word-break:break-word;overflow:hidden">{code}</div></div>'
def t1(p):
    return [user('Open inbox-zero', p), panel('inbox-zero', phead(p) + parts(p) + foot('edit by asking Claude · every change shows here first', btn('run a task','b1','sm') + btn('watch','b2','sm')))]
STEPS = [('1','gmail.list_unread','connection · Gmail'),('2','triage-rules','function · claude-haiku'),('3','calendar.today','connection · Google Calendar'),('4','write the note','function how-we-write · claude-sonnet'),('5','gmail.send to you','connection · Gmail · allow')]
def t2(p):
    st = ''.join(f'<div style="display:flex;gap:12px;align-items:flex-start;padding:10px {P(p)};border-top:1px solid {L1}">{mono(n,12,VI2)}<div style="flex:1;display:flex;flex-direction:column;gap:3px">{tname(a,13)}{sub(b)}</div></div>' for n,a,b in STEPS)
    head_ = f'<div style="padding:{P(p)};display:flex;flex-direction:column;gap:8px;border-bottom:1px solid {L1}">{tname(gt()+"inbox-zero · morning-briefing",15)}{sub("A task: the same five steps, in order, every run.")}<div style="display:flex;gap:8px;flex-wrap:wrap">{chip("weekdays 8:00", VI2)}{chip("last run · result")}{chip("avg 48s · $0.03", MUT)}</div></div>'
    return [user('What does morning-briefing do?', p), panel('inbox-zero · task', head_ + st + foot('runs on studio-mac', btn('run now','b1','sm') + btn('change the schedule','b2','sm')))]
def t3(p):
    diff = f'<div class="m" style="margin:{P(p)};border:1px solid {L2};background:{INK};padding:12px 14px;font-size:12px;line-height:1.8;white-space:pre-wrap"><span style="color:{MUT}">manifest.js · connections.gmail.send</span>\n<span style="color:{ERR}">- allow</span>\n<span style="color:{OK}">+ ask, when the recipient is new</span>\n<span style="color:{MUT}">manifest.js · functions.how-we-write</span>\n<span style="color:{OK}">+ Never write to someone new without asking.</span></div>'
    pn = panel('inbox-zero · change', f'<div style="padding:{P(p)} {P(p)} 0;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">{tname(gt()+"inbox-zero",15)}<span class="chip">not saved</span></div>' + diff + foot('v7 → v8 · checks run before it’s live', btn('save','b1','sm') + btn('undo','b2','sm')))
    return [user('Never send to anyone new without asking me.', p), say('Here’s the change. Gmail sends to new people now ask you first; saving runs its checks.'), pn]
def t4(p):
    c = pad(stack(ptxt('Make inbox-zero public? Anyone with Glyphh could call it at its own address and its runs bill their credit [CONFIRM]. Your inbox stays yours: callers get their own connections.',14), box(f'<div class="m" style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:{VI2}">inbox-zero.glyphh.app</span>{mono("available",12,OK)}</div>',12,L1,INK), rowx(btn('make it public','b1','sm'), btn('org only','b2','sm'), btn('cancel','b3','sm')), gap=12), p)
    return [user('Make inbox-zero public', p), panel('inbox-zero · who can call it', c)]
def t5(p):
    tb = toolbar(seg(['all','results','needs you','errors'],'all'), '', p)
    return [user('Show inbox-zero’s runs', p), panel('inbox-zero · runs', tb + runs(p, 6) + foot('42 runs this week · $1.28'))]
def t6(p):
    return [user('Open inbox-zero', p), panel('inbox-zero', loading_rows(4, p))]
def t7(p):
    return [user('Open inbox-zero', p), panel('inbox-zero', error_block('inbox-zero didn’t open', 'studio-mac, where it runs, isn’t answering. Its tasks wait and run when the machine is back.', 'tr_01JA90A5D8NX', p, btn('open machines','b1','sm') + btn('try again','b2','sm')))]
rows = [prow('01','A program','what it does, its models, connections, functions, tasks, folders, browsers, who can call it, its manifest.js, runs','inbox-zero',t1,2300,3100), prow('02','A task','its steps, each a function on its parts; its schedule','inbox-zero',t2,820,1100), prow('03','Changing it','ask in the harness; the change shows before it’s saved','inbox-zero',t3,820,1100), prow('04','Who can call it','private, org, public at its own address','inbox-zero',t4,640,960), prow('05','Recent runs','','inbox-zero',t5,780,1180), prow('06','Loading','','inbox-zero',t6,640,844), prow('07','Error','with the trace id','inbox-zero',t7,680,960)]
hdr = head('12b','A program','MCP panel','a program’s own page, in the harness · was a super power · Claude drawn · panel width 760 and phone','Everything a program is made of, on one page: what it does, its models, connections, functions, tasks and schedules, its folders and browsers, who can call it, its manifest.js (how it runs and what it’s made of) and what it did lately. Installed, insulated, on your own machine; you change it by asking.',['a program','a task','changing it','who can call it','recent runs','loading','error'])
html, w, hh = board('A program', hdr, rows)
emit('Screen12bProgram.dc.html','hs-12b','Screen 12b · A program',html,w,hh,'Screen 12b · A program')
