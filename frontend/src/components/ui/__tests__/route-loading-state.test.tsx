import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RouteLoadingState } from '@/components/ui/route-loading-state';

describe('RouteLoadingState', () => {
  it('exposes an accessible loading status', () => {
    render(<RouteLoadingState label="Loading experiments" />);

    const status = screen.getByRole('status', {
      name: 'Loading experiments',
    });

    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-live', 'polite');
  });

  it('supports custom classes', () => {
    render(<RouteLoadingState className="custom-loading-state" />);

    expect(screen.getByRole('status')).toHaveClass('custom-loading-state');
  });

  it.each(['overview', 'catalog', 'detail', 'monitoring'] as const)(
    'renders the %s variant',
    (variant) => {
      const { container } = render(<RouteLoadingState variant={variant} />);

      expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThan(0);
    },
  );
});
