/**
 * SessionStart: inject the memory's state into context at boot
 * (Node port of plugin/hooks/session_start.py).
 */
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { cmpCodePoints } from "../../pyjson.js";
import { memoryDir, readInput, rows, writeMarker } from "./common.js";
function main() {
    const data = readInput();
    if (!data)
        return;
    const mem = memoryDir();
    const wins = rows(join(mem, "wins.db"));
    const vetoes = rows(join(mem, "vetoes.db"));
    writeMarker(String(data.session_id ?? "unknown"), {
        start: Date.now() / 1000,
        memory_dir: mem,
        wins: wins.length,
        vetoes: vetoes.length,
        nagged: false,
    });
    const kernel = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "kernel.js");
    const lines = [`ada memory at ${mem} — ${wins.length} wins, ${vetoes.length} vetoes. Kernel: ${kernel}.`];
    // Counter.most_common: by count, ties in first-seen order
    const kinds = new Map();
    for (const [situation] of wins) {
        for (const key of ["task", "kind", "topic"]) {
            // situations may nest; only a plain label names a kind
            const label = situation && Object.hasOwn(situation, key) ? situation[key] : undefined;
            if (typeof label === "string") {
                kinds.set(label, (kinds.get(label) ?? 0) + 1);
                break;
            }
        }
    }
    if (kinds.size) {
        const top = [...kinds.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6)
            .map(([k, n]) => `${k} (${n})`).join(", ");
        lines.push(`Known situation kinds: ${top}.`);
    }
    if (vetoes.length) {
        const vetoed = [...new Set(vetoes.map(([, o]) => o))].sort(cmpCodePoints).slice(0, 6);
        lines.push(`Vetoed approaches: ${vetoed.join(", ")}.`);
    }
    const authors = [...new Set([...wins, ...vetoes].map(([, , a]) => a))].sort(cmpCodePoints);
    if (authors.length > 1)
        lines.push(`Contributors: ${authors.join(", ")}.`);
    lines.push("Query this memory before repeating a kind of decision; record graded outcomes as they land " +
        "(glyphh-think skill has the loop).");
    process.stdout.write(lines.join("\n") + "\n");
}
main();
