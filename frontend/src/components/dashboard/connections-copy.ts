import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type { MarketDataConnectionHealth, MarketDataConnectionState } from '@/lib/api/types';

export type ConnectionsCopy = {
  eyebrow: string;
  title: string;
  description: string;
  readOnlyNotice: string;
  providersTitle: string;
  providersDescription: string;
  noCredentials: string;
  marketTypes: string;
  timeframes: string;
  createTitle: string;
  createDescription: string;
  provider: string;
  displayName: string;
  displayNamePlaceholder: string;
  create: string;
  creating: string;
  connectionsTitle: string;
  connectionsDescription: string;
  total: string;
  state: string;
  health: string;
  lastTested: string;
  neverTested: string;
  lastError: string;
  test: string;
  testing: string;
  enable: string;
  enabling: string;
  disable: string;
  disabling: string;
  loading: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  previous: string;
  next: string;
  page: string;
  createdMessage: string;
  testedMessage: string;
  enabledMessage: string;
  disabledMessage: string;
  states: Record<MarketDataConnectionState, string>;
  healthStatuses: Record<MarketDataConnectionHealth, string>;
};

const copies: Record<DashboardLocale, ConnectionsCopy> = {
  fa: {
    eyebrow: 'Read-only market data',
    title: 'اتصال‌های داده بازار',
    description:
      'منابع عمومی داده تاریخی را برای پژوهش، بک‌تست و ساخت Dataset مدیریت و وضعیت سلامت آن‌ها را بررسی کنید.',
    readOnlyNotice:
      'این بخش فقط برای دریافت داده عمومی است؛ هیچ دسترسی به حساب صرافی یا اجرای معامله واقعی ندارد.',
    providersTitle: 'Providerهای در دسترس',
    providersDescription: 'منابعی که Backend به‌صورت صریح برای داده بازار پشتیبانی می‌کند.',
    noCredentials: 'بدون نیاز به credential',
    marketTypes: 'نوع بازار',
    timeframes: 'تایم‌فریم‌ها',
    createTitle: 'افزودن اتصال',
    createDescription: 'اتصال جدید ابتدا غیرفعال و تست‌نشده ساخته می‌شود.',
    provider: 'Provider',
    displayName: 'نام اتصال',
    displayNamePlaceholder: 'مثلاً Binance historical data',
    create: 'افزودن اتصال',
    creating: 'در حال افزودن',
    connectionsTitle: 'اتصال‌های پیکربندی‌شده',
    connectionsDescription: 'آخرین وضعیت مدیریتی و Health Check هر اتصال',
    total: 'مجموع',
    state: 'وضعیت',
    health: 'سلامت',
    lastTested: 'آخرین تست',
    neverTested: 'هنوز تست نشده',
    lastError: 'آخرین خطا',
    test: 'تست اتصال',
    testing: 'در حال تست',
    enable: 'فعال‌سازی',
    enabling: 'در حال فعال‌سازی',
    disable: 'غیرفعال‌سازی',
    disabling: 'در حال غیرفعال‌سازی',
    loading: 'در حال دریافت اتصال‌ها',
    emptyTitle: 'هنوز اتصالی ساخته نشده است',
    emptyDescription: 'یک Provider عمومی انتخاب کنید و اتصال read-only بسازید.',
    errorTitle: 'دریافت یا به‌روزرسانی اتصال ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
    createdMessage: 'اتصال ساخته شد و پیش از فعال‌سازی باید تست شود.',
    testedMessage: 'Health Check اتصال به‌روزرسانی شد.',
    enabledMessage: 'اتصال فعال شد.',
    disabledMessage: 'اتصال غیرفعال شد.',
    states: {
      disabled: 'غیرفعال',
      enabled: 'فعال',
    },
    healthStatuses: {
      untested: 'تست‌نشده',
      healthy: 'سالم',
      unhealthy: 'ناسالم',
    },
  },
  en: {
    eyebrow: 'Read-only market data',
    title: 'Market data connections',
    description:
      'Manage public historical-data sources for research, backtesting, and dataset creation, and review their latest health state.',
    readOnlyNotice:
      'This area only retrieves public market data. It has no exchange-account access or live trade execution capability.',
    providersTitle: 'Available providers',
    providersDescription: 'Sources explicitly supported by the backend for market-data retrieval.',
    noCredentials: 'No credentials required',
    marketTypes: 'Market types',
    timeframes: 'Timeframes',
    createTitle: 'Add connection',
    createDescription: 'A new connection starts disabled and untested.',
    provider: 'Provider',
    displayName: 'Connection name',
    displayNamePlaceholder: 'For example, Binance historical data',
    create: 'Add connection',
    creating: 'Adding connection',
    connectionsTitle: 'Configured connections',
    connectionsDescription: 'Latest administrative and health-check state for each connection',
    total: 'Total',
    state: 'State',
    health: 'Health',
    lastTested: 'Last tested',
    neverTested: 'Not tested yet',
    lastError: 'Last error',
    test: 'Test connection',
    testing: 'Testing connection',
    enable: 'Enable',
    enabling: 'Enabling',
    disable: 'Disable',
    disabling: 'Disabling',
    loading: 'Loading connections',
    emptyTitle: 'No connections configured yet',
    emptyDescription: 'Choose a public provider and create a read-only connection.',
    errorTitle: 'Unable to load or update connections',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    createdMessage: 'Connection created. Test it before enabling it.',
    testedMessage: 'Connection health check updated.',
    enabledMessage: 'Connection enabled.',
    disabledMessage: 'Connection disabled.',
    states: {
      disabled: 'Disabled',
      enabled: 'Enabled',
    },
    healthStatuses: {
      untested: 'Untested',
      healthy: 'Healthy',
      unhealthy: 'Unhealthy',
    },
  },
};

export function getConnectionsCopy(locale: DashboardLocale): ConnectionsCopy {
  return copies[locale];
}
