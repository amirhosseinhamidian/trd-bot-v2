import type { WalkForwardFoldStatistics } from '@/features/walk-forward/api/types';

export const WALK_FORWARD_FOLD_PAGE_SIZE = 100;
export const WALK_FORWARD_CHART_POINT_LIMIT = 160;

export function normalizeFoldOffset(requestedOffset: number, total: number): number {
  const safeTotal = Math.max(0, total);
  const maximumOffset = Math.max(
    0,
    Math.floor(Math.max(0, safeTotal - 1) / WALK_FORWARD_FOLD_PAGE_SIZE) *
      WALK_FORWARD_FOLD_PAGE_SIZE,
  );

  if (!Number.isSafeInteger(requestedOffset) || requestedOffset < 0) {
    return 0;
  }

  const pageOffset =
    Math.floor(requestedOffset / WALK_FORWARD_FOLD_PAGE_SIZE) * WALK_FORWARD_FOLD_PAGE_SIZE;

  return Math.min(pageOffset, maximumOffset);
}

export function sampleWalkForwardFolds(
  folds: WalkForwardFoldStatistics[],
  limit = WALK_FORWARD_CHART_POINT_LIMIT,
): WalkForwardFoldStatistics[] {
  const safeLimit = Math.max(2, Math.floor(limit));

  if (folds.length <= safeLimit) {
    return folds;
  }

  const lastIndex = folds.length - 1;

  return Array.from({ length: safeLimit }, (_, index) => {
    const sourceIndex = Math.round((index * lastIndex) / (safeLimit - 1));
    return folds[sourceIndex];
  });
}
