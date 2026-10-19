import { Chip, Icon } from '@/ui';
import { otelEnv, selfHostingDocs, serverLogsEnv } from './telemetry';
import styles from './Logs.module.css';

/**
 * rrotor's default: it sends Glyphh nothing. Where the data is instead, the way we recommend to see it (your own
 * OpenTelemetry collector) and the opt-in that brings it here, with what that sends.
 */
export function NothingSent({ title }: { title: string }) {
  return (
    <section className={styles.nothing} aria-label={title}>
      <span className={styles.nothingIcon}>
        <Icon name="logs" size={20} />
      </span>
      <h3 className={styles.nothingTitle}>{title}</h3>
      <p className={styles.text}>
        Your runtimes have sent Glyphh nothing. That is how rrotor works by default: its logs, metrics, traces and audit events stay on your rrotor.
      </p>
      <div className={styles.ways}>
        <div className={styles.way}>
          <div className={styles.wayHead}>
            <h4 className={styles.wayTitle}>Stream to your own collector</h4>
            <Chip tone="green">Recommended</Chip>
          </div>
          <p className={styles.text}>
            Set <code className={styles.code}>{otelEnv}</code> on each node to your OpenTelemetry collector. Everything goes there, and nothing to Glyphh.
          </p>
          <a className={styles.docs} href={selfHostingDocs} target="_blank" rel="noreferrer">
            rrotor’s self-hosting docs
            <Icon name="external" size={14} />
          </a>
        </div>
        <div className={styles.way}>
          <h4 className={styles.wayTitle}>Or send them to Glyphh</h4>
          <p className={styles.text}>
            Set <code className={styles.code}>{serverLogsEnv}=on</code> on each node to see them here.
          </p>
          <p className={styles.warning} role="note">
            <Icon name="alert" size={14} />
            <span>
              Your logs, metrics, traces and audit events then leave your rrotor for Glyphh. Inputs, results and client addresses never do.
            </span>
          </p>
        </div>
      </div>
    </section>
  );
}
