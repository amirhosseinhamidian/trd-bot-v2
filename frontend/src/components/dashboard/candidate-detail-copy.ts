import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type {
  CandidateAction,
  CandidateExitReason,
  CandidateReplayStatus,
  CandidateRiskDecision,
  CandidateStatus,
} from '@/lib/api/types';

type CandidateDetailCopy = {
  eyebrow: string;
  readOnly: string;
  back: string;
  lineageTitle: string;
  lineageDescription: string;
  lineageLoading: string;
  lineageErrorTitle: string;
  lineageErrorDescription: string;
  retry: string;
  page: string;
  previous: string;
  next: string;
  selected: string;
  notSelected: string;
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
    recordedAt: string;
    positionId: string;
    exitReason: string;
  };
  statuses: Record<CandidateStatus, string>;
  actions: Record<CandidateAction, string>;
  replayStatuses: Record<CandidateReplayStatus, string>;
  riskDecisions: Record<CandidateRiskDecision, string>;
  exitReasons: Record<CandidateExitReason, string>;
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
    retry: 'تلاش مجدد',
    page: 'صفحه',
    previous: 'قبلی',
    next: 'بعدی',
    selected: 'انتخاب‌شده',
    notSelected: 'انتخاب‌نشده',
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
    replayStatuses: {
      opened: 'موقعیت باز شد',
      risk_rejected: 'رد ریسک',
      no_fill: 'بدون Fill',
    },
    riskDecisions: {
      approved: 'تأیید',
      rejected: 'رد',
    },
    exitReasons: {
      invalidation: 'ابطال',
      target: 'هدف',
      time_expiry: 'پایان زمان',
      end_of_data: 'پایان داده',
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
    retry: 'Try again',
    page: 'Page',
    previous: 'Previous',
    next: 'Next',
    selected: 'Selected',
    notSelected: 'Not selected',
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
    replayStatuses: {
      opened: 'Position opened',
      risk_rejected: 'Risk rejected',
      no_fill: 'No fill',
    },
    riskDecisions: {
      approved: 'Approved',
      rejected: 'Rejected',
    },
    exitReasons: {
      invalidation: 'Invalidation',
      target: 'Target',
      time_expiry: 'Time expiry',
      end_of_data: 'End of data',
    },
  },
};

export function getCandidateDetailCopy(locale: DashboardLocale): CandidateDetailCopy {
  return copies[locale];
}
