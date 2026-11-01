import { Link } from 'react-router';
import { CopyField } from '@/ui';
import styles from './AddRuntime.module.css';

type ConnectProps = {
  title: string;
  /** The connector URL to add in Claude: `https://<host>/mcp`. */
  connector: string;
  note: string;
};

/** The connector URL to add in Claude, then the SDKs (with a runtime key) and the Claude Code plugin. */
export function Connect({ title, connector, note }: ConnectProps) {
  return (
    <div className={styles.part}>
      <h3 className={styles.subTitle}>{title}</h3>
      <CopyField value={connector} label="connector URL" />
      <span className={styles.meta}>{note}</span>
      <div className={styles.grid}>
        <CopyField value="pip install glyphh" label="pip command" />
        <CopyField value="npm i @glyphh-ai/glyphh" label="npm command" />
      </div>
      <span className={styles.meta}>
        Your apps call it with a <Link to="/runtime-keys">runtime key</Link>. In Claude Code, add the Glyphh marketplace, then the Glyphh plugin:
      </span>
      <div className={styles.grid}>
        <CopyField value="/plugin marketplace add glyphh-ai/glyphh" label="marketplace command" />
        <CopyField value="/plugin install glyphh@glyphh" label="plugin command" />
      </div>
    </div>
  );
}
