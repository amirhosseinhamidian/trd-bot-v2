import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type BadgeVariant = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

const variants: Record<BadgeVariant, string> = {
  neutral: 'border-app-border bg-app-surface-muted text-app-muted',
  info: 'border-app-info-border bg-app-info-soft text-app-info',
  success: 'border-app-success-border bg-app-success-soft text-app-success',
  warning: 'border-app-warning-border bg-app-warning-soft text-app-warning',
  danger: 'border-app-danger-border bg-app-danger-soft text-app-danger',
};

export function Badge({ className, variant = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex max-w-full items-center rounded-full border px-2.5 py-1 text-center text-xs leading-5 font-medium break-words whitespace-normal',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
