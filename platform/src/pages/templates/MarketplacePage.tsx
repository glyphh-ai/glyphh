import { useNavigate } from 'react-router';
import { useAdaCloud } from '@/api/ada';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { panelId, tabId, Tabs } from '@/ui';
import { BotTemplates } from './BotTemplates';
import { ModelTemplates } from './TemplatesPage';

type Kind = 'models' | 'bots';

/**
 * The Marketplace: what Glyphh builds for an org to add, of two kinds, each its own tab with a search and pages:
 * Models (Ada model templates, installed for the person) and Bots (copied into the org as bots of its own). Models
 * are Ada Cloud's, so with it off only Bots shows. The tab is the path: /marketplace/models, /marketplace/bots.
 */
export function MarketplacePage({ kind }: { kind: Kind }) {
  const ada = useAdaCloud();
  const navigate = useNavigate();
  const shown: Kind = ada === false ? 'bots' : kind;
  const tabs = ada === false ? [{ id: 'bots' as const, label: 'Bots' }] : [{ id: 'models' as const, label: 'Models' }, { id: 'bots' as const, label: 'Bots' }];
  return (
    <>
      <PageHeader title="Marketplace" description="Models and bots built to do one job well. Add one and it is yours: a copy of your own to use, teach and change." />
      <Tabs label="Kind" tabs={tabs} value={shown} onChange={(next) => navigate(`/marketplace/${next}`)} />
      <div role="tabpanel" id={panelId(shown)} aria-labelledby={tabId(shown)}>
        {shown === 'models' ? <ModelTemplates /> : <BotTemplates />}
      </div>
    </>
  );
}
