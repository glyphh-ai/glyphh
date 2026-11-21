import { useEffect, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router';
import { useLinkProvider, useMe, useRenameMe, useUnlinkProvider } from '@/api/queries';
import { useProviders } from '@/api/session';
import { SSO, type Provider } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { providerLabel } from '@/components/ProviderButtons';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { Button, Chip, Icon, LoadingCard, TextField, useToast, type IconName } from '@/ui';
import { SettingsTitle } from './SettingsTitle';
import styles from './settings.module.css';

export function ProfilePage() {
  const me = useMe();
  const providers = useProviders();
  const rename = useRenameMe();
  const link = useLinkProvider();
  const unlink = useUnlinkProvider();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [name, setName] = useState('');
  const [unlinking, setUnlinking] = useState<Provider | null>(null);

  useEffect(() => {
    if (me.data) setName(me.data.name ?? '');
  }, [me.data]);

  // The server sends the browser back here with ?linked=<provider> once a link is made.
  const linked = params.get('linked');
  useEffect(() => {
    if (!linked) return;
    toast.show(`${providerLabel(linked)} is linked. You can sign in with it now.`);
    setParams({}, { replace: true });
  }, [linked, setParams, toast]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    rename.mutate(name.trim(), { onSuccess: () => toast.show('Name saved.') });
  };

  const linkedProviders = me.data?.providers ?? [];
  const allProviders = Array.from(new Set([...(providers.data?.providers ?? []), ...linkedProviders]));

  return (
    <>
      <SettingsTitle title="Profile">Your name, and the accounts you sign in with.</SettingsTitle>

      <SettingsSection title="Name" description="How you show to the rest of your organisation.">
        {me.isPending && <LoadingCard lines={2} />}
        {me.data && (
          <form className={styles.form} onSubmit={submit}>
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
            <TextField label="Email" value={me.data.email} readOnly hint="From the account you sign in with." />
            <div>
              <Button type="submit" loading={rename.isPending} disabled={!name.trim() || name.trim() === (me.data.name ?? '')}>
                Update
              </Button>
            </div>
            <ApiErrorNotice error={rename.error} />
          </form>
        )}
      </SettingsSection>

      <SettingsSection title="Sign-in methods" description="Link another account to sign in with it too. You always keep at least one.">
        {me.data && (
          <List label="Sign-in methods">
            {allProviders.map((provider) => {
              const isLinked = linkedProviders.includes(provider);
              const icon: IconName = provider === 'github' ? 'github' : provider === SSO ? 'key' : 'google';
              return (
                <Row
                  key={provider}
                  title={
                    <>
                      <Icon name={icon} size={18} />
                      {providerLabel(provider)}
                    </>
                  }
                  badges={isLinked && <Chip tone="green">Linked</Chip>}
                  meta={provider === SSO ? 'Your organisation’s sign-in; its admin sets it up.' : undefined}
                  actions={
                    provider === SSO ? null : isLinked ? (
                      <Button size="sm" variant="ghost" disabled={linkedProviders.length < 2} onClick={() => setUnlinking(provider as Provider)}>
                        Unlink
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        loading={link.isPending && link.variables === provider}
                        onClick={() => link.mutate(provider as Provider, { onSuccess: ({ url }) => window.location.assign(url) })}
                      >
                        Link
                      </Button>
                    )
                  }
                />
              );
            })}
          </List>
        )}
        <ApiErrorNotice error={link.error} />
      </SettingsSection>

      <ConfirmDialog
        open={unlinking !== null}
        title={`Unlink ${unlinking ? providerLabel(unlinking) : ''}?`}
        description="You won’t be able to sign in with it until you link it again."
        confirmLabel="Unlink"
        pending={unlink.isPending}
        error={unlink.error}
        onConfirm={() => unlinking && unlink.mutate(unlinking, { onSuccess: () => setUnlinking(null) })}
        onClose={() => {
          unlink.reset();
          setUnlinking(null);
        }}
      />
    </>
  );
}
