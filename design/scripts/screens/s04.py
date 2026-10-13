from sp import *
U = 'glyphh.ai/pay'
def fld(id_, lab, ph, val='', err=None, focus=False):
    bc = ERR if err else (VI if focus else L2)
    e = f'<div class="m" style="margin-top:8px;font-size:12px;color:{ERR}">{err}</div>' if err else ''
    v = f' value="{val}"' if val else ''
    return f'<div style="flex:1;min-width:0"><label class="lb" for="{id_}">{lab}</label><input id="{id_}" class="in" placeholder="{ph}"{v} style="border-color:{bc}">{e}</div>'
def card(p, filled=False, err=None, focus=False):
    n = fld('cn','card number','1234 1234 1234 1234','4242 4242 4242 4242' if filled else '', err, focus)
    r = f'<div style="display:flex;gap:10px">{fld("ce","expiry","MM / YY","08 / 29" if filled else "")}{fld("cc","cvc","CVC","•••" if filled else "")}</div>'
    c = fld('co','country','','United States')
    return stack(n, r, c, note('card details go to Stripe, not to Glyphh'), gap=14)
def summary(rows):
    return box(kv(rows) , 4, L1, INK)
def plan(p, sel=1):
    opts = [('Free','[PRICE]','[CREDIT] credit a month'),('Pro','[PRICE] / month','[CREDIT] credit · [N] machines'),('Team','[PRICE] / member / month','shared credit · org admin')]
    out = ''
    for i,(n,pr,d) in enumerate(opts):
        b = VI if i==sel else L2
        out += f'<label style="display:flex;gap:14px;align-items:center;padding:14px 16px;border:1px solid {b};cursor:pointer"><span style="width:14px;height:14px;border:1px solid {VI if i==sel else L2};display:flex;align-items:center;justify-content:center;flex:none">{"<span style=" + chr(34) + "width:8px;height:8px;background:" + VI + chr(34) + "></span>" if i==sel else ""}</span><span style="flex:1;display:flex;flex-direction:column;gap:4px"><span class="m" style="font-size:14px;color:{FG}">{n}</span><span class="t" style="font-size:13px;color:{MUT}">{d}</span></span><span class="m" style="font-size:13px;color:{FG2};text-align:right">{pr}</span></label>'
    return stack(note('plan'), f'<div style="display:flex;flex-direction:column;gap:8px">{out}</div>', gap=4)
def s1(p):
    return eyebrow('pay · subscribe') + title('Choose a plan', p) + plan(p) + card(p, True) + stack(btn('subscribe · [PRICE] / month','b1','w'), note('renews monthly · cancel any time from Billing'))
def s2(p):
    amts = ''.join(f'<button type="button" class="{"b1" if a=="$50" else "b2"} sm" style="flex:1">{a}</button>' for a in ['$20','$50','$100','other'])
    return (eyebrow('pay · add funds') + stack(title('Add funds', p), ptxt('Credit pays for models, machines and connections beyond your plan. Balance now <span class="m" style="color:#F5F3FA">$3.18</span>.'))
            + stack(note('amount'), f'<div style="display:flex;gap:8px">{amts}</div>', gap=4) + summary([('card','visa ·· [LAST4]'),('new balance','$53.18')]) + btn('add $50.00','b1','w'))
def s3(p):
    return eyebrow('pay · change the card') + stack(title('Change the card', p), ptxt('Used for your plan and for auto top-up. The old card is removed once this one is saved.')) + summary([('current','visa ·· [LAST4] · exp [MM/YY]')]) + card(p, False, None, True) + btn('save card','b1','w dis')
def s4(p):
    return eyebrow('pay · add funds') + title('Add funds', p) + summary([('amount','$50.00'),('card','visa ·· [LAST4]')]) + f'<button type="button" class="b1 w dis" style="opacity:1;gap:10px">{spinner(14)}processing</button>' + note('don’t close this tab · usually a few seconds')
def s5(p):
    bank = f'<div style="border:1px solid {L2};background:#fff;color:#2A2826;padding:20px;display:flex;flex-direction:column;gap:12px;font-family:sans-serif"><div style="font-size:13px;color:#6B6862">[YOUR BANK]</div><div style="font-size:16px;font-weight:600">Confirm this payment</div><div style="font-size:13px;line-height:1.5;color:#4A4743">Approve $50.00 to GLYPHH AI in your banking app, or enter the code we sent to ···· [LAST 2].</div><div style="height:40px;border:1px solid #CFCAC0"></div><div style="height:40px;background:#2A2826"></div></div>'
    return eyebrow('pay · your bank’s check') + stack(title('Your bank wants to check', p), ptxt('This is your bank, not Glyphh. Once it says yes, you come straight back here.')) + bank + rowx(btn('cancel payment','b3'))
def s6(p):
    return mark('ok') + stack(title('Paid', p), ptxt('$50.00 added. Your balance is <span class="m" style="color:#F5F3FA">$53.18</span>. A receipt is on its way to chris@[COMPANY].com.')) + summary([('receipt','[RECEIPT NO.]'),('card','visa ·· [LAST4]')]) + rowx(btn('back to Claude','b1',prompt=True), btn('view billing','b2'))
def s7(p):
    return eyebrow('pay · add funds', ERR) + title('Add funds', p) + summary([('amount','$50.00')]) + card(p, True, 'Your card was declined. Your bank gave no reason; try another card or call them.') + btn('try again','b1','w')
def s8(p):
    return mark('err') + stack(title('The payment didn’t go through', p), ptxt('We couldn’t reach Stripe. You were not charged. Try again in a minute; if it keeps failing, send us the trace id.')) + rowx(btn('try again','b1'), btn('back to Claude','b2')) + trace('tr_01JA8E1W7KQ5')
rows = [sp_row('01','Subscribe','choose a plan, pay by card',U,s1,dh=1120,ph=1180), sp_row('02','Add funds','one-off credit',U,s2,dh=820,ph=844), sp_row('03','Change the card','Stripe’s Payment Element in our look',U,s3,dh=940,ph=980), sp_row('04','Processing','after pay',U,s4), sp_row('05','The bank’s check','3-D Secure, the bank’s own frame',U,s5,dh=880,ph=900), sp_row('06','Paid','receipt sent',U,s6), sp_row('07','Refused','the card was declined',U,s7,dh=980,ph=1000), sp_row('08','Error','with the trace id',U,s8)]
hdr = head('04','Pay','simple page','served by the server at glyphh.ai/pay · Stripe’s Payment Element styled to the look · opened from Billing or a needs-funds link','Subscribe to a plan, add funds, or change the card. The card fields are Stripe’s Payment Element dressed in Glyphh’s fields, so card numbers never touch Glyphh.',['subscribe','add funds','change the card','processing','the bank’s check','paid','refused','error'])
html, w, hh = board('Pay', hdr, rows)
emit('Screen04Pay.dc.html','hs-04','Screen 04 · Pay',html,w,hh,'Screen 04 · Pay')
