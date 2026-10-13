from mp import *
def overview(p, auto=('off',DIM), bal='$3.18', low=False, card='visa ·· [LAST4] · exp [MM/YY]'):
    g = grid(1 if p else 3, [stat('plan','Pro','[PRICE] / month · renews Nov 1',p), stat('balance',bal,'credit left this period' if not low else '<span style="color:' + WARN + '">low · programs pause at $0</span>',p), stat('auto top-up',auto[0],'add $20 when under $5' if auto[0]=='on' else 'off: programs pause at $0',p)], 8)
    rows = kv([('card', card),('next invoice','Nov 1 · [PRICE]'),('billing email','chris@[COMPANY].com')])
    return pad(stack(g, rows, rowx(btn('add funds','b1','sm'), btn('change plan','b2','sm'), btn('change the card','b2','sm'), btn('invoices','b3','sm')), gap=14), p)
def t1(p):
    return [user('Show my billing', p), panel('billing', overview(p) + foot('payments open Pay on glyphh.ai · Stripe'))]
def topup(p, saved=False):
    t = f'<div style="display:grid;grid-template-columns:repeat({1 if p else 2},minmax(0,1fr));gap:12px"><div><label class="lb" for="th">when the balance is under</label><input id="th" class="in" value="$5.00"></div><div><label class="lb" for="am">add</label><input id="am" class="in" value="$20.00"></div></div>'
    cap = f'<div><label class="lb" for="mx">no more than, per month</label><input id="mx" class="in" value="$100.00"></div>'
    tog = f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">{tname("auto top-up",14)}{seg(["off","on"],"on")}</div>'
    msg = f'<div class="m" style="display:flex;gap:8px;align-items:center;font-size:12px;color:{OK}">{ic("check",13,OK)}saved · charges visa ·· [LAST4]</div>' if saved else mono('charges visa ·· [LAST4] · you get an email each time',12,MUT)
    return pad(stack(tog, t, cap, msg, rowx(btn('done' if saved else 'save','b1','sm'), btn('cancel','b3','sm') if not saved else ''), gap=14), p)
def t2(p): return [user('Turn on auto top-up', p), panel('billing · auto top-up', topup(p))]
def t3(p): return [panel('billing · auto top-up', topup(p, True)), say('Auto top-up is on: $20 when you drop under $5, at most $100 a month.')]
def t4(p):
    l = pad(stack(ptxt('Opening Pay on glyphh.ai to add funds. Come back here when it’s done; this updates by itself.',14), box(f'<div class="m" style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:13px"><span style="color:{FG}">glyphh.ai/pay?add=50</span>{ic("ext",14,MUT)}</div>',12,L1,INK), f'<div style="display:flex;gap:8px;align-items:center">{chip("link")}{mono("waiting for Pay",12,VI2)}<span class="cur m" style="color:{FG}">█</span></div>', gap=12), p)
    return [user('Add $50', p), panel('billing · add funds', l)]
def t5(p):
    return [say('Your balance is almost gone.'), panel('billing', overview(p, bal='$0.42', low=True))]
def t6(p):
    return [user('Show my billing', p), panel('billing', error_block('The last charge failed', 'Your bank declined $20.00 for auto top-up on Oct 11. Programs pause at $0; change the card or add funds another way.', 'tr_01JA8ZK0V3TS', p, btn('change the card','b1','sm') + btn('add funds','b2','sm')))]
def t7(p): return [user('Show my billing', p), panel('billing', loading_rows(3, p))]
rows = [prow('01','Billing','plan, balance, auto top-up, the card','Billing',t1,900,1360), prow('02','Auto top-up','when, how much, a monthly cap','Auto top-up',t2,800,1000), prow('03','Saved','','Auto top-up',t3,700,960), prow('04','Opens Pay','a link type; the panel waits','Add funds',t4,640,900), prow('05','Low balance','before programs pause','Billing',t5,820,1300), prow('06','A charge failed','error with trace id','Billing',t6,700,960), prow('07','Loading','','Billing',t7,620,844)]
hdr = head('19','Billing','MCP panel','the plan and credit from the server’s ledger · every payment opens Pay (screen 04) · Claude drawn · panel width 760 and phone','Your plan, your balance and auto top-up. Anything that charges a card opens Pay, so the card itself is only ever entered on Glyphh’s own page.',['billing','auto top-up','saved','opens Pay','low balance','charge failed','loading'])
html, w, hh = board('Billing', hdr, rows)
emit('Screen19Billing.dc.html','hs-19','Screen 19 · Billing',html,w,hh,'Screen 19 · Billing')
