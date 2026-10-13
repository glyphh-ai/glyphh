from mp import *
def runhead(p, s, line):
    return f'<div style="padding:{"14px 16px" if p else "16px 20px"};display:flex;flex-direction:column;gap:8px;border-bottom:1px solid {L1}"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">{tname(gt()+"reels",15)}{s}</div>{sub(line)}</div>'
def steps(p, cur):
    names = ['youtube.fetch','clips.find','clips.cut','captions.write','instagram · post']
    out = ''
    for i,n in enumerate(names):
        c = OK if i<cur else (VI if i==cur else L2)
        out += f'<div style="flex:1;display:flex;flex-direction:column;gap:6px;min-width:0"><div style="height:3px;background:{c}"></div>{mono(n if not p else str(i+1),11,FG2 if i<=cur else MUT)}</div>'
    return f'<div style="display:flex;gap:6px;padding:{"12px 16px" if p else "14px 20px"}">{out}</div>'
U = 'Make reels from https://youtu.be/[VIDEO] and post the best three.'
def t1(p):
    return [user(U, p), say(f'On it. Your {prog("reels")} program is running on studio-mac. Watch live:'), stream('reels','studio-mac','watch',p,240 if p else 360, site='youtube.com/watch?v=[VIDEO]', step='make-reels · step 2 of 5 · clips.find on claude-sonnet'), f'<div style="display:flex;gap:8px;flex-wrap:wrap">{chip("working", blink=True)}{mono("run r_7c9e · 1m 04s · $0.06 so far",12,MUT)}</div>']
def t2(p):
    return [user(U, p), say(f'You have the machine. reels is paused until you give it back.'), stream('reels','studio-mac','control',p,240 if p else 360, site='youtube.com/watch?v=[VIDEO]&t=312')]
def t3(p):
    q = pad(stack(ptxt('That link is a playlist of 12 videos. Which one should reels use?',14), *[f'<label style="display:flex;gap:12px;align-items:center;min-height:44px;padding:0 12px;border:1px solid {VI if i==0 else L2};cursor:pointer"><span style="width:14px;height:14px;border:1px solid {VI if i==0 else L2};display:flex;align-items:center;justify-content:center;flex:none">{"<span style=" + chr(34) + "width:8px;height:8px;background:" + VI + chr(34) + "></span>" if i==0 else ""}</span><span class="t" style="flex:1;font-size:14px;color:{FG}">{t}</span>{mono(d,12,MUT)}</label>' for i,(t,d) in enumerate([('1 · [VIDEO TITLE]','18:22'),('2 · [VIDEO TITLE]','09:41'),('3 · [VIDEO TITLE]','24:05')])], rowx(btn('use this one','b1','sm'), btn('all 12','b2','sm')), gap=10), p)
    return [user(U.replace('[VIDEO]','[PLAYLIST]'), p), panel('reels', runhead(p, chip('needs input'), 'make-reels · paused at step 1 of 5 · it carries on when you answer') + q)]
def t4(p):
    a = pad(stack(ptxt('reels wants to post to Instagram as <span class="m" style="color:#F5F3FA">@[HANDLE]</span>. It may only post reels you approve; it can’t read your messages or followers.',14), rowx(btn('connect Instagram','b1','sm'), btn('skip posting','b2','sm')), mono('or open the link we sent to chris@[COMPANY].com',12,MUT), gap=12), p)
    return [user(U, p), panel('reels', runhead(p, chip('needs auth'), 'make-reels · paused at step 5 of 5 · 6 reels made, not posted') + steps(p,4) + a)]
def t5(p):
    w = pad(stack(ptxt('This one takes a while, about 6 minutes for an 18 minute video. I’ll tell you here when it’s done; you can close Claude.',14), kv([('run','r_7c9e'),('started','14:02'),('so far','3 of 5 steps · $0.11')]), rowx(btn('watch','b2','sm'), btn('stop the run','bd','sm')), gap=12), p)
    return [user(U, p), panel('reels', runhead(p, chip('working', blink=True), 'make-reels · run as its manifest.js says · insulated on studio-mac') + steps(p,2) + w)]
def t6(p):
    tiles = ''.join(f'<div style="display:flex;flex-direction:column;gap:6px"><div style="aspect-ratio:9/16;background:#16141D;border:1px solid {L1 if i>2 else VI};display:flex;align-items:flex-end;padding:6px">{mono(f"0:{14+i*6:02d}",11,FG2)}</div>{mono(("posted" if i<3 else "kept"),11,OK if i<3 else MUT)}</div>' for i in range(6))
    r = pad(stack(f'<div style="display:grid;grid-template-columns:repeat({3 if p else 6},minmax(0,1fr));gap:8px">{tiles}</div>', mono('used · claude-sonnet, whisper · YouTube, Instagram · 4 functions · the instagram browser · ~/reels',12,MUT), box(f'<div class="m" style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px;color:{FG2}"><span>r2://reels/7c9e.zip · 84 MB</span><span style="color:{MUT}">fetch with a token you approve</span></div>',12,L1,INK), rowx(btn('download','b1','sm'), btn('open on Instagram','b2','sm'), btn('run again','b3','sm')), gap=14), p)
    return [user(U, p), say('Done. Six reels; the best three are posted.'), panel('reels', runhead(p, chip('result'), 'make-reels · finished in 5m 48s · $0.31 · studio-mac') + steps(p,5) + r)]
def t7(p):
    return [user(U, p), panel('reels', runhead(p, chip('error'), 'make-reels · stopped at step 1 of 5') + steps(p,0) + error_block('reels couldn’t fetch the video', 'YouTube says the video is private. Use a public or unlisted video, or ask its owner to share it with you.', 'tr_01JA8QH3W5ZD', p, btn('try another link','b1','sm') + btn('watch the replay','b2','sm')))]
rows = [prow('01','Working, watching live','the machine streams wherever it was called','Reels from a video',t1,900,980), prow('02','Taken control','the program pauses while you drive','Reels from a video',t2,820,900), prow('03','Needs input','one answer and it carries on','Reels from a playlist',t3,820,1000), prow('04','Needs auth','a connection, then it continues','Reels from a video',t4,760,980), prow('05','Working, check back','long runs report when done','Reels from a video',t5,780,1000), prow('06','Result','a link to the output in R2','Reels from a video',t6,860,1200), prow('07','Error','why it stopped, the trace id','Reels from a video',t7,760,960)]
hdr = head('12','A program running','MCP panel','what a call returns while a program runs · every type drawn: working, panel, needs input, needs auth, result, error · Claude drawn','A program called from anywhere runs one of its tasks step by step, each step a function on its models, connections, folders and browsers, and streams its machine live into the conversation. You can watch, or take control and give it back; it stops only to ask for what it can’t do without you.',['working + live stream','taken control','needs input','needs auth','working, check back','result','error'])
html, w, hh = board('A program running', hdr, rows)
emit('Screen12Running.dc.html','hs-12','Screen 12 · A program running',html,w,hh,'Screen 12 · A program running')
