import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AdvancedDisclosure } from '@/components/ui/advanced-disclosure';

describe('AdvancedDisclosure', () => {
  it('keeps technical content collapsed by default and exposes a touch-sized summary', () => {
    render(
      <AdvancedDisclosure
        title="Advanced details"
        description="Identifiers and reproducibility inputs"
      >
        <p>experiment-123</p>
      </AdvancedDisclosure>,
    );

    const summary = screen.getByText('Advanced details').closest('summary');
    const details = summary?.parentElement;

    expect(summary).toHaveClass('min-h-14');
    expect(summary).toHaveClass('focus-visible:ring-2');
    expect(details).not.toHaveAttribute('open');
    expect(screen.getByText('experiment-123')).toBeInTheDocument();

    fireEvent.click(summary!);

    expect(details).toHaveAttribute('open');
  });
});
