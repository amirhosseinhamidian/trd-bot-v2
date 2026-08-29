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
        'flex min-h-52 flex-col items-center justify-center rounded-2xl border border-dashed border-app-border bg-app-surface/70 p-6 text-center',
        className,
      )}
      {...props}
    >
      {icon ? (
        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-app-border bg-app-surface-muted text-app-muted">
          {icon}
        </div>
      ) : null}

      <h3 className="text-sm font-semibold text-app-foreground">{title}</h3>

      {description ? (
        <p className="mt-2 max-w-md text-sm leading-6 text-app-muted">{description}</p>
      ) : null}

      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
