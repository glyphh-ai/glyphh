import { hostingOff, plans } from '@/test/fixtures';
import { feature, featureNames } from './plans';
import type { Plan } from './types';

describe('a plan’s features', () => {
  it('reads a boolean with the plan’s built map beside it', () => {
    const pro = hostingOff.plans[1]!;
    expect(feature(pro, 'sync')).toEqual({ included: true, built: false });
    expect(feature(pro, 'offline')).toEqual({ included: false, built: true });
    expect(feature(hostingOff.plans[3]!, 'offline')).toEqual({ included: true, built: true });
  });

  it('takes roles and audit logs from sso when the server names neither', () => {
    const enterprise = hostingOff.plans[3]!;
    expect(feature(enterprise, 'rbac')).toEqual({ included: true, built: false });
    expect(feature(enterprise, 'audit')).toEqual({ included: true, built: false });
    expect(feature(plans[3]!, 'audit')).toEqual({ included: true, built: true });
    expect(feature({ ...enterprise, features: { ...enterprise.features, rbac: true }, built: { ...enterprise.built, sso: true } }, 'rbac')).toEqual({ included: true, built: true });
  });

  it('reads {included, built} per feature alike', () => {
    const plan: Plan = { ...plans[1]!, features: { sync: { included: true, built: false }, sso: { included: false, built: false } } };
    expect(feature(plan, 'sync')).toEqual({ included: true, built: false });
    expect(feature(plan, 'sso')).toEqual({ included: false, built: false });
    expect(featureNames(plan)).toEqual(['sync', 'sso']);
  });

  it('takes sync, ha, sso, roles and audit logs as not built unless the built map says so; any other as built', () => {
    const bare = { ...plans[3]!, built: undefined };
    for (const name of ['sync', 'ha', 'sso', 'rbac', 'audit']) expect(feature(bare, name)).toEqual({ included: true, built: false });
    expect(feature(bare, 'offline')).toEqual({ included: true, built: true });
    expect(feature({ ...bare, built: { offline: true } }, 'sync').built).toBe(false);
    expect(feature(plans[1]!, 'sync')).toEqual({ included: true, built: true });
    expect(feature(plans[1]!, 'teleport')).toEqual({ included: false, built: true });
  });
});
