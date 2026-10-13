from mp import *
CONN = [('YouTube','chris@[COMPANY].com','used by reels','connected',OK),('Instagram','@[HANDLE]','used by reels','connected',OK),('Google Calendar','chris@[COMPANY].com','used by venues, standup','connected',OK),('Slack','[WORKSPACE]','used by standup','expired',WARN),('OpenTable','not connected','asked for by venues','needs you',WARN)]
def badge(n):
    return f'<span class="m" style="width:32px;height:32px;flex:none;border:1px solid {L2};display:flex;align-items:center;justify-content:center;font-size:13px;color:{FG}">{n[0]}</span>'
def clist(p):
    out=''
    for n,acct,used,st,c in CONN:
        act = btn('reconnect','b1','sm') if st=='expired' else (btn('connect','b1','sm') if st=='needs you' else '')
        out += item(p, tname(n), sub(f'{acct} · {used}'), status(st,c), act, badge(n))
    return out
def t1(p):
    return [user('What’s connected?', p), say('Five accounts. Slack has expired and OpenTable is waiting for you.'), panel('connections', toolbar(search('search connections','',p), btn('connect one','b2','sm',prompt=True), p) + clist(p) + foot('connections go through Glyphh’s relay · programs never see your passwords'), '5')]
CAT = ['Gmail','GitHub','Linear','Notion','Stripe','HubSpot','Salesforce','Shopify','Airtable','Dropbox','Figma','X']
def t2(p):
    tiles = ''.join(f'<button type="button" style="display:flex;align-items:center;gap:10px;min-height:52px;padding:0 12px;background:{INK2};border:1px solid {L2};color:{FG};cursor:pointer;text-align:left">{badge(n)}<span class="m" style="font-size:13px">{n}</span></button>' for n in (CAT[:6] if p else CAT))
    return [user('Connect something', p), panel('connections · connect one', toolbar(search('search 2,000+ apps [CONFIRM COUNT]','',p),'',p) + pad(stack(mono('popular',12,MUT), f'<div style="display:grid;grid-template-columns:repeat({2 if p else 3},minmax(0,1fr));gap:8px">{tiles}</div>', gap=10), p))]
TOOLS = [('list_videos','read','allow'),('get_transcript','read','allow'),('download_video','read','allow'),('upload_video','write','ask'),('delete_video','delete','deny'),('update_channel','write','deny')]
def t3(p):
    rows=''
    for t,k,v in TOOLS:
        rows += f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;padding:10px {"16px" if p else "20px"};border-top:1px solid {L1}"><span style="display:flex;gap:10px;align-items:center">{tname(t,13)}{mono(k,11,MUT)}</span>{seg(["allow","ask","deny"],v)}</div>'
    head_ = f'<div style="display:flex;gap:12px;align-items:center;padding:{"14px 16px" if p else "16px 20px"};border-bottom:1px solid {L1}">{badge("YouTube")}<span style="flex:1;display:flex;flex-direction:column;gap:4px">{tname("YouTube",15)}{sub("chris@[COMPANY].com · connected 3 days ago")}</span>{status("connected",OK)}</div>'
    return [user('What can reels do with YouTube?', p), panel('connections · YouTube', head_ + section_label('tools · ask means a program asks you in Needs you first', p) + rows + foot('applies to every program in [ORG NAME] [CONFIRM: per program?]', btn('disconnect','bd','sm'))), say('Reads are allowed, uploads ask you first, deletes are denied.')]
def t4(p):
    return [user('Connect OpenTable', p), panel('connections · OpenTable', waiting('waiting for you to sign in to OpenTable', 'A tab opened on opentable.com. Approve Glyphh there and come back; this updates by itself.', p, f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">{btn("open it again","b2","sm")}{btn("cancel","b3","sm")}</div>'))]
def t5(p):
    return [panel('connections · OpenTable', f'<div style="display:flex;gap:12px;align-items:center;padding:{"14px 16px" if p else "16px 20px"}">{badge("OpenTable")}<span style="flex:1;display:flex;flex-direction:column;gap:4px">{tname("OpenTable",15)}{sub("chris@[COMPANY].com · just now")}</span>{status("connected",OK)}</div>' + foot('venues carried on where it stopped', btn('set its tools','b2','sm'))), say('OpenTable is connected. venues is holding Emmer &amp; Rye now.')]
def t6(p):
    return [user('Why did standup fail?', p), panel('connections · Slack', error_block('Slack’s access has expired', 'Slack revoked Glyphh’s token 2 days ago, so standup couldn’t post. Reconnect and it posts today’s standup straight away.', 'tr_01JA8VD8C3MJ', p, btn('reconnect Slack','b1','sm') + btn('remove','b3','sm')))]
def t7(p):
    return [user('What’s connected?', p), panel('connections', empty('Nothing connected', 'Programs connect what they need as they’re built, and ask you first. You can also connect an account now.', btn('connect one','b1','sm',prompt=True), p))]
rows = [prow('01','Connections','connected accounts, which programs use them','Connections',t1,900,1160), prow('02','Connect one','the catalog','Connect an app',t2,760,980), prow('03','A connection’s tools','allow, ask, deny per tool','YouTube',t3,1000,1360), prow('04','Connecting','the provider’s own sign in, then back','Connect OpenTable',t4,620,844), prow('05','Connected','the waiting program carries on','Connect OpenTable',t5,560,844), prow('06','Expired','error with trace id','Connections',t6,700,960), prow('07','Empty','','Connections',t7,620,844)]
hdr = head('16','Connections','MCP panel','accounts connected through Glyphh’s connection relay · Claude drawn · panel width 760 and phone','The accounts your programs act through. Connect one, see which programs use it, and decide per tool what a program may do on its own, must ask about, or may never do.',['connections','connect one','a connection’s tools','connecting','connected','expired','empty'])
html, w, hh = board('Connections', hdr, rows)
emit('Screen16Connections.dc.html','hs-16','Screen 16 · Connections',html,w,hh,'Screen 16 · Connections')
