import {
  forwardRef,
  type HTMLAttributes,
  type TableHTMLAttributes,
  type TdHTMLAttributes,
  type ThHTMLAttributes,
} from 'react';

import { cn } from '@/lib/utils/cn';

export type TableProps = TableHTMLAttributes<HTMLTableElement> & {
  containerClassName?: string;
  scrollLabel?: string;
};

export const Table = forwardRef<HTMLTableElement, TableProps>(
  ({ className, containerClassName, dir, scrollLabel, ...props }, ref) => (
    <div
      role={scrollLabel ? 'region' : undefined}
      aria-label={scrollLabel}
      tabIndex={scrollLabel ? 0 : undefined}
      dir={dir}
      className={cn(
        'relative w-full [scrollbar-gutter:stable] overflow-x-auto overscroll-x-contain rounded-xl border border-app-border bg-app-surface focus-visible:border-app-control-border focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none focus-visible:ring-inset',
        containerClassName,
      )}
    >
      <table
        ref={ref}
        dir={dir}
        className={cn('w-full min-w-full caption-bottom text-sm', className)}
        {...props}
      />
    </div>
  ),
);

Table.displayName = 'Table';

export const TableHeader = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    ref={ref}
    className={cn('border-b border-app-border bg-app-surface-muted', className)}
    {...props}
  />
));

TableHeader.displayName = 'TableHeader';

export const TableBody = forwardRef<
  HTMLTableSectionElement,
  HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn('divide-y divide-app-border', className)} {...props} />
));

TableBody.displayName = 'TableBody';

export const TableRow = forwardRef<HTMLTableRowElement, HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => (
    <tr
      ref={ref}
      className={cn(
        'transition-colors focus-within:bg-app-hover hover:bg-app-hover data-[state=selected]:bg-app-accent-soft',
        className,
      )}
      {...props}
    />
  ),
);

TableRow.displayName = 'TableRow';

export const TableHead = forwardRef<HTMLTableCellElement, ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, scope = 'col', ...props }, ref) => (
    <th
      ref={ref}
      scope={scope}
      className={cn(
        'h-11 px-3 text-start text-xs font-semibold whitespace-nowrap text-app-muted sm:px-4',
        className,
      )}
      {...props}
    />
  ),
);

TableHead.displayName = 'TableHead';

export const TableCell = forwardRef<HTMLTableCellElement, TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => (
    <td
      ref={ref}
      className={cn(
        'px-3 py-3 align-middle text-sm whitespace-nowrap text-app-foreground sm:px-4',
        className,
      )}
      {...props}
    />
  ),
);

TableCell.displayName = 'TableCell';
