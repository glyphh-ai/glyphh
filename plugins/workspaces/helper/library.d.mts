import type { FileCellShape } from './grid.mjs'
export type LibFile = { name: string; folder: string | null; model?: string | null; effort?: string | null; cols: number; rows: number; col_widths: number[]; row_heights: number[]; cells: FileCellShape[] }
export type LibWorkspace = { slug: string; file: LibFile }
export type LibFavorite = { id: string; name: string; url: string; keep_in_panel?: boolean }
export function slugOf(name: string, fallback?: string): string
export function urlOf(raw: unknown): string | null
export function checkWorkspace(input: unknown, library: { workspaces: LibWorkspace[]; favorites: LibFavorite[]; choices?: { models: string[]; efforts: string[] } }):
  | { file: LibFile; slug: string; replaces: string | null; error?: undefined }
  | { error: string }
export function checkWorkspaceDelete(name: string, workspaces: LibWorkspace[]): { slug: string; error?: undefined } | { error: string }
export function checkFavorite(input: unknown, favorites: LibFavorite[]): { id: string; favorites: LibFavorite[]; error?: undefined } | { error: string }
export function usedBy(id: string, workspaces: LibWorkspace[]): string[]
export function checkFavoriteDelete(id: string, favorites: LibFavorite[], workspaces: LibWorkspace[]): { favorites: LibFavorite[]; error?: undefined } | { error: string }
export function pickedFolder(answer: { code: number | null; stdout: string }): string | null
