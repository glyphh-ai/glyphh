import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useInstallTemplate, useRemoveTemplate, useTemplate, type Template } from '@/api/templates';
import { List, Row } from '@/components/List';
import { Button, Card, Chip, Dialog, Icon, LoadingCard, TextField, useToast } from '@/ui';
import { AdaErrorNotice } from '../ada/AdaErrorNotice';
import styles from './templates.module.css';

/** Removing takes the slug typed again: the template's models go with everything in them, and it is not undone. */
function RemoveDialog({ template, onClose }: { template: Template; onClose: () => void }) {
  const remove = useRemoveTemplate();
  const toast = useToast();
  const [typed, setTyped] = useState('');
  const removed = () => {
    toast.show(`${template.name} is removed.`);
    onClose();
  };
  return (
    <Dialog
      open
      onClose={onClose}
      title={`Remove ${template.name}?`}
      description="Its tools leave your connector and its models are deleted with everything in them, for every AI you use. This cannot be undone."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" loading={remove.isPending} disabled={typed !== template.slug} onClick={() => remove.mutate(template.slug, { onSuccess: removed })}>
            Remove
          </Button>
        </>
      }
    >
      <TextField label={`Type ${template.slug}`} mono value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
      <AdaErrorNotice error={remove.error} />
    </Dialog>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Details({ template }: { template: Template }) {
  const install = useInstallTemplate();
  const toast = useToast();
  const [removing, setRemoving] = useState(false);
  const installed = () => toast.show(`${template.name} is installed: your connector has its tools.`);
  const action = template.installed ? (
    <Button variant="ghost" icon="trash" onClick={() => setRemoving(true)}>
      Remove
    </Button>
  ) : (
    <Button variant="primary" icon="plus" loading={install.isPending} onClick={() => install.mutate(template.slug, { onSuccess: installed })}>
      Install
    </Button>
  );
  return (
    <>
      <div className={styles.hero}>
        <div className={styles.heroMain}>
          <span className={`${styles.mark} ${styles.markLarge}`} aria-hidden="true">
            <Icon name="layers" size={22} />
          </span>
          <div className={styles.heroText}>
            <h1 className={styles.title}>{template.name}</h1>
            <div className={styles.chips}>
              <Chip>{template.category}</Chip>
              {template.installed && <Chip tone="green">Installed</Chip>}
            </div>
            <p className={styles.lede}>{template.summary}</p>
          </div>
        </div>
        <div className={styles.heroActions}>{action}</div>
      </div>
      <AdaErrorNotice error={install.error} />
      <div className={styles.layout}>
        <div className={styles.sections}>
          <Card aria-labelledby="keeps">
            <div className={styles.sectionHead}>
              <h2 id="keeps" className={styles.sectionTitle}>
                What it keeps
              </h2>
              <p className={styles.sectionAbout}>Each is an Ada model of your own, made when you install it.</p>
            </div>
            <List label={`${template.name}'s models`}>
              {template.models.map((m) => (
                <Row key={m.key} title={m.title} meta={m.about} />
              ))}
            </List>
          </Card>
          <Card aria-labelledby="tools">
            <div className={styles.sectionHead}>
              <h2 id="tools" className={styles.sectionTitle}>
                The tools it adds to your connector
              </h2>
              <p className={styles.sectionAbout}>Every AI signed in to your Glyphh connector can call them.</p>
            </div>
            <List label={`${template.name}'s tools`}>
              {template.tools.map((t) => (
                <Row key={t.name} title={<span className={styles.mono}>{t.name}</span>} meta={t.description} />
              ))}
            </List>
          </Card>
        </div>
        <Card as="div" className={styles.aside} aria-label="About this template">
          <h2 className={styles.asideTitle}>About</h2>
          <dl className={styles.facts}>
            <Fact label="Kind">{template.category}</Fact>
            <Fact label="Version">v{template.version}</Fact>
            <Fact label="Models">{template.models.length}</Fact>
            <Fact label="Tools">{template.tools.length}</Fact>
            <Fact label="Status">{template.installed ? `Installed, v${template.installed_version ?? template.version}` : 'Not installed'}</Fact>
          </dl>
          <p className={styles.note}>Yours alone, not your org’s: what it keeps is only ever read by the AIs you sign in.</p>
        </Card>
      </div>
      {removing && <RemoveDialog template={template} onClose={() => setRemoving(false)} />}
    </>
  );
}

/** One template: what it keeps and the tools it adds, with Install or Remove; the way back to the library above it. */
export function TemplatePage() {
  const { name = '' } = useParams();
  const template = useTemplate(name);
  return (
    <>
      <Link to="/templates" className={styles.back}>
        <Icon name="arrowLeft" size={14} /> Templates
      </Link>
      {template.isPending && <LoadingCard />}
      <AdaErrorNotice error={template.error} />
      {template.data && <Details template={template.data} />}
    </>
  );
}
