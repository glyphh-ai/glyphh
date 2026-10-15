export type Tile = { key: string; kind: 'fav' | 'layout' | 'folder'; name: string; url?: string; fav?: string; folder?: string; cells?: { url?: string; name: string; panel?: string }[] }
export type Folder = { id: string; name: string; keys: string[] }
export type EchoState = { order: string[]; dock: string[]; folders: Folder[] }
export type Card = { id: string; fav: string; solo: boolean; pinned: boolean }
export type Rect = { left: number; top: number; width: number; height: number }
export type GridCell = { id: string; col: number; row: number; colSpan?: number; rowSpan?: number; fav?: string | null; panel?: string; url?: string | null; title?: string | null; keepInPanel?: boolean }
export type Grid = { workspace: string; colWidths: number[]; rowHeights: number[]; cells: GridCell[] }
export type ViewerLayoutLike = { name: string; colWidths: number[]; rowHeights: number[]; cells: { panel: string; col: number; row: number; colSpan?: number; rowSpan?: number; page?: string; url?: string; title?: string; keepInPanel?: boolean }[] }
export type WallState = { workspace: string | null; cards: Card[] }

export const DOCK_ITEMS: readonly { key: string; title: string }[]
export const DEFAULT_DOCK: string[]
export function dockItemFor(key: string): { key: string; title: string } | null
export function tilesFrom(library: { workspaces: { file: { name: string; cells: { panel: string; favorite?: string }[] } }[]; favorites: { id: string; name: string; url: string }[] }): Tile[]
export function wallTilesFor<T>(input: { dockEnabled: boolean; dockItems: T[]; wallItems: T[]; keyOf: (t: T) => string | null }): T[]
export function keepDockKeys(keys: string[], tiles: Tile[]): string[]
export function orderWall(tiles: Tile[], state?: { order?: string[]; folders?: Folder[] }): Tile[]
export function folderTile(folder: Folder, tiles: Tile[]): Tile
export function pagesOf<T>(list: T[], perPage: number): T[][]
export function moveKey(order: string[], key: string, before: string | null): string[]
export function createFolder<S extends EchoState>(state: S, key: string, onto: string, id: string): S
export function addToFolder<S extends EchoState>(state: S, key: string, folderId: string): S
export function removeFromFolder<S extends EchoState>(state: S, key: string, folderId: string): S
export function renameFolder<S extends EchoState>(state: S, folderId: string, name: string): S
export function pruneEcho<S extends EchoState>(state: S, tiles: Tile[]): S
export const GAP: number
export function flowColumns<C extends { solo?: boolean }>(cards: C[]): C[][]
export function syncFractions(cols: unknown[][], fr?: { colFr?: number[]; rowFr?: number[][] }): { colFr: number[]; rowFr: number[][] }
export function flowRects(cards: { id: string; solo?: boolean }[], band: Rect, fr?: { colFr?: number[]; rowFr?: number[][] }): Map<string, Rect>
export function gridRects(grid: Pick<Grid, 'colWidths' | 'rowHeights' | 'cells'>, band: Rect): Map<string, Rect>
export function gridSeams(grid: Pick<Grid, 'colWidths' | 'rowHeights'>, band: Rect): { cols: { index: number; x: number }[]; rows: { index: number; y: number }[] }
export function slideSeam(fractions: number[], index: number, shift: number, min?: number): number[]
export function openFavorite(cards: Card[], fav: string, newId: string): Card[]
export function swapCards(cards: Card[], a: string, b: string): Card[]
export function swapCells(grid: Grid, a: string, b: string): Grid
export function dissolveGrid(grid: Grid, cards: Card[], newId: () => string): Card[]
export function soloCard(cards: Card[], id: string, side: 'left' | 'right'): Card[]
export function pinCard(cards: Card[], id: string): Card[]
export function workspaceGrid(layout: ViewerLayoutLike, cards: Card[]): { grid: Grid; cards: Card[] }
export function serializeWall(state: { grid: Grid | null; cards: Card[] }): { workspace: string | null; cards: { fav: string; solo: boolean; pinned: boolean }[] }
export function parseWall(raw: unknown): WallState
export function parseEcho(raw: unknown): EchoState & { wall: WallState }
export function wallSaver(options: { save: (state: unknown) => void; delay?: number; setTimer?: (fn: () => void, ms: number) => unknown; clearTimer?: (t: unknown) => void }): { restored(): void; schedule(state: unknown): boolean }
export function dockScales(centers: number[], x: number | null, zoom?: number, sigma?: number): number[]
export function dockTucked(input: { autoHide: boolean; cardsUp: boolean }): boolean
export const SWIPE_WHEEL_PX: number
export const SWIPE_COOLDOWN_MS: number
export const WHEEL_GESTURE_GAP_MS: number
export function swipeStep(input: { dx: number; dy: number; threshold: number; sinceLast?: number; cooldown?: number }): -1 | 0 | 1
export type WheelSwipeState = { accX: number; accY: number; lastEventAt: number; lastStepAt: number; armed: boolean }
export function wheelSwipeState(): WheelSwipeState
export function wheelSwipeFeed(s: WheelSwipeState, deltaX: number, deltaY: number, now: number): -1 | 0 | 1
export function searchWall(tiles: Tile[], query: string): { dim: Set<string>; best: Tile | null }
