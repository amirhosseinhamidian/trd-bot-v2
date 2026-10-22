import type {
  CandidateAction,
  CandidateExitReason,
  CandidateOccurrenceType,
  CandidateRankingEvidenceComponentName,
  CandidateReplaySkipReason,
  CandidateReplayStatus,
  CandidateRiskCheckName,
  CandidateRiskDecision,
  CandidateStatus,
} from '@/features/candidates/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type CandidateCopy = {
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  total: string;
  loading: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  emptyTitle: string;
  emptyDescription: string;
  page: string;
  previous: string;
  next: string;
  selected: string;
  notSelected: string;
  notEvaluated: string;
  unavailableEvidence: string;
  viewDetails: string;
  rankingBreakdown: string;
  rankingBreakdownDescription: string;
  scoreVersion: string;
  tieBreakApplied: string;
  tieBreakNotApplied: string;
  tieOrder: string;
  riskCompatibilityDoesNotAffectRank: string;
  allRiskChecksPassed: string;
  failedRiskChecks: string;
  rankingComponents: Record<CandidateRankingEvidenceComponentName, string>;
  riskChecks: Record<CandidateRiskCheckName, string>;
  fields: {
    rank: string;
    rankingScore: string;
    riskCompatibility: string;
    confidence: string;
    signalScore: string;
    strategy: string;
    timeframe: string;
    replay: string;
    risk: string;
    occurrence: string;
    skipReason: string;
    occurrences: string;
    recordedAt: string;
    exitReason: string;
  };
  statuses: Record<CandidateStatus, string>;
  actions: Record<CandidateAction, string>;
  occurrenceTypes: Record<CandidateOccurrenceType, string>;
  replayStatuses: Record<CandidateReplayStatus, string>;
  riskDecisions: Record<CandidateRiskDecision, string>;
  skipReasons: Record<CandidateReplaySkipReason, string>;
  exitReasons: Record<CandidateExitReason, string>;
};

const copies: Record<PlatformLocale, CandidateCopy> = {
  fa: {
    eyebrow: 'Candidate read model',
    title: 'کاندیدهای پژوهشی',
    description:
      'نمای فقط‌خواندنی از کاندیدهایی که در چرخه Replay بررسی شده‌اند و از Journal پژوهشی مشتق شده‌اند.',
    readOnly: 'فقط پژوهشی',
    total: 'تعداد',
    loading: 'در حال دریافت کاندیدها',
    errorTitle: 'دریافت کاندیدها ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    emptyTitle: 'هنوز کاندیدی ثبت نشده است',
    emptyDescription: 'پس از اجرای چرخه پژوهشی، read model کاندیدها در این بخش نمایش داده می‌شود.',
    page: 'صفحه',
    previous: 'قبلی',
    next: 'بعدی',
    selected: 'انتخاب‌شده',
    notSelected: 'انتخاب‌نشده',
    notEvaluated: 'ارزیابی‌نشده',
    unavailableEvidence: 'شاهد breakdown برای این رکورد قدیمی در دسترس نیست',
    viewDetails: 'مشاهده جزئیات و lineage',
    rankingBreakdown: 'چرا این رتبه؟',
    rankingBreakdownDescription: 'سهم دقیق هر مؤلفه در امتیاز رتبه‌بندی.',
    scoreVersion: 'نسخه فرمول',
    tieBreakApplied: 'امتیاز برابر بود و Candidate ID صعودی tie-break را تعیین کرد.',
    tieBreakNotApplied: 'رتبه بدون نیاز به tie-break امتیاز برابر تعیین شد.',
    tieOrder: 'ترتیب Candidateهای هم‌امتیاز',
    riskCompatibilityDoesNotAffectRank:
      'سازگاری ریسک پس از رتبه‌بندی ارزیابی می‌شود و در امتیاز ranking اثر ندارد.',
    allRiskChecksPassed: 'همه کنترل‌های ریسک عبور کرده‌اند.',
    failedRiskChecks: 'کنترل‌های ریسک ناموفق',
    rankingComponents: {
      confidence: 'اطمینان',
      signal_quality: 'کیفیت سیگنال',
      freshness: 'تازگی',
    },
    riskChecks: {
      candidate_selectable: 'قابل انتخاب بودن Candidate',
      portfolio_active: 'فعال بودن Portfolio',
      dataset_match: 'تطابق Dataset',
      portfolio_capacity: 'ظرفیت Portfolio',
      rank_limit: 'سقف رتبه',
      ranking_score: 'کف امتیاز ranking',
      reward_risk: 'نسبت پاداش به ریسک',
      simulated_budget: 'بودجه شبیه‌سازی‌شده',
    },
    fields: {
      rank: 'رتبه',
      rankingScore: 'امتیاز رتبه‌بندی',
      riskCompatibility: 'سازگاری ریسک',
      confidence: 'اطمینان',
      signalScore: 'امتیاز سیگنال',
      strategy: 'استراتژی',
      timeframe: 'تایم‌فریم',
      replay: 'نتیجه Replay',
      risk: 'تصمیم ریسک',
      occurrence: 'نوع رخداد',
      skipReason: 'دلیل عبور',
      occurrences: 'تعداد رخداد',
      recordedAt: 'آخرین ثبت',
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
  },
  en: {
    eyebrow: 'Candidate read model',
    title: 'Research candidates',
    description:
      'Read-only candidates attempted by the replay lifecycle and derived from persisted research journals.',
    readOnly: 'Research only',
    total: 'Total',
    loading: 'Loading candidates',
    errorTitle: 'Unable to load candidates',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    emptyTitle: 'No candidates recorded yet',
    emptyDescription: 'Candidate read models will appear after a research lifecycle is recorded.',
    page: 'Page',
    previous: 'Previous',
    next: 'Next',
    selected: 'Selected',
    notSelected: 'Not selected',
    notEvaluated: 'Not evaluated',
    unavailableEvidence: 'Breakdown evidence is unavailable for this legacy record',
    viewDetails: 'View details and lineage',
    rankingBreakdown: 'Why this rank?',
    rankingBreakdownDescription: 'Exact contribution of every ranking score component.',
    scoreVersion: 'Formula version',
    tieBreakApplied: 'Scores were equal; ascending Candidate ID determined the tie-break.',
    tieBreakNotApplied: 'No equal-score tie-break was needed for this rank.',
    tieOrder: 'Equal-score candidate order',
    riskCompatibilityDoesNotAffectRank:
      'Risk compatibility is evaluated after ranking and does not affect the ranking score.',
    allRiskChecksPassed: 'All configured risk checks passed.',
    failedRiskChecks: 'Failed risk checks',
    rankingComponents: {
      confidence: 'Confidence',
      signal_quality: 'Signal quality',
      freshness: 'Freshness',
    },
    riskChecks: {
      candidate_selectable: 'Candidate selectable',
      portfolio_active: 'Portfolio active',
      dataset_match: 'Dataset match',
      portfolio_capacity: 'Portfolio capacity',
      rank_limit: 'Rank limit',
      ranking_score: 'Ranking score floor',
      reward_risk: 'Reward to risk',
      simulated_budget: 'Simulated budget',
    },
    fields: {
      rank: 'Rank',
      rankingScore: 'Ranking score',
      riskCompatibility: 'Risk compatibility',
      confidence: 'Confidence',
      signalScore: 'Signal score',
      strategy: 'Strategy',
      timeframe: 'Timeframe',
      replay: 'Replay outcome',
      risk: 'Risk decision',
      occurrence: 'Occurrence',
      skipReason: 'Skip reason',
      occurrences: 'Occurrences',
      recordedAt: 'Latest record',
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
  },
};

export function getCandidateCopy(locale: PlatformLocale): CandidateCopy {
  return copies[locale];
}
