import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type BadgeVariant = 'neutral' | 'info' | 'success' | 'warning' | 'danger';

export type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

const variants: Record<BadgeVariant, string> = {
  neutral: 'border-app-border bg-app-surface-muted text-app-muted',
  info: 'border-app-accent-border bg-app-accent-soft text-app-accent',
  success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-500',
  warning: 'border-amber-500/20 bg-amber-500/10 text-amber-500',
  danger: 'border-red-500/20 bg-red-500/10 text-red-500',
};

export function Badge({ className, variant = 'neutral', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
