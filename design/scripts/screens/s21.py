from mp import *
def P(p): return "16px" if p else "20px"
def av(i): return f'<span class="m" style="width:32px;height:32px;flex:none;border:1px solid {L2};display:flex;align-items:center;justify-content:center;font-size:12px">{i}</span>'
M = [('CT','Chris Timmerman','chris@[COMPANY].com','owner'),('SR','Sam Rivera','sam@[COMPANY].com','admin'),('JP','Jo Park','jo@[COMPANY].com','member'),('AL','Ana Lima','ana@[COMPANY].com','member')]
def members(p, sel=None):
    out=''
    for i,n,e,r in M:
        rr = seg(['member','admin'], 'admin' if (sel==n) else r) if sel==n else f'<span class="chip">{r}</span>'
        out += item(p, tname(n), sub(e), rr, '', av(i) if not p else '')
    return out
def otabs(sel, p): return tabs(['members','invites','API keys','audit log'], sel, p)
def t1(p): return [user('Who’s in the org?', p), panel('org · [ORG NAME]', otabs(0,p) + toolbar(search('search members','',p), btn('invite','b1','sm',prompt=True), p) + members(p) + foot('4 members · 2 admins'))]
def t2(p):
    f = pad(stack(f'<div><label class="lb" for="em">emails, one per line or comma</label><textarea id="em" class="in" style="min-height:88px;padding:12px 14px;resize:vertical">dev@[COMPANY].com, ops@[COMPANY].com</textarea></div>', f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">{sub("as")}{seg(["member","admin"],"member")}</div>', mono('they get an email with a link to Join · invites last 7 days [CONFIRM]',12,MUT), rowx(btn('send 2 invites','b1','sm'), btn('cancel','b3','sm')), gap=12), p)
    return [user('Invite dev@ and ops@', p), panel('org · invite', f)]
def t3(p):
    inv = ''.join(item(p, tname(e), sub(s), f'<span class="chip">{r}</span>', btn('resend','b3','sm') + btn('revoke','bd','sm')) for e,s,r in [('dev@[COMPANY].com','sent just now · by Chris','member'),('ops@[COMPANY].com','sent just now · by Chris','member'),('lee@[PARTNER].com','expired 2d ago','member')])
    return [panel('org · [ORG NAME]', otabs(1,p) + inv + foot('3 invites · 1 expired')), say('Sent. They’ll show as members once they accept.')]
def t4(p): return [user('Make Jo an admin', p), panel('org · [ORG NAME]', otabs(0,p) + members(p, 'Jo Park') + foot('Jo becomes an admin: invites, keys, roles, the audit log', btn('save','b1','sm') + btn('cancel','b3','sm')))]
def t5(p):
    keys = ''.join(item(p, tname(n), sub(f'<span class="m">{k}</span> · {d}'), mono(u,12,MUT), btn('revoke','bd','sm')) for n,k,d,u in [('zapier','gk_live_…[LAST4]','calls inbox-zero, reels','used 3h ago'),('ci','gk_live_…[LAST4]','calls standup','used 1d ago')])
    new = f'<div style="margin:{P(p)};border:1px solid {VI};background:{INK};padding:14px;display:flex;flex-direction:column;gap:10px">{mono("new key · reporting · shown once",12,VI2)}<div class="m" style="display:flex;justify-content:space-between;gap:10px;align-items:center;font-size:13px;color:{FG};word-break:break-all"><span>gk_live_[SHOWN ONCE, COPY IT NOW]</span><button type="button" class="b3 sm" aria-label="Copy key">{ic("copy",14)}</button></div>{sub("Store it somewhere safe. Glyphh keeps only a hash, so it can’t be shown again.")}</div>'
    return [user('Make an API key for reporting', p), panel('org · [ORG NAME]', otabs(2,p) + new + keys + foot('keys call programs over the API, on the org’s credit', btn('new key','b2','sm',prompt=True)))]
AUD = [('14:02','Chris','made an API key','reporting'),('13:40','Sam','approved a result','reels → Codex'),('11:15','Chris','invited','dev@, ops@'),('09:02','Jo','connected','OpenTable'),('yesterday','Sam','made public','leads'),('yesterday','Chris','changed a role','Jo → admin')]
def t6(p):
    rows = ''.join(f'<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:baseline;padding:10px {P(p)};border-top:1px solid {L1}">{mono(w,12,MUT,"width:76px;flex:none")}<span class="t" style="font-size:14px;color:{FG}">{who} <span style="color:{FG2}">{what}</span> <span class="m" style="font-size:13px;color:{VI2}">{obj}</span></span></div>' for w,who,what,obj in AUD)
    return [user('What changed in the org today?', p), panel('org · [ORG NAME]', otabs(3,p) + toolbar(search('search the log','',p), seg(['today','7 days','30 days'],'today') if not p else '', p) + rows + foot('kept for [N] days [CONFIRM] · export as CSV', btn('export','b3','sm')))]
def t7(p):
    return [user('Invite dev@ to the org', p), panel('org', pad(stack(cat('sleepy', 56), h('Only org admins can do that', 18), ptxt('You’re a member of [ORG NAME]. Ask an admin, Chris or Sam, to invite dev@[COMPANY].com.', 14), rowx(btn('ask Chris','b1','sm')), gap=12), p))]
rows = [prow('01','Members','roles at a glance','Org',t1,820,1120), prow('02','Invite','emails and a role','Org',t2,700,960), prow('03','Invites','pending, resend, revoke','Org',t3,720,1120), prow('04','Change a role','','Org',t4,800,1180), prow('05','API keys','a new key, shown once','Org',t5,860,1300), prow('06','The audit log','who did what','Org',t6,840,1240), prow('07','Not an admin','','Org',t7,620,900)]
hdr = head('21','Org','MCP panel · org admins','for org admins · Claude drawn · panel width 760 and phone','The org’s people and access: members and roles, invites, API keys for calling programs from other software, and the audit log of who did what.',['members','invite','invites','change a role','API keys','audit log','not an admin'])
html, w, hh = board('Org', hdr, rows)
emit('Screen21Org.dc.html','hs-21','Screen 21 · Org',html,w,hh,'Screen 21 · Org')
