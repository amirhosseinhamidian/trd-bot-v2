import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils/cn';

export type PageFrameProps = HTMLAttributes<HTMLDivElement>;

export function PageFrame({ className, ...props }: PageFrameProps) {
  return <div className={cn('min-w-0 space-y-8', className)} {...props} />;
}
