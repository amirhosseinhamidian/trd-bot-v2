import type {
  CandidateDecisionLineageKind,
  CandidateDecisionLineageStatus,
  CandidateExitReason,
  CandidateRiskDecision,
} from '@/features/candidates/api/types';
import type {
  PortfolioTimelineEventType,
  PositionLineageStatus,
  SimulatedPositionSide,
  SimulatedPositionStatus,
} from '@/features/portfolios/api/types';
import type { PlatformLocale } from '@/platform/i18n';

type PositionDetailCopy = {
  back: string;
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  accountingTitle: string;
  accountingDescription: string;
  lineageTitle: string;
  lineageDescription: string;
  rankingTitle: string;
  rankingUnavailable: string;
  riskTitle: string;
  eventsTitle: string;
  eventsDescription: string;
  eventsEmpty: string;
  viewResource: string;
  lineageStatuses: Record<PositionLineageStatus, string>;
  nodeStatuses: Record<CandidateDecisionLineageStatus, string>;
  nodeKinds: Record<CandidateDecisionLineageKind, string>;
  positionStatuses: Record<SimulatedPositionStatus, string>;
  sides: Record<SimulatedPositionSide, string>;
  riskDecisions: Record<CandidateRiskDecision, string>;
  exitReasons: Record<CandidateExitReason, string>;
  eventTypes: Record<PortfolioTimelineEventType, string>;
  reasons: Record<string, string>;
  fields: Record<string, string>;
};

const copies: Record<PlatformLocale, PositionDetailCopy> = {
  fa: {
    back: 'بازگشت به پرتفوی',
    eyebrow: 'Historical position lineage',
    title: 'جزئیات موقعیت شبیه‌سازی‌شده',
    description:
      'نمای فقط‌خواندنی حسابداری موقعیت و زنجیره کامل منشأ آن از Dataset و Experiment تا تصمیم ریسک و خروج.',
    readOnly: 'فقط‌خواندنی و پژوهشی',
    accountingTitle: 'حسابداری موقعیت',
    accountingDescription: 'ورود، خروج، کارمزد و P&L دقیق ثبت‌شده در شبیه‌سازی تاریخی.',
    lineageTitle: 'زنجیره منشأ و تصمیم',
    lineageDescription: 'هر مرحله فقط از شواهد persisted ساخته شده و داده حدسی نمایش داده نمی‌شود.',
    rankingTitle: 'شواهد رتبه و ریسک',
    rankingUnavailable: 'شواهد نسخه‌دار رتبه برای این رکورد در دسترس نیست.',
    riskTitle: 'کنترل‌های ریسک',
    eventsTitle: 'رویدادهای موقعیت',
    eventsDescription: 'رویدادهای دقیق این Position با ترتیب ممیزی ثبت‌شده.',
    eventsEmpty: 'رویداد مرتبطی برای این موقعیت ثبت نشده است.',
    viewResource: 'مشاهده منبع',
    lineageStatuses: {
      complete: 'Lineage کامل',
      unavailable: 'شواهد lineage ناموجود',
      conflict: 'تعارض در شواهد lineage',
    },
    nodeStatuses: {
      available: 'موجود',
      not_created: 'ایجاد نشده',
      not_evaluated: 'ارزیابی نشده',
      unavailable: 'ناموجود',
    },
    nodeKinds: {
      dataset: 'Dataset',
      experiment: 'Experiment',
      signal: 'Signal',
      candidate: 'Candidate',
      risk: 'تصمیم ریسک',
      position: 'Position',
      exit: 'خروج',
    },
    positionStatuses: { open: 'باز', closed: 'بسته' },
    sides: { long: 'Long', short: 'Short' },
    riskDecisions: { approved: 'تأییدشده', rejected: 'ردشده' },
    exitReasons: {
      invalidation: 'ابطال سناریو',
      target: 'رسیدن به هدف',
      trend_reversal: 'برگشت روند',
      portfolio_risk: 'ریسک پرتفوی',
      data_unreliable: 'داده نامطمئن',
      time_expiry: 'پایان زمان اعتبار',
      end_of_data: 'پایان داده',
    },
    eventTypes: {
      portfolio_created: 'ایجاد پرتفوی',
      position_opened: 'باز شدن موقعیت',
      position_marked: 'به‌روزرسانی قیمت',
      position_closed: 'بسته شدن موقعیت',
      portfolio_completed: 'تکمیل پرتفوی',
    },
    reasons: {
      lineage_evidence_unavailable: 'رکورد lineage برای این موقعیت قدیمی یا ناموجود است.',
      conflicting_lineage_evidence: 'بیش از یک رکورد ناسازگار به این موقعیت اشاره می‌کند.',
      exit_not_created: 'این موقعیت هنوز خروج ثبت‌شده ندارد.',
    },
    fields: {
      positionId: 'شناسه موقعیت',
      portfolioId: 'شناسه پرتفوی',
      journalId: 'شناسه Journal',
      pair: 'جفت‌ارز',
      strategy: 'استراتژی',
      quantity: 'مقدار',
      entryPrice: 'قیمت ورود',
      currentPrice: 'آخرین قیمت ثبت‌شده',
      exitPrice: 'قیمت خروج',
      reservedNotional: 'سرمایه رزروشده',
      entryFee: 'کارمزد ورود',
      exitFee: 'کارمزد خروج',
      grossPnl: 'P&L ناخالص',
      realizedPnl: 'P&L خالص تحقق‌یافته',
      unrealizedPnl: 'P&L تحقق‌نیافته',
      openedAt: 'زمان ورود',
      currentAt: 'زمان آخرین قیمت',
      closedAt: 'زمان خروج',
      rank: 'رتبه',
      rankingScore: 'امتیاز رتبه',
      scoreVersion: 'نسخه امتیاز',
      passedChecks: 'کنترل‌های موفق',
      failedChecks: 'کنترل‌های ناموفق',
      eventNumber: 'شماره رویداد',
      equity: 'ارزش پرتفوی',
      price: 'قیمت',
      occurredAt: 'زمان رویداد',
    },
  },
  en: {
    back: 'Back to portfolio',
    eyebrow: 'Historical position lineage',
    title: 'Simulated position detail',
    description:
      'Read-only position accounting and full persisted origin chain from dataset and experiment through risk decision and exit.',
    readOnly: 'Read-only research',
    accountingTitle: 'Position accounting',
    accountingDescription: 'Exact entry, exit, fees, and P&L stored by the historical simulation.',
    lineageTitle: 'Origin and decision lineage',
    lineageDescription:
      'Every stage is derived from persisted evidence; unavailable facts are not inferred.',
    rankingTitle: 'Ranking and risk evidence',
    rankingUnavailable: 'Versioned ranking evidence is unavailable for this record.',
    riskTitle: 'Risk checks',
    eventsTitle: 'Position events',
    eventsDescription: 'Exact events for this position in their persisted audit order.',
    eventsEmpty: 'No matching events are recorded for this position.',
    viewResource: 'View resource',
    lineageStatuses: {
      complete: 'Complete lineage',
      unavailable: 'Lineage evidence unavailable',
      conflict: 'Conflicting lineage evidence',
    },
    nodeStatuses: {
      available: 'Available',
      not_created: 'Not created',
      not_evaluated: 'Not evaluated',
      unavailable: 'Unavailable',
    },
    nodeKinds: {
      dataset: 'Dataset',
      experiment: 'Experiment',
      signal: 'Signal',
      candidate: 'Candidate',
      risk: 'Risk decision',
      position: 'Position',
      exit: 'Exit',
    },
    positionStatuses: { open: 'Open', closed: 'Closed' },
    sides: { long: 'Long', short: 'Short' },
    riskDecisions: { approved: 'Approved', rejected: 'Rejected' },
    exitReasons: {
      invalidation: 'Invalidation',
      target: 'Target reached',
      trend_reversal: 'Trend reversal',
      portfolio_risk: 'Portfolio risk',
      data_unreliable: 'Unreliable data',
      time_expiry: 'Time expiry',
      end_of_data: 'End of data',
    },
    eventTypes: {
      portfolio_created: 'Portfolio created',
      position_opened: 'Position opened',
      position_marked: 'Position marked',
      position_closed: 'Position closed',
      portfolio_completed: 'Portfolio completed',
    },
    reasons: {
      lineage_evidence_unavailable:
        'The lineage record for this position is legacy or unavailable.',
      conflicting_lineage_evidence: 'Multiple incompatible records point to this position.',
      exit_not_created: 'This position does not have a recorded exit yet.',
    },
    fields: {
      positionId: 'Position ID',
      portfolioId: 'Portfolio ID',
      journalId: 'Journal ID',
      pair: 'Pair',
      strategy: 'Strategy',
      quantity: 'Quantity',
      entryPrice: 'Entry price',
      currentPrice: 'Last recorded price',
      exitPrice: 'Exit price',
      reservedNotional: 'Reserved notional',
      entryFee: 'Entry fee',
      exitFee: 'Exit fee',
      grossPnl: 'Gross P&L',
      realizedPnl: 'Net realized P&L',
      unrealizedPnl: 'Unrealized P&L',
      openedAt: 'Opened at',
      currentAt: 'Last priced at',
      closedAt: 'Closed at',
      rank: 'Rank',
      rankingScore: 'Ranking score',
      scoreVersion: 'Score version',
      passedChecks: 'Passed checks',
      failedChecks: 'Failed checks',
      eventNumber: 'Event number',
      equity: 'Portfolio equity',
      price: 'Price',
      occurredAt: 'Occurred at',
    },
  },
};

export function getPositionDetailCopy(locale: PlatformLocale): PositionDetailCopy {
  return copies[locale];
}
