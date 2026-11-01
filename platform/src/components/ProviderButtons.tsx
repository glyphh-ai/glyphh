import { useState, type FormEvent } from 'react';
import { SSO } from '@/api/types';
import { Button, Icon, TextField, type IconName } from '@/ui';
import styles from './ProviderButtons.module.css';

const providers: Record<string, { label: string; icon: IconName }> = {
  github: { label: 'GitHub', icon: 'github' },
  google: { label: 'Google', icon: 'google' },
};

export function providerLabel(provider: string): string {
  if (provider === SSO) return 'Single sign-on';
  return providers[provider]?.label ?? provider;
}

type ProviderButtonsProps = {
  providers: string[];
  /** Whether single sign-on is offered too: the person gives their work email, whose domain names their org. */
  sso?: boolean;
  /** Where each provider's button goes: always a full page load, never a fetch. Single sign-on brings the email. */
  href: (provider: string, email?: string) => string;
  verb?: string;
  onChoose?: (provider: string, email?: string) => void;
};

/** One button per sign-in provider, in the server's order, and single sign-on after them when it is offered. */
export function ProviderButtons({ providers: names, sso = false, href, verb = 'Continue with', onChoose }: ProviderButtonsProps) {
  const [asking, setAsking] = useState(false);
  const [email, setEmail] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const given = email.trim();
    if (!given) return;
    onChoose?.(SSO, given);
    window.location.assign(href(SSO, given));
  };

  return (
    <div className={styles.list}>
      {names.map((name) => (
        <a key={name} className={styles.button} href={href(name)} onClick={() => onChoose?.(name)}>
          {providers[name] && <Icon name={providers[name].icon} size={18} />}
          {verb} {providerLabel(name)}
        </a>
      ))}
      {sso && !asking && (
        <button type="button" className={styles.button} onClick={() => setAsking(true)}>
          <Icon name="key" size={18} />
          {verb} single sign-on
        </button>
      )}
      {sso && asking && (
        <form className={styles.sso} onSubmit={submit}>
          <TextField
            label="Work email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@company.com"
            hint="Your organisation’s sign-in is found by your email’s domain."
            autoComplete="email"
            autoFocus
            required
          />
          <Button type="submit" variant="primary" disabled={!email.trim()}>
            {verb} single sign-on
          </Button>
        </form>
      )}
    </div>
  );
}
