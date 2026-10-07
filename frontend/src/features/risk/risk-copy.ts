import type { CandidateRiskCheckName } from '@/lib/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type RiskCopy = {
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  historicalOnly: string;
  filters: {
    title: string;
    description: string;
    fromTime: string;
    toTime: string;
    portfolio: string;
    allPortfolios: string;
    apply: string;
    applying: string;
    reset: string;
    invalidRange: string;
  };
  decisions: {
    title: string;
    description: string;
    evaluated: string;
    approved: string;
    rejected: string;
    approvalRate: string;
    noRate: string;
  };
  emptyTitle: string;
  emptyDescription: string;
  budget: {
    title: string;
    description: string;
    openedDecisions: string;
    allocated: string;
    consumed: string;
    utilization: string;
    noUtilization: string;
  };
  portfolioRisk: {
    title: string;
    description: string;
    portfolios: string;
    openPositions: string;
    equity: string;
    exposure: string;
    concentration: string;
    drawdown: string;
    largestPair: string;
    asOf: string;
    limit: string;
    withinLimit: string;
    overLimit: string;
    noData: string;
  };
  reasons: {
    title: string;
    description: string;
    reconciled: string;
    labels: Record<CandidateRiskCheckName, string>;
  };
  events: {
    title: string;
    description: string;
    journal: string;
    evaluatedAt: string;
    riskBudget: string;
    riskConsumed: string;
    failedChecks: string;
    viewCandidate: string;
    viewPortfolio: string;
    approved: string;
    rejected: string;
    replay: {
      opened: string;
      risk_rejected: string;
      no_fill: string;
    };
  };
  scope: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
};

const riskCheckLabels: Record<PlatformLocale, Record<CandidateRiskCheckName, string>> = {
  fa: {
    candidate_selectable: 'قابل انتخاب بودن کاندید',
    portfolio_active: 'فعال بودن پرتفوی',
    dataset_match: 'تطابق مجموعه‌داده',
    portfolio_capacity: 'ظرفیت پرتفوی',
    rank_limit: 'سقف رتبه',
    ranking_score: 'حداقل امتیاز رتبه‌بندی',
    reward_risk: 'نسبت پاداش به ریسک',
    simulated_budget: 'بودجه شبیه‌سازی',
  },
  en: {
    candidate_selectable: 'Candidate selectable',
    portfolio_active: 'Portfolio active',
    dataset_match: 'Dataset match',
    portfolio_capacity: 'Portfolio capacity',
    rank_limit: 'Rank limit',
    ranking_score: 'Ranking score floor',
    reward_risk: 'Reward to risk',
    simulated_budget: 'Simulated budget',
  },
};

const copies: Record<PlatformLocale, RiskCopy> = {
  fa: {
    eyebrow: 'Historical risk oversight',
    title: 'داشبورد ریسک پژوهشی',
    description:
      'تصمیم‌های ریسک و وضعیت پرتفوی‌های شبیه‌سازی‌شده را از رویدادهای ذخیره‌شده و قابل ممیزی بررسی کنید.',
    readOnly: 'فقط‌خواندنی',
    historicalOnly: 'بدون اجرای سفارش واقعی',
    filters: {
      title: 'محدوده گزارش',
      description:
        'بازه زمانی روی زمان ارزیابی تصمیم‌ها اعمال می‌شود و هر دو سر بازه را شامل می‌شود.',
      fromTime: 'از زمان',
      toTime: 'تا زمان',
      portfolio: 'پرتفوی شبیه‌سازی‌شده',
      allPortfolios: 'همه پرتفوی‌ها',
      apply: 'اعمال فیلتر',
      applying: 'در حال محاسبه',
      reset: 'پاک کردن فیلترها',
      invalidRange: 'زمان پایان باید برابر یا پس از زمان شروع باشد.',
    },
    decisions: {
      title: 'تصمیم‌های ریسک',
      description: 'فقط کاندیدهایی که واقعاً ارزیابی شده‌اند در مخرج نرخ پذیرش قرار می‌گیرند.',
      evaluated: 'ارزیابی‌شده',
      approved: 'تأییدشده',
      rejected: 'ردشده',
      approvalRate: 'نرخ پذیرش',
      noRate: 'بدون تصمیم قابل محاسبه',
    },
    emptyTitle: 'تصمیم ریسکی در این محدوده وجود ندارد',
    emptyDescription:
      'بازه زمانی یا پرتفوی دیگری انتخاب کنید. کاندیدهای ردنشده از ارزیابی در این آمار شمرده نمی‌شوند.',
    budget: {
      title: 'مصرف بودجه ریسک',
      description:
        'ریسک واقعی موقعیت‌های بازشده در برابر بودجه‌ای که همان تصمیم‌های تأییدشده تخصیص داده‌اند.',
      openedDecisions: 'تصمیم منجر به موقعیت',
      allocated: 'بودجه تخصیص‌یافته',
      consumed: 'ریسک مصرف‌شده',
      utilization: 'نسبت مصرف',
      noUtilization: 'در این محدوده موقعیتی باز نشده است.',
    },
    portfolioRisk: {
      title: 'ریسک پرتفوی شبیه‌سازی‌شده',
      description:
        'Exposure و تمرکز در آخرین رویداد تا انتهای بازه؛ drawdown از equity ابتدای بازه محاسبه می‌شود.',
      portfolios: 'پرتفوی‌ها',
      openPositions: 'موقعیت‌های باز',
      equity: 'مجموع equity',
      exposure: 'Exposure شبیه‌سازی‌شده',
      concentration: 'تمرکز بزرگ‌ترین جفت',
      drawdown: 'بیشترین drawdown',
      largestPair: 'بزرگ‌ترین جفت',
      asOf: 'آخرین رویداد',
      limit: 'سقف سیاست',
      withinLimit: 'داخل سقف',
      overLimit: 'بالاتر از سقف',
      noData: 'رویداد پرتفوی در این محدوده موجود نیست.',
    },
    reasons: {
      title: 'علل اصلی رد',
      description:
        'هر تصمیم ردشده دقیقاً به اولین بررسی ناموفق در ترتیب ثابت سیاست نسبت داده می‌شود.',
      reconciled: 'جمع دسته‌ها با تعداد تصمیم‌های ردشده برابر است.',
      labels: riskCheckLabels.fa,
    },
    events: {
      title: 'رویدادهای تصمیم',
      description: 'هر ردیف به کاندید و پرتفوی شبیه‌سازی‌شده همان ارزیابی متصل است.',
      journal: 'شناسه رویداد journal',
      evaluatedAt: 'زمان ارزیابی',
      riskBudget: 'بودجه ریسک',
      riskConsumed: 'ریسک مصرف‌شده',
      failedChecks: 'بررسی‌های ناموفق',
      viewCandidate: 'مشاهده کاندید و زنجیره تصمیم',
      viewPortfolio: 'مشاهده گزارش پرتفوی',
      approved: 'تأییدشده',
      rejected: 'ردشده',
      replay: {
        opened: 'موقعیت شبیه‌سازی‌شده باز شد',
        risk_rejected: 'رد توسط سیاست ریسک',
        no_fill: 'بدون fill تاریخی',
      },
    },
    scope:
      'Snapshot پرتفوی از آخرین رویداد ثبت‌شده تا زمان پایان ساخته می‌شود؛ این صفحه هیچ عملیات معامله‌ای ندارد.',
    errorTitle: 'محاسبه داشبورد ریسک ناموفق بود',
    errorDescription: 'اتصال Backend و مقدار فیلترها را بررسی کرده و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
  },
  en: {
    eyebrow: 'Historical risk oversight',
    title: 'Research risk dashboard',
    description:
      'Review risk decisions and simulated portfolio state from persisted, auditable events.',
    readOnly: 'Read-only',
    historicalOnly: 'No live order execution',
    filters: {
      title: 'Report scope',
      description:
        'The time window filters decision evaluation timestamps and includes both boundaries.',
      fromTime: 'From time',
      toTime: 'To time',
      portfolio: 'Simulated portfolio',
      allPortfolios: 'All portfolios',
      apply: 'Apply filters',
      applying: 'Calculating',
      reset: 'Clear filters',
      invalidRange: 'End time must be equal to or later than start time.',
    },
    decisions: {
      title: 'Risk decisions',
      description:
        'Only candidates actually evaluated by risk policy enter the approval-rate denominator.',
      evaluated: 'Evaluated',
      approved: 'Approved',
      rejected: 'Rejected',
      approvalRate: 'Approval rate',
      noRate: 'No decisions to calculate',
    },
    emptyTitle: 'No risk decisions in this scope',
    emptyDescription:
      'Choose another time window or portfolio. Candidates skipped before evaluation are not counted.',
    budget: {
      title: 'Risk budget consumption',
      description:
        'Actual risk in opened simulations against the budget allocated by those approved decisions.',
      openedDecisions: 'Position-opening decisions',
      allocated: 'Allocated budget',
      consumed: 'Consumed risk',
      utilization: 'Consumption ratio',
      noUtilization: 'No simulated position opened in this scope.',
    },
    portfolioRisk: {
      title: 'Simulated portfolio risk',
      description:
        'Exposure and concentration at the latest event through the range end; drawdown starts at range-opening equity.',
      portfolios: 'Portfolios',
      openPositions: 'Open positions',
      equity: 'Total equity',
      exposure: 'Simulated exposure',
      concentration: 'Largest-pair concentration',
      drawdown: 'Maximum drawdown',
      largestPair: 'Largest pair',
      asOf: 'Latest event',
      limit: 'Policy cap',
      withinLimit: 'Within cap',
      overLimit: 'Above cap',
      noData: 'No portfolio event is available in this scope.',
    },
    reasons: {
      title: 'Primary rejection reasons',
      description:
        'Every rejection is assigned exactly once to the first failed check in fixed policy order.',
      reconciled: 'Category totals equal the rejected-decision count.',
      labels: riskCheckLabels.en,
    },
    events: {
      title: 'Decision events',
      description:
        'Each row links to the candidate and simulated portfolio used for that evaluation.',
      journal: 'Journal event ID',
      evaluatedAt: 'Evaluated at',
      riskBudget: 'Risk budget',
      riskConsumed: 'Risk consumed',
      failedChecks: 'Failed checks',
      viewCandidate: 'View candidate and decision lineage',
      viewPortfolio: 'View portfolio report',
      approved: 'Approved',
      rejected: 'Rejected',
      replay: {
        opened: 'Simulated position opened',
        risk_rejected: 'Rejected by risk policy',
        no_fill: 'No historical fill',
      },
    },
    scope:
      'Portfolio snapshots use the latest persisted event through the range end; this page exposes no trading action.',
    errorTitle: 'Unable to calculate the risk dashboard',
    errorDescription: 'Check the backend connection and filter values, then try again.',
    retry: 'Try again',
  },
};

export function getRiskCopy(locale: PlatformLocale): RiskCopy {
  return copies[locale];
}
