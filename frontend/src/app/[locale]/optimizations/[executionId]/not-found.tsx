'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import { EmptyState } from '@/components/ui';
import { getOptimizationCopy } from '@/features/optimizations/optimization-copy';
import type { PlatformLocale } from '@/platform/i18n';

export default function OptimizationNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: PlatformLocale = params.locale === 'en' ? 'en' : 'fa';
  const copy = getOptimizationCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <EmptyState
        className="w-full max-w-xl"
        title={copy.detail.notFoundTitle}
        description={copy.detail.notFoundDescription}
        icon={<span className="text-sm font-semibold">404</span>}
        action={
          <Link
            href={`/${locale}/optimizations`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-app-accent px-4 py-2.5 text-sm font-semibold text-app-background transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
          >
            {copy.detail.back}
          </Link>
        }
      />
    </div>
  );
}
