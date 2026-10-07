import { describe, expect, it } from 'vitest';

import { getPlatformCopy } from '@/platform/i18n';
import {
  getMobilePlatformNavigation,
  getPlatformNavigation,
  isMobilePlatformNavigationEntryActive,
  isPlatformNavigationItemActive,
  PLATFORM_NAVIGATION_GROUPS,
} from '@/platform/navigation';

describe('platform navigation contract', () => {
  it('captures the frozen grouped information architecture', () => {
    expect(
      PLATFORM_NAVIGATION_GROUPS.map((group) => ({
        key: group.key,
        items: group.items.map((item) => item.key),
      })),
    ).toEqual([
      { key: 'root', items: ['overview'] },
      {
        key: 'research',
        items: ['datasets', 'experiments', 'walkForward', 'optimizations'],
      },
      {
        key: 'strategyDecision',
        items: ['strategies', 'signals', 'candidates', 'risk'],
      },
      { key: 'simulation', items: ['portfolios'] },
      { key: 'data', items: ['connections'] },
      { key: 'system', items: ['monitoring'] },
    ]);
  });

  it('builds every preserved destination for both locales', () => {
    const englishHrefs = getPlatformNavigation('en').flatMap((group) =>
      group.items.map((item) => item.href),
    );
    const persianHrefs = getPlatformNavigation('fa').flatMap((group) =>
      group.items.map((item) => item.href),
    );

    expect(englishHrefs).toEqual([
      '/en',
      '/en/datasets',
      '/en/experiments',
      '/en/walk-forward',
      '/en/optimizations',
      '/en/strategies',
      '/en/signals',
      '/en/candidates',
      '/en/risk',
      '/en/portfolios',
      '/en/connections',
      '/en/monitoring',
    ]);
    expect(persianHrefs).toEqual(englishHrefs.map((href) => href.replace('/en', '/fa')));
  });

  it('builds the frozen compact mobile navigation without losing destinations', () => {
    const mobileNavigation = getMobilePlatformNavigation('en');

    expect(
      mobileNavigation.map((entry) => ({
        key: entry.key,
        label: entry.label,
        href: entry.href,
        items: entry.items.map((item) => item.key),
      })),
    ).toEqual([
      {
        key: 'overview',
        label: 'Overview',
        href: '/en',
        items: ['overview'],
      },
      {
        key: 'research',
        label: 'Research',
        href: undefined,
        items: ['datasets', 'experiments', 'walkForward', 'optimizations'],
      },
      {
        key: 'strategyDecision',
        label: 'Strategy & Decision',
        href: undefined,
        items: ['strategies', 'signals', 'candidates'],
      },
      {
        key: 'more',
        label: 'More',
        href: undefined,
        items: ['risk', 'portfolios', 'connections', 'monitoring'],
      },
    ]);

    const allMobileDestinations = new Set(
      mobileNavigation.flatMap((entry) => entry.items.map((item) => item.href)),
    );

    expect(allMobileDestinations).toEqual(
      new Set(getPlatformNavigation('en').flatMap((group) => group.items.map((item) => item.href))),
    );
    expect(isMobilePlatformNavigationEntryActive(mobileNavigation[3], '/en/risk')).toBe(true);
    expect(isMobilePlatformNavigationEntryActive(mobileNavigation[2], '/en/risk')).toBe(false);
  });

  it('localizes group labels and keeps shell terminology outside dashboard copy', () => {
    const english = getPlatformCopy('en');
    const persian = getPlatformCopy('fa');

    expect(english.navigation.groups).toEqual({
      root: 'Overview',
      research: 'Research',
      strategyDecision: 'Strategy & Decision',
      simulation: 'Simulation',
      data: 'Data',
      system: 'System',
    });
    expect(persian.navigation.groups).toEqual({
      root: 'نمای کلی',
      research: 'پژوهش',
      strategyDecision: 'استراتژی و تصمیم‌گیری',
      simulation: 'شبیه‌سازی',
      data: 'داده',
      system: 'سامانه',
    });
    expect(english.brand.platformName).toBe('Nexora');
    expect(english.brand.productName).toBe('TRD BOT');
    expect(english.navigation.items).toEqual({
      overview: 'Overview',
      datasets: 'Datasets',
      experiments: 'Experiments',
      walkForward: 'Walk-forward',
      optimizations: 'Optimizations',
      strategies: 'Strategies',
      signals: 'Signals',
      candidates: 'Candidates',
      risk: 'Risk',
      portfolios: 'Historical Portfolios',
      connections: 'Connections',
      monitoring: 'Monitoring',
    });
    expect(persian.navigation.items.risk).toBe('ریسک');
    expect(persian.navigation.items.monitoring).toBe('پایش سامانه');
    expect(english.navigation.mobile).toEqual({
      label: 'Mobile navigation',
      more: 'More',
      closeMenu: 'Close menu',
    });
    expect(persian.navigation.mobile.more).toBe('بیشتر');
    expect(persian.header.navigation).toBe('ناوبری پلتفرم');
  });

  it('uses exact matching for overview and nested matching for sections', () => {
    const items = getPlatformNavigation('en').flatMap((group) => group.items);
    const overview = items.find((item) => item.key === 'overview');
    const datasetItem = items.find((item) => item.key === 'datasets');

    expect(overview).toBeDefined();
    expect(datasetItem).toBeDefined();
    expect(isPlatformNavigationItemActive(overview!, '/en')).toBe(true);
    expect(isPlatformNavigationItemActive(overview!, '/en/datasets')).toBe(false);
    expect(isPlatformNavigationItemActive(datasetItem!, '/en/datasets/data-1')).toBe(true);
    expect(isPlatformNavigationItemActive(datasetItem!, '/en/experiments')).toBe(false);
  });
});
