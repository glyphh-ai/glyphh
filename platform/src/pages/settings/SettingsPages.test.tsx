import { fireEvent, screen, within } from '@testing-library/react';
import { me, org, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

describe('Settings', () => {
  it('opens on General, with the settings sidebar and breadcrumb', async () => {
    renderApp('/settings');
    expect(await screen.findByRole('heading', { name: 'General' })).toBeInTheDocument();
    const main = screen.getByRole('complementary', { name: 'Main' });
    expect(within(main).getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/');
    expect(within(main).queryByRole('img', { name: 'Glyphh' })).not.toBeInTheDocument();
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(within(crumbs).getByText('General')).toHaveAttribute('aria-current', 'page');
  });

  describe('General', () => {
    it('renames the organisation', async () => {
      let sent: unknown;
      server.use(
        http.patch(v1('/org'), async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json({ ...org, name: 'Glyphh Labs' });
        }),
      );
      const { user } = renderApp('/settings/general');
      const field = await screen.findByLabelText('Name');
      await vi.waitFor(() => expect(field).toHaveValue('Glyphh'));
      expect(screen.getByRole('button', { name: 'Update' })).toBeDisabled();
      await user.clear(field);
      await user.type(field, 'Glyphh Labs');
      await user.click(screen.getByRole('button', { name: 'Update' }));
      await vi.waitFor(() => expect(sent).toEqual({ name: 'Glyphh Labs' }));
      expect(await screen.findByText('Organisation renamed.')).toBeInTheDocument();
    });

    it('is read-only for a member', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })));
      renderApp('/settings/general');
      expect(await screen.findByText('Only your org’s admin can change this.')).toBeInTheDocument();
      expect(screen.getByLabelText('Name')).toBeDisabled();
    });
  });

  describe('Members', () => {
    it('lists members with the admin marked, and says they are unlimited', async () => {
      renderApp('/settings/members');
      const list = await screen.findByRole('list', { name: 'Members' });
      expect(within(list).getByText('Chris Timmerman')).toBeInTheDocument();
      expect(within(list).getByText('Admin')).toBeInTheDocument();
      expect(within(list).queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
      expect(await screen.findByText('1 member. Members are unlimited on every plan.')).toBeInTheDocument();
    });

    it('makes an invite and shows its link once', async () => {
      server.use(
        http.post(v1('/org/invites'), () =>
          HttpResponse.json(
            { invite: { id: 'inv-1', email: 'sam@example.com', expires_at: '2026-10-23T00:00:00Z', created_at: '2026-10-16T00:00:00Z' }, link: 'https://glyphh.ai/join?invite=tok' },
            { status: 201 },
          ),
        ),
      );
      const { user } = renderApp('/settings/members');
      await user.type(await screen.findByLabelText('Email'), 'sam@example.com');
      await user.click(screen.getByRole('button', { name: 'Invite' }));
      const dialog = await screen.findByRole('dialog', { name: 'Invite made' });
      expect(within(dialog).getByText('https://glyphh.ai/join?invite=tok')).toBeInTheDocument();
    });

    it('shows the server’s refusal of an invite, with no way to a bigger plan', async () => {
      server.use(http.post(v1('/org/invites'), () => apiError(409, 'E_CONFLICT', 'sam@example.com is already a member.')));
      const { user } = renderApp('/settings/members');
      await user.type(await screen.findByLabelText('Email'), 'sam@example.com');
      await user.click(screen.getByRole('button', { name: 'Invite' }));
      expect(await screen.findByText('sam@example.com is already a member.')).toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'See plans' })).not.toBeInTheDocument();
    });

    it('lets the admin remove a member and cancel an invite', async () => {
      const calls: string[] = [];
      server.use(
        http.get(v1('/org/members'), () =>
          HttpResponse.json([
            { id: 'u-chris', email: 'chris@example.com', name: 'Chris Timmerman', role: 'admin', joined_at: '2026-07-05T12:00:00Z' },
            { id: 'u-sam', email: 'sam@example.com', name: null, role: 'member', joined_at: '2026-10-01T12:00:00Z' },
          ]),
        ),
        http.get(v1('/org/invites'), () => HttpResponse.json([{ id: 'inv-2', email: 'alex@example.com', expires_at: '2026-10-20T00:00:00Z', created_at: '2026-10-13T00:00:00Z' }])),
        http.delete(v1('/org/members/:id'), ({ params }) => {
          calls.push(`member ${params.id}`);
          return new HttpResponse(null, { status: 204 });
        }),
        http.delete(v1('/org/invites/:id'), ({ params }) => {
          calls.push(`invite ${params.id}`);
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/settings/members');
      await user.click(await screen.findByRole('button', { name: 'Remove' }));
      await user.click(within(screen.getByRole('dialog', { name: 'Remove this member?' })).getByRole('button', { name: 'Remove' }));
      await user.click(await screen.findByRole('button', { name: 'Cancel' }));
      await user.click(within(screen.getByRole('dialog', { name: 'Cancel this invite?' })).getByRole('button', { name: 'Cancel invite' }));
      await vi.waitFor(() => expect(calls).toEqual(['member u-sam', 'invite inv-2']));
    });
  });

  describe('Profile', () => {
    it('renames the person', async () => {
      let sent: unknown;
      server.use(
        http.patch(v1('/me'), async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json(me);
        }),
      );
      const { user } = renderApp('/settings/profile');
      const field = await screen.findByLabelText('Name');
      await vi.waitFor(() => expect(field).toHaveValue('Chris Timmerman'));
      await user.clear(field);
      await user.type(field, 'Chris T');
      await user.click(screen.getByRole('button', { name: 'Update' }));
      await vi.waitFor(() => expect(sent).toEqual({ name: 'Chris T' }));
    });

    it('shows each sign-in method, and keeps the last one', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, providers: ['github'] })));
      renderApp('/settings/profile');
      const list = await screen.findByRole('list', { name: 'Sign-in methods' });
      expect(within(list).getByText('Linked')).toBeInTheDocument();
      expect(within(list).getByRole('button', { name: 'Unlink' })).toBeDisabled();
      expect(await within(list).findByRole('button', { name: 'Link' })).toBeInTheDocument();
    });

    it('links a provider through the server’s link page', async () => {
      const location = stubLocation();
      server.use(
        http.get(v1('/me'), () => HttpResponse.json({ ...me, providers: ['github'] })),
        http.post(v1('/me/identities'), async ({ request }) => {
          expect(await request.json()).toEqual({ provider: 'google' });
          return HttpResponse.json({ url: 'http://api.test/auth/google/start?link=x' });
        }),
      );
      try {
        const { user } = renderApp('/settings/profile');
        await user.click(await screen.findByRole('button', { name: 'Link' }));
        await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('http://api.test/auth/google/start?link=x'));
      } finally {
        location.restore();
      }
    });

    it('says when the server sends the person back with a new link', async () => {
      renderApp('/account?linked=google');
      expect(await screen.findByText('Google is linked. You can sign in with it now.')).toBeInTheDocument();
    });
  });

  describe('Installs', () => {
    it('lists installs, unlimited on every plan, and signs one out', async () => {
      let ended = '';
      server.use(
        http.delete(v1('/installs/:id'), ({ params }) => {
          ended = String(params.id);
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/settings/installs');
      const list = await screen.findByRole('list', { name: 'Installs' });
      expect(within(list).getByText('studio-mac')).toBeInTheDocument();
      expect(screen.getByText('2 in use. Installs are unlimited on every plan.')).toBeInTheDocument();
      await user.click(within(list).getAllByRole('button', { name: 'Sign out' })[0]!);
      await user.click(within(screen.getByRole('dialog', { name: 'Sign out this install?' })).getByRole('button', { name: 'Sign out' }));
      await vi.waitFor(() => expect(ended).toBe('i-1'));
    });
  });
});

describe('Settings, more', () => {
  it('General shows the server’s refusal when the organisation cannot be read', async () => {
    server.use(http.get(v1('/org'), () => apiError(503, 'E_UNAVAILABLE', 'Glyphh is busy.')));
    renderApp('/settings/general');
    expect(await screen.findByText('Glyphh is busy.')).toBeInTheDocument();
  });

  describe('Members', () => {
    it('counts the members on any plan, Free too', async () => {
      server.use(http.get(v1('/org'), () => HttpResponse.json({ ...org, members: 4, plan: plans[0] })));
      renderApp('/settings/members');
      expect(await screen.findByText('4 members. Members are unlimited on every plan.')).toBeInTheDocument();
    });

    it('shows the server’s refusal when the members cannot be read', async () => {
      server.use(http.get(v1('/org/members'), () => apiError(503, 'E_UNAVAILABLE', 'Members are unavailable.')));
      renderApp('/settings/members');
      expect(await screen.findByText('Members are unavailable.')).toBeInTheDocument();
    });

    it('keeps the member and the invite when the admin cancels', async () => {
      const calls: string[] = [];
      server.use(
        http.get(v1('/org/members'), () =>
          HttpResponse.json([
            { id: 'u-chris', email: 'chris@example.com', name: 'Chris Timmerman', role: 'admin', joined_at: '2026-07-05T12:00:00Z' },
            { id: 'u-sam', email: 'sam@example.com', name: null, role: 'member', joined_at: '2026-10-01T12:00:00Z' },
          ]),
        ),
        http.get(v1('/org/invites'), () => HttpResponse.json([{ id: 'inv-2', email: 'alex@example.com', expires_at: '2026-10-20T00:00:00Z', created_at: '2026-10-13T00:00:00Z' }])),
        http.delete(v1('/org/members/:id'), () => {
          calls.push('member');
          return new HttpResponse(null, { status: 204 });
        }),
        http.delete(v1('/org/invites/:id'), () => {
          calls.push('invite');
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/settings/members');
      await user.click(await screen.findByRole('button', { name: 'Remove' }));
      const remove = screen.getByRole('dialog', { name: 'Remove this member?' });
      expect(within(remove).getByText('sam@example.com')).toBeInTheDocument();
      await user.click(within(remove).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

      await user.click(within(screen.getByRole('list', { name: 'Open invites' })).getByRole('button', { name: 'Cancel' }));
      const cancel = screen.getByRole('dialog', { name: 'Cancel this invite?' });
      await user.click(within(cancel).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(calls).toEqual([]);
    });

    it('closes the new invite’s link with Done, or with Escape', async () => {
      server.use(
        http.post(v1('/org/invites'), () =>
          HttpResponse.json(
            { invite: { id: 'inv-1', email: 'sam@example.com', expires_at: '2026-10-23T00:00:00Z', created_at: '2026-10-16T00:00:00Z' }, link: 'https://glyphh.ai/join?invite=tok' },
            { status: 201 },
          ),
        ),
      );
      const { user } = renderApp('/settings/members');
      await user.type(await screen.findByLabelText('Email'), 'sam@example.com');
      await user.click(screen.getByRole('button', { name: 'Invite' }));
      await user.click(within(await screen.findByRole('dialog', { name: 'Invite made' })).getByRole('button', { name: 'Done' }));
      expect(screen.queryByText('https://glyphh.ai/join?invite=tok')).not.toBeInTheDocument();
      expect(screen.getByLabelText('Email')).toHaveValue('');

      await user.type(screen.getByLabelText('Email'), 'sam@example.com');
      await user.click(screen.getByRole('button', { name: 'Invite' }));
      const dialog = await screen.findByRole('dialog', { name: 'Invite made' });
      fireEvent(dialog, new Event('cancel', { cancelable: true }));
      expect(screen.queryByText('https://glyphh.ai/join?invite=tok')).not.toBeInTheDocument();
    });
  });

  describe('Profile', () => {
    it('starts with an empty name when the person has none', async () => {
      server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, name: null })));
      const { user } = renderApp('/settings/profile');
      const field = await screen.findByLabelText('Name');
      expect(field).toHaveValue('');
      expect(screen.getByRole('button', { name: 'Update' })).toBeDisabled();
      await user.type(field, 'Chris');
      expect(screen.getByRole('button', { name: 'Update' })).toBeEnabled();
    });

    it('unlinks a provider after asking', async () => {
      let unlinked = '';
      server.use(
        http.delete(v1('/me/identities/:provider'), ({ params }) => {
          unlinked = String(params.provider);
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/settings/profile');
      const list = await screen.findByRole('list', { name: 'Sign-in methods' });
      await user.click(within(list).getAllByRole('button', { name: 'Unlink' })[1]!);
      const dialog = screen.getByRole('dialog', { name: 'Unlink Google?' });
      expect(within(dialog).getByText('You won’t be able to sign in with it until you link it again.')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'Unlink' }));
      await vi.waitFor(() => expect(unlinked).toBe('google'));
      await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    });

    it('keeps the provider when the person cancels', async () => {
      const { user } = renderApp('/settings/profile');
      const list = await screen.findByRole('list', { name: 'Sign-in methods' });
      await user.click(within(list).getAllByRole('button', { name: 'Unlink' })[0]!);
      await user.click(within(screen.getByRole('dialog', { name: 'Unlink GitHub?' })).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('shows the link as busy while the server makes it', async () => {
      server.use(
        http.get(v1('/me'), () => HttpResponse.json({ ...me, providers: ['github'] })),
        http.post(v1('/me/identities'), () => new Promise<Response>(() => {})),
      );
      const { user } = renderApp('/settings/profile');
      await user.click(await screen.findByRole('button', { name: 'Link' }));
      expect(screen.getByRole('button', { name: 'Link' })).toHaveAttribute('aria-busy', 'true');
    });
  });

  describe('Installs', () => {
    it('counts the installs, and marks this one', async () => {
      server.use(
        http.get(v1('/installs'), () =>
          HttpResponse.json([
            { id: 'i-3', machine_id: 'mac-3', name: 'new-mac', surface: 'Claude Code', mod_version: null, last_seen_at: null, created_at: '2026-10-16T09:00:00Z', current: true },
          ]),
        ),
      );
      renderApp('/settings/installs');
      expect(await screen.findByText('1 in use. Installs are unlimited on every plan.')).toBeInTheDocument();
      const list = await screen.findByRole('list', { name: 'Installs' });
      expect(within(list).getByText('This one')).toBeInTheDocument();
      expect(within(list).getByText('Claude Code · not seen yet')).toBeInTheDocument();
    });

    it('says when Glyphh is not signed in anywhere', async () => {
      server.use(http.get(v1('/installs'), () => HttpResponse.json([])));
      renderApp('/settings/installs');
      expect(await screen.findByText('Not signed in anywhere')).toBeInTheDocument();
    });

    it('shows the server’s refusal when the installs cannot be read', async () => {
      server.use(http.get(v1('/installs'), () => apiError(503, 'E_UNAVAILABLE', 'Installs are unavailable.')));
      renderApp('/settings/installs');
      expect(await screen.findByText('Installs are unavailable.')).toBeInTheDocument();
    });

    it('keeps the install signed in when the person cancels', async () => {
      let ended = false;
      server.use(
        http.delete(v1('/installs/:id'), () => {
          ended = true;
          return new HttpResponse(null, { status: 204 });
        }),
      );
      const { user } = renderApp('/settings/installs');
      const list = await screen.findByRole('list', { name: 'Installs' });
      await user.click(within(list).getAllByRole('button', { name: 'Sign out' })[1]!);
      const dialog = screen.getByRole('dialog', { name: 'Sign out this install?' });
      expect(within(dialog).getByText('laptop')).toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(ended).toBe(false);
    });
  });
});

describe('Members on every plan', () => {
  it('lists the members and the invite form on Free: no plan limits them', async () => {
    server.use(http.get(v1('/org'), () => HttpResponse.json({ ...org, plan: plans[0] })));
    renderApp('/settings/members');
    expect(await screen.findByRole('list', { name: 'Members' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
  });

  it('lists the members without a count when the org cannot be read', async () => {
    server.use(http.get(v1('/org'), () => apiError(503, 'E_UNAVAILABLE', 'The org is unavailable.')));
    renderApp('/settings/members');
    expect(await screen.findByRole('list', { name: 'Members' })).toBeInTheDocument();
    expect(screen.queryByText(/unlimited on every plan/)).not.toBeInTheDocument();
  });

  it('shows the members loading while the org is known and the list is not yet', async () => {
    server.use(
      http.get(v1('/org'), () => HttpResponse.json({ ...org, members: 2 })),
      http.get(v1('/org/members'), () => new Promise<never>(() => {})),
    );
    renderApp('/settings/members');
    expect(await screen.findByText('2 members. Members are unlimited on every plan.')).toBeInTheDocument();
    expect(screen.getByLabelText('Loading')).toBeInTheDocument();
  });
});
