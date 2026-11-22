import { Link } from 'react-router';
import { Card, CodeBlock, CopyField } from '@/ui';
import { keyEnv } from '@/pages/settings/licence/licence';
import styles from './RuntimesPage.module.css';

/** The glyphh repo's Docker Compose files and their guide. */
export const composeGuideUrl = 'https://github.com/glyphh-ai/glyphh/tree/main/deploy/compose';
const localComposeFile = 'https://raw.githubusercontent.com/glyphh-ai/glyphh/main/deploy/compose/docker-compose.local.yml';

/**
 * rrotor on this computer by hand, as `docker-compose.local.yml` says at its top: fetch it, make a local token (rrotor
 * holds only its SHA-256), start it on 127.0.0.1:7777 and add it to Claude Code. No `#` lines, so it pastes into zsh.
 */
export const localCompose = [
  `curl -fsSLO ${localComposeFile}`,
  'mkdir -p ~/.glyphh/rrotor && (umask 077; openssl rand -hex 32 > ~/.glyphh/rrotor/token)',
  `export RROTOR_LOCAL_TOKEN_SHA256="$(tr -d ' \\n' < ~/.glyphh/rrotor/token | shasum -a 256 | cut -d' ' -f1)"`,
  'docker compose -f docker-compose.local.yml up -d',
  'claude mcp add --transport http --scope user rrotor http://127.0.0.1:7777/mcp \\',
  '  --header "Authorization: Bearer $(cat ~/.glyphh/rrotor/token)"',
].join('\n');

/**
 * Installing rrotor, the runtime for a person's programs and CLIs, on their own computer: from Claude with the glyphh
 * plugin's rrotor skill, or by hand with Docker Compose. Glyphh hosts none; it only grants the licence.
 */
export function InstallRrotor() {
  return (
    <Card aria-labelledby="install-rrotor">
      <h2 id="install-rrotor" className={styles.cardTitle}>
        Install rrotor
      </h2>
      <p className={styles.text}>
        rrotor hosts your programs and CLIs in one container on your own computer, its API on 127.0.0.1:7777 only. Nothing of a run goes through
        Glyphh.
      </p>
      <div className={styles.ways}>
        <div className={styles.way}>
          <h3 className={styles.wayTitle}>From Claude Code</h3>
          <p className={styles.text}>Add the glyphh plugin, then ask Claude to “install rrotor”. The plugin pulls the image, makes a local token and connects Claude Code.</p>
          <CopyField value="/plugin marketplace add glyphh-ai/glyphh" label="marketplace command" />
          <CopyField value="/plugin install glyphh@glyphh" label="plugin command" />
        </div>
        <div className={styles.way}>
          <h3 className={styles.wayTitle}>With Docker Compose</h3>
          <p className={styles.text}>
            The same container by hand, in a terminal with Docker running. See the <a href={composeGuideUrl}>Docker Compose guide</a> for a server
            with HTTPS, air-gapped nodes and clusters.
          </p>
          <CodeBlock code={localCompose} label="Docker Compose commands" />
        </div>
      </div>
      <p className={styles.meta}>
        Your licence key reaches rrotor on its own when it links to Glyphh. A node with no way out reads it from{' '}
        <code className={styles.code}>{keyEnv}</code>: copy it from <Link to="/licence">Licence</Link>. With no key, rrotor runs as Community.
      </p>
    </Card>
  );
}
