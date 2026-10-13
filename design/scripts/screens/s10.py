from mp import *
PROGS = [('reels','Turn a YouTube video into reels.','running',VI,'2m ago','studio-mac','public'),
         ('venues','Find and hold offsite venues.','needs you',WARN,'12m ago','studio-mac','private'),
         ('invoices','Chase unpaid invoices every Monday.','ready',OK,'2h ago','fly · iad','private'),
         ('leads','Score inbound leads from the site form.','ready',OK,'5h ago','fly · iad','public'),
         ('standup','Write the team standup from Linear and GitHub.','failed',ERR,'1d ago','aws · eu-west-1','private')]
PARTS = {'reels': '2 models · 2 connections · 4 functions · 2 tasks · 1 browser', 'venues': '1 model · 2 connections · 3 functions · 1 task · 1 browser', 'invoices': '1 model · 3 connections · 2 functions · 1 task, Mondays 9:00', 'leads': '1 model · 2 connections · 2 functions · 1 task', 'standup': '1 model · 3 connections · 2 functions · 1 task, weekdays 8:30'}
def plist(p, rows=PROGS):
    out = ''
    for n,d,s,c,last,where,vis in rows:
        right = status(s, c)
        meta = mono(f'{last} · {where}' + (' · <span style="color:' + VI2 + '">' + n + '.glyphh.app</span>' if vis=='public' else ' · private'), 12, MUT)
        out += item(p, tname(gt() + n), sub(d) + mono(PARTS[n], 11, DIM), right, meta)
    return out
def head_(p, val=''):
    return toolbar(search('search programs', val, p), btn('new program','b2','sm',prompt=True) if not p else '', p) + (f'<div style="display:flex;gap:6px;padding:10px {"16px" if p else "20px"};border-bottom:1px solid {L1};flex-wrap:wrap">' + ''.join(f'<span class="chip" style="{"border-color:" + FG + ";color:" + FG if i==0 else ""}">{t}</span>' for i,t in enumerate(['all 5','needs you 1','running 1','public 2','failed 1'])) + '</div>')
def t1(p):
    pn = panel('programs', head_(p) + plist(p) + foot('5 programs · on 3 machines', btn('open in a tab','b3','sm')), '5')
    return [user('What programs do I have?', p), say('You have five. One needs you: venues is waiting for approval to hold Emmer &amp; Rye.'), pn]
def t2(p):
    rows = [r for r in PROGS if r[6]=='public']
    pn = panel('programs', head_(p, 'public') + plist(p, rows) + foot('2 of 5 match'), '5')
    return [user('Which of my programs are public?', p), say('Two are public, each at its own address.'), pn]
def t3(p):
    pn = panel('programs', empty('No programs yet', 'Describe a job in a sentence and Glyphh builds it into a program: its functions, its checks, and tools you can call from here.', btn('build one','b1','sm',prompt=True) + btn('see examples','b2','sm'), p))
    return [user('Show my programs', p), pn]
def t4(p):
    return [user('Show my programs', p), panel('programs', toolbar(search('search programs','',p), '', p) + loading_rows(4, p))]
def t5(p):
    return [user('Show my programs', p), say('I couldn’t load them.'), panel('programs', error_block('Programs didn’t load', 'Glyphh’s server didn’t answer. Your programs are fine and still running; only this list failed.', 'tr_01JA8N2C5Y7P', p))]
def t6(p):
    rows = [r for r in PROGS if r[0]=='venues']
    pn = panel('programs', head_(p, 'venue') + plist(p, rows) + foot('1 of 5 match'))
    pn2 = panel('programs', head_(p, 'podcast') + empty('No program matches “podcast”', 'Try another word, or build one that does it.', btn('build a podcast program','b2','sm',prompt=True), p))
    return [user('Find my venue program', p), pn, user('and a podcast one?', p), pn2]
rows = [prow('01','My programs','search, status, last run, where it runs, public or private','Programs',t1,1000,1180), prow('02','Filtered','a chip or the search narrows the list','Public programs',t2,760,960), prow('03','Search, and no match','search inside the panel','Find a program',t6,1080,1360), prow('04','Empty','no programs yet','Programs',t3,700,844), prow('05','Loading','skeleton rows','Programs',t4,700,844), prow('06','Error','with the trace id','Programs',t5,700,844)]
hdr = head('10','Programs','MCP panel','returned as a panel by Glyphh’s MCP server · drawn in Claude at the harness’s panel width (760) and on a phone','Every program you own or your org shares: what it does, what it’s made of (models, connections, functions, tasks, browsers), whether it’s running or needs you, when it last ran, where it runs, and whether it’s public.',['my programs','filtered','search + no match','empty','loading','error'])
html, w, hh = board('Programs', hdr, rows)
emit('Screen10Programs.dc.html','hs-10','Screen 10 · Programs',html,w,hh,'Screen 10 · Programs')
