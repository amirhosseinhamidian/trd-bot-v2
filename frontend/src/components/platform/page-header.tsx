import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

export type PageHeaderProps = Omit<HTMLAttributes<HTMLElement>, 'title'> & {
  actions?: ReactNode;
  backLink?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  metadata?: ReactNode;
  title: ReactNode;
  titleClassName?: string;
};

export function PageHeader({
  actions,
  backLink,
  children,
  className,
  description,
  eyebrow,
  metadata,
  title,
  titleClassName,
  ...props
}: PageHeaderProps) {
  return (
    <header className={cn('min-w-0', className)} {...props}>
      {backLink ? (
        <div className="mb-5 [&>a]:inline-flex [&>a]:min-h-11 [&>a]:items-center">{backLink}</div>
      ) : null}

      <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          {eyebrow ? (
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {eyebrow}
            </p>
          ) : null}

          <h1
            className={cn(
              'text-2xl font-bold tracking-tight text-app-foreground sm:text-3xl lg:text-4xl',
              eyebrow && 'mt-3',
              titleClassName,
            )}
          >
            {title}
          </h1>

          {metadata ? <div className="mt-2">{metadata}</div> : null}

          {description ? (
            <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
              {description}
            </p>
          ) : null}
        </div>

        {actions ? (
          <div
            data-slot="page-header-actions"
            className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:max-w-[45%] sm:shrink-0 sm:justify-end [&>a]:min-h-11 max-sm:[&>a]:w-full [&>button]:min-h-11 max-sm:[&>button]:w-full"
          >
            {actions}
          </div>
        ) : null}
      </div>

      {children ? <div className="mt-5">{children}</div> : null}
    </header>
  );
}
