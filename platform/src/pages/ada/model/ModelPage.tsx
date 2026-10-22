import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { useAdaModel, useDeleteAdaModel, type AdaModel } from '@/api/ada';
import { AdaErrorNotice } from '../AdaErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { plural } from '@/lib/format';
import { Button, Dialog, LoadingCard, panelId, tabId, Tabs, TextField, type Tab } from '@/ui';
import { BacktestTab } from './BacktestTab';
import { ExportTab } from './ExportTab';
import { ImportTab } from './ImportTab';
import { SettingsTab } from './SettingsTab';
import { SpecTab } from './SpecTab';
import { TryTab } from './TryTab';
import styles from '../ada.module.css';

type TabId = 'spec' | 'settings' | 'import' | 'try' | 'backtest' | 'export';
const tabs: ReadonlyArray<Tab<TabId>> = [
  { id: 'spec', label: 'Spec' },
  { id: 'settings', label: 'Settings' },
  { id: 'import', label: 'Import' },
  { id: 'try', label: 'Try it' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'export', label: 'Export' },
];

/** One model: its spec and versions, settings, Import, Try it, Backtest and Export, a tab each (`?tab=`). */
export function ModelPage() {
  const { name = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const model = useAdaModel(name);
  const [deleting, setDeleting] = useState(false);
  const asked = params.get('tab') as TabId | null;
  const tab: TabId = tabs.some((t) => t.id === asked) ? asked! : 'spec';

  return (
    <>
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
            {tab === 'spec' && <SpecTab model={model.data} />}
            {tab === 'settings' && <SettingsTab model={model.data} />}
            {tab === 'import' && <ImportTab model={model.data} />}
            {tab === 'try' && <TryTab model={model.data} />}
            {tab === 'backtest' && <BacktestTab model={model.data} />}
            {tab === 'export' && <ExportTab model={model.data} />}
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
