import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from 'react';
import { cx } from '@/lib/cx';
import { Icon, type IconName } from '../Icon/Icon';
import styles from './Menu.module.css';

type Placement = 'top-start' | 'bottom-end' | 'bottom-start';
const placementClass: Record<Placement, string | undefined> = {
  'top-start': styles.topStart,
  'bottom-end': styles.bottomEnd,
  'bottom-start': styles.bottomStart,
};

/**
 * The open menu: how to close it, and which of its submenus is open. A submenu stays open until another
 * item of the same menu is hovered or chosen, or the menu closes, as desktop menus behave.
 */
type MenuContextValue = {
  close: () => void;
  openSub: string | null;
  setOpenSub: (id: string | null) => void;
};
const MenuContext = createContext<MenuContextValue | null>(null);

type MenuProps = {
  /** Renders the button that opens the menu. */
  trigger: (props: { open: boolean; toggle: () => void; id: string }) => ReactNode;
  placement?: Placement;
  label: string;
  children: ReactNode;
};

export function Menu({ trigger, placement = 'bottom-end', label, children }: MenuProps) {
  const [open, setOpen] = useState(false);
  const [openSub, setOpenSub] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const id = useId();

  const close = useCallback(() => {
    setOpen(false);
    setOpenSub(null);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) close();
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    root.current?.querySelector<HTMLElement>('[role^="menuitem"]')?.focus();
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, close]);

  const context = useMemo(() => ({ close, openSub, setOpenSub }), [close, openSub]);

  return (
    <div className={styles.root} ref={root}>
      {trigger({ open, toggle: () => (open ? close() : setOpen(true)), id })}
      {open && (
        <MenuContext.Provider value={context}>
          <div role="menu" id={id} aria-label={label} className={cx(styles.popover, placementClass[placement])} onKeyDown={moveFocus}>
            {children}
          </div>
        </MenuContext.Provider>
      )}
    </div>
  );
}

type MenuItemProps = {
  icon?: IconName;
  onSelect: () => void;
  children: ReactNode;
};

/** Hovering an item of the top menu closes any submenu that is open beside it. */
function useLeaveSubmenu(inSubmenu: boolean) {
  const menu = useContext(MenuContext);
  return () => {
    if (!inSubmenu) menu?.setOpenSub(null);
  };
}

const SubmenuContext = createContext(false);

export function MenuItem({ icon, onSelect, children }: MenuItemProps) {
  const menu = useContext(MenuContext);
  const leave = useLeaveSubmenu(useContext(SubmenuContext));
  return (
    <button
      type="button"
      role="menuitem"
      className={styles.item}
      onMouseEnter={leave}
      onClick={() => {
        onSelect();
        menu?.close();
      }}
    >
      {icon && <Icon name={icon} />}
      <span className={styles.text}>{children}</span>
    </button>
  );
}

type MenuRadioItemProps = MenuItemProps & { checked: boolean };

export function MenuRadioItem({ icon, onSelect, checked, children }: MenuRadioItemProps) {
  const menu = useContext(MenuContext);
  const leave = useLeaveSubmenu(useContext(SubmenuContext));
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={checked}
      className={cx(styles.item, checked && styles.checked)}
      onMouseEnter={leave}
      onClick={() => {
        onSelect();
        menu?.close();
      }}
    >
      {icon && <Icon name={icon} />}
      <span className={styles.text}>{children}</span>
      {checked && <Icon name="check" className={styles.tick} />}
    </button>
  );
}

type MenuSubmenuProps = { icon?: IconName; label: string; children: ReactNode };

/** An item that opens a second menu beside it, on hover, click or the right arrow. */
export function MenuSubmenu({ icon, label, children }: MenuSubmenuProps) {
  const menu = useContext(MenuContext);
  const id = useId();
  const open = menu?.openSub === id;
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [fromKeyboard, setFromKeyboard] = useState(false);

  useEffect(() => {
    if (open && fromKeyboard) panel.current?.querySelector<HTMLElement>('[role^="menuitem"]')?.focus();
  }, [open, fromKeyboard]);

  const show = (keyboard: boolean) => {
    setFromKeyboard(keyboard);
    menu?.setOpenSub(id);
  };

  return (
    <div className={styles.sub}>
      <button
        ref={trigger}
        type="button"
        role="menuitem"
        aria-haspopup="menu"
        aria-expanded={open}
        className={cx(styles.item, open && styles.active)}
        onMouseEnter={() => show(false)}
        onClick={() => show(false)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowRight' || event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            show(true);
          }
        }}
      >
        {icon && <Icon name={icon} />}
        <span className={styles.text}>{label}</span>
        <Icon name="chevronRight" size={14} />
      </button>
      {open && (
        <SubmenuContext.Provider value>
          <div
            role="menu"
            aria-label={label}
            ref={panel}
            className={cx(styles.popover, styles.subPanel)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowLeft') {
                event.stopPropagation();
                menu?.setOpenSub(null);
                trigger.current?.focus();
              }
            }}
          >
            {children}
          </div>
        </SubmenuContext.Provider>
      )}
    </div>
  );
}

export function MenuSeparator() {
  return <div role="separator" className={styles.separator} />;
}

export function MenuLabel({ children }: { children: ReactNode }) {
  return <div className={styles.label}>{children}</div>;
}

/** Up and down move between the items of the menu that has focus. */
function moveFocus(event: ReactKeyboardEvent<HTMLDivElement>) {
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
  // The handler sits on a menu, so the key always came from inside one.
  const menu = (event.target as HTMLElement).closest('[role="menu"]')!;
  const items = Array.from(menu.querySelectorAll<HTMLElement>(':scope > [role^="menuitem"], :scope > div > [role^="menuitem"]'));
  const index = items.indexOf(document.activeElement as HTMLElement);
  const next = event.key === 'ArrowDown' ? index + 1 : index - 1;
  items[(next + items.length) % items.length]?.focus();
  event.preventDefault();
  event.stopPropagation();
}
