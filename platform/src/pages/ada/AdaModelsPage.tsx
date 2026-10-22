import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useAdaModels, type AdaModelRow } from '@/api/ada';
import { AdaErrorNotice } from './AdaErrorNotice';
import { DeleteModelDialog } from './model/DeleteModelDialog';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { date } from '@/lib/format';
import { Button, Card, EmptyState, LoadingCard, Menu, MenuItem, useToast } from '@/ui';
import styles from './ada.module.css';

const modelPath = (name: string) => `/models/${encodeURIComponent(name)}`;

/**
 * Models, with Ada Cloud on: every model of the org, its active version and the precedents it holds. The whole row
 * opens the model; its menu edits it (the Spec tab, where the model itself is changed) or deletes it.
 */
export function AdaModelsPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const models = useAdaModels();
  const [deleting, setDeleting] = useState<AdaModelRow | null>(null);
  const newModel = (
    <Button variant="primary" icon="plus" onClick={() => navigate('/models/new')}>
      New model
    </Button>
  );

  return (
    <>
      <PageHeader title="Models" description="Each model decides from its own precedents. Open one to change it, load cases, try it or tune it." actions={newModel} />
      {models.isPending && <LoadingCard />}
      <AdaErrorNotice error={models.error} />
      {models.data?.length === 0 && (
        <EmptyState icon="model" title="No models yet" action={newModel}>
          Describe your cases once as a spec. Claude can write it with you through the connector.
        </EmptyState>
      )}
      {models.data && models.data.length > 0 && (
        <Card>
          {/* No scrolling box round this table: it would clip a row's menu. */}
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Model</th>
                <th scope="col">Version</th>
                <th scope="col">Precedents</th>
                <th scope="col">Made</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {models.data.map((model) => (
                <tr key={model.id} className={styles.rowLink} onClick={() => navigate(modelPath(model.name))}>
                  <td>
                    <Link to={modelPath(model.name)} className={styles.link} onClick={(e) => e.stopPropagation()}>
                      {model.name}
                    </Link>
                  </td>
                  <td className={styles.num}>v{model.version}</td>
                  <td className={styles.num}>{model.precedents.toLocaleString('en-GB')}</td>
                  <td>{date(model.created_at)}</td>
                  <td className={styles.rowMenu} onClick={(e) => e.stopPropagation()}>
                    <Menu
                      label={`Actions for ${model.name}`}
                      placement="bottom-end"
                      trigger={({ open, toggle, id }) => (
                        <Button
                          size="sm"
                          variant="ghost"
                          icon="moreVertical"
                          onClick={toggle}
                          aria-label={`Actions for ${model.name}`}
                          aria-haspopup="menu"
                          aria-expanded={open}
                          aria-controls={open ? id : undefined}
                        />
                      )}
                    >
                      {/* Edit opens the model on its Dashboard, like the row (his order, 2026-10-22). */}
                      <MenuItem icon="pencil" onSelect={() => navigate(modelPath(model.name))}>
                        Edit
                      </MenuItem>
                      <MenuItem icon="trash" onSelect={() => setDeleting(model)}>
                        Delete
                      </MenuItem>
                    </Menu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {deleting && (
        <DeleteModelDialog
          model={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            toast.show(`${deleting.name} is deleted.`);
            setDeleting(null);
          }}
        />
      )}
    </>
  );
}
