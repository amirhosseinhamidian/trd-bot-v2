import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Pagination } from '@/components/ui/pagination';

describe('Pagination', () => {
  it('uses full-width mobile controls and requests the next page', async () => {
    const user = userEvent.setup();
    const onOffsetChange = vi.fn();

    render(
      <Pagination
        total={100}
        limit={25}
        offset={0}
        pageLabel="Page"
        previousLabel="Previous"
        nextLabel="Next"
        onOffsetChange={onOffsetChange}
      />,
    );

    const previousButton = screen.getByRole('button', {
      name: 'Previous',
    });
    const nextButton = screen.getByRole('button', {
      name: 'Next',
    });

    expect(previousButton).toBeDisabled();
    expect(nextButton).toHaveClass('w-full', 'sm:w-auto');
    expect(nextButton.parentElement).toHaveClass('grid', 'w-full', 'grid-cols-2', 'sm:flex');

    const currentPage = screen.getByText('1 / 4');

    expect(currentPage).toHaveAttribute('aria-current', 'page');
    expect(currentPage).toHaveAttribute('dir', 'ltr');
    expect(currentPage.parentElement).toHaveAttribute('aria-live', 'polite');
    expect(currentPage.parentElement).toHaveAttribute('aria-atomic', 'true');

    await user.click(nextButton);

    expect(onOffsetChange).toHaveBeenCalledWith(25);
  });

  it('disables navigation while loading', () => {
    render(
      <Pagination
        total={100}
        limit={25}
        offset={25}
        pageLabel="Page"
        previousLabel="Previous"
        nextLabel="Next"
        isLoading
        onOffsetChange={() => undefined}
      />,
    );

    expect(screen.getByRole('navigation', { name: 'Page' })).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });

  it('localizes Persian digits, applies RTL direction, and isolates page numbers', () => {
    render(
      <Pagination
        locale="fa"
        total={50}
        limit={25}
        offset={25}
        pageLabel="صفحه"
        previousLabel="قبلی"
        nextLabel="بعدی"
        onOffsetChange={() => undefined}
      />,
    );

    expect(screen.getByRole('navigation', { name: 'صفحه' })).toHaveAttribute('dir', 'rtl');
    expect(screen.getByText('۲ / ۲')).toHaveAttribute('dir', 'ltr');
  });

  it('honors an explicit direction override', () => {
    render(
      <Pagination
        dir="ltr"
        locale="fa"
        total={50}
        limit={25}
        offset={0}
        pageLabel="صفحه"
        previousLabel="قبلی"
        nextLabel="بعدی"
        onOffsetChange={() => undefined}
      />,
    );

    expect(screen.getByRole('navigation', { name: 'صفحه' })).toHaveAttribute('dir', 'ltr');
    expect(screen.getByText('۱ / ۲')).toBeInTheDocument();
  });

  it('keeps empty and invalid paging inputs finite and non-interactive', () => {
    render(
      <Pagination
        total={0}
        limit={0}
        offset={500}
        pageLabel="Page"
        previousLabel="Previous"
        nextLabel="Next"
        onOffsetChange={() => undefined}
      />,
    );

    expect(screen.getByText('0 / 0')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  });
});
