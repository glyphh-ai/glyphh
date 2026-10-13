from mp import *
def keyrow(p, prov, mask, st, c, models, act=''):
    return item(p, tname(prov), sub(f'<span class="m">{mask}</span> · {models}'), status(st,c), act)
def mrow(p, m, via, price):
    return f'<div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px {"16px" if p else "20px"};border-top:1px solid {L1}">{tname(m,13)}<span style="display:flex;gap:12px">{mono(via,12,VI2 if via=="your key" else MUT)}{mono(price,12,MUT)}</span></div>'
def models(p):
    return (section_label('models programs can use', p) + mrow(p,'claude-sonnet-[VER]','your key','billed by Anthropic') + mrow(p,'claude-haiku-[VER]','your key','billed by Anthropic') + mrow(p,'gpt-[VER]','Glyphh credit','$[PRICE] / 1M tokens') + mrow(p,'gemini-[VER]','Glyphh credit','$[PRICE] / 1M tokens') + mrow(p,'whisper','Glyphh credit','$[PRICE] / min'))
def t1(p):
    keys = keyrow(p,'Anthropic','sk-ant-…[LAST4]','works',OK,'checked 2h ago') + keyrow(p,'OpenAI','sk-…[LAST4]','rejected',ERR,'checked 10m ago', btn('replace','b1','sm'))
    return [user('Which models run on my own keys?', p), say('Claude models use your Anthropic key. Your OpenAI key was rejected, so GPT is on Glyphh credit for now.'), panel('models and keys', toolbar(f'<span class="m" style="font-size:13px;color:{FG}">2 keys</span>', btn('add a key','b2','sm',prompt=True), p) + keys + models(p) + foot('everything else goes through Glyphh’s gateway on your credit'))]
PROVS = ['Anthropic','OpenAI','Google','Mistral','OpenRouter','[OTHER]']
def form(p, val='', st=None):
    opts = ''.join(f'<button type="button" class="m" style="min-height:40px;padding:0 12px;background:{FG if n=="OpenAI" else "transparent"};color:{INK if n=="OpenAI" else FG2};border:1px solid {FG if n=="OpenAI" else L2};font-size:13px;cursor:pointer">{n}</button>' for n in PROVS)
    bc = {None:L2,'checking':VI,'ok':OK,'bad':ERR}[st]
    msg = ''
    if st=='checking': msg = f'<div class="m" style="display:flex;gap:10px;align-items:center;font-size:12px;color:{VI2}">{spinner(13)}checking with OpenAI · listing models<span class="cur" style="color:{FG}">█</span></div>'
    if st=='ok': msg = f'<div class="m" style="display:flex;gap:10px;align-items:center;font-size:12px;color:{OK}">{ic("check",13,OK)}works · 14 models unlocked</div>'
    if st=='bad': msg = f'<div class="m" style="font-size:12px;line-height:1.6;color:{ERR}">OpenAI says this key is invalid (401). Check you copied all of it, and that it isn’t revoked.</div>'
    act = {None:btn('check and save','b1','sm dis'),'checking':btn('checking','b1','sm dis'),'ok':btn('done','b1','sm'),'bad':btn('check again','b1','sm')}[st]
    return pad(stack(mono('provider',12,MUT), f'<div style="display:flex;gap:6px;flex-wrap:wrap">{opts}</div>', f'<div><label class="lb" for="k">API key</label><input id="k" class="in" type="password" placeholder="sk-…" value="{val}" style="border-color:{bc}"></div>', msg, mono('keys are encrypted and only ever sent to the provider · Glyphh can’t show it again',12,MUT), f'<div style="display:flex;gap:8px">{act}{btn("cancel","b3","sm")}</div>', gap=12), p)
def t2(p): return [user('Add my OpenAI key', p), panel('models and keys · add a key', form(p))]
def t3(p): return [panel('models and keys · add a key', form(p,'xxxxxxxxxxxxxxxxxxxx','checking'))]
def t4(p): return [panel('models and keys · add a key', form(p,'xxxxxxxxxxxxxxxxxxxx','ok')), say('Your OpenAI key works. GPT models now run on it instead of your credit.')]
def t5(p): return [panel('models and keys · add a key', form(p,'xxxxxxxxxxxxxxxxxxxx','bad') + f'<div class="m" style="padding:0 {"16px" if p else "20px"} 16px;font-size:12px;color:{MUT}">trace <span style="color:{FG};padding:3px 8px;border:1px solid {L2}">tr_01JA8WQ1J7HV</span></div>')]
def t6(p):
    return [user('Which models run on my own keys?', p), say('None yet; every model runs on Glyphh credit.'), panel('models and keys', empty('No keys of your own', 'Programs use any model through Glyphh’s gateway on your credit. Add a provider key and those models bill to you directly instead.', btn('add a key','b1','sm',prompt=True), p) + models(p).replace('your key','Glyphh credit').replace('billed by Anthropic','$[PRICE] / 1M tokens'))]
rows = [prow('01','Models and keys','which models run on my keys','Models',t1,1000,1300), prow('02','Add a key','provider, the key','Add a key',t2,760,1000), prow('03','Checking it','a live call to the provider','Add a key',t3,660,1000), prow('04','It works','models unlocked','Add a key',t4,700,1000), prow('05','Rejected','why, the trace id','Add a key',t5,700,1060), prow('06','No keys','everything on Glyphh credit','Models',t6,1000,1300)]
hdr = head('17','Models and keys','MCP panel','the gateway’s model list and your own provider keys · Claude drawn · panel width 760 and phone','Any model works through Glyphh’s gateway on your credit. Bring your own key for a provider and its models bill to you instead; each key is checked the moment you add it.',['models and keys','add a key','checking','works','rejected','no keys'])
html, w, hh = board('Models and keys', hdr, rows)
emit('Screen17Models.dc.html','hs-17','Screen 17 · Models and keys',html,w,hh,'Screen 17 · Models and keys')
