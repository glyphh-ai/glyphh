// rrotor's switch (shelved 2026-11-02, back on 2026-11-17). On, the panel has its Apps section, /glyphh publish and
// /glyphh link, and the rrotor row in Account. GLYPHH_RROTOR=0 in Claude Code's environment hides them: the panel is
// then Glyphh's account and Ada's alone (the rrotor, rrotor-programs and publish skills load either way).
import type { Host } from './host'

export const rrotorShown = async (gh: Host): Promise<boolean> => (await gh.env.rrotor().catch(() => undefined)) !== '0'
