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
});
