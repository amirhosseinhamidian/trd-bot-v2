'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type ReactNode, useEffect, useRef, useState } from 'react';

import { type DashboardLocale, getDashboardCopy } from '@/components/dashboard/dashboard-copy';
import ThemeToggle from '@/components/theme/theme-toggle';

const DASHBOARD_NAVIGATION_ID = 'dashboard-navigation';

type DashboardShellProps = {
  children: ReactNode;
  locale: DashboardLocale;
};

export default function DashboardShell({ children, locale }: DashboardShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const openNavigationButtonRef = useRef<HTMLButtonElement>(null);
  const closeNavigationButtonRef = useRef<HTMLButtonElement>(null);
  const wasSidebarOpenRef = useRef(false);
  const pathname = usePathname();
  const copy = getDashboardCopy(locale);

  useEffect(() => {
    if (!isSidebarOpen) {
      if (wasSidebarOpenRef.current) {
        openNavigationButtonRef.current?.focus();
      }

      wasSidebarOpenRef.current = false;
      return;
    }

    wasSidebarOpenRef.current = true;
    closeNavigationButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        setIsSidebarOpen(false);
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isSidebarOpen]);

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
    <div className="min-h-screen bg-app-background text-app-foreground">
      {isSidebarOpen ? (
        <button
          type="button"
          aria-label={copy.header.closeNavigation}
          tabIndex={-1}
          className="fixed inset-0 z-40 bg-app-overlay backdrop-blur-sm lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <aside
        id={DASHBOARD_NAVIGATION_ID}
        aria-label={copy.header.navigation}
        className={[
          'fixed inset-y-0 start-0 z-50 flex w-72 flex-col border-e border-app-border bg-app-chrome p-5 shadow-2xl backdrop-blur transition-transform duration-200 lg:visible lg:translate-x-0',
          isSidebarOpen
            ? 'visible translate-x-0'
            : locale === 'fa'
              ? 'invisible translate-x-full'
              : 'invisible -translate-x-full',
        ].join(' ')}
      >
        <div className="flex items-center justify-between border-b border-app-border pb-5">
          <div>
            <p className="text-lg font-bold tracking-tight text-app-foreground">
              {copy.brand.name}
            </p>
            <p className="mt-1 text-xs text-app-subtle">{copy.brand.description}</p>
          </div>

          <button
            ref={closeNavigationButtonRef}
            type="button"
            aria-label={copy.header.closeNavigation}
            className="rounded-lg border border-app-border p-2 text-app-muted transition hover:bg-app-hover hover:text-app-foreground focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none lg:hidden"
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
                  aria-current={isActive ? 'page' : undefined}
                  onClick={() => setIsSidebarOpen(false)}
                  className={[
                    'rounded-xl border px-4 py-3 text-sm font-medium transition focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none',
                    isActive
                      ? 'border-app-accent-border bg-app-accent-soft text-app-accent'
                      : 'border-transparent text-app-muted hover:bg-app-hover hover:text-app-foreground',
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
                className="flex cursor-not-allowed items-center justify-between rounded-xl px-4 py-3 text-sm text-app-subtle"
              >
                <span>{item.label}</span>

                <span className="rounded-full bg-app-surface-muted px-2 py-1 text-[10px] text-app-subtle">
                  {copy.navigation.comingSoon}
                </span>
              </div>
            );
          })}
        </nav>

        <div className="rounded-2xl border border-app-warning-border bg-app-warning-soft p-4">
          <div className="flex items-center gap-2 text-xs font-medium text-app-warning">
            <span className="h-2 w-2 rounded-full bg-amber-400" />
            {copy.header.researchMode}
          </div>
        </div>
      </aside>

      <div className="lg:ps-72">
        <header className="sticky top-0 z-30 border-b border-app-border bg-app-chrome px-4 py-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <button
              ref={openNavigationButtonRef}
              type="button"
              aria-label={copy.header.openNavigation}
              aria-controls={DASHBOARD_NAVIGATION_ID}
              aria-expanded={isSidebarOpen}
              className="rounded-xl border border-app-border p-2.5 text-app-muted transition hover:bg-app-hover hover:text-app-foreground focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
            >
              <span aria-hidden="true">☰</span>
            </button>

            <div className="hidden items-center gap-2 text-xs text-app-subtle sm:flex">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              {copy.header.researchMode}
            </div>

            <div className="flex items-center gap-2">
              <ThemeToggle locale={locale} />

              <Link
                href={alternatePath}
                className="rounded-xl border border-app-border bg-app-surface px-4 py-2 text-sm font-medium text-app-foreground transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
              >
                {copy.header.language}
              </Link>
            </div>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
