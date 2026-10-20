import { Link } from 'react-router';
import { CopyField } from '@/ui';
import styles from './AddRuntime.module.css';

type ConnectProps = {
  title: string;
  /** The connector URL to add in Claude; none for a runtime with no public HTTPS host. */
  connector?: string;
  note: string;
  /** Where the SDKs reach a runtime on this computer. */
  runtimeUrl?: string;
};

/** The connector URL to add in Claude (or the SDKs' runtime URL), then the SDKs and the Claude Code plugin. */
export function Connect({ title, connector, note, runtimeUrl }: ConnectProps) {
  return (
    <div className={styles.part}>
      <h3 className={styles.subTitle}>{title}</h3>
      {connector && <CopyField value={connector} label="connector URL" />}
      {runtimeUrl && (
        <>
          <CopyField value={`export GLYPHH_RUNTIME_URL=${runtimeUrl}`} label="runtime URL" />
          <span className={styles.meta}>
            The SDKs read it, with a runtime key from <Link to="/keys">API Keys</Link>.
          </span>
        </>
      )}
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
