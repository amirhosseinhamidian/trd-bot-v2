'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';

import { EmptyState } from '@/components/ui';
import { getDatasetDetailCopy } from '@/features/datasets/dataset-detail-copy';
import type { PlatformLocale } from '@/platform/i18n';

export default function DatasetNotFound() {
  const params = useParams<{ locale: string }>();
  const locale: PlatformLocale = params.locale === 'en' ? 'en' : 'fa';

  const copy = getDatasetDetailCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <EmptyState
        title={copy.notFound.title}
        description={copy.notFound.description}
        className="w-full max-w-xl"
        icon={<span className="text-sm font-semibold">404</span>}
        action={
          <Link
            href={`/${locale}/datasets`}
            className="inline-flex min-h-10 items-center justify-center rounded-xl bg-app-accent px-4 py-2.5 text-sm font-semibold text-app-background transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
          >
            {copy.notFound.back}
          </Link>
        }
      />
    </div>
  );
}
