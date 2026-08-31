import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

import DashboardShell from '@/components/layout/dashboard-shell';

vi.mock('next/navigation', () => ({
  usePathname: () => '/en',
}));

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

vi.mock('@/components/theme/theme-toggle', () => ({
  default: () => <button type="button">Theme</button>,
}));

describe('DashboardShell mobile navigation', () => {
  it('connects the menu button to the navigation and marks the active page', () => {
    render(
      <DashboardShell locale="en">
        <div>Content</div>
      </DashboardShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    expect(openButton).toHaveAttribute('aria-controls', 'dashboard-navigation');
    expect(openButton).toHaveAttribute('aria-expanded', 'false');

    const navigation = screen.getByRole('complementary', {
      name: 'Dashboard navigation',
    });

    expect(navigation).toHaveAttribute('id', 'dashboard-navigation');
    expect(navigation).toHaveClass('invisible', 'lg:visible');

    expect(
      screen.getByRole('link', {
        name: 'Overview',
      }),
    ).toHaveAttribute('aria-current', 'page');

    expect(
      screen.getByRole('link', {
        name: 'Strategies',
      }),
    ).toHaveAttribute('href', '/en/strategies');
  });

  it('moves focus into the sidebar and restores it after Escape', async () => {
    const user = userEvent.setup();

    render(
      <DashboardShell locale="en">
        <div>Content</div>
      </DashboardShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    await user.click(openButton);

    expect(openButton).toHaveAttribute('aria-expanded', 'true');

    const navigation = screen.getByRole('complementary', {
      name: 'Dashboard navigation',
    });

    expect(navigation).toHaveClass('visible');

    const closeButton = within(navigation).getByRole('button', {
      name: 'Close navigation',
    });

    expect(closeButton).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(openButton).toHaveAttribute('aria-expanded', 'false');
    expect(openButton).toHaveFocus();
  });

  it('restores focus when the close button is activated', async () => {
    const user = userEvent.setup();

    render(
      <DashboardShell locale="en">
        <div>Content</div>
      </DashboardShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    await user.click(openButton);

    const navigation = screen.getByRole('complementary', {
      name: 'Dashboard navigation',
    });
    const closeButton = within(navigation).getByRole('button', {
      name: 'Close navigation',
    });

    await user.click(closeButton);

    expect(openButton).toHaveAttribute('aria-expanded', 'false');
    expect(openButton).toHaveFocus();
  });

  it('uses localized accessible navigation labels in Persian', () => {
    render(
      <DashboardShell locale="fa">
        <div>محتوا</div>
      </DashboardShell>,
    );

    expect(
      screen.getByRole('button', {
        name: 'باز کردن ناوبری',
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('complementary', {
        name: 'ناوبری داشبورد',
      }),
    ).toBeInTheDocument();
  });
});
