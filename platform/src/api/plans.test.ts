import { onFree, plans } from '@/test/fixtures';
import { feature } from './plans';
import type { Plan } from './types';

describe('a plan’s features', () => {
  it('reads a boolean with the plan’s built map beside it', () => {
    expect(feature(onFree.plans[2]!, 'sso')).toEqual({ included: false, built: true });
    expect(feature(onFree.plans[4]!, 'sso')).toEqual({ included: true, built: true });
  });

  it('includes roles and audit logs where sso is, built only when the server says so', () => {
    const enterprise = onFree.plans[4]!;
    expect(feature(enterprise, 'rbac')).toEqual({ included: true, built: false });
    expect(feature(enterprise, 'audit')).toEqual({ included: true, built: false });
    expect(feature(plans[4]!, 'audit')).toEqual({ included: true, built: true }); // named in its built map
    expect(feature({ ...enterprise, built: { ...enterprise.built, audit: true } }, 'audit')).toEqual({ included: true, built: true });
    expect(feature({ ...enterprise, features: { ...enterprise.features, rbac: true }, built: { ...enterprise.built, rbac: true } }, 'rbac')).toEqual({ included: true, built: true });
  });

  it('reads {included, built} per feature alike', () => {
    const plan: Plan = { ...plans[2]!, features: { sso: { included: true, built: false } } };
    expect(feature(plan, 'sso')).toEqual({ included: true, built: false });
  });

  it('takes sso, roles and audit logs as not built unless the built map says so; any other as built', () => {
    const bare = { ...plans[4]!, built: undefined };
    for (const name of ['sso', 'rbac', 'audit']) expect(feature(bare, name)).toEqual({ included: true, built: false });
    expect(feature(plans[2]!, 'teleport')).toEqual({ included: false, built: true });
  });

  it('reads a plan that states no features at all as having none', () => {
    const plan: Plan = { ...plans[2]!, features: undefined };
    expect(feature(plan, 'sso')).toEqual({ included: false, built: true });
    expect(feature(plan, 'rbac').included).toBe(false);
  });
});
