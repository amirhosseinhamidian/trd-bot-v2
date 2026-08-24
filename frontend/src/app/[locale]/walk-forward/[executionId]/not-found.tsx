'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getWalkForwardDetailCopy } from '@/components/dashboard/walk-forward-detail-copy';
import { EmptyState } from '@/components/ui';

export default function WalkForwardNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: DashboardLocale = params.locale === 'en' ? 'en' : 'fa';
  const copy = getWalkForwardDetailCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <EmptyState
        className="w-full max-w-xl"
        title={copy.notFoundTitle}
        description={copy.notFoundDescription}
        icon={<span className="font-mono text-sm">404</span>}
        action={
          <Link
            href={`/${locale}/walk-forward`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
          >
            {copy.back}
          </Link>
        }
      />
    </div>
  );
}
