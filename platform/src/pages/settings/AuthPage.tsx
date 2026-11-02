import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { feature } from '@/api/plans';
import { useMe, useRemoveSso, useSetSso, useSso } from '@/api/queries';
import { useSession } from '@/api/session';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { RROTOR_SHOWN } from '@/lib/shelved';
import { Button, CopyField, LoadingCard, Switch, TextField, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from './SettingsTitle';
import styles from './settings.module.css';

const PLANS = '/settings/plans';

/** Settings → Auth: the org's single sign-on by OpenID Connect (Okta, Entra ID, Google Workspace, any), on Enterprise. */
export function AuthPage() {
  const me = useMe();
  const sso = useSso();
  const session = useSession();
  const set = useSetSso();
  const remove = useRemoveSso();
  const toast = useToast();
  const [issuer, setIssuer] = useState('');
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [domains, setDomains] = useState('');
  const [reviewers, setReviewers] = useState('');
  const [enforced, setEnforced] = useState(false);
  const [removing, setRemoving] = useState(false);

  const isAdmin = me.data?.role === 'admin';
  const included = me.data ? feature(me.data.plan, 'sso').included : true;
  const canEdit = isAdmin && included;
  const callbackUrl = sso.data?.callback_url ?? (session.data ? `${session.data.serverUrl}/auth/sso/callback` : '');

  useEffect(() => {
    if (!sso.data) return;
    setIssuer(sso.data.issuer);
    setClientId(sso.data.client_id);
    setDomains(sso.data.domains.join(', '));
    setReviewers((sso.data.reviewers ?? []).join(', '));
    setEnforced(sso.data.enforced);
  }, [sso.data]);

  const listed = (text: string) =>
    text
      .split(/[\s,]+/)
      .map((d) => d.trim().toLowerCase())
      .filter(Boolean);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body = { issuer: issuer.trim(), client_id: clientId.trim(), domains: listed(domains), enforced, reviewers: listed(reviewers) };
    set.mutate(clientSecret ? { ...body, client_secret: clientSecret } : body, {
      onSuccess: () => {
        setClientSecret('');
        toast.show('Single sign-on saved.');
      },
    });
  };

  return (
    <>
      <SettingsTitle title="Auth">How your organisation signs in to Glyphh.</SettingsTitle>

      <SettingsSection
        title="Single sign-on"
        description="Your people sign in with your own identity provider by OpenID Connect: Okta, Entra ID, Google Workspace or any other. On Enterprise."
      >
        {(sso.isPending || me.isPending) && <LoadingCard lines={4} />}
        {sso.error && <ApiErrorNotice error={sso.error} />}
        {sso.data !== undefined && me.data && (
          <form className={styles.form} onSubmit={submit}>
            {!included && (
              <p className={styles.note}>
                Single sign-on is on Enterprise. <Link to={PLANS}>See plans</Link>
              </p>
            )}
            <TextField
              label="Issuer"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              placeholder="https://acme.okta.com"
              hint="Its OpenID configuration is read from /.well-known/openid-configuration before anything is saved."
              disabled={!canEdit}
              required
            />
            <TextField label="Client ID" value={clientId} onChange={(e) => setClientId(e.target.value)} disabled={!canEdit} mono required />
            <TextField
              label="Client secret"
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              hint={sso.data ? 'Set. Leave empty to keep it; it is never shown.' : 'From your identity provider; kept sealed, never shown.'}
              disabled={!canEdit}
              autoComplete="off"
              required={!sso.data}
            />
            <TextField
              label="Email domains"
              value={domains}
              onChange={(e) => setDomains(e.target.value)}
              placeholder="acme.com, acme.co.uk"
              hint="A person whose work email is at one of these signs in here."
              disabled={!canEdit}
              required
            />
            {RROTOR_SHOWN ? (
              <TextField
                label="Reviewer groups"
                value={reviewers}
                onChange={(e) => setReviewers(e.target.value)}
                placeholder="platform-leads, security"
                hint="Groups from your identity provider whose members review the apps published to your rrotors, beside the admin."
                disabled={!canEdit}
              />
            ) : null}
            <CopyField value={callbackUrl} label="Redirect URI" />
            <p className={styles.note}>Register this redirect URI with the client at your identity provider.</p>
            <label className={styles.switchRow}>
              <Switch checked={enforced} onChange={setEnforced} label="Require single sign-on" disabled={!canEdit} />
              <span>
                <span className={styles.switchTitle}>Require single sign-on</span>
                <span className={styles.note}>Your people can no longer sign in with Google or GitHub.</span>
              </span>
            </label>
            <div className={styles.actions}>
              <Button type="submit" variant="primary" loading={set.isPending} disabled={!canEdit || !issuer.trim() || !clientId.trim() || !domains.trim()}>
                {sso.data ? 'Save' : 'Turn on'}
              </Button>
              {sso.data && (
                <Button type="button" variant="ghost" disabled={!canEdit} onClick={() => setRemoving(true)}>
                  Turn off
                </Button>
              )}
            </div>
            <ApiErrorNotice error={set.error} action={<Link to={PLANS}>See plans</Link>} />
            <AdminOnlyNote isAdmin={isAdmin} />
          </form>
        )}
      </SettingsSection>

      <ConfirmDialog
        open={removing}
        title="Turn off single sign-on?"
        description="Your people sign in with Google or GitHub again. The issuer, client and domains are forgotten."
        confirmLabel="Turn off"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setRemoving(false);
              setIssuer('');
              setClientId('');
              setDomains('');
              setReviewers('');
              setEnforced(false);
              toast.show('Single sign-on is off.');
            },
          })
        }
        onClose={() => {
          remove.reset();
          setRemoving(false);
        }}
      />
    </>
  );
}
