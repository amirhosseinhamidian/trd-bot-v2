'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import { getPlatformCopy, type PlatformLocale } from '@/platform/i18n';
import { trapTabFocus } from '@/lib/utils/focus';
import {
  getMobilePlatformNavigation,
  isMobilePlatformNavigationEntryActive,
  isPlatformNavigationItemActive,
  type MobilePlatformNavigationKey,
} from '@/platform/navigation';

type MobilePlatformNavigationProps = {
  locale: PlatformLocale;
  pathname: string;
};

export default function MobilePlatformNavigation({
  locale,
  pathname,
}: MobilePlatformNavigationProps) {
  const [openMenu, setOpenMenu] = useState<MobilePlatformNavigationKey | null>(null);
  const triggerRefs = useRef<Partial<Record<MobilePlatformNavigationKey, HTMLButtonElement>>>({});
  const firstMenuItemRef = useRef<HTMLAnchorElement>(null);
  const menuRef = useRef<HTMLElement>(null);
  const copy = getPlatformCopy(locale);
  const entries = getMobilePlatformNavigation(locale);
  const openEntry = entries.find((entry) => entry.key === openMenu);

  useEffect(() => {
    if (!openMenu) {
      return;
    }

    const menuKey = openMenu;

    firstMenuItemRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        setOpenMenu(null);
        triggerRefs.current[menuKey]?.focus();
        return;
      }

      trapTabFocus(event, menuRef.current);
    }

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [openMenu]);

  function closeMenu(restoreFocus: boolean): void {
    if (restoreFocus && openMenu) {
      triggerRefs.current[openMenu]?.focus();
    }

    setOpenMenu(null);
  }

  return (
    <>
      {openEntry ? (
        <button
          type="button"
          aria-label={copy.navigation.mobile.closeMenu}
          tabIndex={-1}
          className="fixed inset-0 z-40 bg-app-overlay md:hidden"
          onClick={() => closeMenu(true)}
        />
      ) : null}

      <div className="fixed inset-x-0 bottom-0 z-50 md:hidden">
        {openEntry ? (
          <section
            ref={menuRef}
            role="dialog"
            aria-modal="true"
            id={`mobile-navigation-${openEntry.key}`}
            aria-labelledby={`mobile-navigation-${openEntry.key}-title`}
            className="mx-3 mb-2 max-h-[min(70vh,32rem)] overflow-y-auto rounded-2xl border border-app-border bg-app-chrome p-3 shadow-2xl backdrop-blur-xl"
          >
            <div className="mb-2 flex items-center justify-between gap-3 px-2">
              <h2
                id={`mobile-navigation-${openEntry.key}-title`}
                className="text-sm font-semibold text-app-foreground"
              >
                {openEntry.label}
              </h2>

              <button
                type="button"
                aria-label={copy.navigation.mobile.closeMenu}
                className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-app-control-border text-app-muted transition hover:bg-app-hover hover:text-app-foreground focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
                onClick={() => closeMenu(true)}
              >
                <span aria-hidden="true">×</span>
              </button>
            </div>

            <div className="grid gap-1">
              {openEntry.items.map((item, index) => {
                const isActive = isPlatformNavigationItemActive(item, pathname);

                return (
                  <Link
                    key={item.key}
                    ref={index === 0 ? firstMenuItemRef : undefined}
                    href={item.href}
                    aria-current={isActive ? 'page' : undefined}
                    onClick={() => closeMenu(false)}
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
              })}
            </div>
          </section>
        ) : null}

        <nav
          aria-label={copy.navigation.mobile.label}
          className="border-t border-app-border bg-app-chrome px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-2xl backdrop-blur-xl"
        >
          <div className="mx-auto grid max-w-lg grid-cols-4 gap-1">
            {entries.map((entry) => {
              const isActive = isMobilePlatformNavigationEntryActive(entry, pathname);
              const className = [
                'flex min-h-14 items-center justify-center rounded-xl border px-1.5 py-2 text-center text-[11px] leading-tight font-medium transition focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none',
                isActive
                  ? 'border-app-accent-border bg-app-accent-soft text-app-accent'
                  : 'border-transparent text-app-muted hover:bg-app-hover hover:text-app-foreground',
              ].join(' ');

              if (entry.href) {
                return (
                  <Link
                    key={entry.key}
                    href={entry.href}
                    aria-current={isActive ? 'page' : undefined}
                    className={className}
                  >
                    {entry.label}
                  </Link>
                );
              }

              return (
                <button
                  key={entry.key}
                  ref={(node) => {
                    if (node) {
                      triggerRefs.current[entry.key] = node;
                    }
                  }}
                  type="button"
                  aria-controls={`mobile-navigation-${entry.key}`}
                  aria-expanded={openMenu === entry.key}
                  aria-current={isActive ? 'page' : undefined}
                  className={className}
                  onClick={() =>
                    setOpenMenu((current) => (current === entry.key ? null : entry.key))
                  }
                >
                  {entry.label}
                </button>
              );
            })}
          </div>
        </nav>
      </div>
    </>
  );
}
