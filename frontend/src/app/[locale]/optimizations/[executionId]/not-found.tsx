'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getOptimizationCopy } from '@/components/dashboard/optimization-copy';
import { EmptyState } from '@/components/ui';

export default function OptimizationNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: DashboardLocale = params.locale === 'en' ? 'en' : 'fa';
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
