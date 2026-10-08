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

  it('keeps the five target viewport tiers explicit in the shell contract', () => {
    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const main = screen.getByRole('main');
    const sidebar = screen.getByRole('complementary', { name: 'Platform navigation' });
    const mobileNavigation = screen.getByRole('navigation', { name: 'Mobile navigation' });

    expect(main).toHaveClass(
      'w-full',
      'max-w-7xl',
      'min-w-0',
      'px-4',
      'sm:px-6',
      'md:pb-8',
      'lg:px-8',
    );
    expect(main.parentElement).toHaveClass('min-w-0', 'lg:ps-72');
    expect(mobileNavigation.parentElement).toHaveClass('md:hidden');
    expect(sidebar).toHaveClass('w-72', 'md:flex', 'lg:visible', 'lg:translate-x-0');
  });

  it('puts a localized skip link first and moves focus to the main content', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale="en">
        <button type="button">Page action</button>
      </PlatformShell>,
    );

    await user.tab();

    const skipLink = screen.getByRole('link', { name: 'Skip to main content' });
    const main = screen.getByRole('main');

    expect(skipLink).toHaveFocus();
    expect(skipLink).toHaveAttribute('href', '#main-content');
    expect(main).toHaveAttribute('id', 'main-content');
    expect(main).toHaveAttribute('tabindex', '-1');

    await user.click(skipLink);

    expect(main).toHaveFocus();
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
    expect(navigation).toHaveClass('hidden', 'md:flex', 'invisible', 'lg:visible');
    expect(openButton).toHaveClass('hidden', 'h-11', 'w-11', 'md:inline-flex', 'lg:hidden');
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

  it('renders compact mobile navigation and manages group menu focus', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const mobileNavigation = screen.getByRole('navigation', {
      name: 'Mobile navigation',
    });

    expect(mobileNavigation.parentElement).toHaveClass('md:hidden');
    expect(within(mobileNavigation).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'href',
      '/en',
    );
    expect(within(mobileNavigation).getByRole('button', { name: 'Research' })).toBeInTheDocument();
    expect(
      within(mobileNavigation).getByRole('button', { name: 'Strategy & Decision' }),
    ).toBeInTheDocument();
    expect(within(mobileNavigation).getByRole('button', { name: 'More' })).toBeInTheDocument();

    const researchButton = within(mobileNavigation).getByRole('button', { name: 'Research' });

    await user.click(researchButton);

    expect(researchButton).toHaveAttribute('aria-expanded', 'true');

    const researchMenu = document.getElementById('mobile-navigation-research');

    expect(researchMenu).not.toBeNull();
    expect(researchMenu).toHaveAttribute('role', 'dialog');
    expect(researchMenu).toHaveAttribute('aria-modal', 'true');
    expect(within(researchMenu!).getByRole('link', { name: 'Datasets' })).toHaveFocus();
    expect(
      within(researchMenu!)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Datasets', 'Experiments', 'Walk-forward', 'Optimizations']);

    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(within(researchMenu!).getByRole('button', { name: 'Close menu' })).toHaveFocus();

    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(within(researchMenu!).getByRole('link', { name: 'Optimizations' })).toHaveFocus();

    await user.tab();
    expect(within(researchMenu!).getByRole('button', { name: 'Close menu' })).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(researchButton).toHaveAttribute('aria-expanded', 'false');
    expect(researchButton).toHaveFocus();
  });

  it('places secondary destinations in More and marks its section active', async () => {
    const user = userEvent.setup();
    navigationState.pathname = '/en/risk';

    render(
      <PlatformShell locale="en">
        <div>Content</div>
      </PlatformShell>,
    );

    const mobileNavigation = screen.getByRole('navigation', {
      name: 'Mobile navigation',
    });
    const moreButton = within(mobileNavigation).getByRole('button', { name: 'More' });

    expect(moreButton).toHaveAttribute('aria-current', 'page');

    await user.click(moreButton);

    const moreMenu = document.getElementById('mobile-navigation-more');

    expect(moreMenu).not.toBeNull();
    expect(
      within(moreMenu!)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Risk', 'Historical Portfolios', 'Connections', 'Monitoring']);
    expect(within(moreMenu!).getByRole('link', { name: 'Risk' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('moves focus into the tablet drawer and restores it after Escape', async () => {
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

    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(within(navigation).getByRole('link', { name: 'Monitoring' })).toHaveFocus();

    await user.tab();
    expect(closeButton).toHaveFocus();

    await user.keyboard('{Escape}');

    expect(openButton).toHaveAttribute('aria-expanded', 'false');
    expect(openButton).toHaveFocus();
  });

  it('restores focus when the tablet drawer close button is activated', async () => {
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

    const mobileNavigation = screen.getByRole('navigation', {
      name: 'ناوبری موبایل',
    });

    expect(within(sidebar).getByRole('heading', { name: 'پژوهش' })).toBeInTheDocument();
    expect(within(sidebar).getByRole('heading', { name: 'سامانه' })).toBeInTheDocument();
    expect(within(sidebar).getByRole('link', { name: 'ریسک' })).toHaveAttribute('href', '/fa/risk');
    expect(within(mobileNavigation).getByRole('button', { name: 'بیشتر' })).toBeInTheDocument();
    expect(screen.getByText('پلتفرم پژوهش بازار')).toBeInTheDocument();
  });
});
