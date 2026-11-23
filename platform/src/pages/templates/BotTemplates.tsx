import { Link } from 'react-router';
import { decidesLines, runsOnPills, useBotTemplates, type BotTemplate } from '@/api/botTemplates';
import type { RunsWhere } from '@/api/bots';
import { Cat } from '@/bots/cat/Cat';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { NoMatch, Pager, SearchField, useSearchPaging } from '@/components/SearchPaged';
import { Chip, EmptyState, Icon, LoadingCard } from '@/ui';
import styles from './templates.module.css';

export const botTemplatePath = (slug: string) => `/marketplace/bots/${encodeURIComponent(slug)}`;

const matchesBot = (t: BotTemplate, q: string) =>
  [t.name, t.summary, ...t.apps.map((a) => a.name), ...decidesLines(t.decides), ...t.examples, ...runsOnPills(t.runs_on)].some((s) => s.toLowerCase().includes(q));

/** Where a bot can run, as pills: "Cloud", "rrotor", or both; one that needs a rrotor shows "rrotor" alone. */
export function RunsOnPills({ runsOn }: { runsOn: RunsWhere[] }) {
  return (
    <span className={styles.runsOn} role="group" aria-label="Where it can run">
      {runsOnPills(runsOn).map((where) => (
        <span key={where} className={styles.runPill}>
          {where}
        </span>
      ))}
    </span>
  );
}

/** How many of its example prompts a card has room for; its page has them all. */
const CARD_EXAMPLES = 2;

export function BotCard({ template }: { template: BotTemplate }) {
  const title = `bot-${template.slug}-title`;
  const decides = decidesLines(template.decides);
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
            <RunsOnPills runsOn={template.runs_on} />
          </div>
        </div>
        <p className={styles.summary}>{template.summary}</p>
        <dl className={styles.cardFacts}>
          <div>
            <dt>Needs</dt>
            <dd className={styles.chips}>{template.apps.length === 0 ? 'No apps' : template.apps.map((a) => <Chip key={a.app}>{a.name}</Chip>)}</dd>
          </div>
          {decides.length > 0 && (
            <div>
              <dt>Decides</dt>
              <dd>{decides.join(', ')}</dd>
            </div>
          )}
          {template.examples.length > 0 && (
            <div>
              <dt>Ask it</dt>
              <dd>
                <ul className={styles.examples} aria-label={`Things to ask ${template.name}`}>
                  {template.examples.slice(0, CARD_EXAMPLES).map((e) => (
                    <li key={e}>“{e}”</li>
                  ))}
                </ul>
              </dd>
            </div>
          )}
        </dl>
        <div className={styles.cardFoot}>
          <span />
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
      {some && <SearchField typed={paged.typed} onChange={paged.setTyped} placeholder="Bot name, job or app" />}
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
