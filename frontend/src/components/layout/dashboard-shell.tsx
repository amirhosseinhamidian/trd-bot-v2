'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type ReactNode, useState } from 'react';

import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';

type DashboardShellProps = {
  children: ReactNode;
  locale: DashboardLocale;
};

export default function DashboardShell({ children, locale }: DashboardShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const pathname = usePathname();
  const copy = getDashboardCopy(locale);

  const alternateLocale: DashboardLocale = locale === 'fa' ? 'en' : 'fa';

  const alternatePath = (() => {
    const segments = pathname.split('/');

    if (segments.length > 1) {
      segments[1] = alternateLocale;
    }

    return segments.join('/') || `/${alternateLocale}`;
  })();

  const navigation = [
    {
      key: 'overview',
      label: copy.navigation.overview,
      href: `/${locale}`,
      enabled: true,
    },
    {
      key: 'experiments',
      label: copy.navigation.experiments,
      href: `/${locale}/experiments`,
      enabled: true,
    },
    {
      key: 'datasets',
      label: copy.navigation.datasets,
      href: `/${locale}/datasets`,
      enabled: true,
    },
    {
      key: 'monitoring',
      label: copy.navigation.monitoring,
      href: `/${locale}/monitoring`,
      enabled: true,
    },
    {
      key: 'walk-forward',
      label: copy.navigation.walkForward,
      href: `/${locale}/walk-forward`,
      enabled: true,
    },
    {
      key: 'portfolios',
      label: copy.navigation.portfolios,
      href: `/${locale}/portfolios`,
      enabled: true,
    },
    {
      key: 'candidates',
      label: copy.navigation.candidates,
      href: `/${locale}/candidates`,
      enabled: true,
    },
    {
      key: 'signals',
      label: copy.navigation.signals,
      href: `/${locale}/signals`,
      enabled: true,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {isSidebarOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-slate-950/80 backdrop-blur-sm lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <aside
        className={[
          'fixed inset-y-0 start-0 z-50 flex w-72 flex-col border-e border-slate-800 bg-slate-950/95 p-5 shadow-2xl backdrop-blur transition-transform duration-200 lg:translate-x-0',
          isSidebarOpen
            ? 'translate-x-0'
            : locale === 'fa'
              ? 'translate-x-full'
              : '-translate-x-full',
        ].join(' ')}
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-5">
          <div>
            <p className="text-lg font-bold tracking-tight text-white">{copy.brand.name}</p>
            <p className="mt-1 text-xs text-slate-500">{copy.brand.description}</p>
          </div>

          <button
            type="button"
            aria-label="Close navigation"
            className="rounded-lg border border-slate-800 p-2 text-slate-400 hover:bg-slate-900 hover:text-white lg:hidden"
            onClick={() => setIsSidebarOpen(false)}
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>

        <nav className="mt-6 flex flex-1 flex-col gap-2">
          {navigation.map((item) => {
            const isOverview = item.key === 'overview';

            const isActive = isOverview
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);

            if (item.enabled) {
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  onClick={() => setIsSidebarOpen(false)}
                  className={[
                    'rounded-xl border px-4 py-3 text-sm font-medium transition',
                    isActive
                      ? 'border-cyan-400/20 bg-cyan-400/10 text-cyan-300'
                      : 'border-transparent text-slate-400 hover:bg-slate-900 hover:text-white',
                  ].join(' ')}
                >
                  {item.label}
                </Link>
              );
            }

            return (
              <div
                key={item.key}
                aria-disabled="true"
                className="flex cursor-not-allowed items-center justify-between rounded-xl px-4 py-3 text-sm text-slate-500"
              >
                <span>{item.label}</span>

                <span className="rounded-full bg-slate-900 px-2 py-1 text-[10px] text-slate-600">
                  {copy.navigation.comingSoon}
                </span>
              </div>
            );
          })}
        </nav>

        <div className="rounded-2xl border border-amber-400/15 bg-amber-400/5 p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-amber-300">
            <span className="h-2 w-2 rounded-full bg-amber-300" />
            {copy.header.researchMode}
          </div>
        </div>
      </aside>

      <div className="lg:ps-72">
        <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <button
              type="button"
              aria-label="Open navigation"
              className="rounded-xl border border-slate-800 p-2.5 text-slate-300 hover:bg-slate-900 lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
            >
              <span aria-hidden="true">☰</span>
            </button>

            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              {copy.header.researchMode}
            </div>

            <Link
              href={alternatePath}
              className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-400/50 hover:text-cyan-300"
            >
              {copy.header.language}
            </Link>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
