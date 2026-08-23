import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type ActivityPeriod = 'all' | '7d' | '30d';

export type ActivityCopy = {
  title: string;
  description: string;
  typeFilter: string;
  periodFilter: string;
  all: string;
  dataset: string;
  experiment: string;
  walkForward: string;
  allTime: string;
  lastSevenDays: string;
  lastThirtyDays: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  previous: string;
  next: string;
  page: string;
  total: string;
  loading: string;
};

const copies: Record<DashboardLocale, ActivityCopy> = {
  fa: {
    title: 'فعالیت‌های اخیر',
    description: 'آخرین داده‌ها و اجرای فرآیندهای پژوهشی',
    typeFilter: 'نوع فعالیت',
    periodFilter: 'بازه زمانی',
    all: 'همه',
    dataset: 'مجموعه‌داده',
    experiment: 'آزمایش',
    walkForward: 'Walk-forward',
    allTime: 'تمام زمان‌ها',
    lastSevenDays: '۷ روز گذشته',
    lastThirtyDays: '۳۰ روز گذشته',
    emptyTitle: 'فعالیتی پیدا نشد',
    emptyDescription: 'در این بازه هیچ فعالیت پژوهشی ثبت نشده است.',
    errorTitle: 'دریافت فعالیت‌ها ناموفق بود',
    errorDescription: 'اتصال به Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه',
    total: 'تعداد کل',
    loading: 'در حال دریافت فعالیت‌ها',
  },
  en: {
    title: 'Recent activity',
    description: 'Latest research data and executions',
    typeFilter: 'Activity type',
    periodFilter: 'Time period',
    all: 'All',
    dataset: 'Dataset',
    experiment: 'Experiment',
    walkForward: 'Walk-forward',
    allTime: 'All time',
    lastSevenDays: 'Last 7 days',
    lastThirtyDays: 'Last 30 days',
    emptyTitle: 'No activity found',
    emptyDescription: 'No research activity was recorded in this period.',
    errorTitle: 'Unable to retrieve activity',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Page',
    total: 'Total',
    loading: 'Loading activity',
  },
};

export function getActivityCopy(locale: DashboardLocale): ActivityCopy {
  return copies[locale];
}
