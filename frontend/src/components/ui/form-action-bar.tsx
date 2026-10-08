import { forwardRef, type HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type FormActionBarProps = HTMLAttributes<HTMLDivElement> & {
  stickyOnMobile?: boolean;
};

export const FormActionBar = forwardRef<HTMLDivElement, FormActionBarProps>(
  ({ className, stickyOnMobile = false, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="form-actions"
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center',
        '[&>a]:min-h-11 [&>a]:w-full sm:[&>a]:w-auto [&>button]:w-full sm:[&>button]:w-auto',
        stickyOnMobile &&
          'sticky bottom-[4.75rem] z-20 -mx-5 border-y border-app-border bg-app-surface px-5 py-4 shadow-app-surface sm:-mx-6 sm:px-6 md:static md:mx-0 md:border-0 md:bg-transparent md:p-0 md:shadow-none',
        className,
      )}
      {...props}
    />
  ),
);

FormActionBar.displayName = 'FormActionBar';
