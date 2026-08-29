'use client';

import { useEffect, useSyncExternalStore } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

const THEME_STORAGE_KEY = 'trd-theme';
const THEME_CHANGE_EVENT = 'trd-theme-change';

type Theme = 'dark' | 'light';

type ThemeToggleProps = {
  locale: DashboardLocale;
};

function getStoredTheme(): Theme {
  if (typeof window === 'undefined') {
    return 'dark';
  }

  return window.localStorage.getItem(THEME_STORAGE_KEY) === 'light' ? 'light' : 'dark';
}

function subscribeToTheme(onStoreChange: () => void): () => void {
  function handleStorage(event: StorageEvent): void {
    if (event.key === THEME_STORAGE_KEY) {
      onStoreChange();
    }
  }

  window.addEventListener('storage', handleStorage);
  window.addEventListener(THEME_CHANGE_EVENT, onStoreChange);

  return () => {
    window.removeEventListener('storage', handleStorage);
    window.removeEventListener(THEME_CHANGE_EVENT, onStoreChange);
  };
}

function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function getServerTheme(): Theme {
  return 'dark';
}

export default function ThemeToggle({ locale }: ThemeToggleProps) {
  const theme = useSyncExternalStore<Theme>(subscribeToTheme, getStoredTheme, getServerTheme);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  function toggleTheme(): void {
    const nextTheme: Theme = theme === 'dark' ? 'light' : 'dark';

    window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
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
      className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-app-border bg-app-surface text-lg text-app-muted transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent"
      onClick={toggleTheme}
    >
      <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
    </button>
  );
}
