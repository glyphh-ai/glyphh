export type PopupAction = { action: 'same'; url: string } | { action: 'swallow' } | { action: 'own' } | { action: 'deny' }
export function isWebUrl(url: string): boolean
export function nativeToWebUrl(nativeUrl: string, parentUrl: string): string | null
export function popupDecision(input: { url: string; keepInPanel: boolean; parentUrl: string }): PopupAction
export function nativeDecision(input: { url: string; keepInPanel: boolean; parentUrl: string }):
  | { action: 'same'; url: string }
  | { action: 'system'; url: string }
  | { action: 'ignore' }
  | null
export const NATIVE_BINDING: string
export const NATIVE_LINK_SCRIPT: string
export function cleanUserAgent(ua: string): string
export function userAgentMetadata(ua: string, options?: { arm?: boolean }): {
  brands: { brand: string; version: string }[]
  fullVersionList: { brand: string; version: string }[]
  fullVersion: string
  platform: string
  platformVersion: string
  architecture: string
  model: string
  mobile: boolean
  bitness: string
}
