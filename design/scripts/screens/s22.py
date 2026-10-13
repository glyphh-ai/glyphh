from mp import *
def P(p): return "16px" if p else "20px"
def atabs(sel, p): return tabs(['orgs','plans','catalog','audit log'], sel, p)
ORGS = [('[ORG NAME]','Pro · 4 members','$18.40 this period','active',OK),('northwind','Team · 22 members','$412.10','active',OK),('acme-labs','Free · 1 member','$0.00','active',OK),('[ORG NAME 2]','Pro · 3 members','$61.80','past due',WARN),('spamco','Free · 1 member','$0.00','suspended',ERR)]
def t1(p):
    rows = ''.join(item(p, tname(n), sub(f'{pl} · {u}'), status(s,c), '') for n,pl,u,s,c in ORGS)
    return [user('Show me the orgs', p), panel('admin', atabs(0,p) + toolbar(search('search orgs, members, emails','',p), seg(['all','past due','suspended'],'all') if not p else '', p) + rows + foot('[N] orgs · staff only'), '<span class="chip">staff</span>')]
def t2(p):
    acts = pad(stack(kv([('plan','Pro · since [DATE]'),('members','3 · owner kim@[ORG2].com'),('balance','−$4.20 · last charge failed'),('machines','2 · programs 6')]), mono('actions are logged with your name and a reason',12,MUT), f'<div><label class="lb" for="rs">reason</label><input id="rs" class="in" placeholder="why, for the audit log"></div>', rowx(btn('grant credit','b2','sm'), btn('change plan','b2','sm'), btn('suspend','bd','sm')), gap=12), p)
    return [user('Open [ORG NAME 2]', p), panel('admin · [ORG NAME 2]', f'<div style="padding:{P(p)};display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;border-bottom:1px solid {L1}">{tname("[ORG NAME 2]",15)}{status("past due",WARN)}</div>' + acts, '<span class="chip">staff</span>')]
def t3(p):
    g = pad(stack(f'<div style="display:grid;grid-template-columns:repeat({1 if p else 2},minmax(0,1fr));gap:12px"><div><label class="lb" for="ga">credit</label><input id="ga" class="in" value="$25.00"></div><div><label class="lb" for="gr">reason</label><input id="gr" class="in" value="outage on Oct 9 · ticket [ID]"></div></div>', f'<div class="m" style="display:flex;gap:8px;align-items:center;font-size:12px;color:{OK}">{ic("check",13,OK)}granted · logged as chris (staff)</div>', gap=12), p)
    return [panel('admin · [ORG NAME 2] · grant credit', g, '<span class="chip">staff</span>'), say('Granted $25.00 to [ORG NAME 2] and logged it.')]
PLANS = [('Free','[PRICE]','[CREDIT] credit · 1 machine'),('Pro','[PRICE] / month','[CREDIT] credit · [N] machines'),('Team','[PRICE] / member','shared credit · org admin · audit log')]
def t4(p):
    rows = ''.join(item(p, tname(n), sub(d), mono(pr,13,FG), btn('edit','b3','sm')) for n,pr,d in PLANS)
    return [user('Show the plans', p), panel('admin', atabs(1,p) + rows + foot('prices sync to Stripe on save', btn('new plan','b2','sm',prompt=True)), '<span class="chip">staff</span>')]
CAT = [('models','gateway models offered','jev, claude-*, gpt-*, gemini-*, whisper','[N] on'),('connections','apps in the relay','Gmail, YouTube, Slack, OpenTable…','[N] on'),('hosts','one-click machine hosts','Fly.io, AWS, Hetzner','3 on'),('runtimes','runtimes a manifest may ask for','Claude Code, Codex','2 on')]
def t5(p):
    rows = ''.join(item(p, tname(n), sub(f'{d} · {e}'), mono(c,12,MUT), btn('manage','b3','sm')) for n,d,e,c in CAT)
    return [user('What’s in the catalog?', p), panel('admin', atabs(2,p) + rows + foot('what every org can use, before its own limits'), '<span class="chip">staff</span>')]
AUD = [('14:20','chris (staff)','granted credit','[ORG NAME 2] · $25 · outage on Oct 9'),('12:02','sam (staff)','suspended','spamco · abuse report [ID]'),('09:40','chris (staff)','changed a price','Pro · [PRICE]'),('yesterday','system','turned on','connection · OpenTable')]
def t6(p):
    rows = ''.join(f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;padding:10px {P(p)};border-top:1px solid {L1}">{mono(w,12,MUT,"width:76px;flex:none")}<span class="t" style="font-size:14px;color:{FG}">{who} <span style="color:{FG2}">{what}</span> <span class="m" style="font-size:13px;color:{VI2}">{obj}</span></span></div>' for w,who,what,obj in AUD)
    return [user('What did staff change today?', p), panel('admin', atabs(3,p) + toolbar(search('search the log','',p), '', p) + rows + foot('every staff action, with its reason · export', btn('export','b3','sm')), '<span class="chip">staff</span>')]
def t7(p):
    return [user('Show me the orgs', p), panel('admin', pad(stack(cat('sleepy', 56), h('That’s for Glyphh staff', 18), ptxt('Your account isn’t on the staff list, so the admin panel doesn’t open. Nothing was shown or logged beyond this attempt.', 14), mono('trace tr_01JA92K7R1ZD',12,MUT), gap=12), p))]
rows = [prow('01','Orgs','every org, its plan, use and standing','Admin',t1,860,1200), prow('02','An org','actions with a reason','Admin',t2,820,1140), prow('03','Credit granted','logged with who and why','Admin',t3,620,900), prow('04','Plans','prices sync to Stripe','Admin',t4,700,1000), prow('05','The catalog','models, connections, hosts, runtimes','Admin',t5,760,1140), prow('06','The audit log','every staff action','Admin',t6,760,1100), prow('07','Not staff','','Admin',t7,640,900)]
hdr = head('22','Glyphh admin','MCP panel · staff','for Glyphh staff only · Claude drawn · panel width 760 and phone','Running Glyphh itself: every org and its standing, the plans and their prices, the catalog of models, connections, hosts and runtimes every org can use, and an audit log of every staff action with its reason.',['orgs','an org','credit granted','plans','catalog','audit log','not staff'])
html, w, hh = board('Glyphh admin', hdr, rows)
emit('Screen22Admin.dc.html','hs-22','Screen 22 · Glyphh admin',html,w,hh,'Screen 22 · Glyphh admin')
