import type { FeatureState, Plan } from './types';

/** Features that are not built unless the server's `built` map says they are. Offline licences (and any other) are. */
const unbuiltUnlessSaid = new Set(['sync', 'ha', 'sso', 'rbac', 'audit']);

/**
 * Roles and audit logs are included where the server's `sso` flag is, when not named alone; whether they are built
 * is their own (single sign-on is built; they are not until the server says so).
 */
const ridesOn: Record<string, string> = { rbac: 'sso', audit: 'sso' };

/**
 * One of a plan's features, read alike from either shape the server may answer: a boolean with the plan's `built`
 * map beside it, or `{included, built}`. A feature missing from `built` (or with no map at all) is not built when it
 * is one of sync, ha, sso, rbac and audit, so it is never shown as included; any other is.
 */
export function feature(plan: Plan, name: string): FeatureState {
  const value = plan.features[name];
  if (value === undefined && ridesOn[name]) {
    const included = feature(plan, ridesOn[name]).included;
    return { included, built: plan.built?.[name] ?? false };
  }
  if (typeof value === 'object' && value !== null) return { included: value.included, built: value.built };
  return { included: value === true, built: plan.built?.[name] ?? !unbuiltUnlessSaid.has(name) };
}

/** The feature names the plan states, in the server's order. */
export const featureNames = (plan: Plan): string[] => Object.keys(plan.features);
