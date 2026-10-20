import { CopyField } from '@/ui';
import styles from './AddRuntime.module.css';

/** The connector URL to add in Claude, then the SDKs and the Claude Code plugin that reach the runtime. */
export function Connect({ title, connector, note }: { title: string; connector: string; note: string }) {
  return (
    <div className={styles.part}>
      <h3 className={styles.subTitle}>{title}</h3>
      <CopyField value={connector} label="connector URL" />
      <span className={styles.meta}>{note}</span>
      <div className={styles.grid}>
        <CopyField value="pip install glyphh" label="pip command" />
        <CopyField value="npm i @glyphh-ai/glyphh" label="npm command" />
      </div>
      <span className={styles.meta}>In Claude Code, add the Glyphh marketplace, then the Glyphh plugin (Ada is a skill in it):</span>
      <div className={styles.grid}>
        <CopyField value="/plugin marketplace add glyphh-ai/glyphh" label="marketplace command" />
        <CopyField value="/plugin install glyphh@glyphh" label="plugin command" />
      </div>
    </div>
  );
}
