import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type PortfolioDetailCopy = {
  back: string;
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  loading: string;
  retry: string;
  positionsTitle: string;
  positionsDescription: string;
  positionsEmpty: string;
  positionsError: string;
  timelineTitle: string;
  timelineDescription: string;
  timelineEmpty: string;
  timelineError: string;
  previous: string;
  next: string;
  positionsPage: string;
  timelinePage: string;
  modes: {
    paper: string;
    shadow: string;
  };
  portfolioStatuses: {
    active: string;
    completed: string;
  };
  positionSides: {
    long: string;
    short: string;
  };
  positionStatuses: {
    open: string;
    closed: string;
  };
  timelineEvents: {
    portfolio_created: string;
    position_opened: string;
    position_marked: string;
    position_closed: string;
    portfolio_completed: string;
  };
  fields: {
    portfolioId: string;
    datasetId: string;
    startingCash: string;
    cash: string;
    equity: string;
    feeRate: string;
    feesPaid: string;
    realizedPnl: string;
    unrealizedPnl: string;
    createdAt: string;
    updatedAt: string;
    positionId: string;
    pair: string;
    quantity: string;
    entryPrice: string;
    currentPrice: string;
    exitPrice: string;
    openedAt: string;
    closedAt: string;
    eventNumber: string;
    occurredAt: string;
    eventEquity: string;
    eventPrice: string;
    eventRealizedPnl: string;
  };
};

const copies: Record<DashboardLocale, PortfolioDetailCopy> = {
  fa: {
    back: 'بازگشت به گزارش‌های پرتفوی',
    eyebrow: 'Historical portfolio report',
    title: 'جزئیات پرتفوی تاریخی',
    description:
      'نمای فقط‌خواندنی از وضعیت پرتفوی، موقعیت‌های شبیه‌سازی‌شده و Timeline ثبت‌شده روی داده‌های تاریخی.',
    readOnly: 'فقط‌خواندنی و پژوهشی',
    loading: 'در حال دریافت داده‌ها',
    retry: 'تلاش مجدد',
    positionsTitle: 'موقعیت‌های شبیه‌سازی‌شده',
    positionsDescription: 'رکوردهای باز و بسته‌شده این پرتفوی تاریخی.',
    positionsEmpty: 'هیچ موقعیتی برای این پرتفوی ثبت نشده است.',
    positionsError: 'دریافت موقعیت‌ها ناموفق بود.',
    timelineTitle: 'Timeline پرتفوی',
    timelineDescription: 'رویدادهای ثبت‌شده به ترتیب زمانی برای بازبینی و ممیزی.',
    timelineEmpty: 'هیچ رویدادی برای این پرتفوی ثبت نشده است.',
    timelineError: 'دریافت Timeline ناموفق بود.',
    previous: 'قبلی',
    next: 'بعدی',
    positionsPage: 'صفحه موقعیت‌ها',
    timelinePage: 'صفحه Timeline',
    modes: {
      paper: 'پژوهش Paper',
      shadow: 'پژوهش Shadow',
    },
    portfolioStatuses: {
      active: 'فعال',
      completed: 'تکمیل‌شده',
    },
    positionSides: {
      long: 'Long',
      short: 'Short',
    },
    positionStatuses: {
      open: 'باز',
      closed: 'بسته',
    },
    timelineEvents: {
      portfolio_created: 'ایجاد پرتفوی',
      position_opened: 'باز شدن موقعیت',
      position_marked: 'به‌روزرسانی ارزش موقعیت',
      position_closed: 'بسته شدن موقعیت',
      portfolio_completed: 'تکمیل پرتفوی',
    },
    fields: {
      portfolioId: 'شناسه پرتفوی',
      datasetId: 'شناسه مجموعه‌داده',
      startingCash: 'موجودی آغازین',
      cash: 'موجودی ثبت‌شده',
      equity: 'ارزش ثبت‌شده',
      feeRate: 'نرخ کارمزد',
      feesPaid: 'کارمزد ثبت‌شده',
      realizedPnl: 'سود و زیان تحقق‌یافته',
      unrealizedPnl: 'سود و زیان تحقق‌نیافته',
      createdAt: 'زمان ایجاد',
      updatedAt: 'آخرین به‌روزرسانی',
      positionId: 'شناسه موقعیت',
      pair: 'جفت',
      quantity: 'مقدار',
      entryPrice: 'قیمت ورود',
      currentPrice: 'قیمت ثبت‌شده',
      exitPrice: 'قیمت خروج',
      openedAt: 'زمان باز شدن',
      closedAt: 'زمان بسته شدن',
      eventNumber: 'شماره رویداد',
      occurredAt: 'زمان رویداد',
      eventEquity: 'ارزش پرتفوی',
      eventPrice: 'قیمت',
      eventRealizedPnl: 'سود و زیان تحقق‌یافته',
    },
  },
  en: {
    back: 'Back to portfolio reports',
    eyebrow: 'Historical portfolio report',
    title: 'Historical portfolio detail',
    description:
      'Read-only portfolio state, simulated position records, and the stored historical audit timeline.',
    readOnly: 'Read-only research',
    loading: 'Loading data',
    retry: 'Try again',
    positionsTitle: 'Simulated positions',
    positionsDescription: 'Open and closed position records stored for this historical portfolio.',
    positionsEmpty: 'No positions are recorded for this portfolio.',
    positionsError: 'Unable to retrieve positions.',
    timelineTitle: 'Portfolio timeline',
    timelineDescription: 'Recorded lifecycle events in audit order.',
    timelineEmpty: 'No timeline events are recorded for this portfolio.',
    timelineError: 'Unable to retrieve the timeline.',
    previous: 'Previous',
    next: 'Next',
    positionsPage: 'Positions page',
    timelinePage: 'Timeline page',
    modes: {
      paper: 'Paper research',
      shadow: 'Shadow research',
    },
    portfolioStatuses: {
      active: 'Active',
      completed: 'Completed',
    },
    positionSides: {
      long: 'Long',
      short: 'Short',
    },
    positionStatuses: {
      open: 'Open',
      closed: 'Closed',
    },
    timelineEvents: {
      portfolio_created: 'Portfolio created',
      position_opened: 'Position opened',
      position_marked: 'Position marked',
      position_closed: 'Position closed',
      portfolio_completed: 'Portfolio completed',
    },
    fields: {
      portfolioId: 'Portfolio ID',
      datasetId: 'Dataset ID',
      startingCash: 'Starting balance',
      cash: 'Recorded balance',
      equity: 'Recorded equity',
      feeRate: 'Fee rate',
      feesPaid: 'Recorded fees',
      realizedPnl: 'Realized P&L',
      unrealizedPnl: 'Unrealized P&L',
      createdAt: 'Created at',
      updatedAt: 'Last updated',
      positionId: 'Position ID',
      pair: 'Pair',
      quantity: 'Quantity',
      entryPrice: 'Entry price',
      currentPrice: 'Recorded price',
      exitPrice: 'Exit price',
      openedAt: 'Opened at',
      closedAt: 'Closed at',
      eventNumber: 'Event number',
      occurredAt: 'Occurred at',
      eventEquity: 'Portfolio equity',
      eventPrice: 'Price',
      eventRealizedPnl: 'Realized P&L',
    },
  },
};

export function getPortfolioDetailCopy(locale: DashboardLocale): PortfolioDetailCopy {
  return copies[locale];
}
