import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  LEGACY_THEME_STORAGE_KEY,
  THEME_BOOTSTRAP_SCRIPT,
  THEME_BOOTSTRAP_SCRIPT_ID,
  THEME_CHANGE_EVENT,
  THEME_STORAGE_KEY,
} from '@/components/theme/theme';
import ThemeToggle from '@/components/theme/theme-toggle';

function runThemeBootstrap(): void {
  Function(THEME_BOOTSTRAP_SCRIPT)();
}

describe('ThemeToggle', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    delete document.documentElement.dataset.theme;
    document.documentElement.style.colorScheme = '';
  });

  it('uses app-scoped identifiers for the active theme contract', () => {
    expect(THEME_STORAGE_KEY).toBe('app-theme');
    expect(THEME_CHANGE_EVENT).toBe('app-theme-change');
    expect(THEME_BOOTSTRAP_SCRIPT_ID).toBe('app-theme-bootstrap');
  });

  it('bootstraps a stored light preference before hydration', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');

    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('bootstraps dark when no preference is stored', () => {
    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('migrates a valid legacy preference during bootstrap', () => {
    window.localStorage.setItem(LEGACY_THEME_STORAGE_KEY, 'light');

    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('still applies a legacy preference when migration writes are blocked', () => {
    window.localStorage.setItem(LEGACY_THEME_STORAGE_KEY, 'light');
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Storage unavailable', 'SecurityError');
    });

    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('gives the app-scoped preference priority over a legacy preference', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    window.localStorage.setItem(LEGACY_THEME_STORAGE_KEY, 'light');

    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('switches from dark to light and persists the preference', async () => {
    const user = userEvent.setup();

    render(<ThemeToggle locale="en" />);

    const toggle = await screen.findByRole('button', {
      name: 'Switch to light theme',
    });

    await user.click(toggle);

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
    expect(
      screen.getByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();
  });

  it('restores a stored light preference without reverting the bootstrapped theme', async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    runThemeBootstrap();

    render(<ThemeToggle locale="fa" />);

    expect(
      await screen.findByRole('button', {
        name: 'فعال کردن پوسته تیره',
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('is keyboard operable and exposes a visible focus treatment', async () => {
    const user = userEvent.setup();

    render(<ThemeToggle locale="en" />);

    const toggle = await screen.findByRole('button', {
      name: 'Switch to light theme',
    });

    expect(toggle).toHaveClass(
      'focus-visible:ring-2',
      'focus-visible:ring-app-accent',
      'focus-visible:ring-offset-2',
    );

    toggle.focus();
    await user.keyboard('{Enter}');

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');

    await user.keyboard(' ');

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('syncs a theme change received from another tab', async () => {
    render(<ThemeToggle locale="en" />);

    window.dispatchEvent(
      new StorageEvent('storage', {
        key: THEME_STORAGE_KEY,
        newValue: 'light',
      }),
    );

    expect(
      await screen.findByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
  });

  it('syncs and migrates a legacy theme change received from another tab', async () => {
    render(<ThemeToggle locale="en" />);

    window.localStorage.setItem(LEGACY_THEME_STORAGE_KEY, 'light');
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: LEGACY_THEME_STORAGE_KEY,
        newValue: 'light',
      }),
    );

    expect(
      await screen.findByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('falls back to dark when local storage is cleared in another tab', async () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    runThemeBootstrap();

    render(<ThemeToggle locale="en" />);

    expect(
      await screen.findByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();

    window.dispatchEvent(
      new StorageEvent('storage', {
        key: null,
        newValue: null,
      }),
    );

    expect(
      await screen.findByRole('button', {
        name: 'Switch to light theme',
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('keeps the current session usable when local storage writes fail', async () => {
    const user = userEvent.setup();

    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('Storage unavailable', 'SecurityError');
    });

    render(<ThemeToggle locale="en" />);

    const toggle = await screen.findByRole('button', {
      name: 'Switch to light theme',
    });

    await user.click(toggle);

    expect(document.documentElement.dataset.theme).toBe('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(
      screen.getByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();
  });
});
