import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { adaKeys, useAdaVersions, type AdaModel, type AdaVersion, type AdaVersionDetail, type VersionChange } from '@/api/ada';
import { adaApi } from '@/api/client';
import { useMembers } from '@/api/queries';
import { date } from '@/lib/format';
import { specText } from '@/lib/spec';
import { useCopy } from '@/lib/useCopy';
import { autoSummary } from '@/lib/versions';
import { Button, Card, Chip, LoadingCard, Menu, MenuItem, useToast } from '@/ui';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { ChangeResult } from './ChangeResult';
import { CompareDialog, MakeLiveDialog, NoteDialog, ViewDialog } from './VersionDialogs';
import styles from '../ada.module.css';

type Open = { kind: 'view' | 'live' | 'note' | 'compare'; version: AdaVersion };

/** A version's chip beside its number: live, being made, or its store dropped. */
function badge(version: AdaVersion) {
  if (version.active) return <Chip tone="green" dot>Live</Chip>;
  if (version.store.status === 'dropped') return <Chip>Dropped</Chip>;
  if (version.store.status === 'making') return <Chip tone="amber">Being made</Chip>;
  return null;
}

/**
 * Every version of the model, newest first: its number, its release notes (or, when none were written, what it
 * changed), when it was made, and a menu to view it whole, make it live again (a rollback), edit its notes, compare it
 * with the live version or copy its spec.
 */
export function VersionsTab({ model }: { model: AdaModel }) {
  const versions = useAdaVersions(model.name);
  const members = useMembers();
  const client = useQueryClient();
  const toast = useToast();
  const { copy } = useCopy();
  const [open, setOpen] = useState<Open | null>(null);
  const [change, setChange] = useState<VersionChange | null>(null);
  const live = versions.data?.find((v) => v.active)?.version ?? model.version;

  const who = (id: string) => {
    const member = members.data?.find((m) => m.id === id);
    return member ? (member.name ?? member.email) : null;
  };

  const copySpec = async (version: number) => {
    try {
      const detail = await client.fetchQuery({
        queryKey: [...adaKeys.model(model.name), 'versions', version],
        queryFn: () => adaApi.get<AdaVersionDetail>(`/models/${encodeURIComponent(model.name)}/versions/${version}`),
      });
      await copy(specText(detail.spec));
      toast.show(`Version ${version}’s spec is copied.`);
    } catch {
      toast.show(`Version ${version}’s spec could not be copied.`, 'error');
    }
  };

  if (versions.isPending) return <LoadingCard lines={4} />;
  if (versions.error) return <AdaErrorNotice error={versions.error} />;

  return (
    <Card>
      <p className={styles.about}>
        Every change of the spec or settings is a new version. Any version whose stored cases are kept can be made live again.
      </p>
      {change && <ChangeResult model={model.name} change={change} />}
      {/* No scrolling box round this table: it would clip a row's menu. */}
      <table className={styles.table} aria-label="Versions">
        <thead>
          <tr>
            <th scope="col">Version</th>
            <th scope="col">Description</th>
            <th scope="col">Date</th>
            <th scope="col">
              <span className="visually-hidden">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {[...versions.data].reverse().map((version) => (
            <tr key={version.version}>
              <td className={styles.num}>
                <span className={styles.versionCell}>
                  v{version.version}
                  {badge(version)}
                </span>
              </td>
              <td>{version.note.trim() || <span className={styles.auto}>{autoSummary(version)}</span>}</td>
              <td className={styles.num}>{date(version.made_at)}</td>
              <td className={styles.rowMenu}>
                <Menu
                  label={`Actions for version ${version.version}`}
                  placement="bottom-end"
                  trigger={({ open: shown, toggle, id }) => (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon="moreVertical"
                      onClick={toggle}
                      aria-label={`Actions for version ${version.version}`}
                      aria-haspopup="menu"
                      aria-expanded={shown}
                      aria-controls={shown ? id : undefined}
                    />
                  )}
                >
                  <MenuItem icon="eye" onSelect={() => setOpen({ kind: 'view', version })}>
                    View
                  </MenuItem>
                  {!version.active && version.store.status !== 'making' && (
                    <MenuItem icon="undo" onSelect={() => setOpen({ kind: 'live', version })}>
                      Make live
                    </MenuItem>
                  )}
                  <MenuItem icon="pencil" onSelect={() => setOpen({ kind: 'note', version })}>
                    Edit notes
                  </MenuItem>
                  {!version.active && (
                    <MenuItem icon="diff" onSelect={() => setOpen({ kind: 'compare', version })}>
                      Compare with live
                    </MenuItem>
                  )}
                  <MenuItem icon="copy" onSelect={() => void copySpec(version.version)}>
                    Copy spec
                  </MenuItem>
                </Menu>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {open?.kind === 'view' && (
        <ViewDialog model={model} version={open.version} by={who(open.version.made_by)} onClose={() => setOpen(null)} />
      )}
      {open?.kind === 'live' && (
        <MakeLiveDialog
          model={model}
          version={open.version}
          live={live}
          onClose={() => setOpen(null)}
          onLive={(made) => {
            setChange(made);
            setOpen(null);
          }}
        />
      )}
      {open?.kind === 'note' && <NoteDialog model={model} version={open.version} onClose={() => setOpen(null)} />}
      {open?.kind === 'compare' && <CompareDialog model={model} version={open.version} live={live} onClose={() => setOpen(null)} />}
    </Card>
  );
}
