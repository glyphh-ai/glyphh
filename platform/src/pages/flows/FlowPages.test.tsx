import { fireEvent, screen, within } from '@testing-library/react';
import { renderApp, stubLocation } from '@/test/render';
import { http, HttpResponse, server, serverUrl, sessionHandler } from '@/test/server';
import { pendingLogin, rememberLogin } from './pendingLogin';

const consent = (body: Record<string, unknown>, status = 200) =>
  http.get(`${serverUrl}/auth/consent`, ({ request }) => {
    expect(new URL(request.url).searchParams.get('consent')).toBe('c1');
    return HttpResponse.json(body, { status });
  });

describe('Log in', () => {
  it('offers each provider, starting the platform’s sign-in and coming back afterwards', async () => {
    server.use(sessionHandler(false));
    renderApp('/login?returnTo=/models');
    const github = await screen.findByRole('link', { name: 'Log in with GitHub' });
    expect(github).toHaveAttribute('href', '/auth/login?returnTo=%2Fmodels');
    expect(screen.getByRole('link', { name: 'Log in with Google' })).toBeInTheDocument();
    expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument();
  });

  it('says the person agrees to the terms and the privacy policy', async () => {
    server.use(sessionHandler(false));
    renderApp('/login');
    expect(await screen.findByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', 'https://glyphh.ai/terms');
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', 'https://glyphh.ai/privacy');
  });

  it('says why the last sign-in failed', async () => {
    server.use(sessionHandler(false));
    renderApp('/login?failed=denied');
    expect(await screen.findByText('You chose not to sign in.')).toBeInTheDocument();
  });

  it('sends a signed-out person on a signed-in page to log in, and back after', async () => {
    const location = stubLocation();
    server.use(sessionHandler(false));
    try {
      renderApp('/keys');
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('/login?returnTo=%2Fkeys'));
    } finally {
      location.restore();
    }
  });
});

describe('Log in, more', () => {
  it.each([
    ['/login?returnTo=/models', '/models'],
    ['/login?returnTo=//evil.test', '/'],
    ['/login?returnTo=https://evil.test', '/'],
    ['/login', '/'],
  ])('sends a person already signed in on from %s to %s', async (path, to) => {
    const location = stubLocation();
    try {
      renderApp(path);
      await vi.waitFor(() => expect(location.replace).toHaveBeenCalledWith(to));
    } finally {
      location.restore();
    }
  });

  it('says the sign-in could not finish for a reason it does not know', async () => {
    server.use(sessionHandler(false));
    renderApp('/login?failed=invalid_grant');
    expect(await screen.findByText('The sign-in could not finish. Try again.')).toBeInTheDocument();
  });

  it('says so when the providers cannot be read', async () => {
    server.use(sessionHandler(false), http.get('*/auth/providers', () => HttpResponse.error()));
    renderApp('/login');
    expect(await screen.findByText('Glyphh could not be reached. Try again in a moment.')).toBeInTheDocument();
  });

  it('names a provider it has no icon for as the server does', async () => {
    server.use(sessionHandler(false), http.get('*/auth/providers', () => HttpResponse.json({ providers: ['gitlab'] })));
    renderApp('/login');
    const link = await screen.findByRole('link', { name: 'Log in with gitlab' });
    expect(link.querySelector('svg')).toBeNull();
  });

  it('remembers the provider chosen, so the steps after it are taken for the person', async () => {
    server.use(sessionHandler(false));
    const { user } = renderApp('/login');
    const link = await screen.findByRole('link', { name: 'Log in with Google' });
    const stay = (event: MouseEvent) => event.preventDefault();
    document.addEventListener('click', stay);
    try {
      await user.click(link);
    } finally {
      document.removeEventListener('click', stay);
    }
    expect(pendingLogin()).toBe('google');
  });
});

describe('/authorize', () => {
  it('asks a third-party client’s person to sign in, each provider going to the server', async () => {
    renderApp('/authorize?oauth=o1&client=Claude');
    expect(await screen.findByRole('heading', { name: 'Claude wants to use your Glyphh account' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Continue with GitHub' })).toHaveAttribute('href', `${serverUrl}/auth/github/start?oauth=o1`);
  });

  it('continues the platform’s own log-in with the provider already chosen', async () => {
    const location = stubLocation();
    rememberLogin('google');
    try {
      renderApp('/authorize?oauth=o1&client=Glyphh');
      await vi.waitFor(() => expect(location.replace).toHaveBeenCalledWith(`${serverUrl}/auth/google/start?oauth=o1`));
      expect(screen.getByRole('heading', { name: 'Logging you in' })).toBeInTheDocument();
    } finally {
      location.restore();
    }
  });

  it('calls a client that gives no name “An app”', async () => {
    renderApp('/authorize?oauth=o1');
    expect(await screen.findByRole('heading', { name: 'An app wants to use your Glyphh account' })).toBeInTheDocument();
  });

  it('says the link is incomplete without its sign-in', async () => {
    renderApp('/authorize?client=Claude');
    expect(await screen.findByRole('heading', { name: 'Sign-in link incomplete' })).toBeInTheDocument();
    expect(screen.getByText('This link is missing part of the sign-in. Start again from the app that sent you here.')).toBeInTheDocument();
  });
});

describe('/allow', () => {
  it('shows what the client asks for, with Allow and Deny going to the server', async () => {
    server.use(consent({ kind: 'oauth', client: 'Claude', returns_to: 'claude.ai', resource: 'https://api.glyphh.ai/mcp', email: 'chris@example.com' }));
    renderApp('/allow?consent=c1');
    expect(await screen.findByRole('heading', { name: 'Claude wants to use your Glyphh account' })).toBeInTheDocument();
    expect(screen.getByText('chris@example.com')).toBeInTheDocument();
    expect(screen.getByText('claude.ai')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Allow' })).toHaveAttribute('href', `${serverUrl}/auth/oauth/allow?consent=c1&decision=allow`);
    expect(screen.getByRole('link', { name: 'Deny' })).toHaveAttribute('href', `${serverUrl}/auth/oauth/allow?consent=c1&decision=deny`);
  });

  it('allows the platform’s own log-in without asking', async () => {
    const location = stubLocation();
    rememberLogin('github');
    server.use(consent({ kind: 'oauth', client: 'Glyphh', returns_to: 'platform.glyphh.ai', resource: 'x', email: 'chris@example.com' }));
    try {
      renderApp('/allow?consent=c1');
      await vi.waitFor(() => expect(location.replace).toHaveBeenCalledWith(`${serverUrl}/auth/oauth/allow?consent=c1&decision=allow`));
    } finally {
      location.restore();
    }
  });

  it('shows the server’s words when the consent has expired', async () => {
    server.use(consent({ error: { code: 'E_INVALID', message: 'This sign-in has expired or moved to another browser. Start again in Claude.', trace_id: 't9' } }, 422));
    renderApp('/allow?consent=c1');
    expect(await screen.findByText('This sign-in has expired or moved to another browser. Start again in Claude.')).toBeInTheDocument();
    expect(screen.getByText('Trace t9')).toBeInTheDocument();
  });
});

describe('/allow, more', () => {
  it('asks as usual for the platform’s own name when its log-in did not start in this tab', async () => {
    server.use(consent({ kind: 'oauth', client: 'Glyphh', returns_to: null, resource: 'x', email: 'chris@example.com' }));
    renderApp('/allow?consent=c1');
    expect(await screen.findByRole('heading', { name: 'Glyphh wants to use your Glyphh account' })).toBeInTheDocument();
    expect(screen.queryByText('Then back to')).not.toBeInTheDocument();
  });

  it('cannot continue without a consent', async () => {
    renderApp('/allow');
    expect(await screen.findByRole('heading', { name: 'This sign-in can’t continue' })).toBeInTheDocument();
  });

  it('cannot continue with a consent for an install', async () => {
    server.use(consent({ kind: 'device', code: 'ABCD-EFGH', name: 'studio-mac', surface: 'Claude Code', email: 'chris@example.com' }));
    renderApp('/allow?consent=c1');
    expect(await screen.findByRole('heading', { name: 'This sign-in can’t continue' })).toBeInTheDocument();
  });

  it('says the server could not be reached when the consent cannot be read', async () => {
    server.use(http.get(`${serverUrl}/auth/consent`, () => HttpResponse.error()));
    renderApp('/allow?consent=c1');
    expect(
      await screen.findByText('Glyphh could not be reached, or this browser blocked the request. Start again from the app that sent you here.'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Trace/)).not.toBeInTheDocument();
  });
});

describe('/device', () => {
  it('shows the code to match and the providers', async () => {
    renderApp('/device?code=ABCD-EFGH');
    expect(await screen.findByLabelText('Code')).toHaveTextContent('ABCD-EFGH');
    expect(await screen.findByRole('link', { name: 'Continue with Google' })).toHaveAttribute('href', `${serverUrl}/auth/google/start?code=ABCD-EFGH`);
  });

  it('asks for the code when the link has none', async () => {
    const { user } = renderApp('/device');
    await user.type(await screen.findByLabelText('Code'), 'wxyz-1234');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    expect(await screen.findByText('WXYZ-1234')).toBeInTheDocument();
  });

  it('asks to approve the install that showed the code', async () => {
    server.use(consent({ kind: 'device', code: 'ABCD-EFGH', name: 'studio-mac', surface: 'Claude Code', email: 'chris@example.com' }));
    renderApp('/device/approve?consent=c1');
    expect(await screen.findByText('studio-mac (Claude Code)')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Approve' })).toHaveAttribute('href', `${serverUrl}/auth/approve?consent=c1&decision=approve`);
    expect(screen.getByRole('link', { name: 'Deny' })).toHaveAttribute('href', `${serverUrl}/auth/approve?consent=c1&decision=deny`);
  });

  it('says how it ended', async () => {
    renderApp('/device/done?result=approved');
    expect(await screen.findByRole('heading', { name: 'Signed in' })).toBeInTheDocument();
  });

  it('says when it was denied', async () => {
    renderApp('/device/done?result=denied');
    expect(await screen.findByRole('heading', { name: 'Nothing was signed in' })).toBeInTheDocument();
    expect(screen.getByText('You denied the sign-in. You can close this tab.')).toBeInTheDocument();
  });

  it('never sends a blank code on', async () => {
    const { user, router } = renderApp('/device');
    await user.type(await screen.findByLabelText('Code'), '   ');
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
    fireEvent.submit(screen.getByLabelText('Code').closest('form')!);
    expect(router.state.location.search).toBe('');
    expect(screen.getByRole('heading', { name: 'Enter the code from Claude' })).toBeInTheDocument();
  });

  it('cannot approve without a consent', async () => {
    renderApp('/device/approve');
    expect(await screen.findByRole('heading', { name: 'This sign-in can’t continue' })).toBeInTheDocument();
  });

  it('cannot approve a consent for an app', async () => {
    server.use(consent({ kind: 'oauth', client: 'Claude', returns_to: null, resource: 'x', email: 'chris@example.com' }));
    renderApp('/device/approve?consent=c1');
    expect(await screen.findByRole('heading', { name: 'This sign-in can’t continue' })).toBeInTheDocument();
  });

  it('shows the server’s words when the install’s consent has expired', async () => {
    server.use(consent({ error: { code: 'E_INVALID', message: 'This code has expired. Start again in Claude.', trace_id: 't8' } }, 422));
    renderApp('/device/approve?consent=c1');
    expect(await screen.findByText('This code has expired. Start again in Claude.')).toBeInTheDocument();
    expect(screen.getByText('Trace t8')).toBeInTheDocument();
  });
});

describe('Server pages', () => {
  it('/error shows the message and the trace id to quote', async () => {
    renderApp('/error?code=E_LIMIT&message=Your%20plan%20allows%201%20install.&trace=tr-77');
    expect(await screen.findByText('Your plan allows 1 install.')).toBeInTheDocument();
    expect(screen.getByText('tr-77')).toBeInTheDocument();
  });

  it('/github says where the app is installed', async () => {
    renderApp('/github?installed=chris-t');
    const card = await screen.findByRole('heading', { name: 'GitHub App installed' });
    expect(within(card.parentElement!).getByText('chris-t')).toBeInTheDocument();
  });

  it('/github without a name says it is on the person’s account', async () => {
    renderApp('/github');
    expect(await screen.findByText('your account')).toBeInTheDocument();
  });

  it('/error without a message says something went wrong', async () => {
    renderApp('/error');
    expect(await screen.findByText('Something went wrong.')).toBeInTheDocument();
    expect(screen.queryByText('If you contact us, quote this trace id.')).not.toBeInTheDocument();
  });

  it('an unknown path says so', async () => {
    renderApp('/nope');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});
