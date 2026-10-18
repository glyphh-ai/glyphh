import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { ApiError } from '@/api/client';
import { useCancelInvite, useInvite, useInvites, useMe, useMembers, useOrg, useRemoveMember } from '@/api/queries';
import type { Invite, Member, NewInvite } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { List, Row } from '@/components/List';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { date } from '@/lib/format';
import { Avatar, Button, Chip, CopyField, Dialog, LoadingCard, TextField } from '@/ui';
import { MembersUpgrade } from './MembersUpgrade';
import { AdminOnlyNote, SettingsTitle } from './SettingsTitle';
import styles from './settings.module.css';

export function MembersPage() {
  const me = useMe();
  const org = useOrg();
  const members = useMembers();
  const invites = useInvites();
  const isAdmin = me.data?.role === 'admin';

  const [removing, setRemoving] = useState<Member | null>(null);
  const [cancelling, setCancelling] = useState<Invite | null>(null);
  const remove = useRemoveMember();
  const cancel = useCancelInvite();

  const limit = org.data?.plan.limits.members;
  // A plan for one, with no one else here yet: nothing to list or invite, so the page says how to get members.
  const solo = org.data !== undefined && limit !== null && limit !== undefined && limit <= 1 && org.data.members <= 1;

  if (org.isPending) return <LoadingCard />;
  if (solo) return <MembersUpgrade isAdmin={isAdmin} />;

  return (
    <>
      <SettingsTitle title="Members">Who is in your organisation, and who is invited.</SettingsTitle>

      <SettingsSection
        title="Members"
        description={org.data && (limit === null ? `${org.data.members} on ${org.data.plan.name}.` : `${org.data.members} of ${limit} on ${org.data.plan.name}.`)}
      >
        {members.isPending && <LoadingCard />}
        {members.error && <ApiErrorNotice error={members.error} />}
        {members.data && (
          <List label="Members">
            {members.data.map((member) => (
              <Row
                key={member.id}
                title={
                  <>
                    <Avatar name={member.name ?? member.email} />
                    {member.name ?? member.email}
                  </>
                }
                badges={member.role === 'admin' && <Chip tone="violet">Admin</Chip>}
                meta={`${member.name ? `${member.email} · ` : ''}joined ${date(member.joined_at)}`}
                actions={
                  isAdmin &&
                  member.role !== 'admin' && (
                    <Button size="sm" variant="ghost" onClick={() => setRemoving(member)}>
                      Remove
                    </Button>
                  )
                }
              />
            ))}
          </List>
        )}
      </SettingsSection>

      <SettingsSection title="Invites" description="An invite link lasts seven days. Anyone with it can join.">
        {isAdmin && <InviteForm />}
        <AdminOnlyNote isAdmin={isAdmin} />
        {invites.data && invites.data.length > 0 && (
          <List label="Open invites">
            {invites.data.map((invite) => (
              <Row
                key={invite.id}
                title={invite.email}
                meta={`Sent ${date(invite.created_at)} · expires ${date(invite.expires_at)}`}
                actions={
                  isAdmin && (
                    <Button size="sm" variant="ghost" onClick={() => setCancelling(invite)}>
                      Cancel
                    </Button>
                  )
                }
              />
            ))}
          </List>
        )}
      </SettingsSection>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this member?"
        description={
          <>
            <strong>{removing?.name ?? removing?.email}</strong> leaves your organisation and moves to a free organisation of their own.
          </>
        }
        confirmLabel="Remove"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => removing && remove.mutate(removing.id, { onSuccess: () => setRemoving(null) })}
        onClose={() => {
          remove.reset();
          setRemoving(null);
        }}
      />

      <ConfirmDialog
        open={cancelling !== null}
        title="Cancel this invite?"
        description={
          <>
            The link sent to <strong>{cancelling?.email}</strong> stops working.
          </>
        }
        confirmLabel="Cancel invite"
        pending={cancel.isPending}
        error={cancel.error}
        onConfirm={() => cancelling && cancel.mutate(cancelling.id, { onSuccess: () => setCancelling(null) })}
        onClose={() => {
          cancel.reset();
          setCancelling(null);
        }}
      />
    </>
  );
}

function InviteForm() {
  const invite = useInvite();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState<NewInvite | null>(null);
  const atLimit = invite.error instanceof ApiError && invite.error.code === 'E_LIMIT';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    invite.mutate(email.trim(), {
      onSuccess: (result) => {
        setSent(result);
        setEmail('');
      },
    });
  };

  return (
    <>
      <form className={styles.form} onSubmit={submit}>
        <div className={styles.formRow}>
          <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" required />
          <Button type="submit" variant="primary" loading={invite.isPending} disabled={!email.trim()}>
            Invite
          </Button>
        </div>
        <ApiErrorNotice error={invite.error} action={atLimit ? <Link to="/settings/billing">See plans</Link> : undefined} />
      </form>

      <Dialog
        open={sent !== null}
        onClose={() => setSent(null)}
        title="Invite made"
        description={
          <>
            Send this link to <strong>{sent?.invite.email}</strong>. It is shown once, and lasts seven days.
          </>
        }
        actions={
          <Button variant="primary" onClick={() => setSent(null)}>
            Done
          </Button>
        }
      >
        {sent && <CopyField value={sent.link} label="invite link" />}
      </Dialog>
    </>
  );
}
