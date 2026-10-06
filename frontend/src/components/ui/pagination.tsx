'use client';

import { Button } from '@/components/ui/button';

export type PaginationProps = {
  dir?: 'ltr' | 'rtl';
  isLoading?: boolean;
  limit: number;
  nextLabel: string;
  offset: number;
  onOffsetChange: (offset: number) => void;
  pageLabel: string;
  previousLabel: string;
  total: number;
};

export function Pagination({
  dir,
  isLoading = false,
  limit,
  nextLabel,
  offset,
  onOffsetChange,
  pageLabel,
  previousLabel,
  total,
}: PaginationProps) {
  const pageSize = Math.max(1, limit);
  const itemCount = Math.max(0, total);
  const totalPages = itemCount === 0 ? 0 : Math.ceil(itemCount / pageSize);
  const maximumOffset = Math.max(0, (totalPages - 1) * pageSize);
  const currentOffset = Math.min(Math.max(0, offset), maximumOffset);
  const hasPrevious = currentOffset > 0;
  const hasNext = currentOffset + pageSize < itemCount;

  const currentPage = itemCount === 0 ? 0 : Math.floor(currentOffset / pageSize) + 1;

  return (
    <nav
      aria-label={pageLabel}
      aria-busy={isLoading}
      dir={dir}
      className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p
        aria-live="polite"
        aria-atomic="true"
        className="text-center text-xs text-app-muted sm:text-start"
      >
        {pageLabel}:{' '}
        <span
          dir="ltr"
          aria-current="page"
          className="font-medium text-app-foreground tabular-nums"
        >
          {currentPage} / {totalPages}
        </span>
      </p>

      <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto">
        <Button
          variant="secondary"
          size="sm"
          className="w-full sm:w-auto"
          disabled={!hasPrevious || isLoading}
          onClick={() => onOffsetChange(Math.max(0, currentOffset - pageSize))}
        >
          {previousLabel}
        </Button>

        <Button
          variant="secondary"
          size="sm"
          className="w-full sm:w-auto"
          disabled={!hasNext || isLoading}
          onClick={() => onOffsetChange(currentOffset + pageSize)}
        >
          {nextLabel}
        </Button>
      </div>
    </nav>
  );
}
