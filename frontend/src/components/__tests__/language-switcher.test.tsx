import { render, screen } from '@testing-library/react';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import LanguageSwitcher from '@/components/language-switcher';

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe('LanguageSwitcher', () => {
  it('uses semantic theme colors and visible keyboard focus in both locale states', () => {
    render(
      <LanguageSwitcher
        locale="en"
        persianLabel="فارسی"
        englishLabel="English"
        ariaLabel="Language"
      />,
    );

    expect(screen.getByRole('navigation', { name: 'Language' })).toHaveAttribute('dir', 'ltr');

    const english = screen.getByRole('link', { name: 'English' });
    const persian = screen.getByRole('link', { name: 'فارسی' });

    expect(english).toHaveClass('bg-app-accent', 'text-app-background');
    expect(persian).toHaveClass('text-app-muted', 'hover:bg-app-hover');

    for (const link of [english, persian]) {
      expect(link).toHaveClass(
        'focus-visible:ring-2',
        'focus-visible:ring-app-accent',
        'focus-visible:outline-none',
      );
    }
  });
});
