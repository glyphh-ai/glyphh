/**
 * The Ada memory as an MCP server (stdio, newline-delimited JSON-RPC
 * 2.0), in Node — a port of plugin/mcp/server.py with the same tools,
 * schemas and outputs, on the same store ($GLYPHH_HOME/ada, else
 * ~/.glyphh/ada). The spaces load once and refresh() before every read,
 * so rows other sessions (or the Python server) wrote always count.
 * Situations may nest, and every read takes a weights tree; `facts`
 * returns the weighted read as fact trees.
 */
import { Space, type Situation, type Weights } from "../../kernel.js";
export declare function memoryDir(): string;
/** wins + vetoes, opened lazily so the server starts even if the store
 *  can't open — the error then surfaces on the first tool call. */
export declare class Memory {
    readonly path: string;
    private spacesCache;
    constructor(path: string);
    spaces(): {
        wins: Space;
        vetoes: Space;
    };
    query(situation: Situation, weights?: Weights | null): Record<string, unknown>;
    facts(situation: Situation, weights: Weights | null, top: number): Record<string, unknown>;
    calibrate(weights: Weights | null): Record<string, unknown>;
    record(store: "wins" | "vetoes", situation: Situation, outcome: string, author: string): Record<string, unknown>;
    check(situation: Situation, outcome: string): Record<string, unknown>;
    status(): Record<string, unknown>;
}
export declare const TOOLS: ({
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            situation: {
                type: string;
                description: string;
                minProperties: number;
            };
            weights: {
                type: string;
                description: string;
            };
            top?: undefined;
            outcome?: undefined;
            author?: undefined;
        };
        required: string[];
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            situation: {
                type: string;
                description: string;
                minProperties: number;
            };
            weights: {
                type: string;
                description: string;
            };
            top: {
                type: string;
                minimum: number;
                maximum: number;
                description: string;
            };
            outcome?: undefined;
            author?: undefined;
        };
        required: string[];
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            weights: {
                type: string;
                description: string;
            };
            situation?: undefined;
            top?: undefined;
            outcome?: undefined;
            author?: undefined;
        };
        required?: undefined;
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            situation: {
                type: string;
                description: string;
                minProperties: number;
            };
            outcome: {
                type: string;
                description: string;
            };
            author: {
                type: string;
                description: string;
            };
            weights?: undefined;
            top?: undefined;
        };
        required: string[];
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            situation: {
                type: string;
                description: string;
                minProperties: number;
            };
            outcome: {
                type: string;
                description: string;
            };
            weights?: undefined;
            top?: undefined;
            author?: undefined;
        };
        required: string[];
    };
} | {
    name: string;
    description: string;
    inputSchema: {
        type: string;
        properties: {
            situation?: undefined;
            weights?: undefined;
            top?: undefined;
            outcome?: undefined;
            author?: undefined;
        };
        required?: undefined;
    };
})[];
/** One JSON-RPC message in, one response out (null for notifications). */
export declare function handle(memory: Memory, msg: Record<string, unknown>): Record<string, unknown> | null;
