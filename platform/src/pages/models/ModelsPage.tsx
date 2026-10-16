import { useState } from 'react';
import { useDeleteModel, useModels } from '@/api/queries';
import type { Model } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Card, Chip, EmptyState, LoadingCard } from '@/ui';
import styles from './ModelsPage.module.css';

export function ModelsPage() {
  const models = useModels();
  const remove = useDeleteModel();
  const [deleting, setDeleting] = useState<Model | null>(null);

  return (
    <>
      <PageHeader title="Models" description="Your Ada models: each version by its commit, and where it is active." />

      {models.isPending && <LoadingCard />}
      {models.error && <ApiErrorNotice error={models.error} />}
      {models.data?.length === 0 && (
        <EmptyState icon="model" title="No models yet">
          Make one with Ada in Claude, and its versions show here as you deploy them.
        </EmptyState>
      )}

      <div className={styles.stack}>
        {models.data?.map((model) => (
          <Card key={model.id}>
            <div className={styles.head}>
              <div className={styles.title}>
                <h2 className={styles.name}>{model.name}</h2>
                {model.repo && <span className={styles.repo}>{model.repo}</span>}
              </div>
              <Button size="sm" variant="danger" onClick={() => setDeleting(model)}>
                Delete
              </Button>
            </div>
            {model.versions.length === 0 ? (
              <p className={styles.none}>No versions yet.</p>
            ) : (
              <div className={styles.tableBox}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th scope="col">Version</th>
                      <th scope="col">Commit</th>
                      <th scope="col">Made</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...model.versions].reverse().map((version) => (
                      <tr key={version.id}>
                        <td>v{version.version}</td>
                        <td className={styles.mono}>{version.commit_sha.slice(0, 7)}</td>
                        <td>{date(version.created_at)}</td>
                        <td>
                          {version.active_on.length > 0 ? (
                            <Chip tone="green" dot>
                              Active
                            </Chip>
                          ) : (
                            <span className={styles.muted}>Not active</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={deleting !== null}
        title="Delete this model?"
        description={
          <>
            <strong>{deleting?.name}</strong> and all its versions are deleted. This cannot be undone.
          </>
        }
        confirmLabel="Delete"
        pending={remove.isPending}
        error={remove.error}
        onConfirm={() => deleting && remove.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
        onClose={() => {
          remove.reset();
          setDeleting(null);
        }}
      />
    </>
  );
}
