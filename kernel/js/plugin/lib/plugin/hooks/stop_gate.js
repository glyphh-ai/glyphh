/**
 * Stop: the LEARN gate (Node port of plugin/hooks/stop_gate.py). Once
 * per session, if the memory exists and nothing was recorded, block the
 * stop and ask for graded outcomes — exactly once.
 */
import { existsSync } from "node:fs";
import { join } from "node:path";
import { count, readInput, readMarker, writeMarker } from "./common.js";
function main() {
    const data = readInput();
    if (!data)
        return 0;
    if (data.stop_hook_active)
        return 0; // never loop on our own block
    const sessionId = String(data.session_id ?? "unknown");
    const marker = readMarker(sessionId);
    if (Object.keys(marker).length === 0 || marker.nagged)
        return 0;
    const mem = String(marker.memory_dir ?? "");
    if (!mem || !existsSync(mem))
        return 0;
    const recorded = count(join(mem, "wins.db")) - Number(marker.wins ?? 0)
        + count(join(mem, "vetoes.db")) - Number(marker.vetoes ?? 0);
    if (recorded > 0)
        return 0; // the loop closed itself this session
    marker.nagged = true;
    writeMarker(sessionId, marker);
    process.stderr.write("ada memory: nothing has been recorded this session. If any decision was graded by its " +
        "outcome (a command worked or failed, a fix held, the user accepted or corrected an approach), record it to " +
        "wins/vetoes now per the glyphh-think skill. If nothing was graded, say so and finish — this reminder fires " +
        "once per session.\n");
    return 2;
}
process.exitCode = main();
