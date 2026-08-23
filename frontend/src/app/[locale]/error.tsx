'use client';

import { useParams } from 'next/navigation';

import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';

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
      <div className="w-full max-w-lg rounded-3xl border border-red-400/20 bg-red-400/5 p-8 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-red-400/20 bg-red-400/10 text-xl text-red-300">
          !
        </div>

        <h1 className="mt-5 text-xl font-bold text-white">{copy.error.title}</h1>

        <p className="mt-3 text-sm leading-7 text-slate-400">{copy.error.description}</p>

        {error.digest ? (
          <p dir="ltr" className="mt-3 font-mono text-xs text-slate-600">
            {error.digest}
          </p>
        ) : null}

        <button
          type="button"
          onClick={reset}
          className="mt-6 rounded-xl bg-cyan-400 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300"
        >
          {copy.error.retry}
        </button>
      </div>
    </div>
  );
}
