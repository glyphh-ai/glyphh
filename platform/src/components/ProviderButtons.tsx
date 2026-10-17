import { Icon, type IconName } from '@/ui';
import styles from './ProviderButtons.module.css';

const providers: Record<string, { label: string; icon: IconName }> = {
  github: { label: 'GitHub', icon: 'github' },
  google: { label: 'Google', icon: 'google' },
};

export function providerLabel(provider: string): string {
  return providers[provider]?.label ?? provider;
}

type ProviderButtonsProps = {
  providers: string[];
  /** Where each provider's button goes: always a full page load, never a fetch. */
  href: (provider: string) => string;
  verb?: string;
  onChoose?: (provider: string) => void;
};

/** One button per sign-in provider, in the server's order. */
export function ProviderButtons({ providers: names, href, verb = 'Continue with', onChoose }: ProviderButtonsProps) {
  return (
    <div className={styles.list}>
      {names.map((name) => (
        <a key={name} className={styles.button} href={href(name)} onClick={() => onChoose?.(name)}>
          {providers[name] && <Icon name={providers[name].icon} size={18} />}
          {verb} {providerLabel(name)}
        </a>
      ))}
    </div>
  );
}
