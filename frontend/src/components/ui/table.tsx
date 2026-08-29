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
  ({ className, containerClassName, scrollLabel, ...props }, ref) => (
    <div
      role={scrollLabel ? 'region' : undefined}
      aria-label={scrollLabel}
      tabIndex={scrollLabel ? 0 : undefined}
      className={cn(
        'relative w-full overflow-x-auto overscroll-x-contain rounded-xl border border-app-border bg-app-surface focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none focus-visible:ring-inset',
        containerClassName,
      )}
    >
      <table
        ref={ref}
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
    <tr ref={ref} className={cn('transition-colors hover:bg-app-hover', className)} {...props} />
  ),
);

TableRow.displayName = 'TableRow';

export const TableHead = forwardRef<HTMLTableCellElement, ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, scope = 'col', ...props }, ref) => (
    <th
      ref={ref}
      scope={scope}
      className={cn(
        'h-11 px-4 text-start text-xs font-medium whitespace-nowrap text-app-muted',
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
      className={cn('px-4 py-3 text-sm whitespace-nowrap text-app-foreground', className)}
      {...props}
    />
  ),
);

TableCell.displayName = 'TableCell';
