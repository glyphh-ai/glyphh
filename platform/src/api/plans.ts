import type { FeatureState, Plan } from './types';

/**
 * One of a plan's features, read alike from either shape the server may answer: a boolean with the plan's `built`
 * map beside it, or `{included, built}`. A feature the server does not mark as unbuilt is built.
 */
export function feature(plan: Plan, name: string): FeatureState {
  const value = plan.features[name];
  if (typeof value === 'object' && value !== null) return { included: value.included, built: value.built };
  return { included: value === true, built: plan.built?.[name] ?? true };
}

/** The feature names the plan states, in the server's order. */
export const featureNames = (plan: Plan): string[] => Object.keys(plan.features);
