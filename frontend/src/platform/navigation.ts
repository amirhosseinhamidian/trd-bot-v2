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

const LEGACY_SHELL_NAVIGATION_ORDER: readonly PlatformNavigationItemKey[] = [
  'overview',
  'experiments',
  'optimizations',
  'strategies',
  'datasets',
  'connections',
  'monitoring',
  'walkForward',
  'portfolios',
  'risk',
  'candidates',
  'signals',
];

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

export function getLegacyShellNavigation(locale: PlatformLocale): PlatformNavigationItem[] {
  const items = getPlatformNavigation(locale).flatMap((group) => group.items);
  const itemsByKey = new Map(items.map((item) => [item.key, item]));

  return LEGACY_SHELL_NAVIGATION_ORDER.map((key) => {
    const item = itemsByKey.get(key);

    if (!item) {
      throw new Error(`Missing platform navigation item: ${key}`);
    }

    return item;
  });
}

export function isPlatformNavigationItemActive(
  item: PlatformNavigationItem,
  pathname: string,
): boolean {
  return item.key === 'overview'
    ? pathname === item.href
    : pathname === item.href || pathname.startsWith(`${item.href}/`);
}
