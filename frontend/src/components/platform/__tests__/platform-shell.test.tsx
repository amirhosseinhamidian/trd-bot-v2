import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PlatformShell from '@/components/platform/platform-shell';

const navigationState = vi.hoisted(() => ({
  pathname: '/en',
}));

vi.mock('next/navigation', () => ({
  usePathname: () => navigationState.pathname,
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

describe('PlatformShell', () => {
  beforeEach(() => {
    navigationState.pathname = '/en';
  });

  it('renders the Nexora platform and TRD BOT product context', () => {
    const { container } = render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    expect(screen.getByText('Nexora')).toBeInTheDocument();
    expect(screen.getByText('TRD BOT')).toBeInTheDocument();
    expect(screen.getByText('Market research platform')).toBeInTheDocument();
    expect(screen.queryByText('TRD Research')).not.toBeInTheDocument();
    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      expect.stringContaining('nexora-mark.jpg'),
    );
    expect(container.querySelector('main')).toHaveClass('w-full', 'min-w-0', 'px-4');
  });

  it('renders the frozen navigation groups and destinations in platform order', () => {
    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const sidebar = screen.getByRole('complementary', {
      name: 'Platform navigation',
    });

    expect(
      within(sidebar)
        .getAllByRole('heading')
        .map((heading) => heading.textContent),
    ).toEqual(['Research', 'Strategy & Decision', 'Simulation', 'Data', 'System']);
    expect(
      within(sidebar)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual([
      'Overview',
      'Datasets',
      'Experiments',
      'Walk-forward',
      'Optimizations',
      'Strategies',
      'Signals',
      'Candidates',
      'Risk',
      'Historical Portfolios',
      'Connections',
      'Monitoring',
    ]);
  });

  it('connects the menu button to platform navigation and marks nested routes active', () => {
    navigationState.pathname = '/en/datasets/data-1';

    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    expect(openButton).toHaveAttribute('aria-controls', 'platform-navigation');
    expect(openButton).toHaveAttribute('aria-expanded', 'false');

    const navigation = screen.getByRole('complementary', {
      name: 'Platform navigation',
    });

    expect(navigation).toHaveAttribute('id', 'platform-navigation');
    expect(navigation).toHaveClass('invisible', 'lg:visible');
    expect(
      within(navigation).getByRole('link', {
        name: 'Datasets',
      }),
    ).toHaveAttribute('aria-current', 'page');
    expect(
      within(navigation).getByRole('link', {
        name: 'Overview',
      }),
    ).not.toHaveAttribute('aria-current');
  });

  it('moves focus into the mobile drawer and restores it after Escape', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    await user.click(openButton);

    expect(openButton).toHaveAttribute('aria-expanded', 'true');

    const navigation = screen.getByRole('complementary', {
      name: 'Platform navigation',
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

  it('restores focus when the mobile drawer close button is activated', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const openButton = screen.getByRole('button', {
      name: 'Open navigation',
    });

    await user.click(openButton);

    const navigation = screen.getByRole('complementary', {
      name: 'Platform navigation',
    });
    const closeButton = within(navigation).getByRole('button', {
      name: 'Close navigation',
    });

    await user.click(closeButton);

    expect(openButton).toHaveAttribute('aria-expanded', 'false');
    expect(openButton).toHaveFocus();
  });

  it('uses the frozen Persian groups, labels, and accessible names', () => {
    navigationState.pathname = '/fa';

    render(
      <PlatformShell locale="fa">
        <div>محتوا</div>
      </PlatformShell>,
    );

    expect(
      screen.getByRole('button', {
        name: 'باز کردن ناوبری',
      }),
    ).toBeInTheDocument();

    const sidebar = screen.getByRole('complementary', {
      name: 'ناوبری پلتفرم',
    });

    expect(within(sidebar).getByRole('heading', { name: 'پژوهش' })).toBeInTheDocument();
    expect(within(sidebar).getByRole('heading', { name: 'سامانه' })).toBeInTheDocument();
    expect(within(sidebar).getByRole('link', { name: 'ریسک' })).toHaveAttribute('href', '/fa/risk');
    expect(screen.getByText('پلتفرم پژوهش بازار')).toBeInTheDocument();
  });
});
