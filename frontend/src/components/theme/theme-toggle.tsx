'use client';

import { useEffect, useSyncExternalStore } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import {
  DEFAULT_THEME,
  THEME_CHANGE_EVENT,
  THEME_STORAGE_KEY,
  applyTheme,
  getAppliedTheme,
  getStoredTheme,
  resolveTheme,
  setStoredTheme,
  type Theme,
} from '@/components/theme/theme';

type ThemeToggleProps = {
  locale: DashboardLocale;
};

function subscribeToTheme(onStoreChange: () => void): () => void {
  function handleStorage(event: StorageEvent): void {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) {
      return;
    }

    const nextTheme = event.key === null ? DEFAULT_THEME : resolveTheme(event.newValue);

    applyTheme(nextTheme);
    onStoreChange();
  }

  window.addEventListener('storage', handleStorage);
  window.addEventListener(THEME_CHANGE_EVENT, onStoreChange);

  return () => {
    window.removeEventListener('storage', handleStorage);
    window.removeEventListener(THEME_CHANGE_EVENT, onStoreChange);
  };
}

function getServerTheme(): Theme {
  return DEFAULT_THEME;
}

export default function ThemeToggle({ locale }: ThemeToggleProps) {
  const theme = useSyncExternalStore<Theme>(subscribeToTheme, getAppliedTheme, getServerTheme);

  useEffect(() => {
    applyTheme(getStoredTheme());
  }, []);

  function toggleTheme(): void {
    const nextTheme: Theme = theme === 'dark' ? 'light' : 'dark';

    applyTheme(nextTheme);
    setStoredTheme(nextTheme);
    window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
  }

  const label =
    locale === 'fa'
      ? theme === 'dark'
        ? 'فعال کردن پوسته روشن'
        : 'فعال کردن پوسته تیره'
      : theme === 'dark'
        ? 'Switch to light theme'
        : 'Switch to dark theme';

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-app-border bg-app-surface text-lg text-app-muted transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
      onClick={toggleTheme}
    >
      <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
    </button>
  );
}
