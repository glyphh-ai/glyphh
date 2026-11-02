// rrotor is shelved (his ruling, 2026-11-02): the panel is Glyphh's account and Ada's, with no Apps section, no
// /glyphh publish or /glyphh link, and no rrotor row in Account; the rrotor, rrotor-programs and publish skills sit
// in shelved/skills, where Claude Code does not load them. Nothing is deleted: GLYPHH_RROTOR=1 in Claude Code's
// environment brings the mod's parts back (and moving the skills back to skills/ brings theirs).
import type { Host } from './host'

export const rrotorShown = async (gh: Host): Promise<boolean> => (await gh.env.rrotor().catch(() => undefined)) === '1'
