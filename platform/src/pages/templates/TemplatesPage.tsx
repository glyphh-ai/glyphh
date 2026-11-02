import { useState } from 'react';
import { useInstallTemplate, useRemoveTemplate, useTemplates, type Template } from '@/api/templates';
import { List, Row } from '@/components/List';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Button, Card, Chip, Dialog, EmptyState, LoadingCard, TextField, useToast } from '@/ui';
import { AdaErrorNotice } from '../ada/AdaErrorNotice';
import styles from '../ada/ada.module.css';

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
      description={
        <>
          Its tools leave your connector and its models are deleted with everything in them, for every AI you use. This cannot be undone.
        </>
      }
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

function TemplateCard({ template, onRemove }: { template: Template; onRemove: () => void }) {
  const install = useInstallTemplate();
  const toast = useToast();
  const title = `${template.slug}-title`;
  const action = template.installed ? (
    <Button variant="ghost" icon="trash" onClick={onRemove}>
      Remove
    </Button>
  ) : (
    <Button variant="primary" icon="plus" loading={install.isPending} onClick={() => install.mutate(template.slug, { onSuccess: () => toast.show(`${template.name} is installed: your connector has its tools.`) })}>
      Install
    </Button>
  );
  return (
    <Card id={template.slug} aria-labelledby={title} className={styles.release}>
      <div className={styles.leverHead}>
        <div className={styles.chips}>
          <h2 id={title} className={styles.cardTitle}>
            {template.name}
          </h2>
          <Chip>{template.category}</Chip>
          {template.installed && <Chip tone="green">Installed</Chip>}
        </div>
        {action}
      </div>
      <p className={styles.summary}>{template.summary}</p>
      <AdaErrorNotice error={install.error} />
      <h3 className={styles.label}>What it keeps</h3>
      <List label={`${template.name}'s models`}>
        {template.models.map((m) => (
          <Row key={m.key} title={m.title} meta={m.about} />
        ))}
      </List>
      <h3 className={styles.label}>The tools it adds to your connector</h3>
      <List label={`${template.name}'s tools`}>
        {template.tools.map((t) => (
          <Row key={t.name} title={<span className={styles.mono}>{t.name}</span>} meta={t.description} />
        ))}
      </List>
      <p className={styles.details}>Version {template.version} · yours alone, not your org’s</p>
    </Card>
  );
}

/**
 * Templates: the library a person installs from for themselves. Each makes Ada models of their own and adds tools to
 * their own Glyphh connector, so any AI on it shares them; Agentic memory is their glyphh.
 */
export function TemplatesPage() {
  const templates = useTemplates();
  const [removing, setRemoving] = useState<Template | null>(null);
  return (
    <>
      <PageHeader
        title="Templates"
        description="Build your glyphh. A template adds tools to your own connector over Ada models of your own, so every AI you use shares what it keeps."
      />
      {templates.isPending && <LoadingCard />}
      <AdaErrorNotice error={templates.error} />
      {templates.data?.length === 0 && <EmptyState icon="layers" title="No templates yet" />}
      {templates.data && (
        <div className={styles.stack}>
          {templates.data.map((template) => (
            <TemplateCard key={template.slug} template={template} onRemove={() => setRemoving(template)} />
          ))}
        </div>
      )}
      {removing && <RemoveDialog template={removing} onClose={() => setRemoving(null)} />}
    </>
  );
}
