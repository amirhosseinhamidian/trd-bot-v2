'use client';

import { Button } from '@/components/ui/button';

export type PaginationProps = {
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
  isLoading = false,
  limit,
  nextLabel,
  offset,
  onOffsetChange,
  pageLabel,
  previousLabel,
  total,
}: PaginationProps) {
  const hasPrevious = offset > 0;
  const hasNext = offset + limit < total;

  const currentPage = total === 0 ? 0 : Math.floor(offset / limit) + 1;
  const totalPages = total === 0 ? 0 : Math.ceil(total / limit);

  return (
    <nav
      aria-label={pageLabel}
      aria-busy={isLoading}
      className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-center text-xs text-app-muted sm:text-start">
        {pageLabel}: {currentPage} / {totalPages}
      </p>

      <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto">
        <Button
          variant="secondary"
          size="sm"
          className="w-full sm:w-auto"
          disabled={!hasPrevious || isLoading}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          {previousLabel}
        </Button>

        <Button
          variant="secondary"
          size="sm"
          className="w-full sm:w-auto"
          disabled={!hasNext || isLoading}
          onClick={() => onOffsetChange(offset + limit)}
        >
          {nextLabel}
        </Button>
      </div>
    </nav>
  );
}
