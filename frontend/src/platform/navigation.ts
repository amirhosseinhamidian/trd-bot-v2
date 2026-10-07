import { getPlatformCopy, type PlatformLocale } from '@/platform/i18n';

export type PlatformNavigationGroupKey =
  'root' | 'research' | 'strategyDecision' | 'simulation' | 'data' | 'system';

export type PlatformNavigationItemKey =
  | 'overview'
  | 'datasets'
  | 'experiments'
  | 'walkForward'
  | 'optimizations'
  | 'strategies'
  | 'signals'
  | 'candidates'
  | 'risk'
  | 'portfolios'
  | 'connections'
  | 'monitoring';

export type PlatformNavigationItemDefinition = {
  key: PlatformNavigationItemKey;
  path: '' | `/${string}`;
  enabled: boolean;
};

export type PlatformNavigationGroupDefinition = {
  key: PlatformNavigationGroupKey;
  items: readonly PlatformNavigationItemDefinition[];
};

export type PlatformNavigationItem = PlatformNavigationItemDefinition & {
  href: string;
  label: string;
};

export type PlatformNavigationGroup = {
  key: PlatformNavigationGroupKey;
  label: string;
  items: PlatformNavigationItem[];
};

export type MobilePlatformNavigationKey = 'overview' | 'research' | 'strategyDecision' | 'more';

export type MobilePlatformNavigationEntry = {
  key: MobilePlatformNavigationKey;
  label: string;
  href?: string;
  items: PlatformNavigationItem[];
};

export const PLATFORM_NAVIGATION_GROUPS = [
  {
    key: 'root',
    items: [{ key: 'overview', path: '', enabled: true }],
  },
  {
    key: 'research',
    items: [
      { key: 'datasets', path: '/datasets', enabled: true },
      { key: 'experiments', path: '/experiments', enabled: true },
      { key: 'walkForward', path: '/walk-forward', enabled: true },
      { key: 'optimizations', path: '/optimizations', enabled: true },
    ],
  },
  {
    key: 'strategyDecision',
    items: [
      { key: 'strategies', path: '/strategies', enabled: true },
      { key: 'signals', path: '/signals', enabled: true },
      { key: 'candidates', path: '/candidates', enabled: true },
      { key: 'risk', path: '/risk', enabled: true },
    ],
  },
  {
    key: 'simulation',
    items: [{ key: 'portfolios', path: '/portfolios', enabled: true }],
  },
  {
    key: 'data',
    items: [{ key: 'connections', path: '/connections', enabled: true }],
  },
  {
    key: 'system',
    items: [{ key: 'monitoring', path: '/monitoring', enabled: true }],
  },
] as const satisfies readonly PlatformNavigationGroupDefinition[];

export function getPlatformNavigation(locale: PlatformLocale): PlatformNavigationGroup[] {
  const copy = getPlatformCopy(locale);

  return PLATFORM_NAVIGATION_GROUPS.map((group) => ({
    key: group.key,
    label: copy.navigation.groups[group.key],
    items: group.items.map((item) => ({
      ...item,
      href: `/${locale}${item.path}`,
      label: copy.navigation.items[item.key],
    })),
  }));
}

export function getMobilePlatformNavigation(
  locale: PlatformLocale,
): MobilePlatformNavigationEntry[] {
  const copy = getPlatformCopy(locale);
  const groups = getPlatformNavigation(locale);
  const groupsByKey = new Map(groups.map((group) => [group.key, group]));

  function getGroup(key: PlatformNavigationGroupKey): PlatformNavigationGroup {
    const group = groupsByKey.get(key);

    if (!group) {
      throw new Error(`Missing platform navigation group: ${key}`);
    }

    return group;
  }

  const root = getGroup('root');
  const research = getGroup('research');
  const strategyDecision = getGroup('strategyDecision');
  const simulation = getGroup('simulation');
  const data = getGroup('data');
  const system = getGroup('system');
  const overview = root.items[0];
  const risk = strategyDecision.items.find((item) => item.key === 'risk');

  if (!overview || !risk) {
    throw new Error('Missing required mobile platform navigation destination');
  }

  return [
    {
      key: 'overview',
      label: root.label,
      href: overview.href,
      items: [overview],
    },
    {
      key: 'research',
      label: research.label,
      items: research.items,
    },
    {
      key: 'strategyDecision',
      label: strategyDecision.label,
      items: strategyDecision.items.filter((item) => item.key !== 'risk'),
    },
    {
      key: 'more',
      label: copy.navigation.mobile.more,
      items: [risk, ...simulation.items, ...data.items, ...system.items],
    },
  ];
}

export function isMobilePlatformNavigationEntryActive(
  entry: MobilePlatformNavigationEntry,
  pathname: string,
): boolean {
  return entry.items.some((item) => isPlatformNavigationItemActive(item, pathname));
}

export function isPlatformNavigationItemActive(
  item: PlatformNavigationItem,
  pathname: string,
): boolean {
  return item.key === 'overview'
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
