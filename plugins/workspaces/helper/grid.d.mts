export type BuilderCell = { content: string; col: number; row: number; colSpan: number; rowSpan: number }
export type Builder = { cols: number; rows: number; cells: BuilderCell[]; selected: number }
export type FileCellShape = { panel: string; col: number; row: number; col_span?: number; row_span?: number; favorite?: string }
export const MAX_GRID: number
export function initCells(cols: number, rows: number): Builder
export function cellAt(cells: BuilderCell[], col: number, row: number): number
export function fromFile(file: { cols: number; rows: number; cells: FileCellShape[] }): Builder
export function resize(b: Builder, cols: number, rows: number): Builder
export function select(b: Builder, index: number): Builder
export function canMergeRight(b: Builder, index: number): boolean
export function canMergeDown(b: Builder, index: number): boolean
export function canSplit(b: Builder, index: number): boolean
export function mergeRight(b: Builder, index: number): Builder
export function mergeDown(b: Builder, index: number): Builder
export function split(b: Builder, index: number): Builder
export function assign(b: Builder, index: number, content: string): Builder
export function fileCells(b: Builder): FileCellShape[]
