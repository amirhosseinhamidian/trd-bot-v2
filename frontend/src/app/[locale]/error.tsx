'use client';

import { useParams } from 'next/navigation';

import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';
import { ErrorState } from '@/components/ui';

type ErrorPageProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  const params = useParams<{ locale: string }>();
  const locale: DashboardLocale = params.locale === 'en' ? 'en' : 'fa';
  const copy = getDashboardCopy(locale);

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <ErrorState
        className="w-full max-w-lg"
        title={copy.error.title}
        description={copy.error.description}
        retryLabel={copy.error.retry}
        onRetry={reset}
        details={
          error.digest ? (
            <span dir="ltr" className="block text-left">
              {error.digest}
            </span>
          ) : undefined
        }
      />
    </div>
  );
}
