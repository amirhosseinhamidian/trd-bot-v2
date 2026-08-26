import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type PortfolioCopy = {
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  total: string;
  loading: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  previous: string;
  next: string;
  page: string;
  viewDetails: string;
  modes: {
    paper: string;
    shadow: string;
  };
  statuses: {
    active: string;
    completed: string;
  };
  fields: {
    portfolioId: string;
    datasetId: string;
    startingCash: string;
    cash: string;
    equity: string;
    realizedPnl: string;
    unrealizedPnl: string;
    feesPaid: string;
    positions: string;
    timelineEvents: string;
    updatedAt: string;
  };
};

const copies: Record<DashboardLocale, PortfolioCopy> = {
  fa: {
    eyebrow: 'Historical simulation archive',
    title: 'گزارش‌های پرتفوی تاریخی',
    description:
      'خلاصه‌های فقط‌خواندنی ساخته‌شده از مجموعه‌داده‌های تاریخی؛ بدون اتصال حساب یا ارسال سفارش واقعی.',
    readOnly: 'فقط‌خواندنی و پژوهشی',
    total: 'تعداد گزارش‌ها',
    loading: 'در حال دریافت گزارش‌های پرتفوی تاریخی',
    emptyTitle: 'گزارشی ثبت نشده است',
    emptyDescription: 'هنوز هیچ گزارش پرتفوی تاریخی برای نمایش وجود ندارد.',
    errorTitle: 'دریافت گزارش‌ها ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    previous: 'قبلی',
    next: 'بعدی',
    page: 'صفحه گزارش‌های پرتفوی',
    viewDetails: 'مشاهده گزارش',
    modes: {
      paper: 'پژوهش Paper',
      shadow: 'پژوهش Shadow',
    },
    statuses: {
      active: 'رکورد فعال',
      completed: 'تکمیل‌شده',
    },
    fields: {
      portfolioId: 'شناسه گزارش',
      datasetId: 'شناسه مجموعه‌داده',
      startingCash: 'موجودی آغازین',
      cash: 'موجودی ثبت‌شده',
      equity: 'ارزش ثبت‌شده',
      realizedPnl: 'سود و زیان تحقق‌یافته',
      unrealizedPnl: 'سود و زیان تحقق‌نیافته',
      feesPaid: 'کارمزد ثبت‌شده',
      positions: 'رکوردهای موقعیت',
      timelineEvents: 'رویدادهای Timeline',
      updatedAt: 'آخرین به‌روزرسانی',
    },
  },
  en: {
    eyebrow: 'Historical simulation archive',
    title: 'Historical portfolio reports',
    description:
      'Read-only summaries derived from stored historical datasets, with no account connection or live order submission.',
    readOnly: 'Read-only research',
    total: 'Reports',
    loading: 'Loading historical portfolio reports',
    emptyTitle: 'No reports recorded',
    emptyDescription: 'There are no historical portfolio reports to display yet.',
    errorTitle: 'Unable to retrieve reports',
    errorDescription: 'Check the backend connection, then try again.',
    retry: 'Try again',
    previous: 'Previous',
    next: 'Next',
    page: 'Portfolio report page',
    viewDetails: 'View report',
    modes: {
      paper: 'Paper research',
      shadow: 'Shadow research',
    },
    statuses: {
      active: 'Active record',
      completed: 'Completed',
    },
    fields: {
      portfolioId: 'Report ID',
      datasetId: 'Dataset ID',
      startingCash: 'Starting balance',
      cash: 'Recorded balance',
      equity: 'Recorded equity',
      realizedPnl: 'Realized P&L',
      unrealizedPnl: 'Unrealized P&L',
      feesPaid: 'Recorded fees',
      positions: 'Position records',
      timelineEvents: 'Timeline events',
      updatedAt: 'Last updated',
    },
  },
};

export function getPortfolioCopy(locale: DashboardLocale): PortfolioCopy {
  return copies[locale];
}
