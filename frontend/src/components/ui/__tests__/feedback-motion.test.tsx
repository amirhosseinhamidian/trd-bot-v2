import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';

describe('Feedback motion primitives', () => {
  it('keeps decorative skeletons hidden and respects reduced motion', () => {
    const { container } = render(<Skeleton className="h-8" />);
    const skeleton = container.firstElementChild;

    expect(skeleton).toHaveAttribute('aria-hidden', 'true');
    expect(skeleton).toHaveClass(
      'animate-pulse',
      'motion-reduce:animate-none',
      'bg-app-surface-muted',
    );
  });

  it('announces a labelled spinner and respects reduced motion', () => {
    render(<Spinner label="Loading datasets" />);

    const spinner = screen.getByRole('status', { name: 'Loading datasets' });

    expect(spinner).not.toHaveAttribute('aria-hidden');
    expect(spinner).toHaveClass('animate-spin', 'motion-reduce:animate-none');
  });

  it('keeps an unlabelled spinner decorative', () => {
    const { container } = render(<Spinner />);

    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
