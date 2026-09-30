/**
 * UserPromptSubmit: inject precedent relevant to the incoming prompt
 * (Node port of plugin/hooks/user_prompt.py — same tokens, tiers,
 * weights, threshold and output, byte for byte).
 *
 * The doorbell of the memory: fast, deterministic, model-free. It rings
 * when the prompt lexically resembles stored experience — situations,
 * outcomes (wins AND vetoes), and user-defined aliases. Matching, most
 * to least certain: exact token, shared prefix/stem, one edit away.
 */
export declare function tokens(text: string): Set<string>;
