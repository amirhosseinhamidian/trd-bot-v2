import { render, screen } from '@testing-library/react';

import { EmptyState } from '@/components/ui/empty-state';
import { describe, expect, it } from 'vitest';

describe('EmptyState', () => {
  it('renders an accessible status message', () => {
    render(<EmptyState title="No results" description="Try changing the active filters." />);

    const status = screen.getByRole('status');

    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByText('No results')).toBeInTheDocument();
    expect(screen.getByText('Try changing the active filters.')).toBeInTheDocument();
  });

  it('renders an optional action', () => {
    render(
      <EmptyState title="No datasets" action={<button type="button">Create dataset</button>} />,
    );

    expect(screen.getByRole('button', { name: 'Create dataset' })).toBeInTheDocument();
  });
});
