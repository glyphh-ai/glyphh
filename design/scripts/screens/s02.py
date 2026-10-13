from sp import *
U = 'glyphh.ai/signin'
def provider(p, busy=None):
    g = f'<button type="button" class="b1 w" style="justify-content:flex-start;gap:12px">{spinner(14) if busy=="google" else google_g()}<span>{"opening Google" if busy=="google" else "continue with Google"}</span></button>'
    gh = f'<button type="button" class="b2 w" style="justify-content:flex-start;gap:12px">{github_g()}<span>continue with GitHub</span></button>'
    return stack(g, gh)
def s1(p):
    return (eyebrow(f'{gt()}glyphh sign in') + stack(title('Sign in to Glyphh', p), ptxt('Use the account your team uses. New here? Signing in makes your account and your own org.')) + provider(p)
            + note('By continuing you agree to the terms and the privacy policy.<br>Signing in from a harness? You come back to it after.'))
def s2(p):
    return (eyebrow(f'{gt()}glyphh sign in') + stack(title('Sign in to Glyphh', p), ptxt('Taking you to Google. Keep this tab open; it closes itself when you are back.')) + provider(p, 'google')
            + note('waiting for Google<span class="cur" style="color:#F5F3FA">█</span>'))
def s3(p):
    return (mark('ok') + stack(title('You’re signed in', p), ptxt('Signed in as <span class="m" style="color:#F5F3FA">chris@[COMPANY].com</span> in the org <span class="m" style="color:#F5F3FA">[ORG NAME]</span>.'))
            + box(stack(note('next'), ptxt('Go back to Claude. Glyphh is ready there; ask it for your programs or build one.', 14)), 16)
            + rowx(btn('back to Claude', 'b1', prompt=True), btn('switch account', 'b2')) + note('this tab can be closed'))
def s4(p):
    return (mark('err') + stack(title('That email isn’t verified', p), ptxt('Google says <span class="m" style="color:#F5F3FA">sam@[DOMAIN].com</span> hasn’t been verified, so Glyphh can’t trust it as yours. Verify it with Google, then sign in again, or use GitHub.'))
            + stack(btn('try Google again', 'b1', 'w'), btn('continue with GitHub', 'b2', 'w')) + trace('tr_01JA8B2V0R4N'))
def s5(p):
    return (mark('err') + stack(title('Sign in didn’t finish', p), ptxt('Something went wrong on our side between Google and Glyphh. Nothing was saved. Try again; if it fails twice, send us the trace id.'))
            + rowx(btn('try again', 'b1'), btn('status', 'b2')) + trace('tr_01JA8B7HFQ1Z'))
rows = [sp_row('01','Sign in','Google or GitHub; one press',U,s1), sp_row('02','Loading','after a provider is chosen',U,s2), sp_row('03','Signed in','back to the harness',U,s3), sp_row('04','Refused','the provider’s email isn’t verified',U,s4), sp_row('05','Error','with the trace id',U,s5)]
hdr = head('02','Sign in','simple page','served by the server at glyphh.ai/signin · opened from a link or inline where the harness allows','The one way in. Google or GitHub, no passwords. Opened from Claude’s first call, from the home page, or from an invite; it hands you back to wherever you came from.',['sign in','loading','signed in','refused','error'])
html, w, hh = board('Sign in', hdr, rows)
emit('Screen02SignIn.dc.html','hs-02','Screen 02 · Sign in',html,w,hh,'Screen 02 · Sign in')
