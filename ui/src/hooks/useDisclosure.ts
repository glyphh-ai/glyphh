import { useCallback, useState } from "react";

/** Open or closed: a dialog, a menu, a panel. */
export function useDisclosure(initial = false) {
  const [open, setOpen] = useState(initial);
  const show = useCallback(() => setOpen(true), []);
  const hide = useCallback(() => setOpen(false), []);
  const toggle = useCallback(() => setOpen((o) => !o), []);
  return { open, show, hide, toggle };
}
