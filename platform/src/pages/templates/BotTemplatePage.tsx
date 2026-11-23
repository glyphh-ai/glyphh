import { Link, useNavigate, useParams } from 'react-router';
import { decidesLines, decisionName, needsRrotor, runsOnPills, useAddBotTemplate, useBotTemplate, type BotTemplate } from '@/api/botTemplates';
import { useConnections } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { List, Row } from '@/components/List';
import { Button, Card, Chip, EmptyState, Icon, LoadingCard, useToast } from '@/ui';
import { RunsOnPills } from './BotTemplates';
import styles from './templates.module.css';

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
  return { ready: connections.isSuccess, missing: connections.isSuccess ? template.apps.filter((a) => !have.has(a.app)) : [] };
}

/** Where apps are connected: the Bots area's CONNECTIONS, the one place for them, its catalog open. */
const CONNECT = '/bots?rail=connections&add=1';

/** The apps it needs, each said as connected or not; one that is not is connected in Bots, under Connections. */
function Needs({ template }: { template: BotTemplate }) {
  const { missing } = useMissing(template);
  const away = new Set(missing.map((a) => a.app));
  if (template.apps.length === 0) return <p className={styles.sectionAbout}>It needs no app.</p>;
  return (
    <List label="Apps it needs">
      {template.apps.map((app) => (
        <Row
          key={app.app}
          title={app.name}
          meta={away.has(app.app) ? 'Not connected yet' : 'Connected'}
          actions={
            away.has(app.app) ? (
              <Link to={CONNECT} className={styles.open}>
                Connect it in Bots
              </Link>
            ) : (
              <Chip tone="green">Connected</Chip>
            )
          }
        />
      ))}
    </List>
  );
}

/** Where it can run, in a sentence, beside the pills. */
function whereWords(template: BotTemplate): string {
  const cloud = template.runs_on.includes('cloud');
  const rrotor = template.runs_on.includes('rrotor');
  if (cloud && rrotor) return 'On Glyphh cloud with nothing to install, or on a rrotor of your own.';
  if (rrotor) return 'Only on a rrotor of your own: it needs that machine’s files and commands. Set one up before you add it.';
  return 'On Glyphh cloud. Nothing to install.';
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
            Apps
          </h2>
          <p className={styles.sectionAbout}>The apps it works in. Connect them before you add it.</p>
        </div>
        <Needs template={template} />
      </Card>
      <Card aria-labelledby="decides">
        <div className={styles.sectionHead}>
          <h2 id="decides" className={styles.sectionTitle}>
            What it decides
          </h2>
          <p className={styles.sectionAbout}>Each is learned in an Ada model of your own: it asks you until it has learned your answers.</p>
        </div>
        {template.decides.length === 0 ? (
          <p className={styles.sectionAbout}>It decides nothing on its own.</p>
        ) : (
          <List label="What it decides">
            {template.decides.map((d) => (
              <Row key={d.name} title={`Decides: ${decidesLines([d])[0]}`} meta={d.question || undefined} />
            ))}
          </List>
        )}
      </Card>
      {template.examples.length > 0 && (
        <Card aria-labelledby="examples">
          <div className={styles.sectionHead}>
            <h2 id="examples" className={styles.sectionTitle}>
              Things to ask it
            </h2>
            <p className={styles.sectionAbout}>Once it is yours, these wait in its chat.</p>
          </div>
          <ul className={styles.examples} aria-label="Things to ask it">
            {template.examples.map((e) => (
              <li key={e}>“{e}”</li>
            ))}
          </ul>
        </Card>
      )}
      <Card aria-labelledby="where">
        <div className={styles.sectionHead}>
          <h2 id="where" className={styles.sectionTitle}>
            Where it can run
          </h2>
          <RunsOnPills runsOn={template.runs_on} />
        </div>
        <p className={styles.sectionAbout}>{whereWords(template)}</p>
      </Card>
    </div>
  );
}

/** The server's refusal to add it: for a bot that needs a rrotor the org has not got, its sentence and where one is set up. */
function Refused({ error }: { error: unknown }) {
  const rrotor = needsRrotor(error);
  if (!rrotor) return <ApiErrorNotice error={error} />;
  const setUp = rrotor.setupUrl.startsWith('/') ? (
    <Link to={rrotor.setupUrl}>Set up a rrotor</Link>
  ) : rrotor.setupUrl ? (
    <a href={rrotor.setupUrl} target="_blank" rel="noreferrer">
      Set up a rrotor
    </a>
  ) : undefined;
  return <ApiErrorNotice error={error} action={setUp} />;
}

function Details({ template }: { template: BotTemplate }) {
  const add = useAddBotTemplate();
  const toast = useToast();
  const navigate = useNavigate();
  // The server adds it only once every app it needs is connected (422, reason connections): Add waits for them.
  const { ready, missing } = useMissing(template);
  const added = (bot: { slug: string; name: string }) => {
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
            <RunsOnPills runsOn={template.runs_on} />
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
      <Refused error={add.error} />
      <div className={styles.layout}>
        <Overview template={template} />
        <Card as="div" className={styles.aside} aria-label="About this bot">
          <h2 className={styles.asideTitle}>About</h2>
          <dl className={styles.facts}>
            <Fact label="Runs on">{runsOnPills(template.runs_on).join(', ')}</Fact>
            <Fact label="Apps">{template.apps.map((a) => a.name).join(', ') || 'None'}</Fact>
            <Fact label="Decides">{template.decides.map((d) => decisionName(d.name)).join(', ') || 'Nothing'}</Fact>
            {template.version && <Fact label="Version">{template.version}</Fact>}
          </dl>
          <p className={styles.note}>Added, it is a copy of your org’s own: change it, teach it, run it. This template stays as it is.</p>
        </Card>
      </div>
    </>
  );
}

/** One bot in the Marketplace: what it does, the apps it needs, what it decides, things to ask it, where it can run, and Add to my bots. */
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
