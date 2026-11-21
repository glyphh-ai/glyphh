import { useEffect, useState, type FormEvent } from 'react';
import { useMe, useOrg, useRenameOrg } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { Button, LoadingCard, TextField, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from './SettingsTitle';
import styles from './settings.module.css';

export function GeneralPage() {
  const org = useOrg();
  const me = useMe();
  const rename = useRenameOrg();
  const toast = useToast();
  const [name, setName] = useState('');
  const isAdmin = me.data?.role === 'admin';

  useEffect(() => {
    if (org.data) setName(org.data.name);
  }, [org.data]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    rename.mutate(name.trim(), { onSuccess: () => toast.show('Organisation renamed.') });
  };

  return (
    <>
      <SettingsTitle title="General">Your organisation’s name.</SettingsTitle>
      <SettingsSection title="Organisation name" description="Shown to your members and on the invites you send.">
        {org.isPending && <LoadingCard lines={2} />}
        {org.error && <ApiErrorNotice error={org.error} />}
        {org.data && (
          <form className={styles.form} onSubmit={submit}>
            <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} disabled={!isAdmin} />
            <div>
              <Button type="submit" loading={rename.isPending} disabled={!isAdmin || !name.trim() || name.trim() === org.data.name}>
                Update
              </Button>
            </div>
            <ApiErrorNotice error={rename.error} />
            <AdminOnlyNote isAdmin={isAdmin} />
          </form>
        )}
      </SettingsSection>
    </>
  );
}
