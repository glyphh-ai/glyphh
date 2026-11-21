import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Card, CopyField, Icon, type IconName } from '@/ui';
import styles from './home.module.css';

export const docsUrl = 'https://docs.glyphh.ai';

function Resource({ icon, name, children }: { icon: IconName; name: string; children: ReactNode }) {
  return (
    <>
      <span className={styles.resourceIcon}>
        <Icon name={icon} size={16} />
      </span>
      <span className={styles.resourceName}>{name}</span>
      {children}
    </>
  );
}

/** Where to go next: the docs, the connector for Claude, the SDK, and the Marketplace. */
export function Resources({ connector }: { connector: string | null }) {
  return (
    <section aria-labelledby="resources">
      <h2 id="resources" className={styles.rowTitle}>
        Resources
      </h2>
      <div className={styles.resources}>
        <Card>
          <a href={docsUrl} className={styles.resource}>
            <Resource icon="external" name="Docs">
              <span className={styles.meta}>Specs, precedents, bots and the API, step by step.</span>
            </Resource>
          </a>
        </Card>
        <Card>
          <div className={styles.resource}>
            <Resource icon="chip" name="Connect Claude">
              <span className={styles.meta}>Add it in Claude as a custom connector. You’ll be asked to allow it once.</span>
              {connector && <CopyField value={connector} label="connector URL" />}
            </Resource>
          </div>
        </Card>
        <Card>
          <div className={styles.resource}>
            <Resource icon="layers" name="SDK and CLI">
              <span className={styles.meta}>Python, for your own code and the shell.</span>
              <CopyField value="pip install glyphh" label="pip command" />
            </Resource>
          </div>
        </Card>
        <Card>
          <Link to="/marketplace" className={styles.resource}>
            <Resource icon="model" name="Marketplace">
              <span className={styles.meta}>Model templates and bots, ready to add to your org.</span>
            </Resource>
          </Link>
        </Card>
      </div>
    </section>
  );
}
