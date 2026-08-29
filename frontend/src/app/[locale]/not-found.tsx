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
        icon={<span className="text-sm font-semibold">404</span>}
        action={
          <Link
            href={`/${locale}`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-app-accent px-4 py-2.5 text-sm font-semibold text-app-background transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
          >
            {copy.notFound.back}
          </Link>
        }
      />
    </div>
  );
}
