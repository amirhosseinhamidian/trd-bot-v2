import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type {
  CandidateAction,
  CandidateDecisionLineageKind,
  CandidateDecisionLineageStatus,
  CandidateExitReason,
  CandidateOccurrenceType,
  CandidateReplaySkipReason,
  CandidateReplayStatus,
  CandidateRiskDecision,
  CandidateStatus,
} from '@/lib/api/types';

export type CandidateLineageReason =
  | 'exit_not_created'
  | 'legacy_evidence_unavailable'
  | 'no_fill'
  | 'not_selected'
  | 'position_not_created'
  | 'position_opened'
  | 'risk_rejected'
  | 'skipped';

type CandidateDetailCopy = {
  eyebrow: string;
  readOnly: string;
  back: string;
  lineageTitle: string;
  lineageDescription: string;
  lineageLoading: string;
  lineageErrorTitle: string;
  lineageErrorDescription: string;
  decisionLineageTitle: string;
  decisionLineageDescription: string;
  decisionBreakdownTitle: string;
  decisionBreakdownDescription: string;
  rankHistoryTitle: string;
  rankHistoryDescription: string;
  evidenceAvailable: string;
  evidenceUnavailable: string;
  viewResource: string;
  retry: string;
  page: string;
  previous: string;
  next: string;
  selected: string;
  notSelected: string;
  notEvaluated: string;
  fields: {
    candidateId: string;
    datasetId: string;
    experimentId: string;
    signalId: string;
    strategy: string;
    timeframe: string;
    confidence: string;
    signalScore: string;
    createdAt: string;
    validUntil: string;
    occurrences: string;
    journal: string;
    rank: string;
    rankingScore: string;
    replay: string;
    risk: string;
    occurrence: string;
    skipReason: string;
    recordedAt: string;
    positionId: string;
    exitReason: string;
  };
  statuses: Record<CandidateStatus, string>;
  actions: Record<CandidateAction, string>;
  occurrenceTypes: Record<CandidateOccurrenceType, string>;
  replayStatuses: Record<CandidateReplayStatus, string>;
  riskDecisions: Record<CandidateRiskDecision, string>;
  skipReasons: Record<CandidateReplaySkipReason, string>;
  exitReasons: Record<CandidateExitReason, string>;
  lineageKinds: Record<CandidateDecisionLineageKind, string>;
  lineageStatuses: Record<CandidateDecisionLineageStatus, string>;
  lineageReasons: Record<CandidateLineageReason, string>;
};

const copies: Record<DashboardLocale, CandidateDetailCopy> = {
  fa: {
    eyebrow: 'Candidate detail',
    readOnly: 'فقط پژوهشی',
    back: 'بازگشت به کاندیدها',
    lineageTitle: 'Lineage پژوهشی',
    lineageDescription: 'رخدادهای persisted این کاندید، از جدیدترین به قدیمی‌ترین.',
    lineageLoading: 'در حال دریافت lineage',
    lineageErrorTitle: 'دریافت lineage ناموفق بود',
    lineageErrorDescription: 'اتصال Backend را بررسی و دوباره تلاش کنید.',
    decisionLineageTitle: 'زنجیره تصمیم',
    decisionLineageDescription:
      'منابع پژوهشی و مراحل تصمیم، از Dataset تا Exit، با وضعیت دقیق هر مرحله.',
    decisionBreakdownTitle: 'شواهد آخرین تصمیم',
    decisionBreakdownDescription: 'اجزای رتبه و کنترل‌های ریسک آخرین رخداد ذخیره‌شده.',
    rankHistoryTitle: 'تاریخچه رتبه',
    rankHistoryDescription: 'رتبه‌های ذخیره‌شده این Candidate از جدیدترین به قدیمی‌ترین.',
    evidenceAvailable: 'شاهد موجود',
    evidenceUnavailable: 'شاهد قدیمی ناموجود',
    viewResource: 'مشاهده منبع',
    retry: 'تلاش مجدد',
    page: 'صفحه',
    previous: 'قبلی',
    next: 'بعدی',
    selected: 'انتخاب‌شده',
    notSelected: 'انتخاب‌نشده',
    notEvaluated: 'ارزیابی‌نشده',
    fields: {
      candidateId: 'Candidate ID',
      datasetId: 'Dataset ID',
      experimentId: 'Experiment ID',
      signalId: 'Signal ID',
      strategy: 'استراتژی',
      timeframe: 'تایم‌فریم',
      confidence: 'اطمینان',
      signalScore: 'امتیاز سیگنال',
      createdAt: 'زمان ایجاد',
      validUntil: 'اعتبار تا',
      occurrences: 'تعداد رخداد',
      journal: 'Journal',
      rank: 'رتبه',
      rankingScore: 'امتیاز رتبه‌بندی',
      replay: 'نتیجه Replay',
      risk: 'تصمیم ریسک',
      occurrence: 'نوع رخداد',
      skipReason: 'دلیل عبور',
      recordedAt: 'زمان ثبت',
      positionId: 'Position ID',
      exitReason: 'دلیل خروج',
    },
    statuses: {
      candidate: 'کاندید',
      selected: 'انتخاب‌شده',
      stale: 'منقضی',
      invalidated: 'باطل‌شده',
    },
    actions: {
      long: 'Long',
      short: 'Short',
      neutral: 'Neutral',
      no_trade: 'No trade',
    },
    occurrenceTypes: {
      attempted: 'بررسی‌شده',
      skipped: 'عبور شده',
    },
    replayStatuses: {
      opened: 'موقعیت باز شد',
      risk_rejected: 'رد ریسک',
      no_fill: 'بدون Fill',
    },
    riskDecisions: {
      approved: 'تأیید',
      rejected: 'رد',
    },
    skipReasons: {
      position_opened: 'موقعیت کاندید قبلی باز شد',
    },
    exitReasons: {
      invalidation: 'ابطال',
      target: 'هدف',
      trend_reversal: 'بازگشت روند',
      portfolio_risk: 'ریسک پرتفوی',
      data_unreliable: 'داده نامطمئن',
      time_expiry: 'پایان زمان',
      end_of_data: 'پایان داده',
    },
    lineageKinds: {
      dataset: 'Dataset',
      experiment: 'Experiment',
      signal: 'Signal',
      candidate: 'Candidate',
      risk: 'Risk',
      position: 'Position',
      exit: 'Exit',
    },
    lineageStatuses: {
      available: 'موجود',
      not_created: 'هنوز ایجاد نشده',
      not_evaluated: 'ارزیابی‌نشده',
      unavailable: 'برای رکورد قدیمی در دسترس نیست',
    },
    lineageReasons: {
      exit_not_created: 'خروج هنوز ثبت نشده است',
      legacy_evidence_unavailable: 'شواهد تفصیلی در رکورد قدیمی موجود نیست',
      no_fill: 'سفارش شبیه‌سازی‌شده Fill نشد',
      not_selected: 'Candidate انتخاب نشد',
      position_not_created: 'Position ایجاد نشده است',
      position_opened: 'Position کاندید قبلی باز شد',
      risk_rejected: 'Candidate در کنترل ریسک رد شد',
      skipped: 'Candidate عبور داده شد',
    },
  },
  en: {
    eyebrow: 'Candidate detail',
    readOnly: 'Research only',
    back: 'Back to candidates',
    lineageTitle: 'Research lineage',
    lineageDescription: 'Persisted occurrences for this candidate, newest first.',
    lineageLoading: 'Loading lineage',
    lineageErrorTitle: 'Unable to load lineage',
    lineageErrorDescription: 'Check the backend connection and try again.',
    decisionLineageTitle: 'Decision lineage',
    decisionLineageDescription:
      'Research sources and decision stages from Dataset through Exit, with explicit availability.',
    decisionBreakdownTitle: 'Latest decision evidence',
    decisionBreakdownDescription: 'Ranking components and risk checks from the latest occurrence.',
    rankHistoryTitle: 'Rank history',
    rankHistoryDescription: 'Persisted ranks for this candidate, newest first.',
    evidenceAvailable: 'Evidence available',
    evidenceUnavailable: 'Legacy evidence unavailable',
    viewResource: 'View source',
    retry: 'Try again',
    page: 'Page',
    previous: 'Previous',
    next: 'Next',
    selected: 'Selected',
    notSelected: 'Not selected',
    notEvaluated: 'Not evaluated',
    fields: {
      candidateId: 'Candidate ID',
      datasetId: 'Dataset ID',
      experimentId: 'Experiment ID',
      signalId: 'Signal ID',
      strategy: 'Strategy',
      timeframe: 'Timeframe',
      confidence: 'Confidence',
      signalScore: 'Signal score',
      createdAt: 'Created at',
      validUntil: 'Valid until',
      occurrences: 'Occurrences',
      journal: 'Journal',
      rank: 'Rank',
      rankingScore: 'Ranking score',
      replay: 'Replay outcome',
      risk: 'Risk decision',
      occurrence: 'Occurrence',
      skipReason: 'Skip reason',
      recordedAt: 'Recorded at',
      positionId: 'Position ID',
      exitReason: 'Exit reason',
    },
    statuses: {
      candidate: 'Candidate',
      selected: 'Selected',
      stale: 'Stale',
      invalidated: 'Invalidated',
    },
    actions: {
      long: 'Long',
      short: 'Short',
      neutral: 'Neutral',
      no_trade: 'No trade',
    },
    occurrenceTypes: {
      attempted: 'Attempted',
      skipped: 'Skipped',
    },
    replayStatuses: {
      opened: 'Position opened',
      risk_rejected: 'Risk rejected',
      no_fill: 'No fill',
    },
    riskDecisions: {
      approved: 'Approved',
      rejected: 'Rejected',
    },
    skipReasons: {
      position_opened: 'Earlier candidate position opened',
    },
    exitReasons: {
      invalidation: 'Invalidation',
      target: 'Target',
      trend_reversal: 'Trend reversal',
      portfolio_risk: 'Portfolio risk',
      data_unreliable: 'Data unreliable',
      time_expiry: 'Time expiry',
      end_of_data: 'End of data',
    },
    lineageKinds: {
      dataset: 'Dataset',
      experiment: 'Experiment',
      signal: 'Signal',
      candidate: 'Candidate',
      risk: 'Risk',
      position: 'Position',
      exit: 'Exit',
    },
    lineageStatuses: {
      available: 'Available',
      not_created: 'Not created yet',
      not_evaluated: 'Not evaluated',
      unavailable: 'Unavailable for legacy record',
    },
    lineageReasons: {
      exit_not_created: 'An exit has not been recorded yet',
      legacy_evidence_unavailable: 'Detailed evidence is unavailable for this legacy record',
      no_fill: 'The simulated order did not fill',
      not_selected: 'The candidate was not selected',
      position_not_created: 'A position was not created',
      position_opened: 'An earlier candidate position opened',
      risk_rejected: 'The candidate was rejected by risk controls',
      skipped: 'The candidate was skipped',
    },
  },
};

export function getCandidateDetailCopy(locale: DashboardLocale): CandidateDetailCopy {
  return copies[locale];
}
