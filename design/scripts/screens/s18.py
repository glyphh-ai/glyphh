from mp import *
def period(p):
    return f'<div style="padding:{"16px" if p else "20px"};display:flex;flex-direction:column;gap:12px;border-bottom:1px solid {L1}"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">{mono("Oct 1 – Oct 31 · day 12 of 31",12,MUT)}{mono("resets in 19 days",12,MUT)}</div><div style="display:flex;align-items:baseline;gap:10px;flex-wrap:wrap"><span class="d" style="font-size:{32 if p else 40}px">$18.40</span>{sub("used of $40.00 credit this period · $3.18 balance after")}</div>{bar(46)}</div>'
def breakdown(p, rows):
    out=''
    tot = sum(r[1] for r in rows)
    for n,v,extra in rows:
        pct = round(v/tot*100)
        out += f'<div style="display:flex;flex-direction:column;gap:8px;padding:12px {"16px" if p else "20px"};border-top:1px solid {L1}"><div style="display:flex;justify-content:space-between;gap:10px">{tname(n,13)}<span style="display:flex;gap:12px">{mono(extra,12,MUT) if not p else ""}{mono("$%.2f" % v,13,FG)}</span></div>{bar(pct, VI2 if pct>30 else VI)}</div>'
    return out
PROG = [('reels',7.80,'41 runs'),('venues',4.10,'6 runs'),('standup',3.20,'12 runs'),('invoices',2.10,'2 runs'),('leads',1.20,'88 runs')]
MOD = [('claude-sonnet-[VER]',0.00,'your key · 2.1M tokens'),('gpt-[VER]',8.60,'Glyphh credit · 1.4M tokens'),('whisper',4.20,'Glyphh credit · 140 min'),('gemini-[VER]',2.40,'Glyphh credit · 0.8M tokens')]
CON = [('YouTube',2.80,'210 calls'),('Instagram',1.10,'18 calls'),('Google Calendar',0.40,'96 calls'),('OpenTable',0.30,'12 calls')]
MAC = [('studio-mac',0.00,'your computer · no charge'),('fly-iad',3.60,'312 hours')]
def t(sel, rows, note_):
    def f(p):
        names=['program','model','connection','machine']
        return [user(f'Where did my credit go this month{", by " + names[sel] if sel else ""}?', p), say(note_), panel('usage', period(p) + tabs(['by program','by model','by connection','by machine'], sel, p) + breakdown(p, [r if r[1]>0 else (r[0],0.0001,r[2]) for r in rows]) + foot('[CONFIRM] what counts toward credit', btn('billing','b3','sm')))]
    return f
def t5(p):
    return [user('Where did my credit go this month?', p), panel('usage', period(p).replace('$18.40','$0.00').replace('46','0').replace('$3.18 balance after','nothing used yet') + empty('Nothing used yet this period', 'Runs, models, connections and hosted machines show here as programs use them.', '', p))]
def t6(p): return [user('Where did my credit go this month?', p), panel('usage', loading_rows(4, p))]
def t7(p): return [user('Where did my credit go this month?', p), panel('usage', error_block('Usage didn’t load', 'The meter is behind by a few minutes. Your programs keep running; try again shortly.', 'tr_01JA8YC4R2PE', p))]
def t8(p):
    a = pad(stack(ptxt('You’ve used 90% of this period’s credit. At $0 programs pause and ask you in Needs you.',14), rowx(btn('add funds','b1','sm'), btn('turn on auto top-up','b2','sm')), gap=12), p)
    return [say('Heads up: credit is running low.'), panel('usage', period(p).replace('$18.40','$36.10').replace('46','90') + a)]
rows = [prow('01','By program','this period’s credit and use','Usage',t(0,PROG,'reels used the most: 41 runs, mostly captions.'),1000,1300), prow('02','By model','your keys cost no credit','Usage',t(1,MOD,'GPT on Glyphh credit is the biggest line; your OpenAI key would move it off credit.'),920,1200), prow('03','By connection','','Usage',t(2,CON,'Connections are small; YouTube is most of it.'),880,1160), prow('04','By machine','hosted machines','Usage',t(3,MAC,'Only fly-iad costs credit; your own computer is free.'),800,1060), prow('05','Running low','90% used','Usage',t8,640,900), prow('06','Nothing used yet','start of a period','Usage',t5,760,1000), prow('07','Loading','','Usage',t6,640,844), prow('08','Error','with the trace id','Usage',t7,680,900)]
hdr = head('18','Usage','MCP panel','metered by the server’s credit ledger · Claude drawn · panel width 760 and phone','This period’s credit and what used it: by program, by model, by connection and by machine, with a warning before it runs out.',['by program','by model','by connection','by machine','running low','nothing yet','loading','error'])
html, w, hh = board('Usage', hdr, rows)
emit('Screen18Usage.dc.html','hs-18','Screen 18 · Usage',html,w,hh,'Screen 18 · Usage')
