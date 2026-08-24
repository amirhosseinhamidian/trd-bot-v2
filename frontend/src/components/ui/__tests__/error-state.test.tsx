import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ErrorState } from '@/components/ui/error-state';

describe('ErrorState', () => {
  it('renders an assertive error message', () => {
    render(<ErrorState title="Request failed" description="The resource could not be loaded." />);

    const alert = screen.getByRole('alert');

    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(screen.getByText('Request failed')).toBeInTheDocument();
  });

  it('calls the retry handler', () => {
    const onRetry = vi.fn();

    render(<ErrorState title="Request failed" retryLabel="Retry" onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('renders optional error details', () => {
    render(<ErrorState title="Request failed" details={<span>digest-123</span>} />);

    expect(screen.getByText('digest-123')).toBeInTheDocument();
  });
});
