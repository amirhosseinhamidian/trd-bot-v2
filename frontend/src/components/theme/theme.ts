export const THEME_STORAGE_KEY = 'trd-theme';
export const THEME_CHANGE_EVENT = 'trd-theme-change';

export type Theme = 'dark' | 'light';

export const DEFAULT_THEME: Theme = 'dark';

export function resolveTheme(value: string | null): Theme {
  return value === 'light' ? 'light' : DEFAULT_THEME;
}

export function getStoredTheme(): Theme {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME;
  }

  try {
    return resolveTheme(window.localStorage.getItem(THEME_STORAGE_KEY));
  } catch {
    return DEFAULT_THEME;
  }
}

export function setStoredTheme(theme: Theme): boolean {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    return true;
  } catch {
    return false;
  }
}

export function getAppliedTheme(): Theme {
  if (typeof document === 'undefined') {
    return getStoredTheme();
  }

  const appliedTheme = document.documentElement.dataset.theme;

  if (appliedTheme === 'light' || appliedTheme === 'dark') {
    return appliedTheme;
  }

  return getStoredTheme();
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') {
    return;
  }

  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

export const THEME_BOOTSTRAP_SCRIPT = `
(() => {
  try {
    const storedTheme = window.localStorage.getItem('trd-theme');
    const theme = storedTheme === 'light' ? 'light' : 'dark';

    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  } catch {
    document.documentElement.dataset.theme = 'dark';
    document.documentElement.style.colorScheme = 'dark';
  }
})();
`;
