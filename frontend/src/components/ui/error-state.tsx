import type { ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { EmptyState, type EmptyStateProps } from '@/components/ui/empty-state';
import { cn } from '@/lib/utils/cn';

export type ErrorStateProps = Omit<EmptyStateProps, 'action' | 'icon'> & {
  details?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorState({
  className,
  description,
  details,
  onRetry,
  retryLabel,
  title,
  ...props
}: ErrorStateProps) {
  const hasDetails = details !== undefined && details !== null;
  const canRetry = Boolean(onRetry && retryLabel);

  return (
    <EmptyState
      {...props}
      role="alert"
      aria-live="assertive"
      title={title}
      description={description}
      className={cn('border-solid border-red-400/20 bg-red-400/5', className)}
      icon={
        <span aria-hidden="true" className="font-bold text-red-300">
          !
        </span>
      }
      action={
        hasDetails || canRetry ? (
          <div className="flex flex-col items-center gap-4">
            {hasDetails ? <div className="font-mono text-xs text-slate-600">{details}</div> : null}

            {canRetry ? (
              <Button type="button" size="sm" variant="danger" onClick={onRetry}>
                {retryLabel}
              </Button>
            ) : null}
          </div>
        ) : undefined
      }
    />
  );
}
