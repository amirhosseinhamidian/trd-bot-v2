export const THEME_STORAGE_KEY = 'app-theme';
export const LEGACY_THEME_STORAGE_KEY = 'trd-theme';
export const THEME_CHANGE_EVENT = 'app-theme-change';
export const THEME_BOOTSTRAP_SCRIPT_ID = 'app-theme-bootstrap';

export type Theme = 'dark' | 'light';

export const DEFAULT_THEME: Theme = 'dark';

export function isTheme(value: string | null): value is Theme {
  return value === 'light' || value === 'dark';
}

export function resolveTheme(value: string | null): Theme {
  return isTheme(value) ? value : DEFAULT_THEME;
}

export function getStoredTheme(): Theme {
  if (typeof window === 'undefined') {
    return DEFAULT_THEME;
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);

    if (isTheme(storedTheme)) {
      return storedTheme;
    }

    const legacyTheme = window.localStorage.getItem(LEGACY_THEME_STORAGE_KEY);

    if (isTheme(legacyTheme)) {
      setStoredTheme(legacyTheme);
      return legacyTheme;
    }

    return DEFAULT_THEME;
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
    const isTheme = (value) => value === 'light' || value === 'dark';
    const storedTheme = window.localStorage.getItem('${THEME_STORAGE_KEY}');
    const legacyTheme = isTheme(storedTheme)
      ? null
      : window.localStorage.getItem('${LEGACY_THEME_STORAGE_KEY}');
    const theme = isTheme(storedTheme)
      ? storedTheme
      : isTheme(legacyTheme)
        ? legacyTheme
        : 'dark';

    if (!isTheme(storedTheme) && isTheme(legacyTheme)) {
      try {
        window.localStorage.setItem('${THEME_STORAGE_KEY}', legacyTheme);
      } catch {
        // Applying the preference must not depend on storage write access.
      }
    }

    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  } catch {
    document.documentElement.dataset.theme = 'dark';
    document.documentElement.style.colorScheme = 'dark';
  }
})();
`;
