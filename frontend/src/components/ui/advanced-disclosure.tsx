import type { DetailsHTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils/cn';

export type AdvancedDisclosureProps = Omit<
  DetailsHTMLAttributes<HTMLDetailsElement>,
  'children' | 'title'
> & {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
};

export function AdvancedDisclosure({
  children,
  className,
  description,
  title,
  ...props
}: AdvancedDisclosureProps) {
  return (
    <details
      className={cn(
        'group rounded-2xl border border-app-border bg-app-surface shadow-app-surface',
        className,
      )}
      {...props}
    >
      <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 rounded-2xl px-5 py-4 transition marker:hidden hover:bg-app-hover focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none sm:px-6 [&::-webkit-details-marker]:hidden">
        <span className="min-w-0">
          <span className="block text-base font-semibold text-app-foreground">{title}</span>
          {description ? (
            <span className="mt-1 block text-sm leading-6 text-app-muted">{description}</span>
          ) : null}
        </span>

        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          fill="none"
          className="size-5 shrink-0 text-app-muted transition-transform duration-200 group-open:rotate-180 motion-reduce:transition-none"
        >
          <path
            d="m5 7.5 5 5 5-5"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </summary>

      <div className="border-t border-app-border px-5 py-5 sm:px-6 sm:py-6">{children}</div>
    </details>
  );
}
