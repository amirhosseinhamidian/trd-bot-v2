import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

type CandidateComparisonCopy = {
  title: string;
  description: string;
  selectedCount: string;
  selectionHint: string;
  selectCandidate: string;
  incompatibleCandidate: string;
  limitReached: string;
  compare: string;
  comparing: string;
  clearSelection: string;
  insufficientSelection: string;
  error: string;
  retry: string;
  resultTitle: string;
  resultDescription: string;
  candidate: string;
  rank: string;
  score: string;
  historicalOnly: string;
};

const copies: Record<DashboardLocale, CandidateComparisonCopy> = {
  fa: {
    title: 'مقایسه Candidateها',
    description: 'Breakdown کاندیدهای یک تصمیم پژوهشی را کنار هم مقایسه کنید.',
    selectedCount: 'انتخاب‌شده',
    selectionHint: 'بین دو تا چهار Candidate با Journal یکسان انتخاب کنید.',
    selectCandidate: 'انتخاب برای مقایسه',
    incompatibleCandidate: 'این Candidate متعلق به Journal دیگری است.',
    limitReached: 'حداکثر چهار Candidate قابل مقایسه است.',
    compare: 'مقایسه',
    comparing: 'در حال مقایسه',
    clearSelection: 'پاک‌کردن انتخاب',
    insufficientSelection: 'برای مقایسه حداقل دو Candidate انتخاب کنید.',
    error: 'مقایسه Candidateها ناموفق بود. انتخاب‌ها را بررسی و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    resultTitle: 'Breakdown کنارهم',
    resultDescription: 'ترتیب بر اساس رتبه‌ی ذخیره‌شده در همان Journal است.',
    candidate: 'Candidate',
    rank: 'رتبه',
    score: 'امتیاز',
    historicalOnly: 'این مقایسه فقط خروجی پژوهش تاریخی است.',
  },
  en: {
    title: 'Candidate comparison',
    description: 'Compare breakdowns from the same persisted research decision side by side.',
    selectedCount: 'Selected',
    selectionHint: 'Select two to four candidates that share the same latest journal.',
    selectCandidate: 'Select for comparison',
    incompatibleCandidate: 'This candidate belongs to a different latest journal.',
    limitReached: 'At most four candidates can be compared.',
    compare: 'Compare candidates',
    comparing: 'Comparing',
    clearSelection: 'Clear selection',
    insufficientSelection: 'Select at least two candidates to compare.',
    error: 'Candidate comparison failed. Check the selection and try again.',
    retry: 'Try again',
    resultTitle: 'Side-by-side breakdown',
    resultDescription: 'Order follows the persisted rank from the shared journal.',
    candidate: 'Candidate',
    rank: 'Rank',
    score: 'Score',
    historicalOnly: 'This comparison is historical research output only.',
  },
};

export function getCandidateComparisonCopy(locale: DashboardLocale): CandidateComparisonCopy {
  return copies[locale];
}
