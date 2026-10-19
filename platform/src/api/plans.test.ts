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

  it('reads {included, built} per feature alike', () => {
    const plan: Plan = { ...plans[1]!, features: { sync: { included: true, built: false }, sso: { included: false, built: false } } };
    expect(feature(plan, 'sync')).toEqual({ included: true, built: false });
    expect(feature(plan, 'sso')).toEqual({ included: false, built: false });
    expect(featureNames(plan)).toEqual(['sync', 'sso']);
  });

  it('takes a feature the server does not mark unbuilt as built, and one it does not name as not included', () => {
    expect(feature(plans[1]!, 'sync')).toEqual({ included: true, built: true });
    expect(feature(plans[1]!, 'teleport')).toEqual({ included: false, built: true });
  });
});
