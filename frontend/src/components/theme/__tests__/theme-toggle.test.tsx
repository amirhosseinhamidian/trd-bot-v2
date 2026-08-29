import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import ThemeToggle from '@/components/theme/theme-toggle';

describe('ThemeToggle', () => {
  afterEach(() => {
    window.localStorage.clear();
    delete document.documentElement.dataset.theme;
    document.documentElement.style.colorScheme = '';
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
    expect(window.localStorage.getItem('trd-theme')).toBe('light');
    expect(
      screen.getByRole('button', {
        name: 'Switch to dark theme',
      }),
    ).toBeInTheDocument();
  });

  it('restores a stored light preference', async () => {
    window.localStorage.setItem('trd-theme', 'light');

    render(<ThemeToggle locale="fa" />);

    expect(
      await screen.findByRole('button', {
        name: 'فعال کردن پوسته تیره',
      }),
    ).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});
