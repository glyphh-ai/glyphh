import { Link } from 'react-router';
import { useTemplates, type Template } from '@/api/templates';
import { NoMatch, Pager, SearchField, useSearchPaging } from '@/components/SearchPaged';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { plural } from '@/lib/format';
import { Chip, EmptyState, Icon, LoadingCard } from '@/ui';
import { AdaErrorNotice } from '../ada/AdaErrorNotice';
import styles from './templates.module.css';

export const templatePath = (slug: string) => `/templates/${encodeURIComponent(slug)}`;

const matchesTemplate = (t: Template, q: string) =>
  [t.name, t.category, t.summary, ...t.tools.map((tool) => tool.name)].some((s) => s.toLowerCase().includes(q));

/** One template as a card; the whole card opens its details. */
function TemplateCard({ template }: { template: Template }) {
  const title = `${template.slug}-title`;
  return (
    <li>
      <Link to={templatePath(template.slug)} className={styles.card} aria-labelledby={title}>
        <div className={styles.cardHead}>
          <span className={styles.mark} aria-hidden="true">
            <Icon name="layers" />
          </span>
          <div className={styles.cardTitles}>
            <h2 id={title} className={styles.name}>
              {template.name}
            </h2>
            <div className={styles.chips}>
              <Chip>{template.category}</Chip>
              {template.installed && <Chip tone="green">Installed</Chip>}
            </div>
          </div>
        </div>
        <p className={styles.summary}>{template.summary}</p>
        <div className={styles.cardFoot}>
          <span>
            {plural(template.models.length, 'model')} · {plural(template.tools.length, 'tool')} · v{template.version}
          </span>
          <span className={styles.open}>
            Details <Icon name="chevronRight" />
          </span>
        </div>
      </Link>
    </li>
  );
}

/**
 * Templates: the library a person installs from for themselves, as cards with a search and pages, like Models and
 * API Keys. Each template makes Ada models of the person's own and adds tools to their own Glyphh connector, so any
 * AI on it shares them; a card opens the template's details (TemplatePage), where it is installed or removed.
 */
export function TemplatesPage() {
  const templates = useTemplates();
  const paged = useSearchPaging(templates.data, matchesTemplate);
  const some = templates.data !== undefined && templates.data.length > 0;
  return (
    <>
      <PageHeader
        title="Templates"
        description="Build your glyphh. A template adds tools to your own connector over Ada models of your own, so every AI you use shares what it keeps."
      />
      {templates.isPending && <LoadingCard />}
      <AdaErrorNotice error={templates.error} />
      {templates.data?.length === 0 && <EmptyState icon="layers" title="No templates yet" />}
      {some && <SearchField typed={paged.typed} onChange={paged.setTyped} placeholder="Template name, kind or tool" />}
      {some && paged.total === 0 && <NoMatch q={paged.q} noun="template" />}
      {paged.total > 0 && (
        <ul className={styles.grid} aria-label="Templates">
          {paged.shown.map((template) => (
            <TemplateCard key={template.slug} template={template} />
          ))}
        </ul>
      )}
      {some && <Pager page={paged.page} total={paged.total} from={paged.from} to={paged.to} last={paged.last} onPage={paged.setPage} />}
    </>
  );
}
