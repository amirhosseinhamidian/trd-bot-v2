'use client';

import { useParams } from 'next/navigation';

import { ErrorState } from '@/components/ui';
import { getPlatformCopy, type PlatformLocale } from '@/platform/i18n';

type ErrorPageProps = {
  error: Error & {
    digest?: string;
  };
  reset: () => void;
};

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  const params = useParams<{ locale: string }>();
  const locale: PlatformLocale = params.locale === 'en' ? 'en' : 'fa';
  const copy = getPlatformCopy(locale).feedback.error;

  return (
    <div className="flex min-h-[65vh] items-center justify-center">
      <ErrorState
        className="w-full max-w-lg"
        title={copy.title}
        description={copy.description}
        retryLabel={copy.retry}
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
