import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useAdaModel, useDeleteAdaModel, type AdaModel } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { plural } from '@/lib/format';
import { Button, Dialog, LoadingCard, panelId, tabId, Tabs, TextField, type Tab } from '@/ui';
import { BacktestTab } from './BacktestTab';
import { DashboardTab } from './DashboardTab';
import { ViewTab } from './ViewTab';
import { ExportTab } from './ExportTab';
import { ImportTab } from './ImportTab';
import { SettingsTab } from './SettingsTab';
import { SpecTab } from './SpecTab';
import { TryTab } from './TryTab';
import styles from '../ada.module.css';

type TabId = 'dashboard' | 'view' | 'try' | 'import' | 'backtest' | 'settings' | 'export' | 'spec';
// His order, 2026-10-22: the dashboard first, the spec last.
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'view', label: '3D view' },
  { id: 'try', label: 'Try it' },
  { id: 'import', label: 'Import' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'settings', label: 'Settings' },
  { id: 'export', label: 'Export' },
  { id: 'spec', label: 'Spec' },
];

/**
 * One model, a tab each (`?tab=`): its dashboard, its 3D view, Try it, Import, Backtest, Settings, Export, and its
 * spec and versions; the way back to the models above its name.
 */
export function ModelPage() {
  const { name = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const model = useAdaModel(name);
  const [deleting, setDeleting] = useState(false);
  const asked = params.get('tab') as TabId | null;
  const tab: TabId = tabs.some((t) => t.id === asked) ? asked! : 'dashboard';

  return (
    <>
      <Link to="/models" className={styles.back}>
        ← Models
      </Link>
      <PageHeader
        title={name}
        description={model.data && `Version ${model.data.version} is live · ${plural(model.data.precedents, 'precedent')}`}
        actions={
          model.data && (
            <Button variant="danger" icon="trash" onClick={() => setDeleting(true)}>
              Delete
            </Button>
          )
        }
      />
      {model.isPending && <LoadingCard />}
      <AdaErrorNotice error={model.error} />
      {model.data && (
        <div className={styles.stack}>
          <Tabs label="Model" tabs={tabs} value={tab} onChange={(id) => setParams({ tab: id }, { replace: true })} />
          <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)} className={styles.stack}>
            {tab === 'dashboard' && <DashboardTab model={model.data} />}
            {tab === 'view' && <ViewTab model={model.data} />}
            {tab === 'try' && <TryTab model={model.data} />}
            {tab === 'import' && <ImportTab model={model.data} />}
            {tab === 'backtest' && <BacktestTab model={model.data} />}
            {tab === 'settings' && <SettingsTab model={model.data} />}
            {tab === 'export' && <ExportTab model={model.data} />}
            {tab === 'spec' && <SpecTab model={model.data} />}
          </div>
        </div>
      )}
      {deleting && model.data && <DeleteModelDialog model={model.data} onClose={() => setDeleting(false)} />}
    </>
  );
}

/** Deleting a model takes its name typed again: every precedent and version goes, and it is not undone. */
function DeleteModelDialog({ model, onClose }: { model: AdaModel; onClose: () => void }) {
  const navigate = useNavigate();
  const remove = useDeleteAdaModel();
  const [typed, setTyped] = useState('');
  return (
    <Dialog
      open
      onClose={onClose}
      title="Delete this model?"
      description={
        <>
          <strong>{model.name}</strong>, its {plural(model.precedents, 'precedent')} and every version are deleted. This cannot be undone.
        </>
      }
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            loading={remove.isPending}
            disabled={typed !== model.name}
            onClick={() => remove.mutate(model.name, { onSuccess: () => navigate('/models', { replace: true }) })}
          >
            Delete
          </Button>
        </>
      }
    >
      <TextField label="Type the model’s name" mono value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
      <AdaErrorNotice error={remove.error} />
    </Dialog>
  );
}
