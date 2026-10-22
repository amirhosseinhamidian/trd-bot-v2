import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

export type EmptyStateProps = Omit<HTMLAttributes<HTMLDivElement>, 'title'> & {
  action?: ReactNode;
  description?: string;
  icon?: ReactNode;
  title: string;
};

export function EmptyState({
  action,
  className,
  description,
  icon,
  title,
  ...props
}: EmptyStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex min-h-52 min-w-0 flex-col items-center justify-center rounded-2xl border border-dashed border-app-border bg-app-surface p-5 text-center sm:p-6',
        className,
      )}
      {...props}
    >
      {icon ? (
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-app-border bg-app-surface-muted text-app-muted">
          {icon}
        </div>
      ) : null}

      <h3 className="max-w-full text-sm font-semibold break-words text-app-foreground">{title}</h3>

      {description ? (
        <p className="mt-2 max-w-full text-sm leading-6 break-words text-app-muted sm:max-w-md">
          {description}
        </p>
      ) : null}

      {action ? <div className="mt-5 max-w-full min-w-0">{action}</div> : null}
    </div>
  );
}
