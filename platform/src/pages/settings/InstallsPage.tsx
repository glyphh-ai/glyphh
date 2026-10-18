import { useState } from 'react';
import { useInstalls, useSignOutInstall } from '@/api/queries';
import type { Install } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { ago } from '@/lib/format';
import { Button, Chip, EmptyState, Icon, LoadingCard } from '@/ui';
import { SettingsTitle } from './SettingsTitle';

export function InstallsPage() {
  const installs = useInstalls();
  const signOut = useSignOutInstall();
  const [ending, setEnding] = useState<Install | null>(null);

  return (
    <>
      <SettingsTitle title="Installs">Where Glyphh is signed in as you, such as Claude Code on a machine.</SettingsTitle>
      <SettingsSection
        title="Signed in"
        description={installs.data && `${installs.data.length} in use. Installs are unlimited on every plan.`}
      >
        {installs.isPending && <LoadingCard />}
        {installs.error && <ApiErrorNotice error={installs.error} />}
        {installs.data?.length === 0 && <EmptyState icon="laptop" title="Not signed in anywhere" />}
        {installs.data && installs.data.length > 0 && (
          <List label="Installs">
            {installs.data.map((install) => (
              <Row
                key={install.id}
                title={
                  <>
                    <Icon name="laptop" />
                    {install.name}
                  </>
                }
                badges={install.current && <Chip tone="violet">This one</Chip>}
                meta={[install.surface, install.mod_version && `v${install.mod_version}`, install.last_seen_at ? `seen ${ago(install.last_seen_at)}` : 'not seen yet']
                  .filter(Boolean)
                  .join(' · ')}
                actions={
                  <Button size="sm" variant="ghost" onClick={() => setEnding(install)}>
                    Sign out
                  </Button>
                }
              />
            ))}
          </List>
        )}
      </SettingsSection>

      <ConfirmDialog
        open={ending !== null}
        title="Sign out this install?"
        description={
          <>
            <strong>{ending?.name}</strong> stops working as you until you sign in there again.
          </>
        }
        confirmLabel="Sign out"
        pending={signOut.isPending}
        error={signOut.error}
        onConfirm={() => ending && signOut.mutate(ending.id, { onSuccess: () => setEnding(null) })}
        onClose={() => {
          signOut.reset();
          setEnding(null);
        }}
      />
    </>
  );
}
