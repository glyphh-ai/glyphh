import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useAddBotTemplate, useBotTemplate, type BotTemplate } from '@/api/botTemplates';
import { useConnections } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { Button, Card, Chip, EmptyState, Icon, LoadingCard, panelId, tabId, Tabs, useToast } from '@/ui';
import { useConnect } from '../connections/useConnect';
import styles from './templates.module.css';

type Tab = 'overview' | 'tools';

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The apps it needs that the org has not connected yet; none until the connections are read. */
function useMissing(template: BotTemplate) {
  const connections = useConnections();
  const have = new Set((connections.data ?? []).map((c) => c.app));
  return { ready: connections.isSuccess, missing: connections.isSuccess ? template.required_apps.filter((a) => !have.has(a.slug)) : [] };
}

/**
 * The services it needs, each said as connected or with Connect, which signs in right here (Pipedream's popup, the
 * spinner) and leaves the person on this page, its Add now open to them.
 */
function Needs({ template }: { template: BotTemplate }) {
  const { missing } = useMissing(template);
  const { connect, connecting, error, dialog } = useConnect({ onConnected: () => undefined });
  const away = new Set(missing.map((a) => a.slug));
  if (template.required_apps.length === 0) return <p className={styles.sectionAbout}>It needs no connection.</p>;
  return (
    <>
      <List label="Connections it needs">
        {template.required_apps.map((app) => (
          <Row
            key={app.slug}
            title={
              <Link to={`/connections/${encodeURIComponent(app.slug)}`} className={styles.open}>
                {app.name}
              </Link>
            }
            meta={away.has(app.slug) ? 'Not connected yet' : 'Connected'}
            actions={
              away.has(app.slug) ? (
                <Button size="sm" variant="secondary" icon="plus" loading={connecting === app.slug} onClick={() => connect({ ...app, description: null })}>
                  Connect
                </Button>
              ) : (
                <Chip tone="green">Connected</Chip>
              )
            }
          />
        ))}
      </List>
      <ApiErrorNotice error={error} />
      {dialog}
    </>
  );
}

function Overview({ template }: { template: BotTemplate }) {
  return (
    <div className={styles.sections}>
      <Card aria-labelledby="about">
        <h2 id="about" className={styles.sectionTitle}>
          What it does
        </h2>
        <p className={styles.lede}>{template.description || template.summary}</p>
      </Card>
      <Card aria-labelledby="needs">
        <div className={styles.sectionHead}>
          <h2 id="needs" className={styles.sectionTitle}>
            Connections
          </h2>
          <p className={styles.sectionAbout}>The services it works in. Connect them before its first run.</p>
        </div>
        <Needs template={template} />
      </Card>
      <Card aria-labelledby="gates">
        <div className={styles.sectionHead}>
          <h2 id="gates" className={styles.sectionTitle}>
            What it learns
          </h2>
          <p className={styles.sectionAbout}>Each gate is an Ada model of your own: it asks you until it has learned your answers.</p>
        </div>
        {template.gates.length === 0 ? (
          <p className={styles.sectionAbout}>It has no gates.</p>
        ) : (
          <List label="Its gates">
            {template.gates.map((g) => (
              <Row key={g} title={<span className={styles.mono}>{g}</span>} />
            ))}
          </List>
        )}
      </Card>
    </div>
  );
}

function ToolsList({ template }: { template: BotTemplate }) {
  if (template.tools.length === 0) return <EmptyState icon="layers" title="It uses no tools" />;
  return (
    <Card aria-labelledby="tools">
      <div className={styles.sectionHead}>
        <h2 id="tools" className={styles.sectionTitle}>
          The tools it uses
        </h2>
        <p className={styles.sectionAbout}>Every tool still asks for your yes until you allow it on its connection.</p>
      </div>
      <List label={`${template.name}'s tools`}>
        {template.tools.map((t) => (
          <Row key={t} title={<span className={styles.mono}>{t}</span>} />
        ))}
      </List>
    </Card>
  );
}

function Details({ template }: { template: BotTemplate }) {
  const add = useAddBotTemplate();
  const toast = useToast();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('overview');
  // The server adds it only once every app it needs is connected (422, reason connections): Add waits for them.
  const { ready, missing } = useMissing(template);
  const added =(bot: { slug: string; name: string }) => {
    toast.show(`${bot.name} is yours: it’s in Bots.`);
    navigate(`/bots/${encodeURIComponent(bot.slug)}`);
  };
  return (
    <>
      <div className={styles.hero}>
        <div className={styles.heroMain}>
          <span className={`${styles.mark} ${styles.markLarge}`} aria-hidden="true">
            <Cat look={template.look} size={40} />
          </span>
          <div className={styles.heroText}>
            <h1 className={styles.title}>{template.name}</h1>
            <div className={styles.chips}>
              <Chip>Bot</Chip>
            </div>
            <p className={styles.lede}>{template.summary}</p>
          </div>
        </div>
        <div className={styles.heroActions}>
          {missing.length > 0 && <span className={styles.sectionAbout}>Connect {missing.map((a) => a.name).join(' and ')} first</span>}
          <Button
            variant="primary"
            icon="plus"
            disabled={!ready || missing.length > 0}
            loading={add.isPending}
            onClick={() => add.mutate(template.slug, { onSuccess: added })}
          >
            Add to my bots
          </Button>
        </div>
      </div>
      <ApiErrorNotice error={add.error} />
      <Tabs
        label="This bot"
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'tools', label: 'Tools' },
        ]}
        value={tab}
        onChange={setTab}
      />
      <div className={styles.layout} role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)}>
        {tab === 'overview' ? <Overview template={template} /> : <ToolsList template={template} />}
        <Card as="div" className={styles.aside} aria-label="About this bot">
          <h2 className={styles.asideTitle}>About</h2>
          <dl className={styles.facts}>
            <Fact label="Runs on">{template.model}</Fact>
            <Fact label="Connections">{template.required_apps.map((a) => a.name).join(', ') || 'None'}</Fact>
            <Fact label="Tools">{template.tools.length}</Fact>
            <Fact label="Gates">{template.gates.length}</Fact>
            <Fact label="Skills">{Object.keys(template.skills).length}</Fact>
          </dl>
          <p className={styles.note}>Added, it is a copy of your org’s own: change it, teach it, run it. This template stays as it is.</p>
        </Card>
      </div>
    </>
  );
}

/** One bot in the Marketplace: what it does, the connections it needs, its tools and gates, and Add to my bots. */
export function BotTemplatePage() {
  const { name = '' } = useParams();
  const template = useBotTemplate(name);
  return (
    <>
      <Link to="/marketplace/bots" className={styles.back}>
        <Icon name="arrowLeft" size={14} /> Marketplace
      </Link>
      {template.isPending && <LoadingCard />}
      <ApiErrorNotice error={template.error} />
      {template.missing && <EmptyState icon="search" title="There is no such bot in the Marketplace" />}
      {template.data && <Details template={template.data} />}
    </>
  );
}
