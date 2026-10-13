from mp import *
MS = [('studio-mac','this computer · macOS 15 · arm64','online',OK,'3 programs · 1 running'),('fly-iad','Fly.io · iad · shared-cpu-2x','online',OK,'2 programs'),('aws-eu','AWS · eu-west-1 · t4g.medium','offline',DIM,'last seen 1d ago · 1 program waiting')]
def mlist(p, ms=MS):
    return ''.join(item(p, tname(n), sub(w), status(s,c), mono(m,12,MUT), f'<span style="flex:none;color:{MUT}">{ic("term",16)}</span>' if not p else '') for n,w,s,c,m in ms)
def t1(p):
    pn = panel('machines', toolbar(f'<span class="m" style="font-size:13px;color:{FG}">3 machines · 2 online</span>', btn('add a machine','b1','sm',prompt=True), p) + mlist(p) + foot('rrotor · every machine fenced, outbound only'), '3')
    return [user('Show my machines', p), say('Two are online. aws-eu dropped off yesterday; standup is waiting for it.'), pn]
HOSTS = [('this computer','macOS or Linux · free','term'),('Fly.io','one click · from $[PRICE]/mo','globe'),('AWS','one click · your account','globe'),('Hetzner','one click · from €[PRICE]/mo','globe'),('any Linux box','SSH in, paste one line','term')]
def t2(p):
    hs = ''.join(f'<button type="button" style="display:flex;gap:12px;align-items:center;text-align:left;width:100%;min-height:60px;padding:12px 14px;background:{INK2};border:1px solid {VI if i==0 else L2};color:{FG};cursor:pointer;box-sizing:border-box">{ic(icn,16,VI2 if i==0 else MUT)}<span style="flex:1;display:flex;flex-direction:column;gap:4px"><span class="m" style="font-size:14px">{n}</span><span class="t" style="font-size:13px;color:{MUT}">{d}</span></span>{ic("chev",14,MUT)}</button>' for i,(n,d,icn) in enumerate(HOSTS))
    pn = panel('machines · add', pad(stack(ptxt('Where should it run? A machine runs your programs always on, inside a fence, and only ever connects out.',14), f'<div style="display:grid;grid-template-columns:repeat({1 if p else 2},minmax(0,1fr));gap:8px">{hs}</div>', gap=14), p))
    return [user('Add a machine', p), pn]
def install(p, st):
    line = f'<div class="m" style="display:flex;align-items:center;gap:10px;justify-content:space-between;border:1px solid {L2};background:{INK};padding:12px 14px;font-size:13px;color:{FG}"><span style="overflow:hidden;white-space:{"normal" if p else "nowrap"};word-break:break-all"><span style="color:{VI}">$</span> curl -fsSL https://glyphh.ai/install | sh -s -- --code K7QD-82MX</span><button type="button" class="b3 sm" aria-label="Copy install line">{ic("copy",14)}</button></div>'
    order = ['waiting','registered','starting','ready']
    idx = order.index(st)
    sts = ''
    for i,s in enumerate(order):
        if i<idx: mk=ic('check',13,OK); c=FG2
        elif i==idx: mk=spinner(13) if s!='ready' else ic('check',13,OK); c=FG
        else: mk=f'<span style="width:13px;height:13px;border:1px solid {L2};flex:none"></span>'; c=MUT
        d = {'waiting':'for the machine to run the line','registered':'studio-mac · macOS 15 · arm64','starting':'pulling rrotor 1.4 · starting the fence','ready':'online · ready to install programs'}[s]
        sts += f'<div style="display:flex;gap:12px;align-items:center;padding:10px 0;border-top:1px solid {L1}">{mk}<span class="m" style="width:{90 if p else 110}px;font-size:13px;color:{c}">{s}</span><span class="t" style="flex:1;font-size:13px;color:{MUT if i>idx else FG2}">{d}</span></div>'
    return stack(ptxt('On the computer you want to use, open a terminal and run:',14), line, mono('the code in it lasts 10 minutes · it shows here when the machine calls in',12,MUT), f'<div>{sts}</div>', gap=12)
def t3(p):
    return [user('Add a machine', p), panel('machines · add · this computer', pad(install(p,'waiting'), p) + foot('step 2 of 3', btn('back','b3','sm')))]
def t4(p):
    return [panel('machines · add · this computer', pad(install(p,'starting'), p))]
def t5(p):
    pn = panel('machines · add · this computer', pad(install(p,'ready'), p) + foot('studio-mac is ready', btn('done','b1','sm') + btn('set up runtimes','b2','sm')))
    return [pn, say('studio-mac is ready. Programs you build now can run on it.')]
def t6(p):
    pn = panel('machines', empty('No machines yet', 'Programs run on a machine you own: this computer, a cloud host in one click, or any Linux box.', btn('add a machine','b1','sm',prompt=True), p))
    return [user('Show my machines', p), pn]
def t7(p):
    pn = panel('machines · aws-eu', f'<div style="padding:{"14px 16px" if p else "16px 20px"};display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;border-bottom:1px solid {L1}">{tname("aws-eu",15)}{status("offline",DIM)}</div>' + error_block('aws-eu stopped calling in', 'Its last message, 1 day ago, was that the disk was full. standup is waiting for it. Free space on the box, or restart it from AWS.', 'tr_01JA8SN2E4RK', p, btn('restart from AWS','b1','sm') + btn('move standup to fly-iad','b2','sm') + btn('remove','bd','sm')))
    return [user('Why is aws-eu offline?', p), pn]
rows = [prow('01','Machines','each one, online or not, where it runs','Machines',t1,820,1000), prow('02','Add a machine: where','the hosts','Add a machine',t2,840,1140), prow('03','The install line, waiting','copy, run, it calls in','Add a machine',t3,820,1060), prow('04','Registered, starting','live as it comes up','Add a machine',t4,640,900), prow('05','Ready','','Add a machine',t5,700,960), prow('06','No machines','empty','Machines',t6,640,844), prow('07','Offline, with the reason','error with trace id','Machines',t7,720,1000)]
hdr = head('14','Machines','MCP panel','rrotor machines on any host · Claude drawn · panel width 760 and phone','The machines your programs run on. Add one on this computer, a cloud host in one click, or any Linux box with one line, and watch it come up live.',['machines','add: where','install line · waiting','registered · starting','ready','empty','offline'])
html, w, hh = board('Machines', hdr, rows)
emit('Screen14Machines.dc.html','hs-14','Screen 14 · Machines',html,w,hh,'Screen 14 · Machines')
