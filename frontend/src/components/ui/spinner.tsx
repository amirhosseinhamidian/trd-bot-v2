import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type SpinnerSize = 'sm' | 'md' | 'lg';

export type SpinnerProps = HTMLAttributes<HTMLSpanElement> & {
  label?: string;
  size?: SpinnerSize;
};

const sizes: Record<SpinnerSize, string> = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-9 w-9 border-[3px]',
};

export function Spinner({ className, label, size = 'md', ...props }: SpinnerProps) {
  return (
    <span
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        'inline-block shrink-0 animate-spin rounded-full border-current border-e-transparent',
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
