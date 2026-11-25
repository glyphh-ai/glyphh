import { forgetLogin, pendingLogin, rememberLogin } from './pendingLogin';

describe('the pending log-in note', () => {
  afterEach(() => vi.restoreAllMocks());

  it('remembers the provider chosen, until forgotten', () => {
    expect(pendingLogin()).toBeNull();
    rememberLogin('github');
    expect(pendingLogin()).toEqual(expect.objectContaining({ provider: 'github' }));
    expect(pendingLogin()).not.toHaveProperty('email');
    forgetLogin();
    expect(pendingLogin()).toBeNull();
  });

  it('remembers the work email given for single sign-on', () => {
    rememberLogin('sso', 'pat@acme.com');
    expect(pendingLogin()).toEqual(expect.objectContaining({ provider: 'sso', email: 'pat@acme.com' }));
    forgetLogin();
  });

  it('lasts ten minutes', () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000);
    rememberLogin('google');
    now.mockReturnValue(1_000_000 + 10 * 60 * 1000);
    expect(pendingLogin()).toEqual({ provider: 'google', at: 1_000_000 });
    now.mockReturnValue(1_000_000 + 10 * 60 * 1000 + 1);
    expect(pendingLogin()).toBeNull();
  });

  it('reads a note it cannot make sense of as none', () => {
    sessionStorage.setItem('glyphh.login', '{not json');
    expect(pendingLogin()).toBeNull();
  });

  it('does nothing, and breaks nothing, when the browser refuses storage', () => {
    const refuse = () => {
      throw new DOMException('denied', 'SecurityError');
    };
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(refuse);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(refuse);
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(refuse);
    expect(() => rememberLogin('github')).not.toThrow();
    expect(pendingLogin()).toBeNull();
    expect(() => forgetLogin()).not.toThrow();
  });
});
