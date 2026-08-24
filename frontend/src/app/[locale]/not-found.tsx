'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';
import { EmptyState } from '@/components/ui';

export default function LocaleNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: DashboardLocale = params.locale === 'en' ? 'en' : 'fa';
  const copy = getDashboardCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <EmptyState
        className="w-full max-w-xl"
        title={copy.notFound.title}
        description={copy.notFound.description}
        icon={<span className="font-mono text-sm">404</span>}
        action={
          <Link
            href={`/${locale}`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
          >
            {copy.notFound.back}
          </Link>
        }
      />
    </div>
  );
}
