'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetDetailCopy } from '@/components/dashboard/dataset-detail-copy';
import { EmptyState } from '@/components/ui';

export default function DatasetNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: DashboardLocale = params.locale === 'en' ? 'en' : 'fa';

  const copy = getDatasetDetailCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <EmptyState
        title={copy.notFound.title}
        description={copy.notFound.description}
        className="w-full max-w-xl"
        icon={<span className="font-mono text-sm">404</span>}
        action={
          <Link
            href={`/${locale}/datasets`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-cyan-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
          >
            {copy.notFound.back}
          </Link>
        }
      />
    </div>
  );
}
