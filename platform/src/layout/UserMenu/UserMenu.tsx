import { useRef } from 'react';
import { useMe } from '@/api/queries';
import { useTheme, type ThemeChoice } from '@/theme/ThemeProvider';
import { Avatar, Icon, Menu, MenuItem, MenuLabel, MenuRadioItem, MenuSeparator, MenuSubmenu, type IconName } from '@/ui';
import styles from './UserMenu.module.css';

// High-visibility dark first: it is the default and the main look, the site's own black and white.
const themes: Array<{ choice: ThemeChoice; label: string; icon: IconName }> = [
  { choice: 'dark-hc', label: 'High-visibility dark', icon: 'moonFilled' },
  { choice: 'dark', label: 'Dark mode', icon: 'moon' },
  { choice: 'light', label: 'Light mode', icon: 'sun' },
  { choice: 'light-hc', label: 'Light high contrast', icon: 'sunFilled' },
  { choice: 'system', label: 'System preference', icon: 'monitor' },
];

/** The person at the bottom of the sidebar: who they are, the theme and log out. */
export function UserMenu() {
  const { data: me } = useMe();
  const { choice, setChoice } = useTheme();
  const logOut = useRef<HTMLFormElement>(null);
  const name = me?.name ?? me?.email ?? '';

  return (
    <>
      <Menu
        label="Account"
        placement="top-start"
        trigger={({ open, toggle, id }) => (
          <button type="button" className={styles.trigger} onClick={toggle} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined}>
            <Avatar name={name} />
            <span className={styles.name}>{name}</span>
            <Icon name="user" className={styles.icon} />
          </button>
        )}
      >
        {me && <MenuLabel>{me.email}</MenuLabel>}
        {me && <MenuSeparator />}
        <MenuSubmenu icon="sun" label="Theme">
          {themes.map((theme) => (
            <MenuRadioItem key={theme.choice} icon={theme.icon} checked={choice === theme.choice} onSelect={() => setChoice(theme.choice)}>
              {theme.label}
            </MenuRadioItem>
          ))}
        </MenuSubmenu>
        <MenuSeparator />
        <MenuItem icon="logOut" onSelect={() => logOut.current?.submit()}>
          Log out
        </MenuItem>
      </Menu>
      <form ref={logOut} method="post" action="/auth/logout" hidden />
    </>
  );
}
