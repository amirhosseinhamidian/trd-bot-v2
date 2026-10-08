import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';

describe('platform page layout', () => {
  it('provides the shared page rhythm and allows safe overrides', () => {
    const { container } = render(<PageFrame className="space-y-6">Content</PageFrame>);

    expect(container.firstChild).toHaveClass('min-w-0', 'space-y-6');
    expect(container.firstChild).not.toHaveClass('space-y-8');
  });

  it('renders semantic page copy and responsive action layout', () => {
    render(
      <PageHeader
        eyebrow="Research"
        title="Experiments"
        description="Compare historical runs."
        backLink={<span>Back</span>}
        metadata={<span>experiment-1</span>}
        actions={<button type="button">Run experiment</button>}
      >
        <p>Historical data only</p>
      </PageHeader>,
    );

    expect(screen.getByRole('banner')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Experiments' })).toHaveClass(
      'text-2xl',
      'sm:text-3xl',
      'lg:text-4xl',
    );
    expect(screen.getByText('Research')).toHaveClass('uppercase');
    expect(screen.getByText('Compare historical runs.')).toHaveClass('max-w-3xl');
    expect(screen.getByText('experiment-1').parentElement).toHaveClass('mt-2');
    expect(screen.getByText('Historical data only').parentElement).toHaveClass('mt-5');
    expect(screen.getByRole('button', { name: 'Run experiment' }).parentElement).toHaveClass(
      'w-full',
      'flex-wrap',
      'sm:w-auto',
      'max-sm:[&>button]:w-full',
    );
  });
});
