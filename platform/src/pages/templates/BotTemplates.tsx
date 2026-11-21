import { Link } from 'react-router';
import { useBotTemplates, type BotTemplate } from '@/api/botTemplates';
import { Cat } from '@/bots/cat/Cat';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { NoMatch, Pager, SearchField, useSearchPaging } from '@/components/SearchPaged';
import { plural } from '@/lib/format';
import { Chip, EmptyState, Icon, LoadingCard } from '@/ui';
import styles from './templates.module.css';

export const botTemplatePath = (slug: string) => `/marketplace/bots/${encodeURIComponent(slug)}`;

const matchesBot = (t: BotTemplate, q: string) =>
  [t.name, t.summary, ...t.required_apps.map((a) => a.name), ...t.tools].some((s) => s.toLowerCase().includes(q));

function BotCard({ template }: { template: BotTemplate }) {
  const title = `bot-${template.slug}-title`;
  return (
    <li>
      <Link to={botTemplatePath(template.slug)} className={styles.card} aria-labelledby={title}>
        <div className={styles.cardHead}>
          <span className={styles.mark} aria-hidden="true">
            <Cat look={template.look} size={28} />
          </span>
          <div className={styles.cardTitles}>
            <h2 id={title} className={styles.name}>
              {template.name}
            </h2>
            <div className={styles.chips}>
              <Chip>Bot</Chip>
              {template.required_apps.map((a) => (
                <Chip key={a.slug}>{a.name}</Chip>
              ))}
            </div>
          </div>
        </div>
        <p className={styles.summary}>{template.summary}</p>
        <div className={styles.cardFoot}>
          <span>
            {plural(template.tools.length, 'tool')} · {plural(template.gates.length, 'gate')}
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
 * The Marketplace's Bots: bots Glyphh builds to do one job, searchable and paged; one is added to the org as a copy
 * of its own from its details page (BotTemplatePage).
 */
export function BotTemplates() {
  const templates = useBotTemplates();
  const paged = useSearchPaging(templates.data, matchesBot);
  const some = templates.data !== undefined && templates.data.length > 0;
  return (
    <>
      {templates.isPending && <LoadingCard />}
      <ApiErrorNotice error={templates.error} />
      {templates.data?.length === 0 && <EmptyState icon="user" title="No bots yet" />}
      {some && <SearchField typed={paged.typed} onChange={paged.setTyped} placeholder="Bot name, job, service or tool" />}
      {some && paged.total === 0 && <NoMatch q={paged.q} noun="bot" />}
      {paged.total > 0 && (
        <ul className={styles.grid} aria-label="Bot templates">
          {paged.shown.map((template) => (
            <BotCard key={template.slug} template={template} />
          ))}
        </ul>
      )}
      {some && <Pager page={paged.page} total={paged.total} from={paged.from} to={paged.to} last={paged.last} onPage={paged.setPage} />}
    </>
  );
}
